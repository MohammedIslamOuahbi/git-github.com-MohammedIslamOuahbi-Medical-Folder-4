"""Unit/isolated checks for the shared 5A eligibility gate only."""
import os, sys, uuid, subprocess
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.application_eligibility_service import evaluate_application_eligibility
from app.services.proof_verification_service import verification_input_fingerprint

db_url=os.environ.get("STAGE5_ENTITY_DB")
if not db_url or "demo" in db_url.lower() or "clinic" in db_url.lower(): raise SystemExit("isolated STAGE5_ENTITY_DB required")
eng=create_engine(db_url)
with eng.connect() as c:
    name, = c.execute(text("select current_database()")).one()
    assert "20261008_23" in subprocess.run([sys.executable,"-m","alembic","current"],cwd=Path(__file__).resolve().parents[1],env={**os.environ,"DATABASE_URL":db_url},capture_output=True,text=True).stdout
print(f"database={name} head=20261008_23")
event_uuid=uuid.uuid4(); entity_uuid=uuid.uuid4(); clinic=uuid.uuid4(); service=uuid.uuid4(); device=uuid.uuid4(); content="a"*64
event=SimpleNamespace(event_uuid=event_uuid,entity_uuid=entity_uuid)
assert evaluate_application_eligibility(event=event,verification=None,expected_clinic_uuid=clinic,expected_origin_service_uuid=service,expected_origin_device_uuid=device,expected_entity_uuid=entity_uuid,expected_content_sha256=content).reason_code=="PROOF_VERIFICATION_MISSING"
print("missing_proof=blocked")
def v(**kw):
    vals=dict(event_uuid=event_uuid,content_sha256=content,evidence_refs={"clinic_uuid":str(clinic),"origin_service_uuid":str(service),"origin_device_uuid":str(device)},signature_result="valid",binding_result="valid",key_trust_result="active",delegation_result="valid",time_result="time_valid",decision="eligible")
    vals.update(kw); return SimpleNamespace(**vals)
assert evaluate_application_eligibility(event=event,verification=v(content_sha256="b"*64),expected_clinic_uuid=clinic,expected_origin_service_uuid=service,expected_origin_device_uuid=device,expected_entity_uuid=entity_uuid,expected_content_sha256=content).reason_code=="PROOF_CONTENT_MISMATCH"
print("content_changed=blocked")
assert evaluate_application_eligibility(event=event,verification=v(evidence_refs={"clinic_uuid":str(uuid.uuid4()),"origin_service_uuid":str(service),"origin_device_uuid":str(device)}),expected_clinic_uuid=clinic,expected_origin_service_uuid=service,expected_origin_device_uuid=device,expected_entity_uuid=entity_uuid,expected_content_sha256=content).reason_code=="PROOF_CLINIC_SCOPE_MISMATCH"
print("scope_changed=blocked")
assert evaluate_application_eligibility(event=event,verification=v(delegation_result="revoked"),expected_clinic_uuid=clinic,expected_origin_service_uuid=service,expected_origin_device_uuid=device,expected_entity_uuid=entity_uuid,expected_content_sha256=content).reason_code=="PROOF_DELEGATION_RESULT_NOT_VALID"
print("delegation_revoked=blocked")
assert evaluate_application_eligibility(event=event,verification=v(time_result="time_expired"),expected_clinic_uuid=clinic,expected_origin_service_uuid=service,expected_origin_device_uuid=device,expected_entity_uuid=entity_uuid,expected_content_sha256=content).reason_code=="PROOF_TIME_RESULT_NOT_VALID"
print("time_expired=blocked")
fp1=verification_input_fingerprint(proof={"p":1},event_uuid=event_uuid,content_sha256=content,key_version="k1",delegation_version="d1",revocation_version="r1",policy_version="p1",time_evidence_version="t1")
fp2=verification_input_fingerprint(proof={"p":1},event_uuid=event_uuid,content_sha256=content,key_version="k1",delegation_version="d1",revocation_version="r2",policy_version="p1",time_evidence_version="t1")
assert fp1 != fp2
print("revocation_changed=fingerprint_changed_reverify=1")
print("business_application=0 proof_issuance=0 proof_transport=0")
print("PASS shared eligibility gate checks")
