from __future__ import annotations

import uuid as py_uuid

from app.models.company import Company
from app.models.sync_device import SyncDevice
from app.services.auth_service import AuthService
from app.services.device_identity_service import device_identity_service
from app.services.runtime_mode_service import RuntimeMode, runtime_mode_service


def _login(client, db_session):
    AuthService().create_admin_user(
        db_session,
        first_name="Mission",
        last_name="Admin",
        email="mission-admin@ibnsina-clinic.com",
        password="admin12345",
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "mission-admin@ibnsina-clinic.com", "password": "admin12345"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _register_local_device(db_session, tmp_path):
    device_identity_service._storage_path = tmp_path / "installation_uuid.txt"  # noqa: SLF001
    return device_identity_service.register_or_resolve_local_device(
        db_session,
        device_code="PC-01",
        device_name="Doctor Laptop 01",
        app_version="1.0.0",
    )


def test_mission_server_info_and_session_lifecycle(client, db_session, tmp_path):
    token = _login(client, db_session)
    device = _register_local_device(db_session, tmp_path)

    response = client.get("/api/v1/mission/server-info", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["device_uuid"] == str(device.uuid)
    assert payload["runtime_mode"] == "standalone"

    created = client.post(
        "/api/v1/mission/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mission_code": "MISSION-HMD-2026-07-20",
            "mission_name": "Hassi Messaoud Mission",
            "description": "Remote checkup",
            "expected_devices": [],
        },
    )
    assert created.status_code == 200
    mission_uuid = created.json()["data"]["uuid"]

    activated = client.post(
        f"/api/v1/mission/sessions/{mission_uuid}/activate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert activated.status_code == 200

    current = client.get("/api/v1/mission/sessions/current", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["data"]["uuid"] == mission_uuid


def test_mission_join_issues_device_credential(client, db_session, tmp_path):
    token = _login(client, db_session)
    server_device = _register_local_device(db_session, tmp_path)
    created = client.post(
        "/api/v1/mission/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mission_code": "MISSION-HMD-2026-07-21",
            "mission_name": "Join Mission",
            "description": None,
            "expected_devices": [],
        },
    )
    mission_uuid = created.json()["data"]["uuid"]
    client.post(
        f"/api/v1/mission/sessions/{mission_uuid}/activate",
        headers={"Authorization": f"Bearer {token}"},
    )

    client_device = SyncDevice(
        uuid=py_uuid.uuid4(),
        installation_uuid=py_uuid.uuid4(),
        device_code="PC-02",
        device_name="Assistant Laptop 01",
        hostname="pc-02",
        device_category="desktop",
        is_active=True,
        is_revoked=False,
        registered_at=server_device.registered_at,
    )
    db_session.add(client_device)
    db_session.commit()
    join = client.post(
        f"/api/v1/mission/sessions/{mission_uuid}/join",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "device_uuid": str(client_device.uuid),
            "device_code": "PC-02",
            "device_name": "Assistant Laptop 01",
            "installation_uuid": str(client_device.installation_uuid),
            "app_version": "1.0.0",
            "schema_revision": server_device.schema_revision,
            "last_central_sequence": 0,
            "protocol_version": "1",
        },
    )
    assert join.status_code == 200
    assert join.json()["data"]["credential"]["access_token"]


def test_mission_client_runtime_blocks_local_business_writes(db_session):
    runtime_mode_service.get_or_create(db_session, "http://localhost:8000/api/v1")
    runtime_mode_service.transition(
        db_session,
        new_mode=RuntimeMode.MISSION_CLIENT,
        local_api_url="http://localhost:8000/api/v1",
        changed_by_user_uuid=None,
        mission_server_url="http://10.0.0.2:8000/api/v1",
        mission_server_device_uuid=py_uuid.uuid4(),
        active_mission_session_uuid=py_uuid.uuid4(),
    )
    db_session.add(Company(name="Blocked Company"))
    try:
        db_session.commit()
        assert False, "commit should fail in mission client mode"
    except Exception:
        db_session.rollback()
