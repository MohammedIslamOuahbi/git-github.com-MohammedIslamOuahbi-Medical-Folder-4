"""5A application-eligibility rejection checks; never opens application guards."""
import os, sys, uuid, subprocess
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.services.proof_verification_service import (
    validate_required_fields, verify_binding, verify_key_scope, verify_signature,
)
from app.services.sync_transport_service import SyncTransportService
from app.models.sync_device import SyncDevice

db_url = os.environ.get("STAGE5_ENTITY_DB")
if not db_url:
    raise SystemExit("STAGE5_ENTITY_DB is required (isolated database only)")
url = make_url(db_url)
if url.database and ("demo" in url.database.lower() or "clinic" in url.database.lower()):
    raise SystemExit("refusing demo/clinic database")
engine = create_engine(db_url)
with engine.connect() as c:
    db_name, head = c.execute(text("select current_database(), current_setting('server_version')")).one()
    alembic = subprocess.run([sys.executable, "-m", "alembic", "current"], cwd=Path(__file__).resolve().parents[1], env={**os.environ, "DATABASE_URL": db_url}, capture_output=True, text=True)
    if alembic.returncode != 0 or "20261008_23" not in alembic.stdout:
        raise SystemExit(f"unexpected alembic head: {alembic.stdout.strip()} {alembic.stderr.strip()}")
    print(f"database={db_name} postgres={head} alembic_head=20261008_23")

empty = {}
assert validate_required_fields(empty) == "invalid"
print("missing_proof=blocked_invalid")

proof = {"event_uuid": str(uuid.uuid4()), "content_sha256": "a" * 64, "clinic_uuid": str(uuid.uuid4()),
         "entity_type": "workers", "entity_uuid": str(uuid.uuid4()), "operation": "create",
         "revision_uuid": str(uuid.uuid4()), "origin_user_uuid": str(uuid.uuid4()),
         "origin_device_uuid": str(uuid.uuid4()), "operation_uuid": str(uuid.uuid4()),
         "authorization_policy_version": "5A-P1-20261014", "authorization_reference": "missing-fixture-proof",
         "proof_format_version": "1", "signing_key_id": "unknown", "issued_at": "2026-10-14T00:00:00Z"}
assert validate_required_fields(proof) == "valid"
proof["signature"] = "not-a-valid-signature"
assert verify_signature(proof, "not-a-public-key") == "invalid"
print("invalid_signature=blocked_invalid")
assert verify_binding(proof, event_uuid=uuid.uuid4(), content_sha256=proof["content_sha256"],
                      clinic_uuid=proof["clinic_uuid"], entity_type="workers", entity_uuid=proof["entity_uuid"],
                      operation="create", revision_uuid=proof["revision_uuid"]) == "mismatch"
print("content_or_event_mismatch=blocked_binding_mismatch")

key = SimpleNamespace(state="active", clinic_uuid=uuid.uuid4(), origin_service_uuid=uuid.uuid4(),
                      origin_device_uuid=uuid.uuid4(), algorithm="Ed25519", canonicalization_version="deterministic-json-restricted-v1", key_id="other")
assert verify_key_scope(proof, key, clinic_uuid=uuid.uuid4(), origin_service_uuid=uuid.uuid4(), origin_device_uuid=uuid.uuid4()) == "mismatch"
print("wrong_clinic_service_device_scope=blocked_mismatch")

device_uuid = uuid.uuid4()
with Session(engine) as db:
    db.add(SyncDevice(uuid=device_uuid, installation_uuid=uuid.uuid4(), device_code="fixture-rejection-" + uuid.uuid4().hex[:8],
                      device_name="fixture rejection device", device_category="desktop", is_active=False, is_revoked=True,
                      registered_at=datetime.now(timezone.utc)))
    db.commit()
with Session(engine) as db:
    try:
        SyncTransportService().authorize_device(db, device_uuid)
    except Exception as exc:
        assert "SYNC_DEVICE_NOT_AUTHORIZED" in str(exc)
        print("revoked_device=blocked_SYNC_DEVICE_NOT_AUTHORIZED")
    else:
        raise AssertionError("revoked device authorized")

print("application_eligibility=blocked_without_verified_proof")
print("business_tables_changed=0 transport_application_opened=0")
print("PASS rejection checks; accepted proof issuance/transport remains prerequisite")
