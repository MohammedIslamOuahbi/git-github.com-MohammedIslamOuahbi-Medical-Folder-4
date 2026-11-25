from __future__ import annotations

from sqlalchemy import func, select

from app.models.application_initialization import ApplicationInitialization
from app.models.medical_test import MedicalTest
from app.models.permission import Permission
from app.models.user import User
from app.services.application_seed_service import (
    ApplicationBootstrapError,
    ApplicationSeedService,
    InitialUserPayload,
)


def _payload(email: str = "init.admin@example.test") -> InitialUserPayload:
    return InitialUserPayload(
        first_name="Init",
        last_name="Admin",
        email=email,
        password="SecurePass123",
        phone="+213000000000",
        qualification="Medecin",
    )


def test_fresh_database_bootstrap_succeeds_with_autoflush_disabled(db_session):
    result = ApplicationSeedService().initialize_application(db_session, _payload())

    assert result["success"] is True
    assert result["initialization_completed"] is True
    assert result["has_super_admin"] is True
    assert result["reference_data_seeded"] is True
    assert any(stage["stage"] == "medical_tests" for stage in result["stages"])


def test_second_bootstrap_is_idempotent(db_session):
    service = ApplicationSeedService()

    first = service.initialize_application(db_session, _payload())
    first_users = db_session.scalar(select(func.count(User.id))) or 0
    first_permissions = db_session.scalar(select(func.count(Permission.id))) or 0
    first_tests = db_session.scalar(select(func.count(MedicalTest.id))) or 0

    second = service.initialize_application(db_session, _payload())

    assert second["success"] is True
    assert second["already_initialized"] is True
    assert (db_session.scalar(select(func.count(User.id))) or 0) == first_users
    assert (db_session.scalar(select(func.count(Permission.id))) or 0) == first_permissions
    assert (db_session.scalar(select(func.count(MedicalTest.id))) or 0) == first_tests


def test_existing_initial_user_is_not_duplicated(db_session):
    service = ApplicationSeedService()
    service.initialize_application(db_session, _payload())

    result = service.initialize_application(db_session, _payload())

    assert result["success"] is True
    assert (db_session.scalar(select(func.count(User.id))) or 0) == 1


def test_seeded_sync_metadata_is_populated(db_session):
    ApplicationSeedService().initialize_application(db_session, _payload())

    null_users = db_session.scalar(
        select(func.count(User.id)).where(
            User.uuid.is_(None) | User.sync_status.is_(None) | User.sync_version.is_(None)
        )
    ) or 0
    null_permissions = db_session.scalar(
        select(func.count(Permission.id)).where(
            Permission.uuid.is_(None) | Permission.sync_version.is_(None)
        )
    ) or 0
    null_medical_tests = db_session.scalar(
        select(func.count(MedicalTest.id)).where(
            MedicalTest.uuid.is_(None) | MedicalTest.sync_status.is_(None) | MedicalTest.sync_version.is_(None)
        )
    ) or 0

    assert null_users == 0
    assert null_permissions == 0
    assert null_medical_tests == 0


def test_bootstrap_failure_keeps_original_exception_chain_and_rolls_back(db_session, monkeypatch):
    service = ApplicationSeedService()

    def explode(_db):
        raise RuntimeError("simulated medical test failure")

    monkeypatch.setattr(service, "_seed_medical_tests", explode)

    try:
        service.initialize_application(db_session, _payload())
    except ApplicationBootstrapError as exc:
        assert exc.code == "INITIAL_REFERENCE_DATA_FAILED"
        assert exc.stage == "medical_tests"
        assert isinstance(exc.__cause__, RuntimeError)
        assert "simulated medical test failure" in str(exc.__cause__)
    else:
        raise AssertionError("ApplicationBootstrapError was expected")

    assert (db_session.scalar(select(func.count(User.id))) or 0) == 0
    assert (db_session.scalar(select(func.count(Permission.id))) or 0) == 0
    assert (db_session.scalar(select(func.count(MedicalTest.id))) or 0) == 0
    state = db_session.get(ApplicationInitialization, 1)
    assert state is not None
    assert state.initialization_status == "FAILED"
