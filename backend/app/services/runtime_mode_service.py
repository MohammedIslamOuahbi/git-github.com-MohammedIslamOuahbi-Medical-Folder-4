from __future__ import annotations

import uuid as py_uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import InstallationProfile
from app.exceptions import BadRequestException
from app.models.mission_session import MissionSession
from app.models.runtime_config import RuntimeConfig
from app.services.installation_service import installation_service


class RuntimeMode(str, Enum):
    STANDALONE = "standalone"
    MISSION_SERVER = "mission_server"
    MISSION_CLIENT = "mission_client"


class RuntimeModeService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get_or_create(self, db: Session, local_api_url: str) -> RuntimeConfig:
        state = db.scalar(select(RuntimeConfig).where(RuntimeConfig.id == 1))
        if state is not None:
            return state
        state = RuntimeConfig(
            id=1,
            runtime_mode=RuntimeMode.STANDALONE.value,
            active_api_url=local_api_url,
            local_api_url=local_api_url,
            local_database_write_enabled=True,
            last_mode_change_at=self._now(),
        )
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def transition(
        self,
        db: Session,
        *,
        new_mode: RuntimeMode,
        local_api_url: str,
        changed_by_user_uuid: py_uuid.UUID | None,
        mission_server_url: str | None = None,
        mission_server_device_uuid: py_uuid.UUID | None = None,
        active_mission_session_uuid: py_uuid.UUID | None = None,
        force: bool = False,
    ) -> RuntimeConfig:
        state = self.get_or_create(db, local_api_url)
        previous_mode = RuntimeMode(state.runtime_mode)
        if previous_mode == new_mode:
            return state
        self._validate_transition(
            db,
            state=state,
            previous_mode=previous_mode,
            new_mode=new_mode,
            mission_server_url=mission_server_url,
            mission_server_device_uuid=mission_server_device_uuid,
            active_mission_session_uuid=active_mission_session_uuid,
            force=force,
        )
        state.runtime_mode = new_mode.value
        state.local_api_url = local_api_url
        state.active_api_url = mission_server_url if new_mode == RuntimeMode.MISSION_CLIENT else local_api_url
        state.mission_server_url = mission_server_url if new_mode == RuntimeMode.MISSION_CLIENT else None
        state.mission_server_device_uuid = mission_server_device_uuid if new_mode == RuntimeMode.MISSION_CLIENT else None
        state.active_mission_session_uuid = active_mission_session_uuid
        state.local_database_write_enabled = new_mode != RuntimeMode.MISSION_CLIENT
        state.last_mode_change_at = self._now()
        state.last_mode_change_by_user_uuid = changed_by_user_uuid
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def _validate_transition(
        self,
        db: Session,
        *,
        state: RuntimeConfig,
        previous_mode: RuntimeMode,
        new_mode: RuntimeMode,
        mission_server_url: str | None,
        mission_server_device_uuid: py_uuid.UUID | None,
        active_mission_session_uuid: py_uuid.UUID | None,
        force: bool,
    ) -> None:
        profile = installation_service.current_profile(db)
        if profile == InstallationProfile.CENTRAL_SERVER and new_mode in {RuntimeMode.MISSION_SERVER, RuntimeMode.MISSION_CLIENT}:
            raise BadRequestException("INSTALLATION_PROFILE_FORBIDDEN")
        if previous_mode == RuntimeMode.STANDALONE and new_mode == RuntimeMode.MISSION_CLIENT:
            if not mission_server_url or mission_server_device_uuid is None:
                raise BadRequestException("Mission client mode requires mission server identity and URL.")
        if previous_mode == RuntimeMode.MISSION_CLIENT and new_mode == RuntimeMode.STANDALONE and not force:
            if state.active_mission_session_uuid is not None:
                raise BadRequestException("Mission client must pull mission data before returning to standalone mode.")
        if previous_mode == RuntimeMode.MISSION_SERVER and new_mode == RuntimeMode.STANDALONE and not force:
            mission_uuid = active_mission_session_uuid or state.active_mission_session_uuid
            if mission_uuid is not None:
                mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_uuid))
                if mission is not None and mission.status not in {"finalized", "central_pending", "centralizing", "centralized", "aborted"}:
                    raise BadRequestException("Mission server cannot return to standalone mode before mission finalization or abort.")


runtime_mode_service = RuntimeModeService()
