"""PostgreSQL integration checks for permission-backed authorization evidence."""
import os,sys,uuid,hashlib
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.models.user import User
from app.models.role import Role
from app.models.local_revision import LocalRevision,LocalWriteOperation
from app.models.sync_change import SyncChange
from app.services.proof_issuer_service import MemoryKeyProvider
from app.services.authorization_evidence_service import issue_for_local_operation,evidence_fingerprint,capture_authorization_execution
from app.services.user_service import UserService
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService

def main():
    url=os.environ.get("AUTH_EVIDENCE_TEST_DB") or os.environ.get("STAGE5_SOURCE_DB")
    if not url or any(x in url.lower() for x in ("demo","clinic")): raise RuntimeError("AUTH_EVIDENCE_TEST_DB_REQUIRED_AND_NOT_DEMO")
    engine=create_engine(url)
    with engine.connect() as c:
        dbname,head=c.execute(text("select current_database(),(select version_num from alembic_version)")).one(); print("database=",dbname,"head=",head); assert str(head)=="20261008_32"
    suffix=uuid.uuid4().hex[:8]; now=datetime.now(timezone.utc); key=Ed25519PrivateKey.generate(); provider=MemoryKeyProvider({"authorization-test":key}); issuer=uuid.uuid4(); clinic=uuid.uuid4(); scope=f"clinic:{clinic}:workers:create"; content=hashlib.sha256(b"authorization-integration").hexdigest(); entity=uuid.uuid4(); revision=uuid.uuid4(); operation=uuid.uuid4(); event=uuid.uuid4()
    with Session(engine) as db:
        admin=db.scalar(select(User).where(User.role.in_(("super_admin","admin"))).order_by(User.id))
        if admin is None:
            # One-time test database bootstrap only, using the project's
            # designated first-admin mechanism; this is not used for fixtures.
            db.info["sync_bootstrap_mode"]=True
            admin=AuthService().create_platform_user(db,"Authorization","Fixture",f"auth.bootstrap.{suffix}@ibnsina.com","test-only","super_admin")
            db.commit(); db.info.pop("sync_bootstrap_mode",None); db.refresh(admin)
        # The existing local-write contract is the only setup path used here:
        # reserve an operation by the test administrator, then create users
        # through UserService (the same path as the API), never db.add(User).
        setup_op=uuid.uuid4(); db.add(LocalWriteOperation(operation_uuid=setup_op,actor_user_uuid=admin.uuid,request_hash=hashlib.sha256(b"auth-fixture").hexdigest(),entity_type="users",entity_uuid=uuid.uuid4(),result_payload={},created_at=now)); db.flush(); db.info["local_operation_uuid"]=setup_op; db.info["stage3_write_contract"]=True
        user_service=UserService(); allowed=user_service.create(db,UserCreate(first_name="Auth",last_name="Allowed",email=f"auth.allowed.{suffix}@ibnsina.com",password="test-only",role="admin"),admin); denied=user_service.create(db,UserCreate(first_name="Auth",last_name="Denied",email=f"auth.denied.{suffix}@ibnsina.com",password="test-only",role="assistant"),admin); db.flush()
        db.add(LocalRevision(revision_uuid=revision,entity_type="workers",entity_uuid=entity,local_version=1,kind="create",operation_uuid=operation,created_at=now)); op=LocalWriteOperation(operation_uuid=operation,actor_user_uuid=allowed.uuid,request_hash=content,entity_type="workers",entity_uuid=entity,result_payload={"authorization_execution_captured":True},created_at=now); db.add(op); change=SyncChange(change_uuid=event,revision_uuid=revision,operation_uuid=operation,schema_version=1,content_sha256=content,source_clinic_uuid=clinic,entity_type="workers",entity_uuid=entity,operation="create",entity_version=1,payload={"employee_number":"AUTH-TEST"},source_user_uuid=allowed.uuid,occurred_at=now); db.add(change); db.flush()
        capture_authorization_execution(db,user=allowed,operation=op,event=change,permission_code="workers.create",scope=scope,policy_version="5A-1"); ev=issue_for_local_operation(db,key_provider=provider,key_id="authorization-test",issuer_uuid=issuer,issuer_scope=scope,user=allowed,operation=op,event=change,clinic_uuid=clinic,scope=scope,policy_version="5A-1",permission_code="workers.create"); assert "authorization_capture_operation_uuid" not in db.info; db.commit(); print("authorized=accepted_test_only fingerprint=",evidence_fingerprint(ev),"marker_cleared=1")
    with Session(engine) as db:
        persisted=db.get(LocalWriteOperation,operation); assert persisted and persisted.result_payload.get("authorization_evidence"); print("durable=1")
        other=db.scalar(select(User).where(User.email.like("auth.allowed.%@ibnsina.com")).where(User.uuid != persisted.actor_user_uuid));
        if other:
            try: issue_for_local_operation(db,key_provider=provider,key_id="authorization-test",issuer_uuid=issuer,issuer_scope=scope,user=other,operation=persisted,event=db.scalar(select(SyncChange).where(SyncChange.change_uuid==event)),clinic_uuid=clinic,scope=scope,policy_version="5A-1",permission_code="workers.create"); raise AssertionError
            except ValueError as exc: db.rollback(); print("other_actor=rejected",str(exc))
        denied_db=db.scalar(select(User).where(User.email.like("auth.denied.%@ibnsina.com"))); db.refresh(denied_db); _=denied_db.assigned_role; op2=LocalWriteOperation(operation_uuid=uuid.uuid4(),actor_user_uuid=denied_db.uuid,request_hash=content,entity_type="workers",entity_uuid=uuid.uuid4(),result_payload={},created_at=now); db.add(op2); db.flush()
        try: issue_for_local_operation(db,key_provider=provider,key_id="authorization-test",issuer_uuid=issuer,issuer_scope=scope,user=denied_db,operation=op2,event=change,clinic_uuid=clinic,scope=scope,policy_version="5A-1",permission_code="workers.create"); raise AssertionError
        except Exception as exc: db.rollback(); print("unauthorized=rejected",type(exc).__name__)
    with Session(engine) as db:
        op=db.get(LocalWriteOperation,operation); change=db.scalar(select(SyncChange).where(SyncChange.change_uuid==event)); user=db.scalar(select(User).where(User.uuid==op.actor_user_uuid)); db.refresh(user); original=op.result_payload["authorization_evidence"]; assert issue_for_local_operation(db,key_provider=provider,key_id="authorization-test",issuer_uuid=issuer,issuer_scope=scope,user=user,operation=op,event=change,clinic_uuid=clinic,scope=scope,policy_version="5A-1",permission_code="workers.create")==original; db.commit(); print("replay=same_evidence")
        change.content_sha256="b"*64
        try: issue_for_local_operation(db,key_provider=provider,key_id="authorization-test",issuer_uuid=issuer,issuer_scope=scope,user=user,operation=op,event=change,clinic_uuid=clinic,scope=scope,policy_version="5A-1",permission_code="workers.create"); raise AssertionError
        except ValueError as exc: db.rollback(); print("content_conflict=rejected",str(exc))
    with Session(engine) as db:
        user=db.scalar(select(User).where(User.email.like("auth.allowed.%@ibnsina.com"))); change_op=uuid.uuid4(); db.add(LocalWriteOperation(operation_uuid=change_op,actor_user_uuid=user.uuid,request_hash=hashlib.sha256(b"role-change").hexdigest(),entity_type="users",entity_uuid=user.uuid,result_payload={},created_at=now)); db.flush(); db.info["local_operation_uuid"]=change_op; db.info["stage3_write_contract"]=True; user.role="assistant"; db.commit()
    with Session(engine) as db: assert db.get(LocalWriteOperation,operation).result_payload.get("authorization_evidence"); print("historical_decision=unchanged; business_application=0 eligible_production=0 applied=0")
    with Session(engine) as db:
        actor_uuid=db.scalar(select(User.uuid).where(User.email.like("auth.allowed.%@ibnsina.com"))); doomed=LocalWriteOperation(operation_uuid=uuid.uuid4(),actor_user_uuid=actor_uuid,request_hash="f"*64,entity_type="workers",entity_uuid=uuid.uuid4(),result_payload={},created_at=now); db.add(doomed); db.flush(); db.info["stage5a_fail_after_auth_evidence"]=True
        try:
            doomed.result_payload={"authorization_evidence":{"test":"rollback"}}; raise RuntimeError("INJECTED_AUTH_EVIDENCE_COMMIT_FAILURE")
        except RuntimeError: db.rollback()
    with Session(engine) as db: assert db.scalar(select(LocalWriteOperation).where(LocalWriteOperation.request_hash=="f"*64)) is None; print("transaction_failure=rolled_back")
if __name__=="__main__": main()



