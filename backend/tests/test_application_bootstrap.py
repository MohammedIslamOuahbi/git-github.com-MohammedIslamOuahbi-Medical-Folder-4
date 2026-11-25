from __future__ import annotations

import json

from sqlalchemy.orm import sessionmaker

from app.services.application_seed_service import ApplicationBootstrapError, ApplicationSeedService


def test_cli_application_bootstrap_returns_structured_json_on_success(db_session, monkeypatch, capsys):
    import app.database
    import run_tauri_sidecar

    session_factory = sessionmaker(
        bind=db_session.connection(),
        autoflush=False,
        autocommit=False,
        future=True,
    )

    monkeypatch.setattr(run_tauri_sidecar, "run_alembic_upgrade", lambda: 0)
    monkeypatch.setattr(app.database, "SessionLocal", session_factory)
    monkeypatch.setenv("INITIAL_ADMIN_FIRST_NAME", "Init")
    monkeypatch.setenv("INITIAL_ADMIN_LAST_NAME", "Admin")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "cli.admin@example.test")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "SecurePass123")
    monkeypatch.setenv("INITIAL_ADMIN_PHONE", "")
    monkeypatch.setenv("INITIAL_ADMIN_QUALIFICATION", "")

    exit_code = run_tauri_sidecar.run_application_bootstrap()
    output = capsys.readouterr()
    payload = json.loads(output.out.strip().splitlines()[-1])

    assert exit_code == 0
    assert payload["success"] is True
    assert payload["created_user_email"] == "cli.admin@example.test"


def test_cli_application_bootstrap_returns_structured_json_on_failure(db_session, monkeypatch, capsys):
    import app.database
    import run_tauri_sidecar

    session_factory = sessionmaker(
        bind=db_session.connection(),
        autoflush=False,
        autocommit=False,
        future=True,
    )

    def fail_initialize(self, db, initial_user):  # noqa: ARG001
        raise ApplicationBootstrapError(
            code="INITIAL_REFERENCE_DATA_FAILED",
            stage="medical_tests",
            message="Initial reference data creation failed.",
            error_type="RuntimeError",
            sqlstate=None,
        ) from RuntimeError("simulated chained failure")

    monkeypatch.setattr(run_tauri_sidecar, "run_alembic_upgrade", lambda: 0)
    monkeypatch.setattr(app.database, "SessionLocal", session_factory)
    monkeypatch.setattr(ApplicationSeedService, "initialize_application", fail_initialize)
    monkeypatch.setenv("INITIAL_ADMIN_FIRST_NAME", "Init")
    monkeypatch.setenv("INITIAL_ADMIN_LAST_NAME", "Admin")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "cli.admin@example.test")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "SecurePass123")

    exit_code = run_tauri_sidecar.run_application_bootstrap()
    output = capsys.readouterr()
    payload = json.loads(output.out.strip().splitlines()[-1])

    assert exit_code == 1
    assert payload["success"] is False
    assert payload["code"] == "INITIAL_REFERENCE_DATA_FAILED"
    assert payload["stage"] == "medical_tests"
    assert "simulated chained failure" in output.err
