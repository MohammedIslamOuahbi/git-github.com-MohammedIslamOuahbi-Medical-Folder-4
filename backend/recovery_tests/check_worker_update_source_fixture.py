from __future__ import annotations
import os,sys,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.sync_change import SyncChange
from app.models.local_revision import LocalWriteOperation
from app.models.local_revision import LocalRevision
from app.models.worker import Worker
from app.models.user import User
from app.schemas.worker import WorkerUpdate
from app.services.worker_service import WorkerService
from app.services.sync_journal import payload_sha256
from app.models.proof_pending import OriginProofRequest
from app.models.authorization_evidence_record import AuthorizationEvidenceRecord
from app.models.origin_proof import OriginProof
from app.models.proof_trust import ProofTrustedKey, ProofDelegation
from app.services.authorization_evidence_service import issue_for_local_operation, store_local_evidence, verify_authorization_evidence
from app.services.proof_issuer_service import MemoryKeyProvider, ProofIssuerService
from app.services.proof_verification_service import verify_signature, verify_binding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64
from check_worker_service_integration import prepare_authorized_worker_source

def prepare_worker_update_source(url, fixture):
    engine=create_engine(url); op=uuid.uuid4()
    with Session(engine) as db:
        worker=db.scalar(select(Worker).where(Worker.uuid==fixture.worker_uuid)); user=db.scalar(select(User).where(User.uuid==fixture.user_uuid))
        if not worker or not user: raise RuntimeError('UPDATE_SOURCE_RECORD_MISSING')
        expected=int(worker.sync_version or 0)
        db.info.update(sync_source_device_uuid=fixture.source_device_uuid,sync_source_generation_uuid=fixture.source_generation_uuid,sync_source_clinic_uuid=fixture.clinic_uuid,sync_source_user_uuid=fixture.user_uuid)
        WorkerService().update(db,worker.id,WorkerUpdate(first_name='Updated-'+uuid.uuid4().hex[:8]),user,expected,op)
        db.commit()
    with Session(engine) as db:
        change=db.scalar(select(SyncChange).where(SyncChange.operation_uuid==op))
        worker=db.scalar(select(Worker).where(Worker.uuid==fixture.worker_uuid))
        assert change and change.operation=='update' and change.entity_uuid==fixture.worker_uuid
        assert change.base_version==expected and change.entity_version==expected+1
        assert change.source_user_uuid==fixture.user_uuid and change.source_device_uuid==fixture.source_device_uuid
        assert change.content_sha256==payload_sha256(change.payload)
        base_change=db.scalar(select(SyncChange).where(SyncChange.entity_uuid==fixture.worker_uuid,SyncChange.operation=='insert').order_by(SyncChange.id))
        if base_change is None: raise RuntimeError('WORKER_CREATE_CHANGE_MISSING_FOR_UPDATE')
        operation=db.get(LocalWriteOperation,op)
        policy_version=((operation.result_payload or {}).get('authorization_decision') or {}).get('policy_version') or '5A-P1-20261014'
        parent_revision=db.scalar(select(__import__('app.models.local_revision',fromlist=['LocalRevision']).LocalRevision.revision_uuid).where(__import__('app.models.local_revision',fromlist=['LocalRevision']).LocalRevision.entity_uuid==change.entity_uuid,__import__('app.models.local_revision',fromlist=['LocalRevision']).LocalRevision.local_version==change.base_version))
        request=OriginProofRequest(request_uuid=uuid.uuid4(),operation_uuid=op,event_uuid=change.change_uuid,content_sha256=change.content_sha256,revision_uuid=change.revision_uuid,parent_revision_uuid=parent_revision,origin_user_uuid=change.source_user_uuid,origin_device_uuid=change.source_device_uuid,clinic_uuid=change.source_clinic_uuid,entity_type=change.entity_type,operation='update',policy_version=policy_version,proof_transport_version=1,status='pending_proof',attempt_count=0,last_reason_code='PROOF_NOT_ISSUED',time_state='time_indeterminate',created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc)); db.add(request)
        def pub(k): return base64.b64encode(k.public_key().public_bytes_raw()).decode()
        ak,pk=Ed25519PrivateKey.generate(),Ed25519PrivateKey.generate(); aid='auth-update-'+uuid.uuid4().hex[:8]; pid='origin-update-'+uuid.uuid4().hex[:8]; issuer=uuid.uuid4(); service=uuid.uuid4(); scope=f'clinic:{change.source_clinic_uuid}:workers:update'; now=datetime.now(timezone.utc)
        delegation_id=uuid.uuid4(); db.add(ProofTrustedKey(key_id=aid,clinic_uuid=change.source_clinic_uuid,origin_service_uuid=issuer,origin_device_uuid=change.source_device_uuid,registration_authority_uuid=issuer,public_key=pub(ak),algorithm='Ed25519',canonicalization_version='deterministic-json-restricted-v1',state='active',registered_at=now)); db.add(ProofTrustedKey(key_id=pid,clinic_uuid=change.source_clinic_uuid,origin_service_uuid=service,origin_device_uuid=change.source_device_uuid,registration_authority_uuid=issuer,public_key=pub(pk),algorithm='Ed25519',canonicalization_version='deterministic-json-restricted-v1',state='active',registered_at=now)); db.add(ProofDelegation(delegation_uuid=delegation_id,clinic_uuid=change.source_clinic_uuid,origin_service_uuid=service,user_uuid=change.source_user_uuid,entity_type='workers',operation='update',policy_version=policy_version,issued_at=now,expires_at=now+timedelta(days=7),state='active',authority_ref='update-fixture')); request.last_reason_code=str(delegation_id); db.flush()
        source_user=db.scalar(select(User).where(User.uuid==change.source_user_uuid))
        auth=issue_for_local_operation(db,key_provider=MemoryKeyProvider({aid:ak}),key_id=aid,issuer_uuid=issuer,issuer_scope=scope,user=source_user,operation=operation,event=change,clinic_uuid=change.source_clinic_uuid,scope=scope,policy_version=policy_version,permission_code='workers.update'); store_local_evidence(db,auth); proof=ProofIssuerService(MemoryKeyProvider({pid:pk}),key_id=pid).issue(db,request_uuid=request.request_uuid); db.commit()
        return {'operation_uuid':op,'event_uuid':change.change_uuid,'entity_uuid':change.entity_uuid,'base_version':change.base_version,'entity_version':change.entity_version,'content_sha256':change.content_sha256,'user_uuid':change.source_user_uuid,'base_payload':base_change.payload,'update_payload':change.payload,'source_device_uuid':change.source_device_uuid,'source_generation_uuid':change.source_generation_uuid,'source_clinic_uuid':change.source_clinic_uuid,'revision_uuid':change.revision_uuid,'parent_revision_uuid':parent_revision,'authorization_evidence':auth,'origin_proof':proof,'authorization_public_key':pub(ak),'origin_proof_public_key':pub(pk)}

def main():
    source=os.environ['STAGE5_SOURCE_DB']; fixture=prepare_authorized_worker_source(source,source_device_uuid=uuid.uuid4(),source_generation_uuid=uuid.uuid4(),clinic_uuid=uuid.uuid4())
    result=prepare_worker_update_source(source,fixture)
    print('update_event_created=1',result)
if __name__=='__main__': main()
