"""Smoke-test the external application worker as a real subprocess."""
from __future__ import annotations
import os, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.models.worker import Worker
from app.models.company import Company
from app.models.branch import Branch
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncEventInbox
from app.services.sync_journal import payload_sha256

def main():
    raw = os.environ.get("STAGE5_TARGET_DB", "")
    url = make_url(raw)
    if not url.database or url.database.lower() == "demo": raise RuntimeError("isolated target required")
    engine = create_engine(raw); now = datetime.now(timezone.utc)
    event_id, worker_id, revision_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    peer, publisher, generation, clinic = (uuid.uuid4() for _ in range(4))
    try:
        with Session(engine) as db:
            company = db.execute(select(Worker).limit(1)).scalar_one_or_none()
            if company is None: raise RuntimeError("target worker fixture missing")
            company_uuid = db.scalar(select(Company.uuid).where(Company.id == company.company_id)); branch_uuid = db.scalar(select(Branch.uuid).where(Branch.id == company.branch_id))
            payload = {"employee_number": "ENTRY-" + event_id.hex[:8], "first_name": "External", "last_name": "Worker", "gender": "M", "etat_actual": "active", "is_active": True, "company_uuid": str(company_uuid), "branch_uuid": str(branch_uuid)}
            db.add(SyncEventInbox(event_uuid=event_id, source_clinic_uuid=clinic, source_device_uuid=peer, source_generation_uuid=generation, source_sequence=1, entity_type="workers", entity_uuid=worker_id, revision_uuid=revision_id, parent_revision_uuid=None, operation="insert", schema_version=1, content_sha256=payload_sha256(payload), payload=payload, status="received_waiting_application", received_at=now)); db.commit()
        env = os.environ.copy(); env.update({"DATABASE_URL": raw, "DEPLOYMENT_MODE": "central_server", "WORKER_PEER": str(peer), "WORKER_PUBLISHER_DEVICE": str(publisher), "WORKER_PUBLISHER_GENERATION": str(generation), "WORKER_PUBLISHER_CLINIC": str(clinic), "SYNC_WORKER_ONCE": "1", "WORKER_BATCH_SIZE": "100"})
        subprocess.run([sys.executable, "-m", "app.sync_worker_entrypoint"], cwd=str(ROOT), env=env, check=True, timeout=30)
        with Session(engine) as db:
            row = db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid == event_id)); print("external_row", row.status, row.application_error_code, row.application_error_message); assert row.status == "applied"
            assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid == worker_id)) == 1
            assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid == worker_id)) == 1
        subprocess.run([sys.executable, "-m", "app.sync_worker_entrypoint"], cwd=str(ROOT), env=env, check=True, timeout=30)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid == worker_id)) == 1
            assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid == worker_id)) == 1
        print("external_entrypoint=applied=1 replay_no_duplicate=1")
    finally: engine.dispose()

if __name__ == "__main__": main()
