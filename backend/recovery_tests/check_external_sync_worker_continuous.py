"""Continuous external-worker startup, polling, shutdown, and restart check."""
from __future__ import annotations
import os, subprocess, sys, time, uuid, signal
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.models.worker import Worker
from app.models.company import Company
from app.models.branch import Branch
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncEventInbox
from app.services.sync_journal import payload_sha256

def seed(db, worker_template, company_uuid, branch_uuid):
    eid,wid,rid=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); now=datetime.now(timezone.utc)
    payload={"employee_number":"CONT-"+eid.hex[:8],"first_name":"Continuous","last_name":"Worker","gender":"M","etat_actual":"active","is_active":True,"company_uuid":str(company_uuid),"branch_uuid":str(branch_uuid)}
    db.add(SyncEventInbox(event_uuid=eid,source_clinic_uuid=uuid.uuid4(),source_device_uuid=uuid.uuid4(),source_generation_uuid=uuid.uuid4(),source_sequence=1,entity_type="workers",entity_uuid=wid,revision_uuid=rid,operation="insert",schema_version=1,content_sha256=payload_sha256(payload),payload=payload,status="received_waiting_application",received_at=now));db.commit();return eid,wid

def wait_applied(engine,eid,timeout=15):
    end=time.time()+timeout
    while time.time()<end:
        with Session(engine) as db:
            row=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==eid))
            if row and row.status=="applied": return True
        time.sleep(.2)
    return False

def main():
    raw=os.environ.get("STAGE5_TARGET_DB","");u=make_url(raw)
    if not u.database or u.database.lower()=="demo": raise RuntimeError("isolated target required")
    engine=create_engine(raw); now=datetime.now(timezone.utc)
    with Session(engine) as db:
        db.info.update(stage3_write_contract=True, sync_apply_mode=True)
        company_uuid, branch_uuid = uuid.uuid4(), uuid.uuid4()
        company=Company(uuid=company_uuid,name="External worker fixture")
        db.add(company); db.flush(); branch=Branch(uuid=branch_uuid,company_id=company.id,name="External worker branch"); db.add(branch); db.flush()
        template=None
        first=seed(db,template,company_uuid,branch_uuid)
    source_url=os.environ.get("STAGE5_SOURCE_DB")
    if source_url:
        source_engine=create_engine(source_url)
        with Session(source_engine) as source_db:
            source_db.info.update(stage3_write_contract=True, sync_apply_mode=True)
            if source_db.scalar(select(Company.uuid).where(Company.uuid==company_uuid)) is None:
                source_company=Company(uuid=company_uuid,name="External worker fixture"); source_db.add(source_company); source_db.flush(); source_db.add(Branch(uuid=branch_uuid,company_id=source_company.id,name="External worker branch")); source_db.commit()
        source_engine.dispose()
    peer,publisher,generation,clinic=(uuid.uuid4() for _ in range(4)); env=os.environ.copy();env.update({"DATABASE_URL":raw,"DEPLOYMENT_MODE":"central_server","WORKER_PEER":str(peer),"WORKER_PUBLISHER_DEVICE":str(publisher),"WORKER_PUBLISHER_GENERATION":str(generation),"WORKER_PUBLISHER_CLINIC":str(clinic),"WORKER_BATCH_SIZE":"100","WORKER_INTERVAL_SECONDS":"0.2"})
    flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
    p=subprocess.Popen([sys.executable,"-m","app.sync_worker_entrypoint"],cwd=str(ROOT),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=flags)
    try:
        assert wait_applied(engine,first[0]), "first event not applied"
        with Session(engine) as db: second=seed(db,template,company_uuid,branch_uuid)
        assert wait_applied(engine,second[0]), "second event not applied while running"
        if os.name == "nt": p.send_signal(signal.CTRL_BREAK_EVENT)
        else: p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)
        assert p.returncode is not None
        p2=subprocess.run([sys.executable,"-m","app.sync_worker_entrypoint"],cwd=str(ROOT),env={**env,"SYNC_WORKER_ONCE":"1"},capture_output=True,text=True,timeout=30,check=True)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid.in_([first[1],second[1]])))==2
            assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid.in_([first[1],second[1]])))==2
        print(f"continuous_startup=applied=1 second_event_while_running=applied=1 shutdown_bounded=1 exit_code={p.returncode} restart_no_duplicates=1")
    finally:
        if p.poll() is None: p.terminate(); p.wait(timeout=10)
        engine.dispose()
if __name__=="__main__":main()
