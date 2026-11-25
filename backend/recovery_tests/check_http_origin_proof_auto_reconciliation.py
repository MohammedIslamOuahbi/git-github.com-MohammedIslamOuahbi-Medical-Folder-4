import os,sys,time,subprocess,requests,json,datetime,hashlib
from dataclasses import replace
from pathlib import Path
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.models.origin_proof import OriginProof
from app.models.sync_change import SyncChange
from app.models.origin_proof_transport import OriginProofTransportReceipt
from app.models.origin_proof_reconciliation_task import OriginProofReconciliationTask
from app.models.proof_trust_binding import ProofTrustBinding
from app.models.proof_trust import ProofTrustedKey, ProofDelegation
from app.models.sync_application import SyncApplicationDecision, SyncApplicationAttempt
from app.models.sync_conflict import SyncConflict
from app.services.revocation_chain_service import record_bytes,record_hash,CHAIN_CANONICALIZATION,GENESIS_RECORD_HASH,store_chain_record
from app.services.revocation_checkpoint_service import canonical_checkpoint_bytes,store_checkpoint
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64,uuid
from contextlib import contextmanager
from recovery_tests.check_http_origin_proof_transport import port,prepare_origin_proof_fixture,start
from recovery_tests.check_worker_service_integration import prepare_authorized_worker_source
from recovery_tests.check_worker_update_source_fixture import prepare_worker_update_source
from recovery_tests.check_medical_visit_source_fixture import prepare_medical_visit_source, prepare_medical_visit_update_source
from app.services.entity_application_service import apply_worker_entity
from app.services.entity_application_service import apply_worker_update_entity
from app.services.entity_application_service import apply_medical_visit_entity, apply_medical_visit_update_entity
from app.models.sync_transport import SyncTransportEvent
from app.services.authorization_evidence_service import store_local_evidence
from app.services.proof_verification_service import validate_required_fields
from app.models.authorization_evidence_record import AuthorizationEvidenceRecord
from app.models.company import Company
from app.models.branch import Branch
from app.models.user import User
from app.models.local_revision import LocalWriteOperation
from app.models.local_revision import LocalRevision
from app.models.worker import Worker
from app.models.medical_visit import MedicalVisit
from app.services.medical_visit_service import MedicalVisitService
from app.schemas.medical_visit import MedicalVisitUpdate
from app.models.local_revision import LocalRevision
from app.schemas.company import CompanyCreate
from app.schemas.branch import BranchCreate
from app.services.company_service import CompanyService
from app.services.branch_service import BranchService
from app.services.auth_service import AuthService
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerUpdate
from app.services.sync_application_evaluation_service import resolve_event_dependencies
from app.schemas.sync_transport import OriginProofReceiveRequest
def head32(url):
 with create_engine(url).connect() as c: return c.exec_driver_sql("select version_num from alembic_version").scalar()
@contextmanager
def reconciliation_scenario(source_url, target_url, *, scenario, local_pending):
 s=source_url; t=target_url
 if not s or not t: raise RuntimeError('PROOF_AUTO_RECONCILIATION_FIXTURE_MISSING:STAGE5_SOURCE_DB,STAGE5_TARGET_DB')
 ps=[]; authority_proc=None
 try:
  print('stage=setup source_head='+str(head32(s))+' target_head='+str(head32(t)))
  assert head32(s) == '20261008_37' and head32(t) == '20261008_37'
  f=prepare_origin_proof_fixture(s,t,include_target_event=False)
  visit_fixture=None
  if scenario == 'medical_visit_create':
   visit_fixture=prepare_medical_visit_source(s, source_device_uuid=f.src_dev, source_generation_uuid=f.gen, clinic_uuid=f.clinic)
   with Session(create_engine(s)) as _src:
    _change=_src.scalar(select(SyncChange).where(SyncChange.change_uuid==visit_fixture.event_uuid)); _proof=_src.scalar(select(OriginProof).where(OriginProof.event_uuid==visit_fixture.event_uuid))
   if _change is None or _proof is None: raise RuntimeError('MEDICAL_VISIT_SOURCE_EVENT_MISSING')
   f=replace(f,event=visit_fixture.event_uuid,proof_uuid=_proof.proof_uuid,entity=visit_fixture.visit_uuid,revision=_change.revision_uuid,operation=visit_fixture.operation_uuid,clinic=_change.source_clinic_uuid,src_dev=_change.source_device_uuid,gen=_change.source_generation_uuid)
  if scenario == 'medical_visit_update':
   visit_fixture=prepare_medical_visit_source(s, source_device_uuid=f.src_dev, source_generation_uuid=f.gen, clinic_uuid=f.clinic)
   visit_update_data=prepare_medical_visit_update_source(s, visit_fixture)
   with Session(create_engine(s)) as _src:
    _proof=_src.scalar(select(OriginProof).where(OriginProof.event_uuid==visit_update_data['event_uuid']))
   if _proof is None: raise RuntimeError('MEDICAL_VISIT_UPDATE_ORIGIN_PROOF_MISSING')
   f=replace(f,event=visit_update_data['event_uuid'],proof_uuid=_proof.proof_uuid,entity=visit_update_data['visit_uuid'],revision=uuid.UUID(str(visit_update_data['origin_proof']['revision_uuid'])),operation=visit_update_data['operation_uuid'],clinic=uuid.UUID(str(visit_update_data['origin_proof']['clinic_uuid'])),src_dev=uuid.UUID(str(visit_update_data['origin_proof']['origin_device_uuid'])),gen=f.gen)
  update_data=None
  if scenario == 'update':
   authorized=prepare_authorized_worker_source(s, source_device_uuid=f.src_dev, source_generation_uuid=f.gen, clinic_uuid=f.clinic)
   update_data=prepare_worker_update_source(s, authorized)
   with Session(create_engine(s)) as _src:
    _proof=_src.scalar(select(OriginProof).where(OriginProof.event_uuid==update_data['event_uuid']))
   if _proof is None: raise RuntimeError('UPDATE_ORIGIN_PROOF_MISSING')
   f=replace(f,event=update_data['event_uuid'],proof_uuid=_proof.proof_uuid,entity=update_data['entity_uuid'],revision=update_data['revision_uuid'],operation=update_data['operation_uuid'],clinic=update_data['source_clinic_uuid'])
   with Session(create_engine(t)) as tgtdb:
    company=tgtdb.scalar(select(Company).where(Company.uuid==uuid.UUID(str(update_data['base_payload']['company_uuid'])))); branch=tgtdb.scalar(select(Branch).where(Branch.uuid==uuid.UUID(str(update_data['base_payload']['branch_uuid']))))
    if not company or not branch or branch.company_id != company.id: raise RuntimeError('UPDATE_TARGET_DEPENDENCY_MISSING')
    existing=tgtdb.scalar(select(Worker).where(Worker.uuid==update_data['entity_uuid']))
    if existing is None:
     base=type('Event',(),{})(); base.event_uuid=uuid.uuid4(); base.source_device_uuid=update_data['source_device_uuid']; base.source_generation_uuid=update_data['source_generation_uuid']; base.source_sequence=1; base.entity_type='workers'; base.entity_uuid=update_data['entity_uuid']; base.revision_uuid=uuid.UUID(str(update_data['parent_revision_uuid'])); base.payload=update_data['base_payload']; apply_worker_entity(tgtdb,base)
   with Session(create_engine(t)) as tgtdb:
    row=tgtdb.scalar(select(Worker).where(Worker.uuid==update_data['entity_uuid']))
    if not row or row.sync_version != 1: raise RuntimeError('UPDATE_BASE_SNAPSHOT_INVALID')
  if scenario == 'update' and local_pending:
     local_admin=tgtdb.scalar(select(User).where(User.role.in_(('super_admin','admin'))).order_by(User.id))
     if local_admin is None: raise RuntimeError('UPDATE_LOCAL_PENDING_ADMIN_MISSING')
     tgtdb.info.update(sync_source_device_uuid=f.dst_dev, sync_source_generation_uuid=f.gen, sync_source_clinic_uuid=f.clinic)
     WorkerService().update(tgtdb, row.id, WorkerUpdate(first_name='LocalPendingEdit'), local_admin, 1, uuid.uuid4())
     print('local_pending_edit=committed worker_version=2')
  if os.environ.get('UPDATE_SETUP_ONLY') == '1':
   if scenario != 'update': raise RuntimeError('UPDATE_SETUP_ONLY_REQUIRES_SCENARIO_UPDATE')
   update=update_data
   with Session(create_engine(t)) as tgtdb:
    row=tgtdb.scalar(select(__import__('app.models.worker',fromlist=['Worker']).Worker).where(__import__('app.models.worker',fromlist=['Worker']).Worker.uuid==update['entity_uuid']))
    assert row and row.sync_version==1 and row.first_name==update['base_payload']['first_name']
   assert update['base_version']==1 and update['entity_version']==2
   print(json.dumps({'update_setup_only':True,'event_uuid':str(update['event_uuid']),'entity_uuid':str(update['entity_uuid']),'base_version':1,'entity_version':2,'worker_sync_version':1},sort_keys=True)); return
  # Use the real protected local write as the source event for this
  # reconciliation scenario; the transport fixture remains unchanged.
  if scenario == 'create':
   authorized=prepare_authorized_worker_source(s, source_device_uuid=f.src_dev,
       source_generation_uuid=f.gen, clinic_uuid=f.clinic)
  else:
   pass
  if scenario == 'create':
   with Session(create_engine(s)) as source_session:
    authorized_proof = source_session.scalar(select(OriginProof).where(OriginProof.event_uuid == authorized.event_uuid))
   if authorized_proof is None: raise RuntimeError("AUTHORIZED_WORKER_ORIGIN_PROOF_MISSING")
   f=replace(f, event=authorized.event_uuid, proof_uuid=authorized_proof.proof_uuid, entity=authorized.entity_uuid, revision=authorized.revision_uuid, operation=authorized.operation_uuid, clinic=authorized.clinic_uuid)
  # Prepare stable UUID dependencies through the protected local services.
  with Session(create_engine(s)) as srcdb, Session(create_engine(t)) as tgtdb:
   src_change=srcdb.scalar(select(SyncChange).where(SyncChange.change_uuid==f.event))
   payload=src_change.payload or {}
   company_uuid=payload.get("company_uuid"); branch_uuid=payload.get("branch_uuid")
   if scenario == 'medical_visit_create' and (not company_uuid or not branch_uuid):
    sw=srcdb.scalar(select(Worker).where(Worker.uuid==uuid.UUID(str(payload.get('worker_uuid')))))
    sc=srcdb.get(Company,sw.company_id) if sw else None; sb=srcdb.get(Branch,sw.branch_id) if sw else None
    company_uuid=str(sc.uuid) if sc else None; branch_uuid=str(sb.uuid) if sb else None
   if not company_uuid or not branch_uuid:
    if scenario not in ('medical_visit_create','medical_visit_update'): raise RuntimeError("WORKER_DEPENDENCY_UUIDS_MISSING_FROM_NEW_JOURNAL_EVENT")
   from app.services.sync_journal import payload_sha256
   if payload_sha256(payload) != src_change.content_sha256:
    raise RuntimeError("WORKER_DEPENDENCY_UUID_PAYLOAD_HASH_MISMATCH")
   if company_uuid and branch_uuid:
    src_company=srcdb.scalar(select(Company).where(Company.uuid==uuid.UUID(str(company_uuid))))
    src_branch=srcdb.scalar(select(Branch).where(Branch.uuid==uuid.UUID(str(branch_uuid))))
    admin=tgtdb.scalar(select(User).where(User.role.in_(("super_admin","admin"))).order_by(User.id))
    if admin is None:
     tgtdb.info["sync_bootstrap_mode"] = True
     admin=AuthService().create_platform_user(tgtdb, "Dependency", "Fixture", "dependency.fixture@ibnsina.test", "test-only", "admin")
     tgtdb.commit(); tgtdb.info.pop("sync_bootstrap_mode", None)
    target_company=tgtdb.scalar(select(Company).where(Company.uuid==src_company.uuid)) if src_company else None
    if target_company is None and src_company and admin:
     target_company=CompanyService().create(tgtdb, CompanyCreate(name=src_company.name,address=src_company.address,phone=src_company.phone,email=src_company.email), admin, uuid.uuid4(), trusted_uuid=src_company.uuid)
    target_branch=tgtdb.scalar(select(Branch).where(Branch.uuid==src_branch.uuid)) if src_branch else None
    if target_branch is None and src_branch and target_company:
     tgtdb.info.update(local_operation_uuid=uuid.uuid4(),stage3_write_contract=True)
     branch_operation = tgtdb.info["local_operation_uuid"]
     tgtdb.add(LocalWriteOperation(operation_uuid=branch_operation, actor_user_uuid=admin.uuid, request_hash="dependency-fixture", entity_type="branches", entity_uuid=src_branch.uuid, result_payload={}, created_at=datetime.datetime.now(datetime.timezone.utc)))
     tgtdb.flush()
     target_branch=BranchService().create(tgtdb, BranchCreate(company_id=target_company.id,name=src_branch.name,location=src_branch.location,address=src_branch.address), trusted_uuid=src_branch.uuid)
     tgtdb.commit(); tgtdb.info.pop("local_operation_uuid",None); tgtdb.info.pop("stage3_write_contract",None)
    if target_branch and target_company and target_branch.company_id != target_company.id: raise RuntimeError("DEPENDENCY_BRANCH_COMPANY_MISMATCH")
   if scenario == 'medical_visit_create':
    src_worker=srcdb.scalar(select(Worker).where(Worker.uuid==uuid.UUID(str(payload.get('worker_uuid')))))
    if src_worker is not None and tgtdb.scalar(select(Worker).where(Worker.uuid==src_worker.uuid)) is None:
     we=type('WorkerEvent',(),{})(); we.entity_uuid=src_worker.uuid; we.event_uuid=uuid.uuid4(); we.operation_uuid=uuid.uuid4(); we.revision_uuid=uuid.uuid4(); we.source_sequence=1; we.entity_type='workers'; we.source_device_uuid=f.src_dev; we.payload={'employee_number':src_worker.employee_number,'first_name':src_worker.first_name,'last_name':src_worker.last_name,'gender':src_worker.gender,'etat_actual':src_worker.etat_actual,'is_active':src_worker.is_active,'company_uuid':company_uuid,'branch_uuid':branch_uuid}; apply_worker_entity(tgtdb,we); tgtdb.commit()
  if scenario == 'medical_visit_update':
   with Session(create_engine(t)) as tgtdb:
    if tgtdb.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_fixture.visit_uuid)) is None:
     base=type('VisitEvent',(),{})(); base.event_uuid=uuid.uuid4(); base.operation_uuid=visit_fixture.operation_uuid; base.entity_uuid=visit_fixture.visit_uuid; base.revision_uuid=uuid.UUID(str(visit_fixture.origin_proof['revision_uuid'])); base.payload=visit_fixture.request_payload
     assert apply_medical_visit_entity(tgtdb,base).get('status')=='applied'; tgtdb.commit()
   with Session(create_engine(t)) as verify_base:
    base_visit=verify_base.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_fixture.visit_uuid))
    if base_visit is None or int(base_visit.version)!=1: raise RuntimeError('MEDICAL_VISIT_UPDATE_BASE_SNAPSHOT_INVALID')
   if local_pending:
    with Session(create_engine(t)) as localdb:
     local_visit=localdb.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_fixture.visit_uuid))
     local_user=localdb.scalar(select(User).where(User.role.in_(('super_admin','admin','doctor'))).order_by(User.id))
     if local_visit is None or local_user is None: raise RuntimeError('MEDICAL_VISIT_UPDATE_LOCAL_USER_MISSING')
     from app.services.permission_service import permission_service
     if 'medical_visits.update' not in permission_service.get_effective_permission_codes(local_user):
      localdb.info['sync_bootstrap_mode']=True
      local_user=AuthService().create_platform_user(localdb,'Visit','Pending','visit-pending-'+uuid.uuid4().hex[:8]+'@test.local','test-only','super_admin')
      localdb.commit(); localdb.info.pop('sync_bootstrap_mode',None)
     permission_service.require_permission(local_user,'medical_visits.update')
     localdb.info.update(sync_source_device_uuid=f.dst_dev,sync_source_generation_uuid=f.gen,sync_source_clinic_uuid=f.clinic,sync_source_user_uuid=local_user.uuid)
     MedicalVisitService().update(localdb, local_visit.id, MedicalVisitUpdate(site_name='LocalPendingVisitEdit'), local_user, 1, uuid.uuid4())
     localdb.commit(); print('medical_visit_local_pending=committed version=2 permission_verified=1')
  with Session(create_engine(t)) as depdb:
   dep_event=type("DependencyEvent", (), {"payload": payload})()
   dependency_resolution=resolve_event_dependencies(depdb, dep_event)
   for relation, details in dependency_resolution.items():
    parent_uuid = payload.get("company_uuid") if relation in {"branch", "drilling_site"} else None
    parent_id = dependency_resolution.get("company", {}).get("local_id") if relation in {"branch", "drilling_site"} else None
    if not details.get("required_uuid"):
     status, reason = "not_required", None
    else:
     status = "resolved" if details.get("matched") and details.get("belongs_to_company", True) and details.get("belongs_to_branch", True) else "rejected"
     reason = None if status == "resolved" else ("DEPENDENCY_MISSING" if not details.get("matched") else "DEPENDENCY_RELATIONSHIP_MISMATCH")
    print("dependency", {"relation": relation, "requested_uuid": details.get("required_uuid"), "matched_local_id": details.get("local_id"), "parent_uuid": parent_uuid, "parent_id": parent_id, "status": status, "reason": reason})
   assert all(d.get("matched") for d in dependency_resolution.values() if d.get("required_uuid")), "DEPENDENCY_MISSING"
   assert dependency_resolution.get("branch", {}).get("belongs_to_company", True), "DEPENDENCY_BRANCH_COMPANY_MISMATCH"
   assert dependency_resolution.get("drilling_site", {}).get("belongs_to_branch", True), "DEPENDENCY_SITE_BRANCH_MISMATCH"
   if os.environ.get("DEPENDENCY_ONLY") == "1":
    print("dependency_only=passed")
    return
  # Fixture-only local trust and signed chain/checkpoint setup.
  authority=Ed25519PrivateKey.generate(); authority_uuid=uuid.uuid4(); checkpoint_authority_pub=base64.b64encode(authority.public_key().public_bytes_raw()).decode()
  with Session(create_engine(t)) as db:
   with Session(create_engine(s)) as srcdb:
    pr=srcdb.scalar(select(OriginProof).where(OriginProof.proof_uuid==f.proof_uuid))
    source_key=srcdb.scalar(select(ProofTrustedKey).where(ProofTrustedKey.key_id==pr.proof.get("signing_key_id")))
    source_auth=srcdb.scalar(select(AuthorizationEvidenceRecord).where(AuthorizationEvidenceRecord.operation_uuid==f.operation))
    auth_keyrow=srcdb.scalar(select(ProofTrustedKey).where(ProofTrustedKey.key_id==source_auth.envelope.get("issuer_key_id"))) if source_auth else None
    source_delegation=srcdb.get(ProofDelegation, uuid.UUID(str(pr.proof.get("authorization_reference"))))
    proof_origin_service=uuid.UUID(str(pr.proof.get("origin_service_uuid")))
    chain_scope="origin:"+str(f.clinic)+":"+str(proof_origin_service)
    if source_key is None or source_auth is None or auth_keyrow is None or source_delegation is None:
     raise RuntimeError("AUTHORIZED_WORKER_TRUST_OR_EVIDENCE_MISSING")
    if db.scalar(select(ProofTrustedKey).where(ProofTrustedKey.key_id==source_key.key_id)) is None:
     db.add(ProofTrustedKey(key_id=source_key.key_id,clinic_uuid=source_key.clinic_uuid,origin_service_uuid=source_key.origin_service_uuid,origin_device_uuid=source_key.origin_device_uuid,registration_authority_uuid=source_key.registration_authority_uuid,public_key=source_key.public_key,algorithm=source_key.algorithm,canonicalization_version=source_key.canonicalization_version,state="active",registered_at=source_key.registered_at))
    if db.scalar(select(ProofTrustedKey).where(ProofTrustedKey.key_id==auth_keyrow.key_id)) is None:
     db.add(ProofTrustedKey(key_id=auth_keyrow.key_id,clinic_uuid=auth_keyrow.clinic_uuid,origin_service_uuid=auth_keyrow.origin_service_uuid,origin_device_uuid=auth_keyrow.origin_device_uuid,registration_authority_uuid=auth_keyrow.registration_authority_uuid,public_key=auth_keyrow.public_key,algorithm=auth_keyrow.algorithm,canonicalization_version=auth_keyrow.canonicalization_version,state="active",registered_at=auth_keyrow.registered_at))
    if db.get(ProofDelegation, source_delegation.delegation_uuid) is None:
     db.add(ProofDelegation(delegation_uuid=source_delegation.delegation_uuid,clinic_uuid=source_delegation.clinic_uuid,origin_service_uuid=source_delegation.origin_service_uuid,user_uuid=source_delegation.user_uuid,entity_type=source_delegation.entity_type,operation=source_delegation.operation,policy_version=source_delegation.policy_version,issued_at=source_delegation.issued_at,expires_at=source_delegation.expires_at,state=source_delegation.state,authority_ref=source_delegation.authority_ref))
    store_local_evidence(db, dict(source_auth.envelope))
   keyrow=db.scalar(select(ProofTrustedKey).where(ProofTrustedKey.key_id==pr.proof.get("signing_key_id")))
   binding=ProofTrustBinding(binding_uuid=uuid.uuid4(),signing_key_id=keyrow.key_id,issuer_uuid=proof_origin_service,revocation_authority_uuid=authority_uuid,chain_scope=chain_scope,chain_contract_version="revocation-chain-v1",clinic_uuid=f.clinic,origin_service_uuid=proof_origin_service,policy_version="5A-P1-20261014",state="active",binding_version=1,approval_source="local-trust-admin:fixture",created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),updated_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)); db.add(binding); db.flush()
   revocation_key_id="fixture-revocation-"+uuid.uuid4().hex[:10]
   db.add(ProofTrustedKey(key_id=revocation_key_id,clinic_uuid=f.clinic,origin_service_uuid=proof_origin_service,origin_device_uuid=None,registration_authority_uuid=authority_uuid,public_key=checkpoint_authority_pub,algorithm="Ed25519",canonicalization_version="deterministic-json-restricted-v1",state="active",registered_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
   chain={"record_uuid":uuid.uuid4(),"authority_uuid":authority_uuid,"chain_scope":chain_scope,"contract_version":"revocation-chain-v1","canonicalization_version":CHAIN_CANONICALIZATION,"sequence":1,"previous_record_hash":GENESIS_RECORD_HASH,"record":{"target_type":"key","target_ref":keyrow.key_id,"reason":"fixture"}}
   chain["record_hash"]=record_hash(chain); chain["signature"]=base64.b64encode(authority.sign(record_bytes(chain))).decode(); store_chain_record(db,chain,authority_public_key=checkpoint_authority_pub)
   cp={"checkpoint_uuid":str(uuid.uuid4()),"authority_uuid":str(authority_uuid),"authority_key_id":"fixture-authority","chain_scope":chain_scope,"contract_version":"revocation-chain-v1","policy_version":"5A-P1-20261014","covered_sequence":1,"covered_chain_hash":chain["record_hash"],"challenge":"fixture-challenge","destination_device_uuid":str(f.dst_dev)}
   cp["signature"]=base64.b64encode(authority.sign(canonical_checkpoint_bytes(cp))).decode(); store_checkpoint(db,cp,public_key=checkpoint_authority_pub); db.commit(); print("fixture_checkpoint=complete checkpoint_uuid="+cp["checkpoint_uuid"]+" authority_key_id="+cp["authority_key_id"]+" pub_sha256="+hashlib.sha256(base64.b64decode(checkpoint_authority_pub)).hexdigest()+" canonical_sha256="+hashlib.sha256(canonical_checkpoint_bytes(cp)).hexdigest())
  ap=port(); aenv=dict(os.environ); aenv["PYTHONPATH"]="."; aenv["TIME_AUTHORITY_PORT"]=str(ap); authority_proc=subprocess.Popen([sys.executable,"recovery_tests/_run_test_time_authority.py"],cwd=ROOT,env=aenv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); ps.append(authority_proc); line=authority_proc.stdout.readline().strip(); info=json.loads(line); time_authority_pub=info["public_key"]; authority_url=f"http://127.0.0.1:{ap}"; print("time_authority_pid=",authority_proc.pid,"url=",authority_url)
  sp,tp=port(),port(); test_api_env={"ORIGIN_PROOF_RECONCILIATION_TEST":"1"}; ps.extend([start(s,sp,test_api_env),start(t,tp,test_api_env)])
  print('api_pids=',[p.pid for p in ps])
  deadline=time.monotonic()+20
  while time.monotonic()<deadline:
   try:
    if requests.get(f'http://127.0.0.1:{tp}/openapi.json',timeout=1).ok: break
   except requests.RequestException: pass
   time.sleep(.2)
  with Session(create_engine(s)) as db:
   proof=db.scalar(select(OriginProof).where(OriginProof.proof_uuid==f.proof_uuid)); change=db.scalar(select(SyncChange).where(SyncChange.change_uuid==f.event)); proof_payload=dict(proof.proof); event_payload={'event_uuid':str(f.event),'source_sequence':1,'source_clinic_uuid':str(f.clinic),'source_device_uuid':str(f.src_dev),'source_generation_uuid':str(f.gen),'schema_version':1,'entity_type':change.entity_type,'entity_uuid':str(change.entity_uuid),'revision_uuid':str(change.revision_uuid),'parent_revision_uuid':str(change.parent_revision_uuid) if change.parent_revision_uuid else None,'base_version':change.base_version,'entity_version':change.entity_version,'operation':change.operation,'payload':change.payload,'publish_sequence':1,'publication_channel':f.channel,'publication_source_device_uuid':str(f.src_dev),'publication_source_generation_uuid':str(f.gen),'content_sha256':change.content_sha256}
  h={'X-Sync-Device-UUID':str(f.dst_dev),'X-Sync-Device-Secret':f.dst_secret}; body={'contract_version':'2.1','proof_uuid':str(f.proof_uuid),'event_uuid':str(f.event),'content_sha256':change.content_sha256,'source_device_uuid':str(f.src_dev),'source_generation_uuid':str(f.gen),'source_clinic_uuid':str(f.clinic),'channel':f.channel,'proof':proof_payload}
  try:
   OriginProofReceiveRequest.model_validate(body)
   print('proof_receive_model_validate=ok')
  except Exception as exc:
   errors=getattr(exc, 'errors', lambda: [])()
   print('proof_receive_model_validate=failed', [{"loc":e.get("loc"),"type":e.get("type"),"msg":e.get("msg")} for e in errors])
   raise
  required_fields=("event_uuid","content_sha256","clinic_uuid","entity_type","operation","revision_uuid","authorization_policy_version","proof_format_version","signing_key_id","issued_at","origin_user_uuid","origin_device_uuid","origin_service_uuid","operation_uuid","authorization_reference")
  print('proof_receive_binding_check=', validate_required_fields(proof_payload), 'missing_fields=', [k for k in required_fields if proof_payload.get(k) in (None,'')],
        'non_string_fields=', {k:type(v).__name__ for k,v in proof_payload.items() if not isinstance(v,str)},
        'operation=', proof_payload.get('operation'), 'content_len=', len(proof_payload.get('content_sha256','')),
        'event_match=', str(proof_payload.get('event_uuid')) == str(f.event),
        'content_match=', proof_payload.get('content_sha256') == change.content_sha256)
  r=requests.post(f'http://127.0.0.1:{tp}/api/v1/sync/v2/proof-receive',json=body,headers=h,timeout=10); print('proof_receive_status=',r.status_code, r.text); r.raise_for_status()
  with Session(create_engine(t)) as db: rec=db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==f.event)); assert rec is not None; print('receipt_uuid=',rec.receipt_uuid)
  evbody={'contract_version':'2.1','source_clinic_uuid':str(f.clinic),'source_device_uuid':str(f.src_dev),'source_generation_uuid':str(f.gen),'channel':f.channel,'events':[event_payload],'limit':100,'publisher_device_uuid':str(f.src_dev),'publisher_generation_uuid':str(f.gen),'publisher_clinic_uuid':str(f.clinic)}
  r=requests.post(f'http://127.0.0.1:{tp}/api/v1/sync/v2/receive',json=evbody,headers=h,timeout=10); print('event_receive_status=',r.status_code); r.raise_for_status()
  with Session(create_engine(t)) as db: task=db.scalar(select(OriginProofReconciliationTask).where(OriginProofReconciliationTask.event_uuid==f.event)); print('task=',task.task_uuid if task else None); assert task is not None
  env=dict(os.environ); env['DATABASE_URL']=t; env['RECONCILIATION_EVENT_UUID']=str(f.event); env['RECONCILIATION_PROOF_UUID']=str(f.proof_uuid); env['RECONCILIATION_PEER_UUID']=str(f.dst_dev); env['RECONCILIATION_TASK_UUID']=str(task.task_uuid); env['TEST_REVOCATION_AUTHORITY_PUBLIC_KEY']=checkpoint_authority_pub; env['TIME_AUTHORITY_URL']=authority_url; env['TEST_TIME_AUTHORITY_PUBLIC_KEY']=time_authority_pub; env['RECONCILIATION_CHAIN_SCOPE']=chain_scope; env['CHECKPOINT_CHALLENGE']='fixture-challenge'; env['CHECKPOINT_UUID']=cp['checkpoint_uuid']; env['CHECKPOINT_COVERED_SEQUENCE']=str(cp['covered_sequence']); env['CHECKPOINT_COVERED_CHAIN_HASH']=cp['covered_chain_hash']; env['RECONCILIATION_POLICY_VERSION']='5A-P1-20261014'; env['TIME_VALID_FROM']=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=1)).isoformat(); env['TIME_VALID_UNTIL']=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=1)).isoformat()
  w=subprocess.Popen([sys.executable,'recovery_tests/_run_origin_proof_reconciliation_worker.py'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); print('worker_started pid=',w.pid); out,err=w.communicate(timeout=30); print(out); print(err); assert w.returncode==0
  # New-session durability gate: the worker's accepted_test_only result must
  # complete its leased task, while the production application decision stays
  # explicitly blocked.  This is intentionally independent of worker memory.
  with Session(create_engine(t)) as db:
   persisted_task=db.get(OriginProofReconciliationTask, task.task_uuid)
   persisted_decision=db.scalar(select(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid==f.event))
   persisted_attempt=db.scalar(select(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid==f.event))
   assert persisted_task is not None and persisted_task.state == "completed"
   assert persisted_decision is not None and persisted_decision.decision in {"blocked_structural", "blocked_authorization_evidence"}
   assert (persisted_decision.evidence_refs or {}).get("authorization", {}).get("status") == "accepted_test_only"
   assert persisted_attempt is not None and persisted_attempt.input_fingerprint
   print("durability task_state=",persisted_task.state,"decision=",persisted_decision.decision,"authorization=accepted_test_only","evidence_uuid=",(persisted_decision.evidence_refs or {}).get("authorization", {}).get("evidence_uuid"),"input_fingerprint=",persisted_attempt.input_fingerprint,"business_application=0","eligible_production=0","applied=0")
   if persisted_decision.decision.startswith("blocked"):
    print("blocked_structural_reason=", persisted_decision.reason_code,
          "blocked_evidence_checks=", json.dumps((persisted_decision.evidence_refs or {}).get("verification", {}), sort_keys=True))
   print(json.dumps({"reconciliation_result":{"task_uuid":str(persisted_task.task_uuid),"event_uuid":str(f.event),"status":"accepted_test_only","input_fingerprint":getattr(persisted_task,"result_fingerprint",None)}}, sort_keys=True))
   if scenario == 'update':
    target_event=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==f.event))
    class UpdateEvent: pass
    ue=UpdateEvent(); ue.event_uuid=target_event.event_uuid; ue.source_device_uuid=target_event.source_device_uuid; ue.entity_type=target_event.entity_type; ue.entity_uuid=target_event.entity_uuid; ue.revision_uuid=target_event.revision_uuid; ue.payload=target_event.payload; ue.base_version=1; ue.operation_uuid=f.operation
    applied=apply_worker_update_entity(db,ue)
    if local_pending:
     assert applied.get('status') == 'conflict'
     print('update_application=conflict reason='+str(applied.get('reason'))+' business_tables_changed_in_test=1 production_application_enabled=0')
    else:
     assert applied.get('status')=='applied'
    print('update_application=applied_test_only version=2 business_tables_changed_in_test=1 production_application_enabled=0')
   elif scenario == 'medical_visit_create':
    target_event=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==f.event))
    class VisitEvent: pass
    ve=VisitEvent(); ve.event_uuid=target_event.event_uuid; ve.operation_uuid=f.operation; ve.entity_uuid=target_event.entity_uuid; ve.revision_uuid=target_event.revision_uuid; ve.payload=target_event.payload
    applied=apply_medical_visit_entity(db,ve); assert applied.get('status') == 'applied'
    print('medical_visit_application=applied_test_only revision=1 business_tables_changed_in_test=1 production_application_enabled=0')
   elif scenario == 'medical_visit_update':
    target_event=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==f.event))
    class VisitUpdateEvent: pass
    ve=VisitUpdateEvent(); ve.event_uuid=target_event.event_uuid; ve.operation_uuid=f.operation; ve.entity_uuid=target_event.entity_uuid; ve.revision_uuid=target_event.revision_uuid; ve.parent_revision_uuid=target_event.parent_revision_uuid; ve.payload=target_event.payload; ve.base_version=1
    applied=apply_medical_visit_update_entity(db,ve)
    if local_pending:
     assert applied.get('status')=='conflict' and applied.get('reason')=='BASE_VERSION_MISMATCH'
     print('medical_visit_update_application=conflict reason=BASE_VERSION_MISMATCH business_tables_changed_in_test=1 production_application_enabled=0')
    else:
     assert applied.get('status')=='applied'
     print('medical_visit_update_application=applied_test_only version=2 business_tables_changed_in_test=1 production_application_enabled=0')
   # Verify the durable application in a new session, then replay the same
   # operation through the shared application service.
   with Session(create_engine(t)) as check:
    if scenario == 'medical_visit_create':
     visit=check.scalar(select(MedicalVisit).where(MedicalVisit.uuid==f.entity)); revs=check.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==f.entity)).all(); local_changes=check.scalars(select(SyncChange).where(SyncChange.entity_uuid==f.entity)).all(); assert visit is not None and len(revs)==1 and len(local_changes)==0; print('medical_visit_durability=one_visit one_revision incoming_sync_changes=0')
    if scenario not in ('medical_visit_create','medical_visit_update'):
     worker=check.scalar(select(Worker).where(Worker.uuid==f.entity))
     revisions=check.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==f.entity).order_by(LocalRevision.local_version)).all()
     local_changes=check.scalars(select(SyncChange).where(SyncChange.entity_uuid==f.entity, SyncChange.operation_uuid != f.operation)).all()
    if scenario not in ('medical_visit_create','medical_visit_update') and local_pending:
     conflicts=check.scalars(select(SyncConflict).where(SyncConflict.incoming_change_uuid==f.event)).all()
     assert worker is not None and worker.sync_version == 2 and worker.first_name == 'LocalPendingEdit'
     assert len(conflicts) == 1 and conflicts[0].base_version == 1
     assert conflicts[0].mission_snapshot.get('first_name') == (update_data or {}).get('update_payload',{}).get('first_name')
     assert len(revisions) == 2 and len(local_changes) == 1
     print('local_conflict_durability=one_conflict local_version_preserved=1 local_sync_changes=1 incoming_sync_changes=0')
    elif scenario not in ('medical_visit_create','medical_visit_update'):
     assert worker is not None and worker.sync_version == 2
     assert len(revisions) == 2
     assert len(local_changes) == 0
    expected_name=(update_data or {}).get('update_payload',{}).get('first_name')
    if not local_pending and expected_name is not None and scenario not in ('medical_visit_create','medical_visit_update'): assert worker.first_name == expected_name
    if scenario not in ('medical_visit_create','medical_visit_update') and not local_pending:
     print('update_durability=version2 revisions=2 replay_local_sync_changes=0')
    if scenario == 'medical_visit_update':
     visit=check.scalar(select(MedicalVisit).where(MedicalVisit.uuid==f.entity)); revs=check.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==f.entity).order_by(LocalRevision.local_version)).all(); local_changes=check.scalars(select(SyncChange).where(SyncChange.entity_uuid==f.entity)).all(); print('medical_visit_update_check', {'present':visit is not None,'version':getattr(visit,'version',None),'revisions':len(revs),'sync_changes':len(local_changes)})
     if local_pending:
      conflicts=check.scalars(select(SyncConflict).where(SyncConflict.incoming_change_uuid==f.event)).all()
      assert visit is not None and visit.version==2 and visit.site_name=='LocalPendingVisitEdit' and len(revs)==2 and len(conflicts)==1 and conflicts[0].status=='physician_review' and conflicts[0].base_version==1 and len(local_changes)==1
      print('medical_visit_local_pending_durability=physician_review reason=BASE_VERSION_MISMATCH local_preserved=1 incoming_sync_changes=0')
     else:
      assert visit is not None and visit.version==2 and len(revs)==2 and len(local_changes)==0; print('medical_visit_update_durability=version2 revisions=2 incoming_sync_changes=0')
   if scenario == 'medical_visit_update':
    with Session(create_engine(t)) as replay_db:
     replay_event=replay_db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==f.event))
     class ReplayVisitEvent: pass
     replay=ReplayVisitEvent(); replay.event_uuid=replay_event.event_uuid; replay.operation_uuid=f.operation; replay.entity_uuid=replay_event.entity_uuid; replay.revision_uuid=replay_event.revision_uuid; replay.parent_revision_uuid=replay_event.parent_revision_uuid; replay.payload=replay_event.payload; replay.base_version=1
     replay_result=apply_medical_visit_update_entity(replay_db,replay)
     if local_pending: assert replay_result.get('status')=='conflict'; print('medical_visit_update_replay=status_conflict no_duplicate_conflict=1')
     else: assert replay_result.get('status')=='replay'; print('medical_visit_update_replay=status_replay no_revision_added=1')
   elif scenario not in ('medical_visit_create',):
    with Session(create_engine(t)) as replay_db:
     replay_event=replay_db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==f.event))
     class ReplayEvent: pass
     replay=ReplayEvent(); replay.event_uuid=replay_event.event_uuid; replay.source_device_uuid=replay_event.source_device_uuid; replay.entity_type=replay_event.entity_type; replay.entity_uuid=replay_event.entity_uuid; replay.revision_uuid=replay_event.revision_uuid; replay.payload=replay_event.payload; replay.base_version=1; replay.operation_uuid=f.operation
     replay_result=apply_worker_update_entity(replay_db,replay)
     if local_pending:
      assert replay_result.get('status') == 'conflict'
      print('update_replay=status_conflict no_duplicate_conflict=1')
     else:
      assert replay_result.get('status') == 'replay'
      print('update_replay=status_replay no_revision_added=1')
  yield {"event_uuid": str(f.event), "proof_uuid": str(f.proof_uuid),
         "receipt_uuid": str(rec.receipt_uuid), "task_uuid": str(task.task_uuid),
         "conflict_uuid": str(conflicts[0].uuid) if 'conflicts' in locals() and conflicts else None,
         "time_authority_url": authority_url, "time_authority_public_key": time_authority_pub,
         "checkpoint_uuid": cp.get("checkpoint_uuid"), "checkpoint_authority_public_key": checkpoint_authority_pub,
         "checkpoint_authority_uuid": cp.get("authority_uuid"), "checkpoint_chain_hash": cp.get("covered_chain_hash"),
         "chain_scope": chain_scope,
         "sign_revocation": lambda canonical: base64.b64encode(authority.sign(canonical)).decode(),
         "revocation_authority_key_id": revocation_key_id,
        "time_authority_alive": authority_proc is not None and authority_proc.poll() is None,
        "api_pids": [p.pid for p in ps if p.poll() is None]}
 finally:
  if authority_proc is not None and authority_proc.poll() is None: authority_proc.terminate(); authority_proc.wait(timeout=10)
  for p in ps:
   if p.poll() is None: p.terminate(); p.wait(timeout=10)
def main():
 s=os.environ.get('STAGE5_SOURCE_DB'); t=os.environ.get('STAGE5_TARGET_DB')
 if not s or not t: raise RuntimeError('PROOF_AUTO_RECONCILIATION_FIXTURE_MISSING:STAGE5_SOURCE_DB,STAGE5_TARGET_DB')
 with reconciliation_scenario(s, t, scenario=os.environ.get('SCENARIO','create'), local_pending=os.environ.get('UPDATE_LOCAL_PENDING') == '1') as result:
  print(json.dumps({"scenario_result": result}, sort_keys=True))
if __name__=='__main__':main()









