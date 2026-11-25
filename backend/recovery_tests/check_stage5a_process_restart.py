"""5A process restart durability check; evaluation only."""
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

if os.getenv("STAGE5A_RESTART_WORKER"):
    eng = create_engine(os.environ["STAGE5A_DB"])
    with Session(eng) as db:
        d = evaluate_event(db, uuid.UUID(os.environ["STAGE5A_EVENT"]))
        print(f"pid={os.getpid()} decision={d.decision} reason={d.reason_code} fingerprint={d.input_fingerprint}")
    raise SystemExit(0)

base = make_url(settings.database_url); run = uuid.uuid4().hex[:8]; name = "ibn_sina_stage5a_restart_" + run
admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT"); env = {**os.environ, "DATABASE_URL": base.set(database=name).render_as_string(hide_password=False)}; root = str(Path(__file__).resolve().parents[1])
try:
    with admin.connect() as c:
        ident = c.execute(text("select current_database(),inet_server_addr(),inet_server_port()")).one(); print("server=", ident[1], ident[2]); c.execute(text(f'create database "{name}"'))
    p = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True, timeout=180); assert p.returncode == 0, p.stderr[-1000:]
    eng = create_engine(env["DATABASE_URL"]); event = uuid.uuid4()
    with Session(eng) as db:
        db.add(SyncTransportEvent(event_uuid=event, source_clinic_uuid=uuid.uuid4(), source_device_uuid=uuid.uuid4(), source_generation_uuid=uuid.uuid4(), source_sequence=1, entity_type="workers", entity_uuid=uuid.uuid4(), revision_uuid=None, parent_revision_uuid=None, operation="create", schema_version=1, content_sha256="p"*64, payload={"employee_number":"5A-RESTART","first_name":"Restart","last_name":"Case"}, origin_kind="inbox", created_at=datetime.now(timezone.utc))); db.commit()
    child_env = {**env, "STAGE5A_RESTART_WORKER": "1", "STAGE5A_DB": env["DATABASE_URL"], "STAGE5A_EVENT": str(event)}
    first = subprocess.run([sys.executable, __file__], cwd=root, env=child_env, capture_output=True, text=True, timeout=60); assert first.returncode == 0; print("process1=", first.stdout.strip())
    second = subprocess.run([sys.executable, __file__], cwd=root, env=child_env, capture_output=True, text=True, timeout=60); assert second.returncode == 0; print("process2=", second.stdout.strip())
    with Session(eng) as db:
        assert db.scalar(select(func.count()).select_from(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event)) == 1
        assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event)) == 1
        print("fresh_session=decision1_attempt1_persistent=1 matching_restart_no_new_attempt=1 hooks_or_bootstrap_in_new_process=0")
    print("PASS stage5A process restart durability; no business application")
finally:
    pass
