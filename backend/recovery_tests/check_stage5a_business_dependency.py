"""5A dependency reassessment: a real workers company/branch UUID arrives later."""
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
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncTransportEvent
from app.models.sync_application import SyncApplicationAttempt, SyncApplicationDecision
from app.services.sync_application_evaluation_service import evaluate_event

base = make_url(settings.database_url); run = uuid.uuid4().hex[:8]; name = "ibn_sina_stage5a_dep_" + run
admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
env = {**os.environ, "DATABASE_URL": base.set(database=name).render_as_string(hide_password=False)}
root = str(Path(__file__).resolve().parents[1])
try:
    with admin.connect() as c:
        ident = c.execute(text("select current_database(),inet_server_addr(),inet_server_port()")).one()
        print("server=", ident[1], ident[2]); c.execute(text(f'create database "{name}"'))
    p = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stderr[-1000:]
    eng = create_engine(env["DATABASE_URL"]); now = datetime.now(timezone.utc)
    with Session(eng) as db:
        db.info["sync_bootstrap_mode"] = True
        company_uuid, branch_uuid, target_uuid, parent_uuid, event_uuid = (uuid.uuid4() for _ in range(5))
        # Parent revision is valid and belongs to the intended worker target.
        db.add(LocalRevision(revision_uuid=parent_uuid, entity_type="workers", entity_uuid=target_uuid, local_version=1, kind="baseline", created_at=now))
        db.add(SyncTransportEvent(event_uuid=event_uuid, source_clinic_uuid=uuid.uuid4(), source_device_uuid=uuid.uuid4(), source_generation_uuid=uuid.uuid4(), source_sequence=1,
            entity_type="workers", entity_uuid=target_uuid, revision_uuid=uuid.uuid4(), parent_revision_uuid=parent_uuid, operation="create", schema_version=1,
            content_sha256="d"*64, payload={"employee_number":"5A-DEP", "first_name":"Dependency", "last_name":"Worker", "company_uuid":str(company_uuid), "branch_uuid":str(branch_uuid)}, origin_kind="inbox", created_at=now))
        db.commit(); db.info.pop("sync_bootstrap_mode", None)
        first = evaluate_event(db, event_uuid); first_reason, first_fp = first.reason_code, first.input_fingerprint
        first_attempts = db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event_uuid))
        print("before_actual=", first.decision, first_reason, "attempts=", first_attempts)
        assert first_reason == "DEPENDENCY_MISSING" and first.decision == "blocked_structural" and first_attempts == 1
        # Limited fixture arrival: real Company then Branch rows, outside evaluation/application.
        db.info["sync_bootstrap_mode"] = True
        company = Company(uuid=company_uuid, name="5A dependency company"); db.add(company); db.flush()
        db.add(Branch(uuid=branch_uuid, company_id=company.id, name="5A dependency branch")); db.commit(); db.info.pop("sync_bootstrap_mode", None)
        second = evaluate_event(db, event_uuid); second_fp = second.input_fingerprint
        second_attempts = db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event_uuid))
        assert second.reason_code == "AUTHORIZATION_EVIDENCE_MISSING" and second.decision == "blocked_authorization_evidence" and second_attempts == 2 and first_fp != second_fp
        third = evaluate_event(db, event_uuid)
        assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event_uuid)) == 2 and third.input_fingerprint == second_fp
        print("after= structural=clear authorization=blocked_authorization_evidence attempts=2 fingerprints_changed=1 unchanged_replay=1")
        business_counts = {t: db.scalar(text(f"select count(*) from {t}")) for t in ("local_revisions", "sync_transport_events", "sync_changes")}
    with Session(eng) as db:
        assert db.scalar(select(func.count()).select_from(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event_uuid)) == 1
        assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event_uuid)) == 2
        assert {t: db.scalar(text(f"select count(*) from {t}")) for t in ("local_revisions", "sync_transport_events", "sync_changes")} == business_counts
        print("fresh_session=persistent; business_tables_unchanged_after_evaluation=1; applied=0; ready_for_application=0")
    print("PASS stage5A business dependency reassessment; no incoming application")
finally:
    pass
