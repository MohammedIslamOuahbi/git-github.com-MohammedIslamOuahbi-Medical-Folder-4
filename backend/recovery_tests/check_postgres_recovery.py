"""Opt-in integration check against the named, isolated PostgreSQL test database.

No schema changes or broad deletes. Every inserted recovery row has this run's scope.
"""
from __future__ import annotations

import json
import sys
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.exceptions import BadRequestException
from app.middleware.error_handler import http_exception_handler
from app.models.legacy_recovery import RecoveryIdentityCandidate, RecoveryItem, RecoverySource
from app.routers.legacy_recovery import router
from app.services.legacy_recovery_service import LegacyRecoveryService
from app.services.recovery_format import digest


def checked_engine():
    url = make_url(settings.database_url)
    if not (url.drivername == "postgresql+psycopg" and url.host in {"localhost", "127.0.0.1"}
            and url.database == "ibn_sina_recovery_test" and (url.port or 5432) == 5432):
        raise RuntimeError("RECOVERY_TEST_DATABASE_NOT_AUTHORIZED")
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        actual = connection.execute(text("SELECT current_database(), current_schema(), inet_server_port()")).one()
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if actual != ("ibn_sina_recovery_test", "public", 5432) or revision not in {"20261007_01", "20261007_02", "20261008_01", "20261008_04"}:
            raise RuntimeError("RECOVERY_TEST_DATABASE_IDENTITY_MISMATCH")
        names = set(connection.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() "
            "AND table_name LIKE 'recovery_%'"
        )).scalars())
        if names != {"recovery_sources", "recovery_items", "recovery_identity_candidates"}:
            raise RuntimeError("RECOVERY_TEST_SCHEMA_MISMATCH")
    return engine


def queue_raw(rows):
    return json.dumps({"entries": {"clinic_sync_queue": json.dumps({"workers": rows})}})


def run():
    engine = checked_engine()
    run_id = uuid.uuid4().hex
    owner = SimpleNamespace(uuid=uuid.uuid4(), role="doctor", is_active=True)
    stranger = SimpleNamespace(uuid=uuid.uuid4(), role="doctor", is_active=True)
    service = LegacyRecoveryService()
    scopes = {f"user:{owner.uuid}:profile:{run_id}-{suffix}" for suffix in ("a", "b", "c", "concurrent", "forced", "interrupted")}

    def capture(session, raw, suffix="a", **options):
        return service.capture(session, owner, kind="browser_local_storage", logical_key="synthetic-working-data",
                               profile_id=f"{run_id}-{suffix}", source_identity=f"synthetic-device-{suffix}",
                               format_version=options.get("format_version", 1), raw_payload=raw,
                               sha256=options.get("sha256", digest(raw)))

    def source_count(session, suffix):
        return session.scalar(select(func.count()).select_from(RecoverySource).where(
            RecoverySource.source_scope == f"user:{owner.uuid}:profile:{run_id}-{suffix}"))

    def business_counts(session):
        names = session.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() "
            "AND table_type='BASE TABLE' AND table_name NOT LIKE 'recovery_%' AND table_name <> 'alembic_version'"
        )).scalars().all()
        return {name: session.scalar(text(f'SELECT count(*) FROM "{name}"')) for name in names}

    before = None
    try:
        with Session(engine) as session:
            before = business_counts(session)
            first_raw = queue_raw([{"id": 7, "uuid": str(uuid.uuid4()), "company_id": 8}] * 2)
            first = capture(session, first_raw)
            first_uuid = first.uuid
            assert first.materialized_count == 2
        with Session(engine) as session:  # Proof of persistence across independent sessions.
            persisted = session.get(RecoverySource, first_uuid)
            assert persisted and persisted.raw_payload == first_raw and persisted.sha256 == digest(first_raw)
            assert session.scalar(select(func.count()).select_from(RecoveryItem).where(RecoveryItem.source_uuid == first_uuid)) == 2
            second = capture(session, first_raw)
            assert second.uuid == first_uuid and source_count(session, "a") == 1
            items = session.scalars(select(RecoveryItem).where(RecoveryItem.source_uuid == first_uuid).order_by(RecoveryItem.ordinal)).all()
            assert len(items) == 2 and [item.ordinal for item in items] == [0, 1]
            assert items[0].raw_fragment == items[1].raw_fragment
        print("PASS independent-session persistence, duplicate snapshot, distinct identical entries")

        with Session(engine) as session:
            changed_raw = queue_raw([{"id": 7, "uuid": str(uuid.uuid4()), "company_id": 8}])
            changed = capture(session, changed_raw)
            assert changed.uuid != first_uuid and changed.parent_source_uuid == first_uuid
            other = capture(session, changed_raw, "b")
            candidates = session.scalars(select(RecoveryIdentityCandidate).where(
                RecoveryIdentityCandidate.item_id.in_(select(RecoveryItem.id).where(
                    RecoveryItem.source_uuid.in_([changed.uuid, other.uuid]))))).all()
            assert len(candidates) == 2 and candidates[0].source_scope != candidates[1].source_scope
            assert all(candidate.legacy_id == "7" and candidate.status == "candidate_needs_review" for candidate in candidates)
            assert all(item.reason_code == "LEGACY_NUMERIC_RELATION" for item in session.scalars(
                select(RecoveryItem).where(RecoveryItem.source_uuid.in_([changed.uuid, other.uuid]))))
        print("PASS changed version link and separate numeric-ID candidates")

        class Interrupted(LegacyRecoveryService):
            def materialize(self, db, source):
                raise RuntimeError("synthetic interruption after source commit")

        rows = [{"uuid": str(uuid.uuid4())} for _ in range(105)]
        raw = queue_raw(rows)
        with Session(engine) as session:
            try:
                Interrupted().capture(session, owner, kind="browser_local_storage", logical_key="synthetic-working-data",
                                      profile_id=f"{run_id}-interrupted", source_identity="synthetic-device",
                                      format_version=1, raw_payload=raw, sha256=digest(raw))
            except RuntimeError as exc:
                assert str(exc) == "synthetic interruption after source commit"
            else:
                raise AssertionError("interruption not triggered")
        with Session(engine) as session:
            assert source_count(session, "interrupted") == 1
            saved = session.scalar(select(RecoverySource).where(RecoverySource.source_scope == f"user:{owner.uuid}:profile:{run_id}-interrupted"))
            assert saved.materialized_count == 0 and saved.raw_payload == raw
            first_page = service.resume(session, owner, saved.uuid)
            assert first_page.materialized_count == 100
        with Session(engine) as session:
            complete = service.resume(session, owner, saved.uuid)
            assert complete.materialized_count == 105 and complete.state == "recorded"
            assert session.scalar(select(func.count()).select_from(RecoveryItem).where(RecoveryItem.source_uuid == saved.uuid)) == 105
            assert service.resume(session, owner, saved.uuid).materialized_count == 105
        print("PASS interrupted registration and bounded resume across sessions")

        failures = 0
        with Session(engine) as session:
            baseline = source_count(session, "c")
            for kwargs in ({"sha256": "0" * 64}, {"format_version": 99}):
                try:
                    capture(session, queue_raw([]), "c", **kwargs)
                except BadRequestException:
                    failures += 1
            assert failures == 2 and source_count(session, "c") == baseline
        print("PASS rejected checksum and unsupported format without writes")

        # Two genuinely independent database sessions start simultaneously.
        barrier = threading.Barrier(2)
        concurrent_raw = queue_raw([{"uuid": str(uuid.uuid4())} for _ in range(3)])
        results, errors = [], []

        def worker():
            try:
                with Session(engine) as session:
                    barrier.wait(timeout=10)
                    result = capture(session, concurrent_raw, "concurrent")
                    results.append(result.uuid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        assert all(not thread.is_alive() for thread in threads), "concurrent request hung"
        if errors:
            raise errors[0]
        with Session(engine) as session:
            assert len(results) == 2 and results[0] == results[1] and source_count(session, "concurrent") == 1
            assert session.scalar(select(func.count()).select_from(RecoveryItem).where(RecoveryItem.source_uuid == results[0])) == 3
        print("PASS concurrent same-source capture using two connections")

        # Synchronize the first source commits so the unique-key race is exercised.
        forced_barrier = threading.Barrier(2)

        class RacingSession(Session):
            def __init__(self):
                super().__init__(engine)
                self.first_commit = True

            def commit(self):
                if self.first_commit:
                    self.first_commit = False
                    forced_barrier.wait(timeout=10)
                return super().commit()

        forced_raw = queue_raw([{"uuid": str(uuid.uuid4())} for _ in range(3)])
        forced_results, forced_errors = [], []

        def forced_worker():
            try:
                with RacingSession() as session:
                    forced_results.append(capture(session, forced_raw, "forced").uuid)
            except Exception as exc:
                forced_errors.append(exc)

        threads = [threading.Thread(target=forced_worker) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        assert all(not thread.is_alive() for thread in threads), "forced race hung"
        if forced_errors:
            raise forced_errors[0]
        with Session(engine) as session:
            assert len(forced_results) == 2 and len(set(forced_results)) == 1 and source_count(session, "forced") == 1
            assert session.scalar(select(func.count()).select_from(RecoveryItem).where(RecoveryItem.source_uuid == forced_results[0])) == 3
        print("PASS forced unique-key race across two connections")

        app = FastAPI()
        app.include_router(router)
        app.add_exception_handler(HTTPException, http_exception_handler)

        def db_override():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_db] = db_override
        with TestClient(app) as client:
            assert client.get("/recovery/sources").status_code == 401
            assert client.post("/recovery/sources", json={}).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: stranger
        with TestClient(app) as client:
            assert client.get(f"/recovery/sources/{first_uuid}/items").status_code == 403
            assert client.post(f"/recovery/sources/{first_uuid}/resume").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: owner
        with TestClient(app) as client:
            listing = client.get("/recovery/sources")
            detail = client.get(f"/recovery/sources/{first_uuid}/items")
            assert listing.status_code == 200 and detail.status_code == 200
            assert "raw_payload" not in listing.text and "raw_fragment" not in detail.text
            assert first_raw not in listing.text and first_raw not in detail.text
        print("PASS real-session API authorization and metadata-only follow-up")

        with Session(engine) as session:
            assert business_counts(session) == before
        print("PASS all non-recovery table row counts unchanged")
    finally:
        # Delete only rows made by this exact, random run; never clear existing data.
        with Session(engine) as session:
            source_ids = select(RecoverySource.uuid).where(RecoverySource.source_scope.in_(scopes))
            item_ids = select(RecoveryItem.id).where(RecoveryItem.source_uuid.in_(source_ids))
            session.execute(delete(RecoveryIdentityCandidate).where(RecoveryIdentityCandidate.item_id.in_(item_ids)))
            session.execute(delete(RecoveryItem).where(RecoveryItem.source_uuid.in_(source_ids)))
            # Delete children before parents; never rely on unspecified SELECT ordering.
            session.execute(delete(RecoverySource).where(
                RecoverySource.source_scope.in_(scopes), RecoverySource.parent_source_uuid.is_not(None)))
            session.execute(delete(RecoverySource).where(RecoverySource.source_scope.in_(scopes)))
            session.commit()
        print("Cleaned only this run's recovery rows")
    engine.dispose()


if __name__ == "__main__":
    run()
