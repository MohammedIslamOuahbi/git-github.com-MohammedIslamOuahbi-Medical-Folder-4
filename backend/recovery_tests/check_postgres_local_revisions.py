"""Stage-three PostgreSQL check, synthetic medical visit only, exact-target gate."""
from __future__ import annotations

import sys
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.database import STAGE3_GUARDED_TABLES
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.exceptions import ConflictException, ServiceUnavailableException
from app.middleware.error_handler import http_exception_handler
from app.models.local_revision import LocalEditAttempt, LocalRevision, LocalWriteOperation
from app.models.medical_visit import MedicalVisit
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.sync_change import SyncChange
from app.routers.medical_visits import get_edit_attempt, router as visits_router
from app.routers.workers import get_own_worker_edit_attempt, router as workers_router
from app.routers.companies import router as companies_router
from app.schemas.medical_visit import MedicalVisitStatusUpdate, MedicalVisitCreate
from app.services.medical_visit_service import MedicalVisitService
from app.services.local_revision_baseline import baseline_batch
from app.services.protected_visit_write import apply_visit_update
from app.services.protected_worker_write import apply_worker_update
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerCreate
from app.services.sync_journal import register_sync_journal
from app.sync.registry import SYNC_ENTITY_REGISTRY


def run():
    url = make_url(settings.database_url)
    if not (url.drivername == "postgresql+psycopg" and url.host in {"localhost", "127.0.0.1"}
            and url.database == "ibn_sina_recovery_test" and (url.port or 5432) == 5432):
        raise RuntimeError("UNAUTHORIZED_TEST_DATABASE")
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
    with engine.connect() as c:
        observed = c.execute(text("SELECT current_database(),current_schema(),inet_server_port()")) .one()
        assert observed == ("ibn_sina_recovery_test", "public", 5432)
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == "20261008_04"
    register_sync_journal()
    assert STAGE3_GUARDED_TABLES == frozenset(SYNC_ENTITY_REGISTRY)
    user = SimpleNamespace(uuid=uuid.uuid4(), id=None, role="doctor", is_active=True)
    other = SimpleNamespace(uuid=uuid.uuid4(), id=None, role="doctor", is_active=True)
    service = MedicalVisitService()
    visit_uuid = uuid.uuid4()
    legacy_visit_uuid = uuid.uuid4()
    deleted_legacy_uuid = uuid.uuid4()
    created_visit_uuid = None
    company_uuid, branch_uuid, worker_uuid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    created_worker_uuid = None
    operation_uuids: set[uuid.UUID] = set()
    attempt_uuids: set[uuid.UUID] = set()

    def event_count(s):
        return s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == visit_uuid))

    try:
        for entity_type, config in SYNC_ENTITY_REGISTRY.items():
            with Session(engine) as s:
                s.add(config.model())
                try:
                    s.flush()
                except HTTPException as exc:
                    assert exc.status_code == 423
                    assert exc.detail["details"]["operation"] == f"unprotected_syncable_write:{entity_type}"
                    assert exc.detail["details"]["retryable"] is False
                    s.rollback()
                else:
                    raise AssertionError(f"unprotected {entity_type} write was accepted")
        print(f"PASS fail-closed ORM guard covers all {len(SYNC_ENTITY_REGISTRY)} registered sync entities")

        with Session(engine) as s:
            s.info["sync_bootstrap_mode"] = True
            s.add(MedicalVisit(uuid=legacy_visit_uuid, visit_date="2026-10-07", status="draft",
                               form_data={"synthetic": True}, version=1))
            s.commit()
        with Session(engine) as s:
            first_count, _ = baseline_batch(s, "medical_visits", limit=100)
            assert first_count == 1
        with Session(engine) as s:
            second_count, _ = baseline_batch(s, "medical_visits", limit=100)
            assert second_count == 1
            revisions = s.scalars(select(LocalRevision).where(LocalRevision.entity_uuid == legacy_visit_uuid)).all()
            assert len(revisions) == 1 and revisions[0].kind == "baseline" and revisions[0].parent_revision_uuid is None
            assert s.scalar(select(MedicalVisit.form_data).where(MedicalVisit.uuid == legacy_visit_uuid)) == {"synthetic": True}
            assert event_count(s) == 0
        print("PASS resumable, idempotent baseline without invented event or medical change")
        with Session(engine) as s:
            legacy = s.scalar(select(MedicalVisit).where(MedicalVisit.uuid == legacy_visit_uuid))
            legacy.status = "tests_in_progress"
            try:
                s.commit()
            except HTTPException as exc:
                assert exc.status_code == 423
                s.rollback()
            else:
                raise AssertionError("unprotected ORM update was accepted")
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == legacy_visit_uuid)) == 0
            revisions = s.scalars(select(LocalRevision).where(LocalRevision.entity_uuid == legacy_visit_uuid)
                                  .order_by(LocalRevision.local_version)).all()
            assert len(revisions) == 1
            assert s.scalar(select(MedicalVisit.status).where(MedicalVisit.uuid == legacy_visit_uuid)) == "draft"
        print("PASS unprotected ORM update is suspended before data/event changes")
        with Session(engine) as s:
            s.info["sync_bootstrap_mode"] = True
            s.add(MedicalVisit(uuid=deleted_legacy_uuid, visit_date="2026-10-07", status="draft", version=1))
            s.commit()
        with Session(engine) as s:
            doomed = s.scalar(select(MedicalVisit).where(MedicalVisit.uuid == deleted_legacy_uuid))
            s.delete(doomed)
            try:
                s.commit()
            except HTTPException as exc:
                assert exc.status_code == 423
                s.rollback()
            else:
                raise AssertionError("unprotected ORM delete was accepted")
        with Session(engine) as s:
            revisions = s.scalars(select(LocalRevision).where(LocalRevision.entity_uuid == deleted_legacy_uuid)
                                  .order_by(LocalRevision.local_version)).all()
            assert revisions == []
            assert s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == deleted_legacy_uuid)) == 0
            assert s.scalar(select(func.count()).select_from(MedicalVisit).where(MedicalVisit.uuid == deleted_legacy_uuid)) == 1
        print("PASS unprotected ORM delete is suspended without deleting the record")

        create_operation = uuid.uuid4(); operation_uuids.add(create_operation)
        create_payload = MedicalVisitCreate(visit_date="2026-10-07", status="draft", form_data={})
        with Session(engine) as s:
            created = service.create(s, create_payload, user, create_operation)
            created_visit_uuid = created.uuid
        with Session(engine) as s:
            replayed = service.create(s, create_payload, user, create_operation)
            assert replayed.id == created.id
            assert s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == created_visit_uuid)) == 1
            assert s.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid == created_visit_uuid)) == 1
        print("PASS created visit and event/revision/receipt commit once; retry returns same visit")

        guarded_create_operation = uuid.uuid4(); operation_uuids.add(guarded_create_operation)
        with Session(engine) as s:
            visit_result = service.create(s, MedicalVisitCreate(
                visit_date="2026-10-07", status="draft",
                form_data={"synthetic": True}), user, guarded_create_operation)
            visit_uuid = visit_result.uuid
            visit_id = visit_result.id
            assert event_count(s) == 1
            assert s.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid == visit_uuid)) == 1
        print("PASS protected ORM creation, revision, receipt and reused SyncChange committed together")

        barrier = threading.Barrier(2)
        results, conflicts, errors = [], [], []

        def competing(status):
            operation_uuid = uuid.uuid4()
            operation_uuids.add(operation_uuid)
            try:
                with Session(engine) as s:
                    s.get(MedicalVisit, visit_id)
                    barrier.wait(timeout=10)
                    result = service.update_status(s, visit_id, MedicalVisitStatusUpdate(status=status), user,
                                                   1, operation_uuid)
                    results.append((operation_uuid, result))
            except ConflictException as exc:
                conflicts.append((operation_uuid, exc))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=competing, args=(status,)) for status in ("tests_in_progress", "ready_for_doctor")]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        assert all(not thread.is_alive() for thread in threads) and not errors, errors
        assert len(results) == 1 and len(conflicts) == 1
        stale_uuid, conflict = conflicts[0]
        attempt_uuids.add(stale_uuid)
        assert conflict.detail["message"] == "EXPECTED_VERSION_CONFLICT"
        with Session(engine) as s:
            assert s.get(MedicalVisit, visit_id).version == 2
            assert s.get(LocalEditAttempt, stale_uuid).attempted_payload["status"] in {"tests_in_progress", "ready_for_doctor"}
            assert event_count(s) == 2
            stale_status = s.get(LocalEditAttempt, stale_uuid).attempted_payload["status"]
            try:
                service.update_status(s, visit_id, MedicalVisitStatusUpdate(status=stale_status), user, 1, stale_uuid)
            except ConflictException as exc:
                assert exc.detail["message"] == "EXPECTED_VERSION_CONFLICT"
            else:
                raise AssertionError("retry of rejected operation was applied")
            try:
                service.update_status(s, visit_id, MedicalVisitStatusUpdate(status="different"), user, 1, stale_uuid)
            except ConflictException as exc:
                assert exc.detail["message"] == "OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT"
            else:
                raise AssertionError("attempt UUID accepted changed content")
        print("PASS two-session CAS: one update, one durable rejected attempt")

        success_uuid, successful = results[0]
        with Session(engine) as s:
            again = service.update_status(s, visit_id, MedicalVisitStatusUpdate(status=successful.status), user, 1, success_uuid)
            assert again.version == successful.version
            assert s.get(MedicalVisit, visit_id).version == 2 and event_count(s) == 2
            try:
                service.update_status(s, visit_id, MedicalVisitStatusUpdate(status="different"), user, 1, success_uuid)
            except ConflictException as exc:
                assert exc.detail["message"] == "OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT"
            else:
                raise AssertionError("reused operation with changed content succeeded")
        print("PASS lost-response retry and operation UUID content mismatch")

        failed_attempt_uuid = uuid.uuid4(); attempt_uuids.add(failed_attempt_uuid)
        def fail_attempt(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().startswith("INSERT INTO local_edit_attempts"):
                raise RuntimeError("synthetic attempt storage failure")
        event.listen(engine, "before_cursor_execute", fail_attempt)
        try:
            with Session(engine) as s:
                try:
                    service.update_status(s, visit_id, MedicalVisitStatusUpdate(status="draft"), user, 1, failed_attempt_uuid)
                except ServiceUnavailableException as exc:
                    assert exc.detail["message"] == "EDIT_ATTEMPT_NOT_SAVED"
                else:
                    raise AssertionError("attempt persistence failure was reported as saved")
        finally:
            event.remove(engine, "before_cursor_execute", fail_attempt)
        with Session(engine) as s:
            assert s.get(LocalEditAttempt, failed_attempt_uuid) is None
            assert s.get(MedicalVisit, visit_id).version == 2
        print("PASS failed attempt commit is never reported as preserved")

        def injected_failure(target):
            operation_uuid = uuid.uuid4()
            operation_uuids.add(operation_uuid)
            current_version = 2
            def fail(_conn, _cursor, statement, _params, _context, _many):
                if statement.lstrip().startswith("INSERT INTO " + target):
                    raise RuntimeError("synthetic " + target + " failure")
            event.listen(engine, "before_cursor_execute", fail)
            try:
                with Session(engine) as s:
                    visit = s.get(MedicalVisit, visit_id)
                    try:
                        apply_visit_update(s, user, visit, action="update", expected_version=current_version,
                                           operation_uuid=operation_uuid, attempted_payload={"doctor_notes": target},
                                           values={"doctor_notes": target})
                    except RuntimeError as exc:
                        assert str(exc) == "synthetic " + target + " failure"
                    else:
                        raise AssertionError("injected failure did not happen")
            finally:
                event.remove(engine, "before_cursor_execute", fail)
            with Session(engine) as s:
                assert s.get(MedicalVisit, visit_id).version == current_version
                assert s.get(MedicalVisit, visit_id).doctor_notes is None
                assert s.get(LocalWriteOperation, operation_uuid) is None
                assert event_count(s) == 2

        injected_failure("local_revisions")
        injected_failure("sync_changes")
        print("PASS revision and event failures each roll back medical update")

        # A status change racing another edit is covered by the same conditional version.
        with Session(engine) as s:
            op = uuid.uuid4(); operation_uuids.add(op)
            visit = s.get(MedicalVisit, visit_id)
            signed = apply_visit_update(s, user, visit, action="validate", expected_version=2,
                                        operation_uuid=op, attempted_payload={"status": "validated"},
                                        values={"status": "validated", "validated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
            assert signed.version == 3
        with Session(engine) as s:
            op = uuid.uuid4(); operation_uuids.add(op)
            try:
                service.update_status(s, visit_id, MedicalVisitStatusUpdate(status="draft"), user, 3, op)
            except ConflictException as exc:
                assert exc.detail["message"] == "SIGNED_DOCUMENT_IMMUTABLE"
            else:
                raise AssertionError("signed visit changed")
            assert s.get(MedicalVisit, visit_id).status == "validated"
        print("PASS validated document remains unchanged")

        with Session(engine) as s:
            s.info["sync_bootstrap_mode"] = True
            company = Company(uuid=company_uuid, name="synthetic-stage-three-" + uuid.uuid4().hex)
            s.add(company); s.flush()
            branch = Branch(uuid=branch_uuid, company_id=company.id, name="synthetic-branch")
            s.add(branch); s.flush()
            worker = Worker(uuid=worker_uuid, company_id=company.id, branch_id=branch.id,
                            employee_number="synthetic-" + uuid.uuid4().hex, first_name="Synthetic",
                            last_name="Worker", medical_file_data={"note": "synthetic"})
            s.add(worker); s.commit()
            worker_id = worker.id
            company_id, branch_id = company.id, branch.id
        worker_create_operation = uuid.uuid4(); operation_uuids.add(worker_create_operation)
        worker_create_payload = WorkerCreate(company_id=company_id, branch_id=branch_id,
                                             employee_number="synthetic-created-" + uuid.uuid4().hex,
                                             first_name="Synthetic", last_name="Created")
        with Session(engine) as s:
            created_worker = WorkerService().create(s, worker_create_payload, user, worker_create_operation)
            created_worker_uuid = created_worker.uuid
        with Session(engine) as s:
            replayed_worker = WorkerService().create(s, worker_create_payload, user, worker_create_operation)
            assert replayed_worker.id == created_worker.id
            assert s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == created_worker_uuid)) == 1
        print("PASS worker create and lost-response retry commit only once")
        worker_barrier = threading.Barrier(2)
        worker_results, worker_conflicts, worker_errors = [], [], []
        def worker_race(action):
            op = uuid.uuid4(); operation_uuids.add(op)
            try:
                with Session(engine) as s:
                    row = s.get(Worker, created_worker.id)
                    worker_barrier.wait(timeout=10)
                    values = ({"deleted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                               "is_active": False} if action == "delete" else {"medical_file_data": {"note": "racing edit"}})
                    apply_worker_update(s, user, row, action=action, expected_version=1,
                                        operation_uuid=op, attempted_payload={"action": action}, values=values)
                    worker_results.append(op)
            except ConflictException:
                attempt_uuids.add(op)
                worker_conflicts.append(op)
            except Exception as exc:
                worker_errors.append(exc)
        threads = [threading.Thread(target=worker_race, args=(action,)) for action in ("update", "delete")]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        assert all(not thread.is_alive() for thread in threads) and not worker_errors, worker_errors
        assert len(worker_results) == 1 and len(worker_conflicts) == 1
        with Session(engine) as s:
            assert s.get(Worker, created_worker.id).sync_version == 2
            assert s.get(LocalEditAttempt, worker_conflicts[0]) is not None
            assert s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == created_worker_uuid)) == 2
        print("PASS simultaneous worker edit versus soft delete: one commit, one recoverable attempt")
        with Session(engine) as s:
            assert s.get(Worker, worker_id).sync_version == 1
            worker_operation = uuid.uuid4(); operation_uuids.add(worker_operation)
            changed = apply_worker_update(s, user, s.get(Worker, worker_id), action="update",
                                          expected_version=1, operation_uuid=worker_operation,
                                          attempted_payload={"medical_file_data": {"note": "changed"}},
                                          values={"medical_file_data": {"note": "changed"}})
            assert changed.sync_version == 2
        with Session(engine) as s:
            again = apply_worker_update(s, user, s.get(Worker, worker_id), action="update",
                                        expected_version=1, operation_uuid=worker_operation,
                                        attempted_payload={"medical_file_data": {"note": "changed"}},
                                        values={"medical_file_data": {"note": "changed"}})
            assert again.sync_version == 2
            stale_worker_op = uuid.uuid4(); attempt_uuids.add(stale_worker_op)
            try:
                apply_worker_update(s, user, s.get(Worker, worker_id), action="delete",
                                    expected_version=1, operation_uuid=stale_worker_op,
                                    attempted_payload={"delete": True}, values={"deleted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
            except ConflictException as exc:
                assert exc.detail["message"] == "EXPECTED_VERSION_CONFLICT"
            else:
                raise AssertionError("stale worker delete succeeded")
        with Session(engine) as s:
            assert s.get(LocalEditAttempt, stale_worker_op).entity_uuid == worker_uuid
            assert s.get(Worker, worker_id).deleted_at is None
            assert s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == worker_uuid)) == 1
        print("PASS worker medical-data update, retry, and stale delete attempt")

        with Session(engine) as s:
            for handler, key in ((get_edit_attempt, stale_uuid),
                                 (get_own_worker_edit_attempt, stale_worker_op)):
                try:
                    handler(key, other, s)
                except Exception as exc:
                    assert exc.__class__.__name__ == "ForbiddenException"
                else:
                    raise AssertionError("unauthorized attempt read succeeded")
                result = handler(key, user, s)
                assert result["data"]["operation_uuid"] == str(key)
        print("PASS attempt readable after new session; direct handler rejects foreign user")

        app = FastAPI()
        app.include_router(visits_router)
        app.include_router(workers_router)
        app.include_router(companies_router)
        app.add_exception_handler(HTTPException, http_exception_handler)
        def db_override():
            with Session(engine) as session:
                yield session
        app.dependency_overrides[get_db] = db_override
        with TestClient(app) as client:
            assert client.get(f"/medical-visits/edit-attempts/{stale_uuid}").status_code == 401
            assert client.get(f"/workers/edit-attempts/{stale_worker_op}").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: other
        with TestClient(app) as client:
            assert client.get(f"/medical-visits/edit-attempts/{stale_uuid}").status_code == 403
            assert client.get(f"/workers/edit-attempts/{stale_worker_op}").status_code == 403
            foreign_replay = client.post("/medical-visits", json=create_payload.model_dump(mode="json"),
                                         headers={"X-Operation-UUID": str(create_operation)})
            assert foreign_replay.status_code == 409 and "data" not in foreign_replay.json()
        app.dependency_overrides[get_current_user] = lambda: user
        http_stale_op = uuid.uuid4(); attempt_uuids.add(http_stale_op)
        with Session(engine) as s:
            legacy_id = s.scalar(select(MedicalVisit.id).where(MedicalVisit.uuid == legacy_visit_uuid))
        with TestClient(app) as client:
            assert client.patch(f"/medical-visits/{legacy_id}/status", json={"status": "pending"}).status_code == 422
            stale_response = client.patch(
                f"/medical-visits/{legacy_id}/status", json={"status": "pending"},
                headers={"X-Expected-Version": "99", "X-Operation-UUID": str(http_stale_op)},
            )
            assert stale_response.status_code == 409
            assert stale_response.json()["details"]["attempt_saved"] is True
            own = client.get(f"/medical-visits/edit-attempts/{http_stale_op}")
            assert own.status_code == 200 and own.json()["data"]["operation_uuid"] == str(http_stale_op)
            suspended_name = "synthetic-suspended-" + uuid.uuid4().hex
            suspended = client.post("/companies", json={"name": suspended_name})
            assert suspended.status_code == 423
            assert suspended.json()["details"]["code"] == "OPERATION_SUSPENDED_FOR_DATA_SAFETY"
            assert suspended.json()["details"]["retryable"] is False
        with Session(engine) as s:
            assert s.get(LocalEditAttempt, http_stale_op) is not None
            assert s.scalar(select(MedicalVisit.status).where(MedicalVisit.uuid == legacy_visit_uuid)) == "draft"
            assert s.scalar(select(func.count()).select_from(Company).where(Company.name == suspended_name)) == 0
        print("PASS actual HTTP 401/403/422/409; stale attempt durable and foreign receipt not disclosed")
    finally:
        # Delete only this run's records, in foreign-key order. Preserve all other rows.
        with Session(engine) as s:
            s.execute(delete(LocalEditAttempt).where(LocalEditAttempt.operation_uuid.in_(attempt_uuids)))
            s.execute(delete(LocalWriteOperation).where(LocalWriteOperation.operation_uuid.in_(operation_uuids)))
            own_visits = [visit_uuid, legacy_visit_uuid, deleted_legacy_uuid] + ([created_visit_uuid] if created_visit_uuid else [])
            own_entities = own_visits + [worker_uuid, branch_uuid, company_uuid] + ([created_worker_uuid] if created_worker_uuid else [])
            s.execute(delete(SyncChange).where(SyncChange.entity_uuid.in_(own_entities)))
            s.execute(delete(LocalRevision).where(LocalRevision.entity_uuid.in_(own_entities),
                                                  LocalRevision.parent_revision_uuid.is_not(None)))
            s.execute(delete(LocalRevision).where(LocalRevision.entity_uuid.in_(own_entities)))
            s.execute(delete(MedicalVisit).where(MedicalVisit.uuid.in_(own_visits)))
            s.execute(delete(Worker).where(Worker.uuid == worker_uuid))
            if created_worker_uuid:
                s.execute(delete(Worker).where(Worker.uuid == created_worker_uuid))
            s.execute(delete(Branch).where(Branch.uuid == branch_uuid))
            s.execute(delete(Company).where(Company.uuid == company_uuid))
            s.commit()
        print("Cleaned only this synthetic visit and its revision/event/attempt rows")
    engine.dispose()


if __name__ == "__main__":
    run()
