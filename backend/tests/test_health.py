from __future__ import annotations

from app.main import health_database


def test_database_health_response_is_sanitized(client):
    response = client.get("/health/database")

    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    serialized = str(payload).lower()

    assert data["database_engine"] == "PostgreSQL"
    assert data["database_status"] in {"connected", "disconnected"}
    assert "password" not in serialized
    assert "database_url" not in serialized


def test_database_health_handles_database_failure(monkeypatch):
    class BrokenPool:
        def checkedout(self):
            return 0

        def size(self):
            return 0

    class BrokenEngine:
        pool = BrokenPool()

        def connect(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.main.engine", BrokenEngine())

    payload = health_database()

    assert payload["data"]["status"] == "error"
    assert payload["data"]["database_status"] == "disconnected"
    assert "database unavailable" not in str(payload).lower()


def test_server_identity_is_public_and_sanitized(client):
    response = client.get("/health/identity")

    assert response.status_code == 200
    data = response.json()["data"]
    serialized = str(data).lower()

    assert data["application"] == "medical-folder"
    assert data["api_status"] == "online"
    assert data["database_engine"] == "PostgreSQL"
    assert data["server_id"]
    assert "database_url" not in serialized
    assert "password" not in serialized


def test_network_info_health_endpoint_returns_hostname_and_ip(client):
    response = client.get("/health/network-info")

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["status"] == "ok"
    assert data["hostname"]
    assert data["local_ip_address"]
    assert data["api_base_url"]
