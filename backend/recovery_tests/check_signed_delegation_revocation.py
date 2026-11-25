"""Focused test of signed delegation revocation (no accept_incoming)."""
from __future__ import annotations
import os, uuid, base64
from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models.proof_trust import ProofDelegation, ProofRevocation
from app.services.proof_revocation_service import register_and_revoke_delegation
from app.services.proof_verification_service import revocation_canonical_bytes
from recovery_tests.check_http_origin_proof_auto_reconciliation import reconciliation_scenario

def main():
    source=os.environ["STAGE5_SOURCE_DB"]; target=os.environ["STAGE5_TARGET_DB"]
    with reconciliation_scenario(source,target,scenario="medical_visit_update",local_pending=True) as f:
        engine=create_engine(target)
        with Session(engine) as db:
            delegation=db.scalar(select(ProofDelegation).order_by(ProofDelegation.issued_at.desc()))
            assert delegation is not None
            record={"revocation_uuid":str(uuid.uuid4()),"target_type":"delegation","target_ref":str(delegation.delegation_uuid),"reason_code":"fixture_compromise","effective_at_declared":datetime.now(timezone.utc).isoformat(),"authority_key_id":f["revocation_authority_key_id"],"policy_version":delegation.policy_version,"target_clinic_uuid":str(delegation.clinic_uuid),"target_origin_service_uuid":str(delegation.origin_service_uuid),"canonicalization_version":"deterministic-json-restricted-v1","authority_ref":"fixture-revocation-authority"}
            record["signature"]=f["sign_revocation"](revocation_canonical_bytes(record))
            row=register_and_revoke_delegation(db,record,clinic_uuid=delegation.clinic_uuid,policy_version=delegation.policy_version); db.commit()
            assert row.revocation_uuid==uuid.UUID(record["revocation_uuid"])
            db.expire_all(); assert db.get(ProofDelegation,delegation.delegation_uuid).state=="revoked"
            print("signed_delegation_revocation=accepted", "signature=valid", "authority_scope=valid", "delegation_state=revoked")
            # Bad signature must leave no row/state transition.
            bad=dict(record,revocation_uuid=str(uuid.uuid4()),signature=base64.b64encode(b"bad").decode())
            try:
                register_and_revoke_delegation(db,bad,clinic_uuid=delegation.clinic_uuid,policy_version=delegation.policy_version)
                raise AssertionError("bad revocation accepted")
            except ValueError as exc:
                assert "REVOCATION_SIGNATURE_INVALID" in str(exc); db.rollback()
            assert db.scalar(select(ProofRevocation).where(ProofRevocation.revocation_uuid==uuid.UUID(bad["revocation_uuid"]))) is None
            print("bad_signature=rejected", "no_partial_revocation=1")
            wrong_scope=dict(record,revocation_uuid=str(uuid.uuid4()),target_clinic_uuid=str(uuid.uuid4()))
            wrong_scope["signature"]=f["sign_revocation"](revocation_canonical_bytes(wrong_scope))
            try:
                register_and_revoke_delegation(db,wrong_scope,clinic_uuid=delegation.clinic_uuid,policy_version=delegation.policy_version)
                raise AssertionError("wrong scope revocation accepted")
            except ValueError as exc:
                assert "REVOCATION_AUTHORITY_SCOPE_INVALID" in str(exc); db.rollback()
            assert db.scalar(select(ProofRevocation).where(ProofRevocation.revocation_uuid==uuid.UUID(wrong_scope["revocation_uuid"]))) is None
            print("wrong_scope=rejected", "no_partial_revocation=1")
            # Exact replay is idempotent.
            replay=register_and_revoke_delegation(db,record,clinic_uuid=delegation.clinic_uuid,policy_version=delegation.policy_version); db.commit(); assert replay.revocation_uuid==row.revocation_uuid
            assert db.scalar(select(ProofRevocation).where(ProofRevocation.revocation_uuid==row.revocation_uuid)) is not None
            print("replay_same_revocation=1", "single_revocation=1")
if __name__=="__main__": main()
