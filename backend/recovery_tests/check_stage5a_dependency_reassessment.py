"""5A-only reassessment after a missing parent/dependency arrives."""
import os, sys, uuid, subprocess
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncTransportEvent
from app.models.sync_application import SyncApplicationAttempt, SyncApplicationDecision
from app.services.sync_application_evaluation_service import evaluate_event

base = make_url(settings.database_url); run = uuid.uuid4().hex[:8]
name = "ibn_sina_stage5a_reassess_" + run
admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
env = {**os.environ, "DATABASE_URL": base.set(database=name).render_as_string(hide_password=False)}
root = str(Path(__file__).resolve().parents[1])
try:
    with admin.connect() as c:
        ident = c.execute(text("select current_database(), inet_server_addr(), inet_server_port()")).one()
        print("server=", ident[1], ident[2]); c.execute(text(f'create database "{name}"'))
    p = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env,
                       capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stderr[-1000:]
    eng = create_engine(env["DATABASE_URL"]); now = datetime.now(timezone.utc)
    with Session(eng) as db:
        db.info["sync_bootstrap_mode"] = True
        co = Company(uuid=uuid.uuid4(), name="5A reassessment fixture"); db.add(co); db.flush()
        br = Branch(uuid=uuid.uuid4(), company_id=co.id, name="5A branch"); db.add(br); db.flush()
        worker = Worker(uuid=uuid.uuid4(), company_id=co.id, branch_id=br.id, employee_number="5A-REASSESS",
                        first_name="Fixture", last_name="Worker", etat_actual="present")
        db.add(worker); db.flush()
        known_parent = uuid.uuid4(); missing_parent = uuid.uuid4(); create_parent = uuid.uuid4(); create_target = uuid.uuid4(); create_event = uuid.uuid4(); update_event = uuid.uuid4()
        # Existing worker's current revision is the parent that will arrive for the update case.
        db.add(LocalRevision(revision_uuid=known_parent, entity_type="workers", entity_uuid=worker.uuid,
                             parent_revision_uuid=None, local_version=1, kind="baseline", created_at=now))
        db.add_all([
            SyncTransportEvent(event_uuid=create_event, source_clinic_uuid=uuid.uuid4(), source_device_uuid=uuid.uuid4(),
                source_generation_uuid=uuid.uuid4(), source_sequence=1, entity_type="workers", entity_uuid=create_target,
                revision_uuid=uuid.uuid4(), parent_revision_uuid=create_parent, operation="create", schema_version=1,
                content_sha256="1"*64, payload={"employee_number":"5A-CREATE","first_name":"New","last_name":"Worker"}, origin_kind="inbox", created_at=now),
            SyncTransportEvent(event_uuid=update_event, source_clinic_uuid=uuid.uuid4(), source_device_uuid=uuid.uuid4(),
                source_generation_uuid=uuid.uuid4(), source_sequence=2, entity_type="workers", entity_uuid=worker.uuid,
                revision_uuid=uuid.uuid4(), parent_revision_uuid=missing_parent, operation="update", schema_version=1,
                content_sha256="2"*64, payload={"employee_number":"5A-REASSESS","first_name":"Fixture","last_name":"Worker"}, origin_kind="inbox", created_at=now),
        ]); db.commit()
        before_business = {t: db.scalar(text(f"select count(*) from {t}")) for t in ("workers", "local_revisions", "sync_changes", "sync_transport_events")}
        c1 = evaluate_event(db, create_event); u1 = evaluate_event(db, update_event)
        c1_reason, u1_reason = c1.reason_code, u1.reason_code; c1_fp, u1_fp = c1.input_fingerprint, u1.input_fingerprint
        a0 = {str(e): db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == e)) for e in (create_event, update_event)}
        print("before=", c1.reason_code, u1.reason_code, "attempts=", a0)
        # Fixture-only arrival of the missing parent; no application engine or incoming event path.
        db.add_all([LocalRevision(revision_uuid=create_parent, entity_type="workers", entity_uuid=create_target,
                             parent_revision_uuid=None, local_version=1, kind="baseline", created_at=datetime.now(timezone.utc)),
                    LocalRevision(revision_uuid=missing_parent, entity_type="workers", entity_uuid=worker.uuid,
                             parent_revision_uuid=known_parent, local_version=2, kind="update", created_at=datetime.now(timezone.utc))])
        db.commit(); db.info.pop("sync_bootstrap_mode", None)
        c2 = evaluate_event(db, create_event); u2 = evaluate_event(db, update_event)
        c2_reason, u2_reason = c2.reason_code, u2.reason_code
        a1 = {str(e): db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == e)) for e in (create_event, update_event)}
        assert c1_reason == "PARENT_REVISION_MISSING" and u1_reason == "PARENT_REVISION_MISSING"
        assert c2.decision == "blocked_authorization_evidence" and u2.decision == "blocked_authorization_evidence"
        assert c2_reason == "AUTHORIZATION_EVIDENCE_MISSING" and u2_reason == "AUTHORIZATION_EVIDENCE_MISSING"
        assert a1[ str(create_event) ] == a0[str(create_event)] + 1 and a1[str(update_event)] == a0[str(update_event)] + 1
        c3 = evaluate_event(db, create_event); u3 = evaluate_event(db, update_event)
        assert c3.input_fingerprint == c2.input_fingerprint and u3.input_fingerprint == u2.input_fingerprint
        assert {t: db.scalar(text(f"select count(*) from {t}")) for t in ("workers", "sync_changes", "sync_transport_events")} == {t: before_business[t] for t in ("workers", "sync_changes", "sync_transport_events")}
        print("after=", c2_reason, u2_reason, "attempts=", a1, "fingerprints_changed=", c1_fp != c2.input_fingerprint, u1_fp != u2.input_fingerprint, "unchanged_input_replay=1")
    with Session(eng) as db:
        assert db.scalar(select(func.count()).select_from(SyncApplicationDecision)) == 2
        assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt)) == 4
        print("fresh_session=persistent decisions=2 attempts=4")
    print("PASS stage5A dependency reassessment; authorization remains blocked; no business application")
finally:
    pass
