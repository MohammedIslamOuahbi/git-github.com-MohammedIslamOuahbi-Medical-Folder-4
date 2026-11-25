from __future__ import annotations

from backend.tests.test_client_sync import _login


def test_device_current_returns_unregistered_state(client, db_session):
    headers = {"Authorization": f"Bearer {_login(client, db_session)}"}

    response = client.get("/api/v1/device/current", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["registered"] is False
    assert payload["device_uuid"] is None
    assert payload["runtime_mode"] == "standalone"


def test_device_current_patch_registers_local_device(client, db_session):
    headers = {"Authorization": f"Bearer {_login(client, db_session)}"}

    response = client.patch("/api/v1/device/current", headers=headers, json={"device_name": "Poste Mission 01"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["registered"] is True
    assert payload["device_name"] == "Poste Mission 01"
    assert payload["device_uuid"]
    assert payload["device_code"]


def test_runtime_status_returns_runtime_config(client, db_session):
    headers = {"Authorization": f"Bearer {_login(client, db_session)}"}

    response = client.get("/api/v1/runtime/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["runtime_mode"] == "standalone"
    assert payload["local_device_registered"] is False
    assert payload["active_api_url"]


def test_mission_server_info_returns_structured_unregistered_state(client, db_session):
    headers = {"Authorization": f"Bearer {_login(client, db_session)}"}

    response = client.get("/api/v1/mission/server-info", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["registered"] is False
    assert payload["device_uuid"] is None
    assert payload["runtime_mode"] == "standalone"
