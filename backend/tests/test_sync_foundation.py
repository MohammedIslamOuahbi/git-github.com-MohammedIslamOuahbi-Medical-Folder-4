from __future__ import annotations

import uuid as py_uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.mission_session import MissionSession
from app.models.permission import Permission
from app.models.runtime_config import RuntimeConfig
from app.models.sync_change import SyncChange
from app.models.sync_device import SyncDevice
from app.models.user import User
from app.models.worker import Worker
from app.models.branch import Branch
from app.services.device_identity_service import DeviceIdentityService, DeviceRevokedError
from app.services.mission_session_service import MissionSessionService
from app.services.runtime_mode_service import RuntimeMode, RuntimeModeService
from app.services.sync_context import set_sync_context, sync_apply_scope


def _create_user(**overrides) -> User:
    return User(
        first_name=overrides.get("first_name", "A"),
        last_name=overrides.get("last_name", "B"),
        email=overrides.get("email", f"{py_uuid.uuid4()}@example.com"),
        password_hash="hashed",
        role=overrides.get("role", "admin"),
    )


def _register_device(db_session, service: DeviceIdentityService, code: str, name: str) -> SyncDevice:
    return service.register_or_resolve_local_device(
        db_session,
        device_code=code,
        device_name=name,
        app_version="1.0.0",
    )


def test_device_uuid_stability_and_unique_code(db_session, tmp_path, monkeypatch):
    service = DeviceIdentityService()
    service._storage_path = tmp_path / "installation_uuid.txt"  # noqa: SLF001
    device = _register_device(db_session, service, "PC-01", "Doctor Laptop 01")
    again = _register_device(db_session, service, "PC-01", "Doctor Laptop 01 Renamed")
    assert device.uuid == again.uuid
    assert again.device_name == "Doctor Laptop 01 Renamed"

    other_service = DeviceIdentityService()
    other_service._storage_path = tmp_path / "other_installation_uuid.txt"  # noqa: SLF001
    _register_device(db_session, other_service, "PC-02", "Doctor Laptop 02")
    with pytest.raises(ValueError):
        _register_device(db_session, DeviceIdentityService(), "PC-02", "Duplicate")


def test_user_identity_is_separate_from_device_identity(db_session, tmp_path):
    service = DeviceIdentityService()
    service._storage_path = tmp_path / "installation_uuid.txt"  # noqa: SLF001
    device = _register_device(db_session, service, "PC-USER", "Shared Device")
    user_one = _create_user(email="one@example.com")
    user_two = _create_user(email="two@example.com")
    db_session.add_all([user_one, user_two])
    db_session.commit()
    assert user_one.uuid != device.uuid
    assert user_two.uuid != device.uuid
    assert user_one.uuid != user_two.uuid


def test_revoked_device_cannot_participate(db_session, tmp_path):
    service = DeviceIdentityService()
    service._storage_path = tmp_path / "installation_uuid.txt"  # noqa: SLF001
    device = _register_device(db_session, service, "PC-REVOKE", "Revoked Device")
    device.is_revoked = True
    db_session.add(device)
    db_session.commit()
    with pytest.raises(DeviceRevokedError):
        service.validate_revocation_state(device)


def test_runtime_mode_state_transitions(db_session):
    service = RuntimeModeService()
    state = service.get_or_create(db_session, "http://localhost:8000/api/v1")
    assert state.runtime_mode == RuntimeMode.STANDALONE.value
    assert state.local_database_write_enabled is True

    with pytest.raises(Exception):
        service.transition(
            db_session,
            new_mode=RuntimeMode.MISSION_CLIENT,
            local_api_url="http://localhost:8000/api/v1",
            changed_by_user_uuid=None,
        )

    state = service.transition(
        db_session,
        new_mode=RuntimeMode.MISSION_CLIENT,
        local_api_url="http://localhost:8000/api/v1",
        changed_by_user_uuid=None,
        mission_server_url="http://10.0.0.20:8000/api/v1",
        mission_server_device_uuid=py_uuid.uuid4(),
        active_mission_session_uuid=py_uuid.uuid4(),
    )
    assert state.runtime_mode == RuntimeMode.MISSION_CLIENT.value
    assert state.local_database_write_enabled is False

    with pytest.raises(Exception):
        service.transition(
            db_session,
            new_mode=RuntimeMode.STANDALONE,
            local_api_url="http://localhost:8000/api/v1",
            changed_by_user_uuid=None,
        )


def test_mission_session_creation_and_server_uniqueness(db_session, tmp_path):
    device_service = DeviceIdentityService()
    device_service._storage_path = tmp_path / "server_installation_uuid.txt"  # noqa: SLF001
    server = _register_device(db_session, device_service, "MS-01", "Mission Server")
    mission_service = MissionSessionService()
    mission = mission_service.create_session(
        db_session,
        mission_code="MISSION-HMD-2026-07-20",
        mission_name="HMD Visit",
        server_device_uuid=server.uuid,
        server_device_name_snapshot=server.device_name,
        created_by_user_uuid=None,
    )
    assert mission.status == "active"
    participant = mission_service.add_participant(
        db_session,
        mission_session_uuid=mission.uuid,
        device_uuid=server.uuid,
        role="mission_server",
    )
    assert participant.role == "mission_server"

    with pytest.raises(Exception):
        mission_service.create_session(
            db_session,
            mission_code="MISSION-HMD-2026-07-20-B",
            mission_name="Competing Mission",
            server_device_uuid=server.uuid,
            server_device_name_snapshot=server.device_name,
            created_by_user_uuid=None,
        )


def test_syncable_write_creates_change_with_uuid_relationships(db_session):
    permission = Permission(code="workers:create", name="Workers Create")
    user = _create_user(email="sync-user@example.com")
    company = Company(name="Acme")
    db_session.add_all([permission, user, company])
    db_session.commit()

    branch = Branch(company_id=company.id, name="Branch A")
    db_session.add(branch)
    db_session.commit()

    db_session.info["sync_source_device_uuid"] = py_uuid.uuid4()
    db_session.info["sync_source_user_uuid"] = user.uuid
    worker = Worker(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=None,
        employee_number="EMP-1",
        national_id="NAT-1",
        first_name="Worker",
        last_name="One",
    )
    db_session.add(worker)
    db_session.commit()

    changes = db_session.scalars(
        select(SyncChange).where(SyncChange.entity_type == "workers", SyncChange.entity_uuid == worker.uuid)
    ).all()
    assert len(changes) == 1
    payload = changes[0].payload
    assert payload["uuid"] == str(worker.uuid)
    assert payload["company_uuid"] == str(company.uuid)
    assert "company_id" not in payload
    assert "branch_id" not in payload
    assert "id" not in payload


def test_remote_apply_mode_does_not_echo_outbound_changes(db_session):
    company = Company(name="Silent Apply Co")
    with sync_apply_scope(db_session):
        db_session.add(company)
        db_session.commit()
    changes = db_session.scalars(select(SyncChange).where(SyncChange.entity_type == "companies")).all()
    assert changes == []
