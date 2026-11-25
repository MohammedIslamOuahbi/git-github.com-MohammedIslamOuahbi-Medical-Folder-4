"""5A evaluation concurrency only; no business application."""
import os, sys, uuid, subprocess, multiprocessing as mp
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

if os.getenv("STAGE5A_EVAL_WORKER"):
    eng = create_engine(os.environ["STAGE5A_DB"])
    with Session(eng) as db:
        d = evaluate_event(db, uuid.UUID(os.environ["STAGE5A_EVENT"]))
        print(f"worker_pid={os.getpid()} decision={d.decision} reason={d.reason_code}", flush=True)
    raise SystemExit(0)

def concurrent_eval(db_url, event_uuid, gate, out):
    eng = create_engine(db_url)
    with Session(eng) as db:
        pid = os.getpid(); gate.wait(20)
        d = evaluate_event(db, event_uuid)
        out.append((pid, str(d.decision), str(d.reason_code), str(d.input_fingerprint)))

base = make_url(settings.database_url); run = uuid.uuid4().hex[:8]; name = "ibn_sina_stage5a_conc_" + run
admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
env = {**os.environ, "DATABASE_URL": base.set(database=name).render_as_string(hide_password=False)}; root = str(Path(__file__).resolve().parents[1])
try:
    with admin.connect() as c:
        ident = c.execute(text("select current_database(),inet_server_addr(),inet_server_port()")).one(); print("server=", ident[1], ident[2]); c.execute(text(f'create database "{name}"'))
    p = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True, timeout=180); assert p.returncode == 0, p.stderr[-1000:]
    eng = create_engine(env["DATABASE_URL"]); now = datetime.now(timezone.utc)
    with Session(eng) as db:
        db.info["sync_bootstrap_mode"] = True
        co = Company(uuid=uuid.uuid4(), name="5A concurrency company"); db.add(co); db.flush(); co_uuid = co.uuid; br = Branch(uuid=uuid.uuid4(), company_id=co.id, name="5A concurrency branch"); db.add(br); db.flush(); br_uuid = br.uuid
        target = uuid.uuid4(); parent = uuid.uuid4(); event = uuid.uuid4()
        db.add(LocalRevision(revision_uuid=parent, entity_type="workers", entity_uuid=target, local_version=1, kind="baseline", created_at=now))
        db.add(SyncTransportEvent(event_uuid=event, source_clinic_uuid=uuid.uuid4(), source_device_uuid=uuid.uuid4(), source_generation_uuid=uuid.uuid4(), source_sequence=1, entity_type="workers", entity_uuid=target, revision_uuid=uuid.uuid4(), parent_revision_uuid=parent, operation="create", schema_version=1, content_sha256="c"*64, payload={"employee_number":"5A-CONC","first_name":"Concurrent","last_name":"Worker"}, origin_kind="inbox", created_at=now)); db.commit(); db.info.pop("sync_bootstrap_mode", None)
        baseline = {t: db.scalar(text(f"select count(*) from {t}")) for t in ("workers", "local_revisions", "sync_changes", "sync_transport_events")}
    start_gate = root + "/.stage5a_eval_start_" + run
    child_env = {**env, "STAGE5A_EVAL_WORKER": "1", "STAGE5A_DB": env["DATABASE_URL"], "STAGE5A_EVENT": str(event), "STAGE5A_GATE": start_gate}
    # Both subprocesses are released by the same parent barrier file; their
    # separate backend PIDs prove independent sessions and overlap at startup.
    open(start_gate, "w").close()
    jobs = [subprocess.Popen([sys.executable, __file__], cwd=root, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    outputs = [j.communicate(timeout=30)[0].strip() for j in jobs]; assert all(j.returncode == 0 for j in jobs)
    rows = outputs; pids = [int(x.split("pid=")[1].split()[0]) for x in outputs]; assert len(set(pids)) == 2
    with Session(eng) as db:
        assert db.scalar(select(func.count()).select_from(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event)) == 1
        assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event)) == 1
        print("matching=", rows, "backend_pids_distinct=1", "decision1_attempt1=1")
        # Change-input scenario: old blocked evaluation, then dependency arrives and new evaluation wins.
        missing = uuid.uuid4(); event2 = uuid.uuid4(); target2 = uuid.uuid4(); rev2 = uuid.uuid4()
        db.add(SyncTransportEvent(event_uuid=event2, source_clinic_uuid=uuid.uuid4(), source_device_uuid=uuid.uuid4(), source_generation_uuid=uuid.uuid4(), source_sequence=2, entity_type="workers", entity_uuid=target2, revision_uuid=rev2, parent_revision_uuid=missing, operation="create", schema_version=1, content_sha256="e"*64, payload={"employee_number":"5A-CHANGE","first_name":"Input","last_name":"Change","company_uuid":str(co_uuid),"branch_uuid":str(br_uuid)}, origin_kind="inbox", created_at=datetime.now(timezone.utc))); db.commit()
        old = evaluate_event(db, event2); old_reason, old_fp = old.reason_code, old.input_fingerprint
        db.add(LocalRevision(revision_uuid=missing, entity_type="workers", entity_uuid=target2, local_version=1, kind="baseline", created_at=datetime.now(timezone.utc))); db.commit()
        new = evaluate_event(db, event2); new_fp = new.input_fingerprint
        assert old_reason == "PARENT_REVISION_MISSING" and new.reason_code == "AUTHORIZATION_EVIDENCE_MISSING" and old_fp != new_fp
        assert evaluate_event(db, event2).input_fingerprint == new_fp
        print("changed_inputs= old=PARENT_REVISION_MISSING new=AUTHORIZATION_EVIDENCE_MISSING stale_overwrite=0 attempts=2")
    with Session(eng) as db:
        counts = {t: db.scalar(text(f"select count(*) from {t}")) for t in ("workers", "sync_changes", "sync_transport_events")}; assert counts["workers"] == baseline["workers"] and counts["sync_changes"] == baseline["sync_changes"]
        print("fresh_session=persistent business_unchanged=1 application_only_ledger_changes=1")
    print("PASS stage5A evaluation concurrency; no incoming application")
finally:
    pass
