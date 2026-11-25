"""5A evaluation transaction rollback and durability only."""
import os, sys, uuid, subprocess
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_transport import SyncTransportEvent
from app.models.sync_application import SyncApplicationAttempt, SyncApplicationDecision
from app.services.sync_application_evaluation_service import evaluate_event

base = make_url(settings.database_url); run = uuid.uuid4().hex[:8]; name = "ibn_sina_stage5a_rb_" + run
admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT"); env = {**os.environ, "DATABASE_URL": base.set(database=name).render_as_string(hide_password=False)}; root = str(Path(__file__).resolve().parents[1])
try:
    with admin.connect() as c:
        ident = c.execute(text("select current_database(),inet_server_addr(),inet_server_port()")).one(); print("server=", ident[1], ident[2]); c.execute(text(f'create database "{name}"'))
    p = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True, timeout=180); assert p.returncode == 0, p.stderr[-1000:]
    eng = create_engine(env["DATABASE_URL"]); event = uuid.uuid4()
    with Session(eng) as db:
        db.add(SyncTransportEvent(event_uuid=event, source_clinic_uuid=uuid.uuid4(), source_device_uuid=uuid.uuid4(), source_generation_uuid=uuid.uuid4(), source_sequence=1, entity_type="workers", entity_uuid=uuid.uuid4(), revision_uuid=None, parent_revision_uuid=None, operation="create", schema_version=1, content_sha256="r"*64, payload={"employee_number":"5A-RB","first_name":"Rollback","last_name":"Case"}, origin_kind="inbox", created_at=datetime.now(timezone.utc))); db.commit()
        db.info["stage5a_fail_after_attempt"] = True
        try: evaluate_event(db, event)
        except RuntimeError as e: print("fail_after_attempt=", str(e))
        db.rollback(); db.info.pop("stage5a_fail_after_attempt", None)
        assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event)) == 0
        assert db.scalar(select(func.count()).select_from(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event)) == 0
    with Session(eng) as db:
        assert db.scalar(text("select count(*) from sync_application_attempts")) == 0; assert db.scalar(text("select count(*) from sync_application_decisions")) == 0; print("after_attempt_failure=persisted_zero=1")
        db.info["stage5a_fail_before_commit"] = True
        try: evaluate_event(db, event)
        except RuntimeError as e: print("fail_before_commit=", str(e))
        db.rollback(); db.info.pop("stage5a_fail_before_commit", None)
        assert db.scalar(text("select count(*) from sync_application_attempts")) == 0 and db.scalar(text("select count(*) from sync_application_decisions")) == 0
        current = evaluate_event(db, event); previous_fp = current.input_fingerprint
        print("retry=decision", current.decision, "reason=", current.reason_code)
        assert db.scalar(text("select count(*) from sync_application_attempts")) == 1
        # Existing decision/history: a changed evidence reference is a new
        # input, but each injected failure must preserve the prior decision.
        db.info["stage5a_fail_after_attempt"] = True
        try: evaluate_event(db, event, authorization_evidence={"reference": "changed-fixture"})
        except RuntimeError as e: print("prior_after_attempt=", str(e))
        db.rollback(); db.info.pop("stage5a_fail_after_attempt", None)
        prior = db.scalar(select(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event)); assert prior.input_fingerprint == previous_fp
        db.info["stage5a_fail_before_commit"] = True
        try: evaluate_event(db, event, authorization_evidence={"reference": "changed-fixture"})
        except RuntimeError as e: print("prior_before_commit=", str(e))
        db.rollback(); db.info.pop("stage5a_fail_before_commit", None)
        prior2 = db.scalar(select(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event)); assert prior2.input_fingerprint == previous_fp
        print("prior_decision_preserved=1 prior_history_preserved=1")
    with Session(eng) as db:
        d = db.scalar(select(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event)); evaluate_event(db, event)
        assert d.input_fingerprint == previous_fp and db.scalar(text("select count(*) from sync_application_attempts")) == 1
        print("fresh_process_session=persistent=1 matching_retry_no_new_attempt=1")
    print("PASS stage5A evaluation rollback; no business application")
finally:
    pass
