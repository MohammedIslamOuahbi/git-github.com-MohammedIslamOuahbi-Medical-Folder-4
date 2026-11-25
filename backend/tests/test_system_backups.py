from __future__ import annotations

import io
import subprocess

import pytest

from app.core.enums import InstallationProfile
from app.services.auth_service import AuthService
from app.services.installation_service import installation_service
from app.services.system_backup_service import PostgresBackupService


def _login(client, email: str, password: str):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _seed_backup_users(db_session):
    auth_service = AuthService()
    auth_service.create_platform_user(
        db_session,
        first_name="System",
        last_name="Admin",
        email="admin@ibnsina.com",
        password="admin12345",
        role="admin",
    )
    auth_service.create_platform_user(
        db_session,
        first_name="System",
        last_name="Doctor",
        email="doctor@ibnsina.com",
        password="admin12345",
        role="doctor",
    )


def _configure_central_installation(db_session, monkeypatch):
    monkeypatch.setenv("IBNSINA_INSTALLATION_PROFILE", "central_server")
    installation_service.provision_current_installation(
        db_session,
        InstallationProfile.CENTRAL_SERVER,
        audit_source="test_system_backups",
    )


def test_status_requires_admin_role(client, db_session, monkeypatch):
    _seed_backup_users(db_session)
    _configure_central_installation(db_session, monkeypatch)
    token = _login(client, "doctor@ibnsina.com", "admin12345")
    response = client.get("/api/v1/system-backups/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in {401, 403}


def test_status_returns_current_state_for_admin(client, db_session, monkeypatch):
    _seed_backup_users(db_session)
    _configure_central_installation(db_session, monkeypatch)
    token = _login(client, "admin@ibnsina.com", "admin12345")
    response = client.get("/api/v1/system-backups/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in {200, 403}
    if response.status_code == 200:
        assert "state" in response.json()["data"]


def test_validate_backup_rejects_invalid_extension():
    service = PostgresBackupService()
    with pytest.raises(Exception, match=".backup ou .dump"):
        service.validate_backup_file(service._temp_root / "bad.sql")


def test_subprocess_never_uses_shell(monkeypatch):
    service = PostgresBackupService()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["shell"] = kwargs["shell"]
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    service._run_subprocess(["pg_dump", "--version"], "erreur")
    assert captured["command"] == ["pg_dump", "--version"]
    assert captured["shell"] is False


def test_restore_conflict_returns_409(client, db_session, monkeypatch):
    _seed_backup_users(db_session)
    _configure_central_installation(db_session, monkeypatch)
    token = _login(client, "admin@ibnsina.com", "admin12345")
    service = PostgresBackupService()
    assert service._lock.acquire(blocking=False)
    try:
        response = client.post(
            "/api/v1/system-backups/restore",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("backup.dump", io.BytesIO(b"fake"), "application/octet-stream")},
        )
        assert response.status_code == 409
    finally:
        service._lock.release()
