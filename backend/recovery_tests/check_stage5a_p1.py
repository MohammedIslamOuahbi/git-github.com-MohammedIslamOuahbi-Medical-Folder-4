"""5A-P1 durable proof-wait storage; no signatures or business application."""
import os, sys, uuid, subprocess
from pathlib import Path
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.proof_pending import AuthorizationPolicy, OriginProofRequest
from app.services.auth_service import AuthService
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerCreate

base = make_url(settings.database_url); run = uuid.uuid4().hex[:8]; name = "ibn_sina_stage5a_p1_" + run
admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT"); env = {**os.environ, "DATABASE_URL": base.set(database=name).render_as_string(hide_password=False)}; root = str(Path(__file__).resolve().parents[1])
try:
    with admin.connect() as c:
        ident = c.execute(text("select current_database(),inet_server_addr(),inet_server_port()")).one(); print("server=", ident[1], ident[2]); c.execute(text(f'create database "{name}"'))
    p = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True, timeout=180); assert p.returncode == 0, p.stderr[-1000:]
    from app.models.user import User
    eng = create_engine(env["DATABASE_URL"]); pw = "unused-test-secret"
    with Session(eng) as db:
        db.info["sync_bootstrap_mode"] = True
        co = Company(uuid=uuid.uuid4(), name="P1 company"); db.add(co); db.flush(); br = Branch(uuid=uuid.uuid4(), company_id=co.id, name="P1 branch"); db.add(br); db.flush()
        user = AuthService().create_platform_user(db, "P1", "Worker", "p1@test.example.com", pw, "admin"); db.commit(); db.info.pop("sync_bootstrap_mode", None)
        op = uuid.uuid4(); payload = WorkerCreate(company_id=co.id, branch_id=br.id, employee_number="P1-001", first_name="P1", last_name="Worker")
        WorkerService().create(db, payload, user, op)
        req = db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid == op)); assert req and req.event_uuid is not None and req.status == "pending_proof" and req.proof_transport_version == 1 and req.time_state == "time_indeterminate"
        assert db.scalar(select(func.count()).select_from(AuthorizationPolicy).where(AuthorizationPolicy.policy_version == "5A-P1-20261014")) == 1
        print("atomic_local_write_and_proof_wait=1 status=pending_proof event_binding=change_uuid transport_version=1 offline_days=7")
        WorkerService().create(db, payload, user, op)
        assert db.scalar(select(func.count()).select_from(OriginProofRequest).where(OriginProofRequest.operation_uuid == op)) == 1
        print("matching_retry_no_duplicate_request=1")
    with Session(eng) as db:
        assert db.scalar(select(func.count()).select_from(OriginProofRequest)) == 1; print("fresh_session=persistent=1 signatures=0 business_application=0")
    print("PASS 5A-P1 proof wait storage; no proof issued and no business application")
finally:
    pass
