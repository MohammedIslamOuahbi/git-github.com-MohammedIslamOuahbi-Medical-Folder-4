from __future__ import annotations

from app.services.sync_safety import suspend_for_data_safety

import uuid as py_uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import Base
from app.exceptions import BadRequestException
from app.models.device_sync_state import DeviceSyncState
from app.models.sync_change import SyncChange
from app.services.sync_context import sync_apply_scope
from app.sync.registry import SYNC_ENTITY_REGISTRY


class MissionCopyService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _state(
        self,
        db: Session,
        *,
        mission_uuid: py_uuid.UUID,
        mission_server_uuid: py_uuid.UUID,
        mission_server_url: str,
    ) -> DeviceSyncState:
        state = db.scalar(
            select(DeviceSyncState).where(
                DeviceSyncState.mission_session_uuid == mission_uuid,
                DeviceSyncState.remote_server_type == "mission_server",
            )
        )
        if state is None:
            state = DeviceSyncState(
                remote_server_uuid=mission_server_uuid,
                remote_server_type="mission_server",
                remote_server_url=mission_server_url,
                mission_session_uuid=mission_uuid,
                last_pulled_sequence=0,
                last_pushed_sequence=0,
                is_sync_running=False,
            )
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    def get_state(
        self,
        db: Session,
        *,
        mission_uuid: py_uuid.UUID,
        mission_server_uuid: py_uuid.UUID | None = None,
        mission_server_url: str | None = None,
    ) -> DeviceSyncState | None:
        state = db.scalar(
            select(DeviceSyncState).where(
                DeviceSyncState.mission_session_uuid == mission_uuid,
                DeviceSyncState.remote_server_type == "mission_server",
            )
        )
        if state is not None or mission_server_uuid is None or mission_server_url is None:
            return state
        return self._state(
            db,
            mission_uuid=mission_uuid,
            mission_server_uuid=mission_server_uuid,
            mission_server_url=mission_server_url,
        )

    def apply_batch(
        self,
        db: Session,
        *,
        mission_uuid: py_uuid.UUID,
        mission_server_uuid: py_uuid.UUID,
        mission_server_url: str,
        changes: list[dict[str, Any]],
        next_sequence: int,
        final_sequence: int,
        current_run_uuid: py_uuid.UUID | None = None,
    ) -> DeviceSyncState:
        suspend_for_data_safety("mission_copy_apply")
        state = self._state(
            db,
            mission_uuid=mission_uuid,
            mission_server_uuid=mission_server_uuid,
            mission_server_url=mission_server_url,
        )
        state.copy_status = "copying"
        state.copy_started_at = state.copy_started_at or self._now()
        state.is_sync_running = True
        state.current_run_uuid = current_run_uuid
        state.final_mission_sequence = final_sequence
        db.add(state)
        db.commit()
        with db.begin_nested():
            try:
                with sync_apply_scope(db):
                    for entity_type in sorted(
                        {item["entity_type"] for item in changes},
                        key=lambda key: SYNC_ENTITY_REGISTRY[key].priority,
                    ):
                        config = SYNC_ENTITY_REGISTRY[entity_type]
                        table = config.model.__table__
                        for change in [item for item in changes if item["entity_type"] == entity_type]:
                            payload = dict(change["payload"] or {})
                            payload.pop("id", None)
                            if change["operation"] == "delete":
                                if "deleted_at" not in table.c:
                                    continue
                                db.execute(
                                    table.update()
                                    .where(table.c.uuid == py_uuid.UUID(str(change["entity_uuid"])))
                                    .values(deleted_at=payload.get("deleted_at") or self._now())
                                )
                                continue
                            statement = pg_insert(table).values(**self._permitted_values(db, config.model, payload))
                            updatable = {
                                key: statement.excluded[key]
                                for key in payload.keys()
                                if key in table.c and key != "uuid"
                            }
                            db.execute(statement.on_conflict_do_update(index_elements=[table.c.uuid], set_=updatable))
                            if db.scalar(select(SyncChange.id).where(SyncChange.change_uuid == py_uuid.UUID(str(change["change_uuid"])))) is None:
                                db.add(
                                    SyncChange(
                                        change_uuid=py_uuid.UUID(str(change["change_uuid"])),
                                        entity_type=change["entity_type"],
                                        entity_uuid=py_uuid.UUID(str(change["entity_uuid"])),
                                        operation=change["operation"],
                                        base_version=max(0, int(change["entity_version"]) - 1),
                                        entity_version=int(change["entity_version"]),
                                        changed_fields=list(change.get("changed_fields") or []),
                                        payload=payload,
                                        source_device_uuid=py_uuid.UUID(change["source_device_uuid"]) if change.get("source_device_uuid") else None,
                                        source_user_uuid=py_uuid.UUID(change["source_user_uuid"]) if change.get("source_user_uuid") else None,
                                        mission_session_uuid=mission_uuid,
                                        mission_server_uuid=mission_server_uuid,
                                        mission_sequence=int(change["mission_sequence"]),
                                        central_status="never_submitted",
                                        occurred_at=self._now(),
                                        copied_to_client_at=self._now(),
                                        retry_count=0,
                                    )
                                )
                    state.last_pulled_sequence = next_sequence
                    state.last_pushed_sequence = final_sequence
                    state.final_mission_sequence = final_sequence
                    state.last_pull_at = self._now()
                    state.last_successful_sync_at = self._now()
                    state.copy_status = "completed" if next_sequence >= final_sequence else "copying"
                    state.copy_completed_at = self._now() if next_sequence >= final_sequence else None
                    state.is_sync_running = False
                    state.last_error_code = None
                    state.last_error_message = None
                    db.add(state)
            except Exception as exc:  # noqa: BLE001
                state.retry_count = int(getattr(state, "retry_count", 0) or 0) + 1
                state.last_failed_sync_at = self._now()
                state.last_error_code = "MISSION_APPLY_FAILED"
                state.last_error_message = str(exc)
                state.copy_status = "failed"
                state.is_sync_running = False
                state.current_run_uuid = current_run_uuid
                db.add(state)
                raise
        db.refresh(state)
        return state

    def _permitted_values(self, db: Session, model: type[Base], payload: dict[str, Any]) -> dict[str, Any]:
        table = model.__table__
        values: dict[str, Any] = {}
        for key, value in payload.items():
            if key not in table.c:
                continue
            column = table.c[key]
            if str(column.type) == "UUID" and value is not None and not isinstance(value, py_uuid.UUID):
                values[key] = py_uuid.UUID(str(value))
            else:
                values[key] = value
        mapper = inspect(model)
        for relationship in mapper.relationships:
            payload_key = f"{relationship.key}_uuid"
            if payload_key not in payload or payload[payload_key] in (None, ""):
                continue
            target_model = relationship.mapper.class_
            target = db.scalar(select(target_model).where(target_model.uuid == py_uuid.UUID(str(payload[payload_key]))))
            if target is None:
                raise BadRequestException(f"Missing related entity for {payload_key}")
            for local_column, remote_column in relationship.local_remote_pairs:
                if local_column.name in table.c and local_column.name.endswith("_id"):
                    values[local_column.name] = getattr(target, remote_column.name)
        if "sync_version" in table.c and "sync_version" not in values:
            values["sync_version"] = 1
        return values


mission_copy_service = MissionCopyService()
