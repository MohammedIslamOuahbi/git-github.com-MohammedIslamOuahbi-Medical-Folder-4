from __future__ import annotations

import pytest


def _login(client, db_session):
    from app.services.auth_service import AuthService

    AuthService().create_admin_user(
        db_session,
        first_name="Sync",
        last_name="Admin",
        email="sync-admin@ibnsina-clinic.com",
        password="admin12345",
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "sync-admin@ibnsina-clinic.com", "password": "admin12345"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_client_sync_requires_authentication(client):
    response = client.get("/api/v1/client-sync/export")
    assert response.status_code == 401


def test_client_sync_export_is_sanitized_and_checksummed(client, db_session):
    from app.models.company import Company

    token = _login(client, db_session)
    db_session.add(Company(name="Desert Clinic", email="contact@example.test"))
    db_session.commit()

    response = client.get(
        "/api/v1/client-sync/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["server_id"]
    assert payload["schema_version"] == 1
    assert payload["mode"] == "SERVER_TO_CLIENT_ONLY"
    assert payload["source_of_truth"] == "SERVER_POSTGRESQL"
    assert payload["target_model"] == "LOCAL_SYNCHRONIZED_COPY"
    assert payload["checksum_sha256"]
    assert "companies" in payload["data"]

    users = payload["data"]["users"]
    assert users
    assert "password_hash" not in users[0]
    assert "workspace_password_hash" not in str(payload)
    assert "DATABASE_URL" not in str(payload)
    assert "SECRET_KEY" not in str(payload)


def test_client_sync_cursor_filters_older_rows(client, db_session):
    from app.models.company import Company

    token = _login(client, db_session)
    db_session.add(Company(name="Cursor One"))
    db_session.commit()

    first = client.get("/api/v1/client-sync/export", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    assert first["to_cursor"] > 0

    second = client.get(
        f"/api/v1/client-sync/export?after_cursor={first['to_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]

    assert second["from_cursor"] == first["to_cursor"]
    assert sum(second["record_counts"].values()) == 0


def test_client_sync_durable_cursor_increases_across_entity_types(client, db_session):
    from app.models.client_sync_change import ClientSyncChange
    from app.models.company import Company
    from app.models.medical_test import MedicalTest

    token = _login(client, db_session)
    db_session.add(Company(name="Journal Company"))
    db_session.commit()
    first_cursor = db_session.query(ClientSyncChange).order_by(ClientSyncChange.id.desc()).first().id

    db_session.add(MedicalTest(name="Journal Test", section="General"))
    db_session.commit()
    second_cursor = db_session.query(ClientSyncChange).order_by(ClientSyncChange.id.desc()).first().id

    assert second_cursor > first_cursor
    response = client.get(
        f"/api/v1/client-sync/export?after_cursor={first_cursor}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["from_cursor"] == first_cursor
    assert payload["to_cursor"] >= second_cursor
    assert payload["record_counts"]["medical_tests"] == 1


def test_client_sync_rejects_future_cursor(client, db_session):
    token = _login(client, db_session)
    response = client.get(
        "/api/v1/client-sync/export?after_cursor=999999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_client_sync_soft_delete_exports_tombstone(client, db_session):
    from datetime import datetime, timezone

    from app.models.company import Company

    token = _login(client, db_session)
    company = Company(name="Delete Tombstone")
    db_session.add(company)
    db_session.commit()

    first = client.get("/api/v1/client-sync/export", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    company.deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    response = client.get(
        f"/api/v1/client-sync/export?after_cursor={first['to_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert any(
        tombstone["entity_type"] == "companies" and str(tombstone["entity_id"]) == str(company.uuid)
        for tombstone in payload["tombstones"]
    )


def test_client_sync_import_service_commits_cursor_metadata(client, db_session, tmp_path):
    import json

    from app.models.client_local_sync import ClientLocalSyncState
    from app.models.company import Company
    from app.services.client_sync_import_service import ClientSyncImportService

    token = _login(client, db_session)
    db_session.add(Company(name="Import Cursor"))
    db_session.commit()

    package = client.get("/api/v1/client-sync/export", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    package_path = tmp_path / "client-sync-package.json"
    package_path.write_text(json.dumps(package, default=str), encoding="utf-8")

    result = ClientSyncImportService().import_package(db_session, package_path)
    state = db_session.get(ClientLocalSyncState, 1)

    assert result["success"] is True
    assert result["to_cursor"] == package["to_cursor"]
    assert state is not None
    assert state.server_id == package["server_id"]
    assert state.last_sync_cursor == package["to_cursor"]


def test_client_sync_import_rejects_duplicate_package(client, db_session, tmp_path):
    import json

    from app.services.client_sync_import_service import ClientSyncImportService

    token = _login(client, db_session)
    package = client.get("/api/v1/client-sync/export", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    package_path = tmp_path / "medical_sync_2026-07-14_15-20-33.sync"
    package_path.write_text(json.dumps(package, default=str), encoding="utf-8")

    service = ClientSyncImportService()
    assert service.import_package(db_session, package_path)["success"] is True

    with pytest.raises(ValueError, match="SYNC_ALREADY_IMPORTED"):
        service.import_package(db_session, package_path)


def test_client_sync_import_rejects_checksum_mismatch(client, db_session, tmp_path):
    import json

    from app.services.client_sync_import_service import ClientSyncImportService

    token = _login(client, db_session)
    package = client.get("/api/v1/client-sync/export", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    package["data"]["companies"].append({"id": 999999, "name": "Tampered"})
    package_path = tmp_path / "medical_sync_tampered.sync"
    package_path.write_text(json.dumps(package, default=str), encoding="utf-8")

    with pytest.raises(ValueError, match="SYNC_CHECKSUM_FAILED"):
        ClientSyncImportService().import_package(db_session, package_path)


def test_client_sync_import_upserts_by_uuid(client, db_session, tmp_path):
    import json

    from app.models.company import Company
    from app.services.client_sync_import_service import ClientSyncImportService

    token = _login(client, db_session)
    server_company = Company(name="Server Canonical Name")
    db_session.add(server_company)
    db_session.commit()

    package = client.get("/api/v1/client-sync/export", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    package_company = next(row for row in package["data"]["companies"] if str(row["uuid"]) == str(server_company.uuid))

    local_company = db_session.get(Company, server_company.id)
    local_company.name = "Local Divergent Name"
    local_company.email = "local@example.test"
    db_session.commit()

    package_path = tmp_path / "medical_sync_uuid_upsert.sync"
    package_path.write_text(json.dumps(package, default=str), encoding="utf-8")

    result = ClientSyncImportService().import_package(db_session, package_path)
    db_session.refresh(local_company)

    assert result["success"] is True
    assert local_company.id == package_company["id"]
    assert local_company.uuid == server_company.uuid
    assert local_company.name == "Server Canonical Name"
