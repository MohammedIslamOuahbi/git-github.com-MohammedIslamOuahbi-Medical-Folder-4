from __future__ import annotations

import pytest
from fastapi.routing import APIRoute


def test_bootstrap_status_requires_initial_setup_when_no_users(client, db_session):
    response = client.get("/api/v1/bootstrap/status")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["has_users"] is False
    assert payload["requires_initial_setup"] is True


def test_application_seed_service_creates_first_super_admin_and_reference_data(db_session):
    from app.models.permission import Permission
    from app.models.user import User
    from app.services.application_seed_service import ApplicationSeedService, InitialUserPayload

    result = ApplicationSeedService().initialize_application(
        db_session,
        InitialUserPayload(
            first_name="Init",
            last_name="Admin",
            email="init.admin@example.test",
            password="SecurePass123",
            phone="+213000000000",
            qualification="Medecin",
        ),
    )

    user = db_session.query(User).filter(User.email == "init.admin@example.test").one()
    assert user.role == "super_admin"
    assert user.password_hash != "SecurePass123"
    assert result["initialization_completed"] is True
    assert db_session.query(Permission).count() > 0


def test_application_seed_service_is_idempotent_for_reference_data(db_session):
    from app.models.medical_test import MedicalTest
    from app.models.permission import Permission
    from app.services.application_seed_service import ApplicationSeedService

    service = ApplicationSeedService()
    service.ensure_reference_data(db_session)
    first_permission_count = db_session.query(Permission).count()
    first_test_count = db_session.query(MedicalTest).count()

    service.ensure_reference_data(db_session)

    assert db_session.query(Permission).count() == first_permission_count
    assert db_session.query(MedicalTest).count() == first_test_count


def test_application_seed_service_handles_second_first_user_creation_idempotently(db_session):
    from app.services.application_seed_service import ApplicationSeedService, InitialUserPayload

    service = ApplicationSeedService()
    service.initialize_application(
        db_session,
        InitialUserPayload(
            first_name="Init",
            last_name="Admin",
            email="init.admin@example.test",
            password="SecurePass123",
        ),
    )

    result = service.initialize_application(
        db_session,
        InitialUserPayload(
            first_name="Other",
            last_name="Admin",
            email="other.admin@example.test",
            password="SecurePass456",
        ),
    )

    assert result["success"] is True
    assert result["has_super_admin"] is True


def test_fastapi_startup_does_not_register_schema_or_seed_hooks() -> None:
    from app.main import app

    assert app.router.on_startup == []
    assert any(isinstance(route, APIRoute) and route.path == "/api/v1/bootstrap/status" for route in app.router.routes)
