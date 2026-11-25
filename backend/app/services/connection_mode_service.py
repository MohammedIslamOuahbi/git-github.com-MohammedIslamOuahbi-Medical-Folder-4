from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.enums import ConnectionMode
from app.exceptions import BadRequestException
from app.models.runtime_config import RuntimeConfig
from app.models.sync_device import SyncDevice
from app.services.device_identity_service import device_identity_service
from app.services.runtime_mode_service import runtime_mode_service


@dataclass(frozen=True)
class ConnectionModeResolution:
    mode: ConnectionMode | None
    configured: bool
    verified: bool
    requires_setup: bool
    server_url: str | None
    source: str

    def as_dict(self) -> dict[str, object | None]:
        return {
            "connection_mode": self.mode.value if self.mode else None,
            "connection_configured": self.configured,
            "connection_verified": self.verified,
            "connection_requires_setup": self.requires_setup,
            "connection_server_url": self.server_url,
            "connection_mode_source": self.source,
        }


class ConnectionModeService:
    def resolve(self, runtime: RuntimeConfig) -> ConnectionModeResolution:
        """Resolve V2 state without treating V1 runtime fields as confirmed setup."""
        try:
            explicit_mode = ConnectionMode(runtime.connection_mode) if runtime.connection_mode else None
        except ValueError:
            explicit_mode = None

        if explicit_mode is not None:
            requires_setup = bool(runtime.connection_requires_setup or not runtime.connection_configured)
            if explicit_mode == ConnectionMode.CLIENT and not runtime.connection_server_url:
                requires_setup = True
            return ConnectionModeResolution(
                mode=explicit_mode,
                configured=bool(runtime.connection_configured),
                verified=bool(runtime.connection_verified),
                requires_setup=requires_setup,
                server_url=runtime.connection_server_url,
                source="v2",
            )

        # Only a V1 mission client with a target URL is a useful candidate. It
        # still requires explicit V2 confirmation because V1 had different
        # semantics and no V2 verification flag.
        if runtime.runtime_mode == "mission_client" and runtime.mission_server_url:
            return ConnectionModeResolution(
                mode=ConnectionMode.CLIENT,
                configured=False,
                verified=False,
                requires_setup=True,
                server_url=runtime.mission_server_url,
                source="legacy_mission_client_candidate",
            )

        return ConnectionModeResolution(
            mode=None,
            configured=False,
            verified=False,
            requires_setup=True,
            server_url=None,
            source="legacy_requires_setup",
        )

    def current(self, db: Session) -> tuple[RuntimeConfig, ConnectionModeResolution]:
        runtime = runtime_mode_service.get_or_create(db, settings.api_base_url)
        return runtime, self.resolve(runtime)

    def configure(
        self,
        db: Session,
        *,
        mode: ConnectionMode,
        server_url: str | None,
        verified: bool,
    ) -> tuple[RuntimeConfig, ConnectionModeResolution]:
        normalized_url = (server_url or "").strip().rstrip("/") or None
        if mode == ConnectionMode.CLIENT and not normalized_url:
            raise BadRequestException("CLIENT mode requires a verified server URL.")

        runtime, _ = self.current(db)
        runtime.connection_mode = mode.value
        runtime.connection_configured = True
        runtime.connection_verified = verified
        runtime.connection_requires_setup = not verified
        runtime.connection_server_url = normalized_url if mode == ConnectionMode.CLIENT else None

        # Device identity stays in sync_devices; runtime_configs only stores
        # the local installation's role and connection state.
        installation_uuid = device_identity_service.load_installation_uuid()
        device = db.scalar(select(SyncDevice).where(SyncDevice.installation_uuid == installation_uuid))
        if device is not None:
            device.connection_mode = mode.value

        db.add(runtime)
        db.commit()
        db.refresh(runtime)
        return runtime, self.resolve(runtime)


connection_mode_service = ConnectionModeService()
