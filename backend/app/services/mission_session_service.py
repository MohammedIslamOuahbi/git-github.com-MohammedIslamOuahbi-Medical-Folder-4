from __future__ import annotations

import uuid as py_uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import BadRequestException
from app.models.mission_session import MissionSession
from app.models.mission_session_device import MissionSessionDevice
from app.models.sync_device import SyncDevice


class MissionSessionService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def create_session(
        self,
        db: Session,
        *,
        mission_code: str,
        mission_name: str,
        server_device_uuid: py_uuid.UUID,
        server_device_name_snapshot: str,
        created_by_user_uuid: py_uuid.UUID | None,
        description: str | None = None,
        base_central_server_uuid: py_uuid.UUID | None = None,
        base_central_generation_uuid: py_uuid.UUID | None = None,
        base_central_sequence: int | None = None,
    ) -> MissionSession:
        active_count = db.scalar(
            select(func.count(MissionSession.id)).where(
                MissionSession.server_device_uuid == server_device_uuid,
                MissionSession.status.in_(["preparing", "active", "finalizing", "central_pending", "centralizing"]),
            )
        ) or 0
        if active_count:
            raise BadRequestException("Only one active mission session may exist for a mission server device.")
        mission = MissionSession(
            mission_code=mission_code,
            mission_name=mission_name,
            description=description,
            server_device_uuid=server_device_uuid,
            server_device_name_snapshot=server_device_name_snapshot,
            created_by_user_uuid=created_by_user_uuid,
            status="active",
            base_central_server_uuid=base_central_server_uuid,
            base_central_generation_uuid=base_central_generation_uuid,
            base_central_sequence=base_central_sequence,
            mission_current_sequence=0,
            started_at=self._now(),
        )
        db.add(mission)
        db.commit()
        db.refresh(mission)
        return mission

    def add_participant(
        self,
        db: Session,
        *,
        mission_session_uuid: py_uuid.UUID,
        device_uuid: py_uuid.UUID,
        role: str,
    ) -> MissionSessionDevice:
        mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_session_uuid))
        if mission is None:
            raise BadRequestException("Mission session not found.")
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))
        if device is None or device.is_revoked:
            raise BadRequestException("Device is invalid or revoked.")
        if role == "mission_server":
            existing_server = db.scalar(
                select(MissionSessionDevice).where(
                    MissionSessionDevice.mission_session_uuid == mission_session_uuid,
                    MissionSessionDevice.role == "mission_server",
                )
            )
            if existing_server is not None:
                raise BadRequestException("A mission session must have exactly one mission server.")
        participant = MissionSessionDevice(
            mission_session_uuid=mission_session_uuid,
            device_uuid=device_uuid,
            device_code_snapshot=device.device_code,
            device_name_snapshot=device.device_name,
            role=role,
            joined_at=self._now(),
            last_seen_at=self._now(),
            is_connected=True,
            status="active" if role == "mission_server" else "connected",
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
        return participant


mission_session_service = MissionSessionService()
