from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import select, text

from app.core.enums import InstallationProfile, InstallationProvisioningStatus
from app.exceptions import BadRequestException
from app.models.audit_log import AuditLog
from app.models.central_server_state import CentralServerState
from app.models.device_sync_state import DeviceSyncState
from app.models.installation_state import InstallationState
from app.models.sync_device import SyncDevice
from app.services.auth_service import AuthService
from app.services.device_identity_service import device_identity_service
from app.services.installation_service import installation_service
from app.services.runtime_mode_service import RuntimeMode, runtime_mode_service


def _login(client, db_session):
    AuthService().create_admin_user(
        db_session,
        first_name="Install",
        last_name="Admin",
        email="install-admin@ibnsina-clinic.com",
        password="admin12345",
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "install-admin@ibnsina-clinic.com", "password": "admin12345"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _switch_installation(tmp_path, name: str) -> None:
    device_identity_service._storage_path = tmp_path / f"{name}.installation_uuid.txt"  # noqa: SLF001


def _configure_mobile_installation(db_session) -> InstallationState:
    installation_service.provision_mobile_installation(
        db_session,
        device_name="PC Medecin 01",
        device_code="PC-01",
        description="Poste mobile",
        central_server_url="http://192.168.1.5:8000",
        audit_source="test",
    )
    state = installation_service.get_or_create_state(db_session)
    state.provisioning_status = InstallationProvisioningStatus.CONFIGURED.value
    state.provisioned_at = installation_service._now()  # noqa: SLF001
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


def _configure_central_installation(db_session) -> InstallationState:
    return installation_service.provision_current_installation(db_session, InstallationProfile.CENTRAL_SERVER, audit_source="test")


def test_profile_endpoint_safe_before_login(client, tmp_path):
    _switch_installation(tmp_path, "mobile-profile-safe")
    response = client.get("/api/v1/installation/profile")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["profile"] == "mobile_device"
    assert payload["provisioning_status"] == "mobile_device_configuration_required"
    assert payload["packaged_profile"] == "mobile_device"
    assert "capabilities" in payload
    assert "device" in payload
    assert "secret" not in str(payload).lower()


def test_mobile_profile_staged_then_bootstrap_required(db_session, tmp_path):
    _switch_installation(tmp_path, "mobile-staged")

    staged = installation_service.get_or_create_state(db_session)
    assert staged.installation_profile == InstallationProfile.MOBILE_DEVICE.value
    assert staged.provisioning_status == "mobile_device_configuration_required"

    provisioned = installation_service.provision_mobile_installation(
        db_session,
        device_name="PC Medecin 01",
        device_code="PC-01",
        description="Poste mobile",
        central_server_url="http://192.168.1.5:8000",
        audit_source="test",
    )
    assert provisioned.installation_profile == InstallationProfile.MOBILE_DEVICE.value
    assert provisioned.provisioning_status == "bootstrap_required"
    assert provisioned.device_uuid is not None

    same_state = installation_service.get_or_create_state(db_session)
    assert same_state.installation_uuid == provisioned.installation_uuid
    assert same_state.installation_profile == InstallationProfile.MOBILE_DEVICE.value
    assert same_state.device_uuid == provisioned.device_uuid


def test_mobile_reload_recovery_and_identity_stability(db_session, tmp_path):
    _switch_installation(tmp_path, "mobile-reload")
    provisioned = installation_service.provision_mobile_installation(
        db_session,
        device_name="PC Medecin 01",
        device_code="PC-01",
        description="Poste mobile",
        central_server_url="http://192.168.1.5:8000",
        audit_source="test",
    )

    reloaded = installation_service.refresh_current_installation(db_session)
    assert reloaded.device_uuid == provisioned.device_uuid
    assert reloaded.device_code == "PC-01"
    assert reloaded.provisioning_status == "bootstrap_required"


def test_mobile_becomes_configured_after_completed_bootstrap(db_session, tmp_path):
    _switch_installation(tmp_path, "mobile-bootstrap-complete")
    state = installation_service.provision_mobile_installation(
        db_session,
        device_name="PC Medecin 01",
        device_code="PC-01",
        description="Poste mobile",
        central_server_url="http://192.168.1.5:8000",
        audit_source="test",
    )
    central_state = CentralServerState(
        server_uuid=py_uuid.uuid4(),
        server_generation_uuid=py_uuid.uuid4(),
        device_uuid=state.device_uuid,
        status="known_remote",
        schema_revision="1",
        protocol_version="1",
        current_central_sequence=42,
    )
    db_session.add(central_state)
    db_session.flush()
    db_session.add(
        DeviceSyncState(
            remote_server_uuid=central_state.server_uuid,
            remote_server_type="central_server",
            remote_server_url="http://192.168.1.5:8000/api/v1",
            mission_session_uuid=None,
            last_pulled_sequence=42,
            last_pushed_sequence=42,
            final_mission_sequence=42,
            copy_status="completed",
            is_sync_running=False,
        )
    )
    db_session.commit()

    refreshed = installation_service.refresh_current_installation(db_session)
    assert refreshed.provisioning_status == "configured"
    assert refreshed.central_server_uuid == central_state.server_uuid


def test_central_status_endpoint_reports_real_checks(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("IBNSINA_INSTALLATION_PROFILE", "central_server")
    _switch_installation(tmp_path, "central-status")

    response = client.get("/api/v1/installation/status")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["profile"] == "central_server"
    assert payload["provisioning_status"] == "central_configuration_required"
    assert any(check["label"] == "Service PostgreSQL" for check in payload["checks"])
    assert any(stage["label"] == "Création de la base" for stage in payload["provisioning_stages"])


def test_installation_endpoints_remain_safe_when_central_state_table_is_missing(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("IBNSINA_INSTALLATION_PROFILE", "mobile_device")
    _switch_installation(tmp_path, "missing-central-table")
    db_session.execute(text("DROP TABLE IF EXISTS central_server_state CASCADE"))
    db_session.commit()

    status_response = client.get("/api/v1/installation/status")
    profile_response = client.get("/api/v1/installation/profile")

    assert status_response.status_code == 200
    status_payload = status_response.json()["data"]
    assert status_payload["profile"] == "mobile_device"
    assert status_payload["provisioning_status"] == "schema_incomplete"
    assert "CENTRAL_SERVER_STATE_TABLE_MISSING" in status_payload["pending_error_codes"]
    assert status_payload["warnings"] == [
        {
            "code": "CENTRAL_SERVER_STATE_TABLE_MISSING",
            "message": "The central server state table is missing. Run the pending database migration.",
        }
    ]

    assert profile_response.status_code == 200
    profile_payload = profile_response.json()["data"]
    assert profile_payload["profile"] == "mobile_device"
    assert profile_payload["provisioning_status"] == "mobile_device_configuration_required"


def test_central_provision_endpoint_configures_server(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("IBNSINA_INSTALLATION_PROFILE", "central_server")
    _switch_installation(tmp_path, "central-provision")

    response = client.post(
        "/api/v1/installation/central/provision",
        json={
            "server_name": "Serveur central Ibn Sina",
            "server_code": "CENTRAL-SERVER",
            "description": "Noeud principal",
            "api_port": 8000,
            "backup_directory": str(tmp_path / "backups"),
            "admin": {
                "first_name": "Amina",
                "last_name": "Admin",
                "email": "amina.admin@ibnsina.local",
                "password": "Admin12345",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provisioning_status"] == "configured"
    assert any(stage["label"] == "Application des migrations" for stage in payload["stages"])

    state = installation_service.get_or_create_state(db_session)
    assert state.installation_profile == InstallationProfile.CENTRAL_SERVER.value
    assert state.provisioning_status == "configured"


def test_profile_mismatch_becomes_blocking_error(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("IBNSINA_INSTALLATION_PROFILE", "central_server")
    _switch_installation(tmp_path, "mismatch")
    installation_service.provision_current_installation(db_session, InstallationProfile.MOBILE_DEVICE, audit_source="test")

    response = client.get("/api/v1/installation/status")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert "INSTALLATION_PROFILE_MISMATCH" in payload["pending_error_codes"]
    state = installation_service.get_or_create_state(db_session)
    assert state.provisioning_status == "failed"


def test_central_only_route_rejected_on_mobile(client, db_session, tmp_path):
    _switch_installation(tmp_path, "mobile-guard")
    _configure_mobile_installation(db_session)
    token = _login(client, db_session)

    response = client.get("/api/v1/central/server-info", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["message"] == "CENTRAL_AUTHORITY_REQUIRED"


def test_mobile_only_route_rejected_on_central(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("IBNSINA_INSTALLATION_PROFILE", "central_server")
    _switch_installation(tmp_path, "central-guard")
    _configure_central_installation(db_session)
    token = _login(client, db_session)

    response = client.post(
        "/api/v1/mission/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mission_code": "MISSION-CENTRAL-BLOCK",
            "mission_name": "Blocked",
            "description": None,
            "expected_devices": [],
        },
    )

    assert response.status_code == 403
    assert response.json()["message"] == "CAPABILITY_NOT_AVAILABLE"


def test_central_server_cannot_enter_mission_client_mode(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("IBNSINA_INSTALLATION_PROFILE", "central_server")
    _switch_installation(tmp_path, "central-runtime")
    _configure_central_installation(db_session)
    runtime_mode_service.get_or_create(db_session, "http://localhost:8000/api/v1")

    try:
        runtime_mode_service.transition(
            db_session,
            new_mode=RuntimeMode.MISSION_CLIENT,
            local_api_url="http://localhost:8000/api/v1",
            changed_by_user_uuid=py_uuid.uuid4(),
            mission_server_url="http://10.0.0.2:8000/api/v1",
            mission_server_device_uuid=py_uuid.uuid4(),
            active_mission_session_uuid=py_uuid.uuid4(),
        )
        assert False, "central server must not enter mission client mode"
    except BadRequestException as exc:
        assert exc.detail["message"] == "INSTALLATION_PROFILE_FORBIDDEN"


def test_mobile_device_cannot_assign_central_sequence(client, db_session, tmp_path):
    _switch_installation(tmp_path, "mobile-central-sequence")
    _configure_mobile_installation(db_session)
    token = _login(client, db_session)

    response = client.post(
        "/api/v1/central-sync/push",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "batch_uuid": str(py_uuid.uuid4()),
            "device_uuid": str(py_uuid.uuid4()),
            "mission_uuid": str(py_uuid.uuid4()),
            "mission_manifest_checksum": "checksum",
            "base_central_sequence": 0,
            "changes": [],
        },
    )

    assert response.status_code == 403
    assert response.json()["message"] == "CENTRAL_AUTHORITY_REQUIRED"


def test_existing_unclassified_installation_remains_unconfigured(client, db_session, tmp_path, monkeypatch):
    monkeypatch.delenv("IBNSINA_INSTALLATION_PROFILE", raising=False)
    _switch_installation(tmp_path, "legacy-install")
    db_session.add(
        SyncDevice(
            uuid=py_uuid.uuid4(),
            installation_uuid=device_identity_service.load_installation_uuid(),
            device_code="PC-LEGACY",
            device_name="Legacy Device",
            hostname="legacy-host",
            device_category="desktop",
            is_active=True,
            is_revoked=False,
            registered_at=installation_service._now(),  # noqa: SLF001
        )
    )
    db_session.commit()

    response = client.get("/api/v1/installation/profile")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["profile"] is None
    assert payload["provisioning_status"] == "unconfigured"


def test_audit_events_are_created_for_profile_enforcement(client, db_session, tmp_path):
    _switch_installation(tmp_path, "audit-mobile")
    _configure_mobile_installation(db_session)
    token = _login(client, db_session)

    response = client.get("/api/v1/central/server-info", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    actions = db_session.scalars(select(AuditLog.action).order_by(AuditLog.id.asc())).all()
    assert "installation_profile_selected" in actions
    assert "installation_profile_provisioning_started" in actions
    assert "installation_status_changed" in actions
    assert "forbidden_profile_operation_attempted" in actions


def test_mobile_provision_route_returns_device_uuid(client, tmp_path):
    _switch_installation(tmp_path, "mobile-route")
    response = client.post(
        "/api/v1/installation/mobile/provision",
        json={
            "device_name": "PC Medecin 01",
            "device_code": "PC-01",
            "description": "Poste mobile",
            "central_server_url": "http://192.168.1.5:8000",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provisioning_status"] == "bootstrap_required"
    assert payload["device_uuid"] is not None


def test_stored_installation_record_persists(db_session, tmp_path):
    _switch_installation(tmp_path, "persisted")
    _configure_mobile_installation(db_session)

    stored = db_session.scalar(select(InstallationState).where(InstallationState.installation_uuid == device_identity_service.load_installation_uuid()))
    assert stored is not None
    assert stored.installation_profile == InstallationProfile.MOBILE_DEVICE.value
