from __future__ import annotations
import os,sys,subprocess,json
from pathlib import Path
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.sync_application import SyncApplicationDecision
from app.models.sync_transport import SyncTransportEvent
from app.models.worker import Worker
from app.models.local_revision import LocalRevision
from app.models.origin_proof_reconciliation_task import OriginProofReconciliationTask
from app.services.entity_application_service import apply_from_reconciliation_result
from app.services.time_freshness_service import TestTimeAuthority, begin_challenge, evaluate_freshness
import time, datetime

def _freshness_revalidator(task, event):
    authority=TestTimeAuthority()
    request=begin_challenge(proof_uuid=task.proof_uuid,event_uuid=event.event_uuid,authority_scope=task.chain_scope)
    request.update(destination_uuid=str(task.peer_device_uuid),policy_version="5A-P1-20261014")
    started=request["started_monotonic"]; response=authority.sign({k:v for k,v in request.items() if k != "started_monotonic"})
    policy={"authority_id":"test-time-authority","test_only":True,"max_rtt_seconds":5,"valid_from":(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=1)).isoformat(),"valid_until":(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=1)).isoformat()}
    result=evaluate_freshness(response,request,authority,ended_monotonic=max(time.monotonic(),started),policy=policy)
    assert result["accepted_test_only"] is True
    return True

def prepare_reconciliation_result():
    """Run the real isolated reconciliation fixture, then return its task IDs.

    The recovery runner is the only place allowed to enable test-only authority
    acceptance; this module never manufactures an accepted decision.
    """
    script=Path(__file__).with_name('check_http_origin_proof_auto_reconciliation.py')
    env=dict(os.environ); env.setdefault('ORIGIN_PROOF_RECONCILIATION_TEST','1')
    proc=subprocess.run([sys.executable,str(script)],env=env,text=True,capture_output=True,timeout=180)
    if proc.returncode:
        raise RuntimeError('RECONCILIATION_FIXTURE_FAILED:'+proc.stdout[-1000:]+proc.stderr[-1000:])
    marker=None
    for line in proc.stdout.splitlines():
        try:
            value=json.loads(line)
            if 'reconciliation_result' in value: marker=value['reconciliation_result']
        except Exception: pass
    if not marker: raise RuntimeError('RECONCILIATION_RESULT_JSON_MISSING')
    e=create_engine(env['STAGE5_TARGET_DB'])
    with Session(e) as db:
        task=db.get(OriginProofReconciliationTask, marker['task_uuid'])
        if task is None or task.state!='completed': raise RuntimeError('RECONCILIATION_TASK_NOT_COMPLETED')
        decision=db.scalar(select(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid==task.event_uuid))
        if decision is None: raise RuntimeError('RECONCILIATION_RESULT_NOT_PERSISTED')
        if str(task.event_uuid) != marker['event_uuid'] or not task.result_payload:
            raise RuntimeError('RECONCILIATION_RESULT_TASK_MISMATCH')
        return task.task_uuid,task.event_uuid,task.result_fingerprint

def main():
    e=create_engine(os.environ['STAGE5_TARGET_DB'])
    task_uuid,event_uuid,fixture_fp=prepare_reconciliation_result()
    with Session(e) as db:
        task=db.get(OriginProofReconciliationTask,task_uuid); ev=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==event_uuid))
        if not task or not task.result_payload or not ev: raise RuntimeError('RECONCILIATION_RESULT_NOT_PERSISTED')
        d=task.result_payload
        entity_uuid=ev.entity_uuid
        try: apply_from_reconciliation_result(db,ev,reconciliation_result=d,current_input_fingerprint='0'*64)
        except Exception as x: assert str(x)=='RECONCILIATION_EVIDENCE_STALE'; db.rollback()
        else: raise AssertionError('stale decision was accepted')
    print('stale_input_rejected=1')
    with Session(e) as db:
        task=db.get(OriginProofReconciliationTask,task_uuid); ev2=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==event_uuid))
        row=apply_from_reconciliation_result(db,ev2,reconciliation_result=task.result_payload,current_input_fingerprint=task.result_fingerprint,freshness_revalidator=lambda: _freshness_revalidator(task,ev2))
        assert row.uuid==ev2.entity_uuid
    with Session(e) as db:
        assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid==entity_uuid))==1
        assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==entity_uuid))==1
    print('verified_apply=1 worker=1 revision=1 business_tables_changed_in_test=1 production_application_enabled=0 eligible_production=0 production_applied=0')
    with Session(e) as db:
        task=db.get(OriginProofReconciliationTask,task_uuid); ev2=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==event_uuid)); apply_from_reconciliation_result(db,ev2,reconciliation_result=task.result_payload,current_input_fingerprint=task.result_fingerprint,freshness_revalidator=lambda: _freshness_revalidator(task,ev2))
    with Session(e) as db:
        assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid==entity_uuid))==1
        assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==entity_uuid))==1
    print('replay_no_duplicate=1')
if __name__=='__main__': main()
