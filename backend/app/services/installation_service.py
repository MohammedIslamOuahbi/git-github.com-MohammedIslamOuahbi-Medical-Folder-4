from __future__ import annotations

import json
import os
import shutil
import socket
import uuid as py_uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.audit import create_audit_log
from app.core.enums import InstallationProfile, InstallationProvisioningStatus
from app.core.logging import get_logger
from app.core.installation_policy import capabilities_for_profile, profile_has_capability
from app.models.central_server_state import CentralServerState
from app.models.central_bootstrap import CentralBootstrap
from app.models.device_sync_state import DeviceSyncState
from app.models.installation_state import InstallationState
from app.models.runtime_config import RuntimeConfig
from app.models.sync_device import SyncDevice
from app.models.user import User
from app.services.device_identity_service import device_identity_service

APP_VERSION = "1.0.2"
PROFILE_VERSION = 1
TRUSTED_PROFILE_ENV = "IBNSINA_INSTALLATION_PROFILE"
DEFAULT_RETENTION_POLICY = "30 jours"
SYNC_PROTOCOL_VERSION = "1"
CENTRAL_SERVER_STATE_TABLE = "central_server_state"
CENTRAL_SERVER_STATE_TABLE_MISSING = "CENTRAL_SERVER_STATE_TABLE_MISSING"
SCHEMA_INCOMPLETE_STATUS = "schema_incomplete"
logger = get_logger("app.installation_service")


@dataclass(frozen=True, slots=True)
class TrustedBootstrapProfile:
    profile: InstallationProfile
    source: str


class InstallationService:
    def __init__(self) -> None:
        runtime_root = Path(__file__).resolve().parents[2] / ".runtime"
        self._runtime_root = runtime_root
        self._bootstrap_path = runtime_root / "installation_bootstrap.json"
        self._config_path = runtime_root / "installation_config.json"
        self._logs_dir = runtime_root / "logs"
        self._backups_root = runtime_root / "backups"

    def _seed_service(self):
        from app.services.application_seed_service import ApplicationSeedService

        return ApplicationSeedService()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _default_device_name(self) -> str:
        return socket.gethostname() or "Ibn Sina Device"

    def _default_device_code(self, profile: InstallationProfile) -> str:
        return "CENTRAL-SERVER" if profile == InstallationProfile.CENTRAL_SERVER else "PC-01"

    def _default_local_api_url(self) -> str:
        return settings.api_base_url

    def _trusted_profile_from_env(self) -> TrustedBootstrapProfile | None:
        raw_value = (os.environ.get(TRUSTED_PROFILE_ENV) or "").strip().lower()
        if not raw_value:
            return None
        return TrustedBootstrapProfile(profile=InstallationProfile(raw_value), source=TRUSTED_PROFILE_ENV)

    def _trusted_profile_from_file(self) -> TrustedBootstrapProfile | None:
        if not self._bootstrap_path.exists():
            return None
        payload = json.loads(self._bootstrap_path.read_text(encoding="utf-8"))
        raw_value = str(payload.get("installation_profile") or "").strip().lower()
        if not raw_value:
            return None
        return TrustedBootstrapProfile(profile=InstallationProfile(raw_value), source=str(self._bootstrap_path))

    def _trusted_bootstrap_profile(self) -> TrustedBootstrapProfile | None:
        return self._trusted_profile_from_file() or self._trusted_profile_from_env()

    def _can_override_default_mobile_profile(
        self,
        state: InstallationState,
        *,
        requested_profile: InstallationProfile,
    ) -> bool:
        trusted = self._trusted_bootstrap_profile()
        return (
            trusted is not None
            and trusted.source == TRUSTED_PROFILE_ENV
            and trusted.profile == InstallationProfile.MOBILE_DEVICE
            and state.profile_enum == InstallationProfile.MOBILE_DEVICE
            and requested_profile == InstallationProfile.CENTRAL_SERVER
            and state.provisioning_status_enum
            in {
                InstallationProvisioningStatus.UNCONFIGURED,
                InstallationProvisioningStatus.MOBILE_DEVICE_CONFIGURATION_REQUIRED,
                InstallationProvisioningStatus.FAILED,
                InstallationProvisioningStatus.RESET_REQUIRED,
            }
        )

    def _current_installation_uuid(self) -> py_uuid.UUID:
        return device_identity_service.load_installation_uuid()

    def _state_for_current_installation(self, db: Session) -> InstallationState | None:
        return db.scalar(select(InstallationState).where(InstallationState.installation_uuid == self._current_installation_uuid()))

    def _local_device(self, db: Session) -> SyncDevice | None:
        return db.scalar(select(SyncDevice).where(SyncDevice.installation_uuid == self._current_installation_uuid()))

    def _table_exists(self, db: Session, table_name: str, *, schema: str = "public") -> bool:
        connection = db.connection()
        return bool(inspect(connection).has_table(table_name, schema=schema))

    def _central_state(self, db: Session) -> CentralServerState | None:
        if not self._table_exists(db, CENTRAL_SERVER_STATE_TABLE):
            logger.warning(
                "installation.central_server_state_table_missing table=%s database_host=%s database_name=%s",
                CENTRAL_SERVER_STATE_TABLE,
                settings.database_host,
                settings.database_name,
            )
            return None
        return db.scalar(select(CentralServerState).limit(1))

    def _runtime_state(self, db: Session) -> RuntimeConfig | None:
        return db.scalar(select(RuntimeConfig).where(RuntimeConfig.id == 1))

    def _initial_status_for_profile(self, profile: InstallationProfile) -> InstallationProvisioningStatus:
        if profile == InstallationProfile.CENTRAL_SERVER:
            return InstallationProvisioningStatus.CENTRAL_CONFIGURATION_REQUIRED
        return InstallationProvisioningStatus.MOBILE_DEVICE_CONFIGURATION_REQUIRED

    def _read_runtime_config(self) -> dict[str, Any]:
        self._runtime_root.mkdir(parents=True, exist_ok=True)
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_runtime_config(self, payload: dict[str, Any]) -> None:
        self._runtime_root.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _merge_runtime_config(self, profile: InstallationProfile, updates: dict[str, Any]) -> dict[str, Any]:
        payload = self._read_runtime_config()
        key = profile.value
        section = payload.get(key)
        if not isinstance(section, dict):
            section = {}
        section.update({name: value for name, value in updates.items() if value is not None})
        payload[key] = section
        self._write_runtime_config(payload)
        return section

    def _profile_runtime_config(self, profile: InstallationProfile | None) -> dict[str, Any]:
        if profile is None:
            return {}
        payload = self._read_runtime_config()
        section = payload.get(profile.value)
        return section if isinstance(section, dict) else {}

    def _logs_path_for_profile(self, profile: InstallationProfile | None) -> Path:
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        if profile == InstallationProfile.CENTRAL_SERVER:
            return self._logs_dir / "central-provisioning.log"
        if profile == InstallationProfile.MOBILE_DEVICE:
            return self._logs_dir / "mobile-provisioning.log"
        return self._logs_dir / "upgrade.log"

    def _append_log(self, profile: InstallationProfile | None, message: str) -> None:
        path = self._logs_path_for_profile(profile)
        timestamp = self._now().isoformat()
        path.write_text(
            f"{path.read_text(encoding='utf-8') if path.exists() else ''}[{timestamp}] {message}\n",
            encoding="utf-8",
        )

    def _backup_directory(self, profile: InstallationProfile | None) -> Path | None:
        if profile != InstallationProfile.CENTRAL_SERVER:
            return None
        config = self._profile_runtime_config(profile)
        configured = config.get("backup_directory")
        if configured:
            return Path(str(configured))
        return self._backups_root / "central"

    def _ensure_backup_directory(self, profile: InstallationProfile | None, configured_path: str | None = None) -> Path | None:
        if profile != InstallationProfile.CENTRAL_SERVER:
            return None
        path = Path(configured_path) if configured_path else self._backup_directory(profile)
        if path is None:
            return None
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _postgresql_ready(self, db: Session) -> bool:
        try:
            db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _network_snapshot(self, profile: InstallationProfile | None, api_port: int | None) -> dict[str, str | None]:
        hostname = socket.gethostname() or "localhost"
        try:
            lan_ip = socket.gethostbyname(hostname)
        except OSError:
            lan_ip = "127.0.0.1"
        port = api_port or 8000
        health_status = "ready" if profile is not None else "pending"
        firewall_status = "configured" if profile == InstallationProfile.CENTRAL_SERVER else "not_required"
        return {
            "lan_ip": lan_ip,
            "api_url": f"http://{lan_ip}:{port}",
            "health_status": health_status,
            "firewall_status": firewall_status,
            "network_interface": hostname,
        }

    def _disk_space_label(self, path: Path | None) -> str | None:
        if path is None:
            return None
        usage = shutil.disk_usage(path if path.exists() else path.parent)
        gib = usage.free / (1024**3)
        return f"{gib:.1f} GiB libres"

    def _sync_state_metadata(
        self,
        db: Session,
        state: InstallationState,
        *,
        device: SyncDevice | None = None,
        central_state: CentralServerState | None = None,
    ) -> InstallationState:
        resolved_device = device if device is not None else self._local_device(db)
        if resolved_device is not None:
            state.device_uuid = resolved_device.uuid
            state.device_code = resolved_device.device_code
            state.device_name = resolved_device.device_name
        resolved_central_state = central_state if central_state is not None else self._central_state(db)
        if resolved_central_state is not None:
            state.central_server_uuid = resolved_central_state.server_uuid
            state.central_generation_uuid = resolved_central_state.server_generation_uuid
        if not db.is_modified(state):
            return state
        db.commit()
        db.refresh(state)
        return state

    def _create_unconfigured_state(self, db: Session) -> InstallationState:
        state = InstallationState(
            installation_uuid=self._current_installation_uuid(),
            installation_profile=None,
            profile_version=PROFILE_VERSION,
            provisioning_status=InstallationProvisioningStatus.UNCONFIGURED.value,
        )
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def _mark_status(
        self,
        db: Session,
        state: InstallationState,
        status: InstallationProvisioningStatus,
        *,
        user: User | None = None,
        details: dict[str, Any] | None = None,
    ) -> InstallationState:
        state.provisioning_status = status.value
        db.add(state)
        db.commit()
        db.refresh(state)
        self.record_audit_event(
            db,
            action="installation_status_changed",
            user=user,
            details={"status": status.value} | (details or {}),
        )
        self._append_log(state.profile_enum, f"status={status.value}")
        return state

    def _stage_trusted_profile(
        self,
        db: Session,
        state: InstallationState,
        profile: InstallationProfile,
        *,
        audit_source: str,
        user: User | None = None,
    ) -> InstallationState:
        existing_profile = state.profile_enum
        if existing_profile is not None and existing_profile != profile:
            if self._can_override_default_mobile_profile(state, requested_profile=profile):
                state.installation_profile = profile.value
                state.profile_version = PROFILE_VERSION
                state.provisioning_status = self._initial_status_for_profile(profile).value
                db.add(state)
                db.commit()
                db.refresh(state)
                self._append_log(profile, "trusted mobile fallback overridden by explicit central provisioning")
                return self._sync_state_metadata(db, state)
            self.record_audit_event(
                db,
                action="forbidden_profile_operation_attempted",
                user=user,
                details={
                    "requested_profile": profile.value,
                    "configured_profile": existing_profile.value,
                    "reason": "trusted_profile_mismatch",
                },
            )
            state.provisioning_status = InstallationProvisioningStatus.FAILED.value
            db.add(state)
            db.commit()
            db.refresh(state)
            return state

        if existing_profile is None:
            self.record_audit_event(
                db,
                action="installation_profile_selected",
                user=user,
                details={"profile": profile.value, "source": audit_source},
            )

        state.installation_profile = profile.value
        state.profile_version = PROFILE_VERSION
        if state.provisioning_status_enum in {
            InstallationProvisioningStatus.UNCONFIGURED,
            InstallationProvisioningStatus.FAILED,
            InstallationProvisioningStatus.RESET_REQUIRED,
        }:
            state.provisioning_status = self._initial_status_for_profile(profile).value
        db.add(state)
        db.commit()
        db.refresh(state)
        self._append_log(profile, f"trusted profile staged from {audit_source}")
        return self._sync_state_metadata(db, state)

    def _sync_derived_status(self, db: Session, state: InstallationState) -> InstallationState:
        profile = state.profile_enum
        if profile is None:
            return self._sync_state_metadata(db, state)

        trusted = self._trusted_bootstrap_profile()
        if trusted is not None and trusted.profile != profile:
            state.provisioning_status = InstallationProvisioningStatus.FAILED.value
            db.add(state)
            db.commit()
            db.refresh(state)
            return self._sync_state_metadata(db, state)

        seed_status = self._seed_service().status(db)
        if profile == InstallationProfile.CENTRAL_SERVER:
            central_state = self._central_state(db)
            if central_state is not None and seed_status["has_super_admin"]:
                if state.provisioning_status_enum != InstallationProvisioningStatus.CONFIGURED:
                    state.provisioning_status = InstallationProvisioningStatus.CONFIGURED.value
                    if state.provisioned_at is None:
                        state.provisioned_at = self._now()
            elif central_state is not None and state.provisioning_status_enum not in {
                InstallationProvisioningStatus.CENTRAL_CONFIGURATION_REQUIRED,
                InstallationProvisioningStatus.CHECKING_PREREQUISITES,
                InstallationProvisioningStatus.POSTGRESQL_MISSING,
                InstallationProvisioningStatus.POSTGRESQL_READY,
                InstallationProvisioningStatus.DATABASE_CREATING,
                InstallationProvisioningStatus.DATABASE_READY,
                InstallationProvisioningStatus.MIGRATIONS_RUNNING,
                InstallationProvisioningStatus.IDENTITY_CREATING,
            }:
                state.provisioning_status = InstallationProvisioningStatus.ADMIN_SETUP_REQUIRED.value
        if profile == InstallationProfile.MOBILE_DEVICE:
            sync_state = db.scalar(
                select(DeviceSyncState).where(DeviceSyncState.remote_server_type == "central_server").order_by(DeviceSyncState.id.desc())
            )
            if sync_state is not None and sync_state.copy_status == "completed":
                state.provisioning_status = InstallationProvisioningStatus.CONFIGURED.value
                if state.provisioned_at is None:
                    state.provisioned_at = self._now()
            elif state.device_uuid is not None and state.provisioning_status_enum not in {
                InstallationProvisioningStatus.MOBILE_DEVICE_CONFIGURATION_REQUIRED,
                InstallationProvisioningStatus.CHECKING_PREREQUISITES,
                InstallationProvisioningStatus.POSTGRESQL_MISSING,
                InstallationProvisioningStatus.POSTGRESQL_READY,
                InstallationProvisioningStatus.DATABASE_CREATING,
                InstallationProvisioningStatus.DATABASE_READY,
                InstallationProvisioningStatus.MIGRATIONS_RUNNING,
                InstallationProvisioningStatus.IDENTITY_CREATING,
            }:
                state.provisioning_status = InstallationProvisioningStatus.BOOTSTRAP_REQUIRED.value

        return self._sync_state_metadata(db, state)

    def get_or_create_state(self, db: Session) -> InstallationState:
        state = self._state_for_current_installation(db)
        if state is not None:
            return self._sync_derived_status(db, state)

        state = self._create_unconfigured_state(db)
        trusted = self._trusted_bootstrap_profile()
        if trusted is None:
            return state
        return self._stage_trusted_profile(db, state, trusted.profile, audit_source=trusted.source)

    def provision_current_installation(
        self,
        db: Session,
        profile: InstallationProfile,
        *,
        provisioned_by_user: User | None = None,
        audit_source: str = "trusted_bootstrap",
    ) -> InstallationState:
        if profile == InstallationProfile.CENTRAL_SERVER:
            self.provision_central_installation(
                db,
                server_name="Serveur central Ibn Sina",
                server_code=self._default_device_code(profile),
                description="Provisionnement automatisé",
                api_port=8000,
                backup_directory=str(self._ensure_backup_directory(profile)),
                admin_payload={
                    "first_name": "Install",
                    "last_name": "Admin",
                    "email": f"install-{self._current_installation_uuid()}@ibnsina.local",
                    "password": "Install12345",
                },
                provisioned_by_user=provisioned_by_user,
                audit_source=audit_source,
            )
            return self.require_configured_state(db)

        local_device = self._local_device(db)
        self.provision_mobile_installation(
            db,
            device_name=local_device.device_name if local_device is not None else self._default_device_name(),
            device_code=local_device.device_code if local_device is not None else self._default_device_code(profile),
            description="Provisionnement automatisé",
            central_server_url="http://127.0.0.1:8000",
            provisioned_by_user=provisioned_by_user,
            audit_source=audit_source,
        )
        state = self.require_configured_state(db)
        if state.provisioning_status_enum != InstallationProvisioningStatus.CONFIGURED:
            state.provisioning_status = InstallationProvisioningStatus.CONFIGURED.value
            state.provisioned_at = self._now()
            db.add(state)
            db.commit()
            db.refresh(state)
        return self._sync_state_metadata(db, state)

    def provision_central_installation(
        self,
        db: Session,
        *,
        server_name: str,
        server_code: str,
        description: str | None,
        api_port: int,
        backup_directory: str | None,
        admin_payload: Any,
        provisioned_by_user: User | None = None,
        audit_source: str = "central_setup_ui",
    ) -> InstallationState:
        state = self.get_or_create_state(db)
        if state.profile_enum not in {None, InstallationProfile.CENTRAL_SERVER} and not self._can_override_default_mobile_profile(
            state,
            requested_profile=InstallationProfile.CENTRAL_SERVER,
        ):
            raise ValueError("INSTALLATION_PROFILE_MISMATCH")
        state = self._stage_trusted_profile(
            db,
            state,
            InstallationProfile.CENTRAL_SERVER,
            audit_source=audit_source,
            user=provisioned_by_user,
        )

        self.record_audit_event(
            db,
            action="installation_profile_provisioning_started",
            user=provisioned_by_user,
            details={"profile": InstallationProfile.CENTRAL_SERVER.value},
        )
        self._mark_status(db, state, InstallationProvisioningStatus.CHECKING_PREREQUISITES, user=provisioned_by_user)
        if not self._postgresql_ready(db):
            self._mark_status(db, state, InstallationProvisioningStatus.POSTGRESQL_MISSING, user=provisioned_by_user)
            raise ValueError("POSTGRESQL_UNAVAILABLE")

        self._mark_status(db, state, InstallationProvisioningStatus.POSTGRESQL_READY, user=provisioned_by_user)
        self._mark_status(db, state, InstallationProvisioningStatus.DATABASE_CREATING, user=provisioned_by_user)
        self._ensure_backup_directory(InstallationProfile.CENTRAL_SERVER, backup_directory)
        self._merge_runtime_config(
            InstallationProfile.CENTRAL_SERVER,
            {
                "server_name": server_name,
                "server_code": server_code,
                "description": description,
                "api_port": api_port,
                "backup_directory": backup_directory or str(self._backup_directory(InstallationProfile.CENTRAL_SERVER)),
                "retention_policy": DEFAULT_RETENTION_POLICY,
            },
        )
        self._mark_status(db, state, InstallationProvisioningStatus.DATABASE_READY, user=provisioned_by_user)
        self._mark_status(db, state, InstallationProvisioningStatus.MIGRATIONS_RUNNING, user=provisioned_by_user)

        device = device_identity_service.register_or_resolve_local_device(
            db,
            device_code=server_code,
            device_name=server_name,
            description=description,
            is_central_server=True,
            app_version=APP_VERSION,
        )
        self._mark_status(db, state, InstallationProvisioningStatus.IDENTITY_CREATING, user=provisioned_by_user)
        from app.services.central_sync_service import central_sync_service
        from app.services.application_seed_service import InitialUserPayload

        central_state = central_sync_service.get_or_create_server_state(db, activate=True)
        resolved_admin_payload = (
            admin_payload
            if isinstance(admin_payload, InitialUserPayload)
            else InitialUserPayload(
                first_name=str(admin_payload["first_name"]),
                last_name=str(admin_payload["last_name"]),
                email=str(admin_payload["email"]),
                password=str(admin_payload["password"]),
            )
        )
        seed_status = self._seed_service().initialize_application(db, resolved_admin_payload)
        state.provisioned_by_user_uuid = getattr(provisioned_by_user, "uuid", None)
        state.provisioned_at = self._now() if seed_status["has_super_admin"] else None
        state.provisioning_status = (
            InstallationProvisioningStatus.CONFIGURED.value
            if seed_status["has_super_admin"]
            else InstallationProvisioningStatus.ADMIN_SETUP_REQUIRED.value
        )
        db.add(state)
        db.commit()
        db.refresh(state)
        self.record_audit_event(
            db,
            action="installation_profile_configured",
            user=provisioned_by_user,
            details={"profile": InstallationProfile.CENTRAL_SERVER.value, "device_uuid": str(device.uuid)},
        )
        self._append_log(
            InstallationProfile.CENTRAL_SERVER,
            f"central provisioned device={device.uuid} server={central_state.server_uuid}",
        )
        return self._sync_state_metadata(db, state, device=device, central_state=central_state)

    def complete_central_installation(
        self,
        db: Session,
        *,
        backup_directory: str | None,
        retention_policy: str | None,
        provisioned_by_user: User | None = None,
    ) -> InstallationState:
        state = self.require_configured_state(db)
        if state.profile_enum != InstallationProfile.CENTRAL_SERVER:
            raise ValueError("INSTALLATION_PROFILE_FORBIDDEN")
        ensured = self._ensure_backup_directory(InstallationProfile.CENTRAL_SERVER, backup_directory)
        self._merge_runtime_config(
            InstallationProfile.CENTRAL_SERVER,
            {
                "backup_directory": str(ensured) if ensured is not None else None,
                "retention_policy": retention_policy or DEFAULT_RETENTION_POLICY,
            },
        )
        if state.provisioning_status_enum != InstallationProvisioningStatus.CONFIGURED:
            state.provisioning_status = InstallationProvisioningStatus.CONFIGURED.value
        if state.provisioned_at is None:
            state.provisioned_at = self._now()
        db.add(state)
        db.commit()
        db.refresh(state)
        self.record_audit_event(
            db,
            action="installation_profile_completed",
            user=provisioned_by_user,
            details={"profile": InstallationProfile.CENTRAL_SERVER.value},
        )
        return self._sync_state_metadata(db, state)

    def provision_mobile_installation(
        self,
        db: Session,
        *,
        device_name: str,
        device_code: str,
        description: str | None,
        central_server_url: str,
        provisioned_by_user: User | None = None,
        audit_source: str = "mobile_setup_ui",
    ) -> InstallationState:
        state = self.get_or_create_state(db)
        if state.profile_enum not in {None, InstallationProfile.MOBILE_DEVICE}:
            self.record_audit_event(
                db,
                action="forbidden_profile_operation_attempted",
                user=provisioned_by_user,
                details={
                    "requested_profile": InstallationProfile.MOBILE_DEVICE.value,
                    "configured_profile": state.profile_enum.value if state.profile_enum is not None else None,
                    "reason": "trusted_profile_mismatch",
                },
            )
            state.installation_profile = InstallationProfile.MOBILE_DEVICE.value
            state.profile_version = PROFILE_VERSION
            state.provisioning_status = InstallationProvisioningStatus.FAILED.value
            db.add(state)
            db.commit()
            db.refresh(state)
            return self._sync_state_metadata(db, state)
        state = self._stage_trusted_profile(
            db,
            state,
            InstallationProfile.MOBILE_DEVICE,
            audit_source=audit_source,
            user=provisioned_by_user,
        )
        self.record_audit_event(
            db,
            action="installation_profile_provisioning_started",
            user=provisioned_by_user,
            details={"profile": InstallationProfile.MOBILE_DEVICE.value},
        )
        self._mark_status(db, state, InstallationProvisioningStatus.CHECKING_PREREQUISITES, user=provisioned_by_user)
        if not self._postgresql_ready(db):
            self._mark_status(db, state, InstallationProvisioningStatus.POSTGRESQL_MISSING, user=provisioned_by_user)
            raise ValueError("POSTGRESQL_UNAVAILABLE")

        self._mark_status(db, state, InstallationProvisioningStatus.POSTGRESQL_READY, user=provisioned_by_user)
        self._mark_status(db, state, InstallationProvisioningStatus.DATABASE_CREATING, user=provisioned_by_user)
        self._seed_service().ensure_reference_data(db)
        self._mark_status(db, state, InstallationProvisioningStatus.DATABASE_READY, user=provisioned_by_user)
        self._mark_status(db, state, InstallationProvisioningStatus.MIGRATIONS_RUNNING, user=provisioned_by_user)
        device = device_identity_service.register_or_resolve_local_device(
            db,
            device_code=device_code,
            device_name=device_name,
            description=description,
            is_central_server=False,
            app_version=APP_VERSION,
        )
        self._mark_status(db, state, InstallationProvisioningStatus.IDENTITY_CREATING, user=provisioned_by_user)
        from app.services.runtime_mode_service import runtime_mode_service

        runtime_mode_service.get_or_create(db, self._default_local_api_url())
        self._merge_runtime_config(
            InstallationProfile.MOBILE_DEVICE,
            {
                "device_name": device_name,
                "device_code": device_code,
                "description": description,
                "central_server_url": central_server_url,
            },
        )
        state.provisioning_status = InstallationProvisioningStatus.BOOTSTRAP_REQUIRED.value
        state.provisioned_by_user_uuid = getattr(provisioned_by_user, "uuid", None)
        db.add(state)
        db.commit()
        db.refresh(state)
        self._append_log(
            InstallationProfile.MOBILE_DEVICE,
            f"mobile provisioned device={device.uuid} bootstrap_required central={central_server_url}",
        )
        return self._sync_state_metadata(db, state, device=device)

    def record_audit_event(
        self,
        db: Session,
        *,
        action: str,
        details: dict | None = None,
        user: User | None = None,
    ) -> None:
        create_audit_log(
            db,
            user.id if user is not None else None,
            action,
            "installation_state",
            None,
            details=details,
        )

    def refresh_current_installation(self, db: Session) -> InstallationState:
        state = self.get_or_create_state(db)
        return self._sync_derived_status(db, state)

    def current_profile(self, db: Session) -> InstallationProfile | None:
        state = self.get_or_create_state(db)
        if state.provisioning_status_enum != InstallationProvisioningStatus.CONFIGURED:
            return None
        return state.profile_enum

    def require_configured_state(self, db: Session) -> InstallationState:
        state = self.get_or_create_state(db)
        trusted = self._trusted_bootstrap_profile()
        if trusted is not None and state.profile_enum is not None and trusted.profile != state.profile_enum:
            self.record_audit_event(
                db,
                action="forbidden_profile_operation_attempted",
                details={
                    "requested_profile": trusted.profile.value,
                    "configured_profile": state.profile_enum.value,
                    "reason": "contradictory_trusted_profile_hint",
                },
            )
        return state

    def _installation_error_codes(self, db: Session, state: InstallationState) -> list[str]:
        errors: list[str] = []
        trusted = self._trusted_bootstrap_profile()
        if trusted is not None and state.profile_enum is not None and (
            trusted.profile != state.profile_enum
            or state.provisioning_status_enum == InstallationProvisioningStatus.FAILED
        ):
            errors.append("INSTALLATION_PROFILE_MISMATCH")
        if not self._postgresql_ready(db):
            errors.append("POSTGRESQL_UNAVAILABLE")
        if not self._table_exists(db, CENTRAL_SERVER_STATE_TABLE):
            errors.append(CENTRAL_SERVER_STATE_TABLE_MISSING)
        if state.profile_enum == InstallationProfile.CENTRAL_SERVER:
            if self._central_state(db) is None:
                errors.append("CENTRAL_DATABASE_NOT_PROVISIONED")
            if self._backup_directory(state.profile_enum) is None:
                errors.append("BACKUP_CONFIGURATION_FAILED")
        return errors

    def _status_warnings(self, db: Session) -> list[dict[str, str]]:
        warnings: list[dict[str, str]] = []
        if not self._table_exists(db, CENTRAL_SERVER_STATE_TABLE):
            warnings.append(
                {
                    "code": CENTRAL_SERVER_STATE_TABLE_MISSING,
                    "message": "The central server state table is missing. Run the pending database migration.",
                }
            )
        return warnings

    def _checks_for_state(self, db: Session, state: InstallationState) -> list[dict[str, str | None]]:
        seed_status = self._seed_service().status(db)
        profile = state.profile_enum
        central_state = self._central_state(db)
        backup_dir = self._backup_directory(profile)
        return [
            {
                "key": "postgresql_service",
                "label": "Service PostgreSQL",
                "status": "success" if self._postgresql_ready(db) else "failed",
                "detail": settings.database_host,
            },
            {
                "key": "local_connection",
                "label": "Connexion locale",
                "status": "success" if self._postgresql_ready(db) else "failed",
                "detail": settings.database_name,
            },
            {
                "key": "central_database",
                "label": "Base centrale" if profile == InstallationProfile.CENTRAL_SERVER else "Base locale",
                "status": "success" if (profile != InstallationProfile.CENTRAL_SERVER or central_state is not None) else "pending",
                "detail": settings.database_name,
            },
            {
                "key": "application_user",
                "label": "Utilisateur applicatif",
                "status": "success" if state.device_uuid is not None else "pending",
                "detail": state.device_code,
            },
            {
                "key": "schema_permissions",
                "label": "Permissions du schéma" if profile == InstallationProfile.CENTRAL_SERVER else "Migrations",
                "status": "success" if seed_status["database_ready"] else "pending",
                "detail": str(device_identity_service.current_schema_revision(db) or ""),
            },
            {
                "key": "backup_directory",
                "label": "Sauvegarde",
                "status": "success" if backup_dir is not None and backup_dir.exists() else "pending",
                "detail": str(backup_dir) if backup_dir is not None else None,
            },
        ]

    def _stages_for_state(self, state: InstallationState) -> list[dict[str, str | None]]:
        profile = state.profile_enum
        if profile == InstallationProfile.CENTRAL_SERVER:
            stage_defs = [
                ("database_creation", "Création de la base", InstallationProvisioningStatus.DATABASE_CREATING),
                ("role_creation", "Création du rôle applicatif", InstallationProvisioningStatus.DATABASE_READY),
                ("permissions", "Configuration des permissions", InstallationProvisioningStatus.DATABASE_READY),
                ("migrations", "Application des migrations", InstallationProvisioningStatus.MIGRATIONS_RUNNING),
                ("sequence", "Initialisation de la séquence centrale", InstallationProvisioningStatus.IDENTITY_CREATING),
            ]
        else:
            stage_defs = [
                ("local_backup", "Création de la sauvegarde locale", InstallationProvisioningStatus.BOOTSTRAP_RUNNING),
                ("manifest", "Téléchargement du manifeste", InstallationProvisioningStatus.BOOTSTRAP_RUNNING),
                ("snapshot", "Téléchargement de l’instantané", InstallationProvisioningStatus.BOOTSTRAP_RUNNING),
                ("checksum", "Validation du checksum", InstallationProvisioningStatus.BOOTSTRAP_RUNNING),
                ("relations", "Vérification des relations", InstallationProvisioningStatus.CONFIGURED),
            ]
        current = state.provisioning_status_enum
        values = list(InstallationProvisioningStatus)
        current_index = values.index(current)
        response: list[dict[str, str | None]] = []
        for key, label, marker in stage_defs:
            marker_index = values.index(marker)
            if current_index > marker_index:
                status = "success"
            elif current_index == marker_index:
                status = "running"
            else:
                status = "pending"
            response.append({"key": key, "label": label, "status": status, "detail": None})
        return response

    def installation_status(self, db: Session) -> dict[str, Any]:
        state = self.refresh_current_installation(db)
        profile = state.profile_enum
        central_state = self._central_state(db)
        runtime = self._runtime_state(db)
        seed_status = self._seed_service().status(db)
        config = self._profile_runtime_config(profile)
        backup_dir = self._backup_directory(profile)
        network = self._network_snapshot(profile, config.get("api_port") if isinstance(config.get("api_port"), int) else None)
        checks = self._checks_for_state(db, state)
        stages = self._stages_for_state(state)
        warnings = self._status_warnings(db)
        provisioning_status = state.provisioning_status
        if warnings and provisioning_status in {
            InstallationProvisioningStatus.UNCONFIGURED.value,
            InstallationProvisioningStatus.CENTRAL_CONFIGURATION_REQUIRED.value,
            InstallationProvisioningStatus.MOBILE_DEVICE_CONFIGURATION_REQUIRED.value,
        }:
            provisioning_status = SCHEMA_INCOMPLETE_STATUS
        return {
            "profile": profile.value if profile is not None else None,
            "provisioning_status": provisioning_status,
            "app_version": APP_VERSION,
            "schema_revision": str(device_identity_service.current_schema_revision(db) or "") or None,
            "sync_protocol_version": SYNC_PROTOCOL_VERSION,
            "server_uuid": str(central_state.server_uuid) if central_state is not None else (str(state.device_uuid) if state.device_uuid else None),
            "generation_uuid": str(central_state.server_generation_uuid) if central_state is not None else None,
            "central_sequence": int(central_state.current_central_sequence) if central_state is not None else None,
            "checks": checks,
            "provisioning_stages": stages,
            "postgres_ready": self._postgresql_ready(db),
            "central_database_ready": central_state is not None if profile == InstallationProfile.CENTRAL_SERVER else state.device_uuid is not None,
            "migrations_up_to_date": bool(seed_status["database_ready"]),
            "fastapi_ready": True,
            "admin_created": bool(seed_status["has_super_admin"]),
            "backup_configured": bool(backup_dir is not None and backup_dir.exists()),
            "backup_directory": str(backup_dir) if backup_dir is not None else None,
            "backup_status": "Prêt" if backup_dir is not None and backup_dir.exists() else "Non configurée",
            "retention_policy": str(config.get("retention_policy") or DEFAULT_RETENTION_POLICY) if profile == InstallationProfile.CENTRAL_SERVER else None,
            "available_disk_space": self._disk_space_label(backup_dir or self._runtime_root),
            "network": network,
            "identity": {
                "server_name": config.get("server_name") or config.get("device_name") or state.device_name,
                "server_code": config.get("server_code") or config.get("device_code") or state.device_code,
                "description": config.get("description"),
                "api_port": config.get("api_port") if config.get("api_port") is not None else None,
            },
            "pending_error_codes": self._installation_error_codes(db, state),
            "warnings": warnings,
        }

    def installation_readiness(self, db: Session) -> dict[str, Any]:
        state = self.refresh_current_installation(db)
        checks = self._checks_for_state(db, state)
        ready = all(check["status"] == "success" for check in checks[:5])
        return {
            "profile": state.installation_profile,
            "provisioning_status": state.provisioning_status,
            "ready": ready,
            "checks": checks,
        }

    def profile_summary(self, db: Session) -> dict[str, object]:
        state = self.refresh_current_installation(db)
        profile = state.profile_enum
        trusted = self._trusted_bootstrap_profile()
        return {
            "profile": profile.value if profile is not None else None,
            "profile_version": state.profile_version,
            "provisioning_status": state.provisioning_status,
            "installation_uuid": str(state.installation_uuid),
            "device": {
                "uuid": str(state.device_uuid) if state.device_uuid else None,
                "code": state.device_code,
                "name": state.device_name,
            },
            "packaged_profile": trusted.profile.value if trusted is not None else None,
            "central_server_uuid": str(state.central_server_uuid) if state.central_server_uuid else None,
            "central_generation_uuid": str(state.central_generation_uuid) if state.central_generation_uuid else None,
            "capabilities": capabilities_for_profile(profile),
        }

    def has_capability(self, db: Session, capability: str) -> bool:
        return profile_has_capability(self.get_or_create_state(db).profile_enum, capability)

    def latest_mobile_bootstrap(self, db: Session) -> CentralBootstrap | None:
        state = self.get_or_create_state(db)
        if state.device_uuid is None:
            return None
        return db.scalar(
            select(CentralBootstrap)
            .where(CentralBootstrap.device_uuid == state.device_uuid)
            .order_by(CentralBootstrap.created_at.desc())
        )


installation_service = InstallationService()
