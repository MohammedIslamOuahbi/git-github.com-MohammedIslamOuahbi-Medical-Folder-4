from __future__ import annotations

import uuid

from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.company import Company
from app.models.drilling_site import DrillingSite
from app.models.runtime_config import RuntimeConfig
from app.services.auth_service import AuthService


def _login(client, email: str, password: str, device_uuid: uuid.UUID) -> tuple[dict[str, str], dict[str, str]]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    tokens = response.json()["data"]
    return (
        {"Authorization": f"Bearer {tokens['access_token']}", "X-Device-UUID": str(device_uuid)},
        tokens,
    )


def _seed_worker_prerequisites(db_session):
    company = Company(name="V2 Acceptance Company")
    branch = Branch(company=company, name="V2 Acceptance Branch")
    site = DrillingSite(company=company, branch=branch, name="V2 Acceptance Site", location="HQ", status="active")
    db_session.add_all([company, branch, site])
    db_session.flush()
    return company, branch, site


def _reset_connection_mode(db_session) -> None:
    runtime = db_session.get(RuntimeConfig, 1)
    if runtime is None:
        return
    runtime.connection_mode = None
    runtime.connection_configured = False
    runtime.connection_verified = False
    runtime.connection_requires_setup = True
    runtime.connection_server_url = None
    db_session.commit()


def test_server_pc_acceptance_enforces_api_policy_and_keeps_medical_workflow(client, db_session):
    admin = AuthService().create_platform_user(
        db_session,
        "V2",
        "Administrator",
        "v2-acceptance@ibnsina-clinic.com",
        "admin12345",
        role="super_admin",
    )
    device_uuid = uuid.uuid4()
    headers, tokens = _login(client, admin.email, "admin12345", device_uuid)

    # Setup is authenticated: an unconfigured caller cannot set server identity.
    assert client.put("/api/v1/runtime/connection-mode", json={"connection_mode": "SERVER_PC"}).status_code == 401

    configured = client.put(
        "/api/v1/runtime/connection-mode",
        json={"connection_mode": "SERVER_PC", "connection_verified": True},
        headers=headers,
    )
    assert configured.status_code == 200
    assert configured.json()["data"]["connection_mode"] == "SERVER_PC"
    assert configured.json()["data"]["connection_requires_setup"] is False

    runtime_status = client.get("/api/v1/runtime/status", headers=headers)
    assert runtime_status.status_code == 200
    assert runtime_status.json()["data"]["connection_mode"] == "SERVER_PC"
    assert runtime_status.json()["data"]["connection_verified"] is True

    # The backend, not React, rejects global user administration in SERVER_PC.
    assert client.get("/api/v1/users", headers=headers).status_code == 403

    company, branch, site = _seed_worker_prerequisites(db_session)
    worker_response = client.post(
        "/api/v1/workers",
        headers=headers,
        json={
            "company_id": company.id,
            "branch_id": branch.id,
            "drilling_site_id": site.id,
            "employee_number": "V2-001",
            "national_id": "990000000000000001",
            "first_name": "V2",
            "last_name": "Worker",
            "gender": "F",
            "birth_date": "1992-01-01",
        },
    )
    assert worker_response.status_code == 201
    worker_id = worker_response.json()["data"]["id"]

    audit = db_session.query(AuditLog).filter(AuditLog.entity_type == "worker", AuditLog.entity_id == worker_id).one()
    assert audit.worker_id == worker_id
    assert audit.device_uuid == device_uuid

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200

    server_mode = client.put(
        "/api/v1/runtime/connection-mode",
        json={"connection_mode": "SERVER", "connection_verified": True},
        headers=headers,
    )
    assert server_mode.status_code == 200
    assert client.get("/api/v1/users", headers=headers).status_code == 200

    _reset_connection_mode(db_session)
