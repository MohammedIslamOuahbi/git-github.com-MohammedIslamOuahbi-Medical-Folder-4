import os,uuid
from datetime import datetime,timezone,timedelta
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from app.services.origin_proof_reconciliation_queue import *
from app.models.origin_proof_reconciliation_task import OriginProofReconciliationTask
engine=create_engine(os.environ["DATABASE_URL"])
def main():
 e,p,d=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); scope="queue:"+str(uuid.uuid4())
 with Session(engine) as s:
  a=enqueue(s,event_uuid=e,proof_uuid=p,peer_device_uuid=d,chain_scope=scope); b=enqueue(s,event_uuid=e,proof_uuid=p,peer_device_uuid=d,chain_scope=scope); assert a.task_uuid==b.task_uuid; s.commit(); print("dedup_one_task=1")
  q=s.get(OriginProofReconciliationTask,a.task_uuid); q.state="leased"; q.lease_until=datetime.now(timezone.utc)-timedelta(seconds=1); s.commit()
  q=claim(s,worker_id="worker-restarted",lease_seconds=30); assert q and q.claimed_by=="worker-restarted"; s.commit(); print("lease_recovered=1")
  s.rollback(); assert s.scalar(select(func.count()).select_from(OriginProofReconciliationTask).where(OriginProofReconciliationTask.task_uuid==a.task_uuid))==1; print("rollback_no_orphan=1")
if __name__=="__main__":main()
