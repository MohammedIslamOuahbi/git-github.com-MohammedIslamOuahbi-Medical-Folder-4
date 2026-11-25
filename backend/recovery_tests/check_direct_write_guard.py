"""Prove direct service use is guarded without importing app.main/sync_journal."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.database import SessionLocal
from app.models.company import Company
from app.schemas.company import CompanyCreate
from app.services.company_service import CompanyService


url = make_url(settings.database_url)
assert url.database == "ibn_sina_recovery_test"
assert url.host in {"localhost", "127.0.0.1"}
name = "direct-guard-" + uuid.uuid4().hex
with SessionLocal() as db:
    try:
        CompanyService().create(db, CompanyCreate(name=name))
    except HTTPException as exc:
        assert exc.status_code == 423
        assert exc.detail["details"]["retryable"] is False
        db.rollback()
    else:
        raise AssertionError("direct service write was accepted")
    assert db.scalar(select(func.count()).select_from(Company).where(Company.name == name)) == 0
print("PASS standalone direct service import is guarded before write")
