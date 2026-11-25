"""Deterministic separate-commit lease takeover regression."""
from __future__ import annotations
import os, sys, threading, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy import create_engine, select, func, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncEventInbox
from app.services.sync_transport_worker import SyncTransportWorker

def db_url():
    u=make_url(os.environ.get("STAGE5_TARGET_DB") or "")
    if not u.database or u.database.lower()=="demo": raise RuntimeError("isolated target required")
    return u

def main():
    engine=create_engine(db_url().render_as_string(hide_password=False)); factory=sessionmaker(engine, expire_on_commit=False)
    event_id, worker_id, revision, source, generation, clinic = (uuid.uuid4() for _ in range(6)); now=datetime.now(timezone.utc)
    with Session(engine) as db:
        company=db.scalar(select(Company).order_by(Company.id)); branch=db.scalar(select(Branch).where(Branch.company_id==company.id).order_by(Branch.id)) if company else None
        if not company or not branch: raise RuntimeError("target dependency fixture lacks company/branch")
        payload={"employee_number":"LEASE-"+event_id.hex[:8],"first_name":"Lease","last_name":"Recovery","gender":"M","etat_actual":"active","is_active":True,"company_uuid":str(company.uuid),"branch_uuid":str(branch.uuid)}
        db.add(SyncEventInbox(event_uuid=event_id,source_clinic_uuid=clinic,source_device_uuid=source,source_generation_uuid=generation,source_sequence=1,entity_type="workers",entity_uuid=worker_id,revision_uuid=revision,parent_revision_uuid=None,operation="insert",schema_version=1,content_sha256="0"*64,payload=payload,status="received_waiting_application",received_at=now)); db.commit()
    claimed=threading.Event(); release=threading.Event(); a_result=[]; a_error=[]
    def pause(row): claimed.set(); release.wait(10)
    def sender(_): pass
    def run_a():
        try:
            w=SyncTransportWorker(factory,peer_device_uuid=source,channel="lease",publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=sender,after_application_business_commit=pause)
            a_result.append(w.run_application_once(limit=1,event_uuid=event_id))
        except Exception as exc:
            a_error.append(repr(exc)); claimed.set()
    ta=threading.Thread(target=run_a); ta.start(); assert claimed.wait(10), f"consumer A did not reach commit barrier {a_error}"
    with Session(engine) as db:
        row=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id)); assert row.status=="applying"; lease_a=row.application_lease_uuid
        assert db.scalar(select(Worker).where(Worker.uuid==worker_id)) is not None
        print("after_business_commit=visible inbox=applying lease_a=live")
    w_b=SyncTransportWorker(factory,peer_device_uuid=source,channel="lease",publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=sender)
    assert w_b.run_application_once(limit=1,event_uuid=event_id)==0; print("live_lease_takeover=blocked")
    with Session(engine) as db:
        db.execute(update(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id).values(application_lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))); db.commit()
        check=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id)); print("lease_expired=",check.application_lease_expires_at < datetime.now(timezone.utc), "status=",check.status)
    b_result=w_b.run_application_once(limit=1,event_uuid=event_id); print("takeover_result=",b_result); assert b_result==1; print("expired_lease_recovered=1")
    release.set(); ta.join(10); assert not ta.is_alive()
    with Session(engine) as db:
        row=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id)); revisions=db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==worker_id)); workers=db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid==worker_id)); assert row.status=="applied" and workers==1 and revisions==1
        print("final inbox=applied worker=1 revisions=1 stale_owner_cannot_overwrite=1")
    engine.dispose()

if __name__=="__main__": main()
