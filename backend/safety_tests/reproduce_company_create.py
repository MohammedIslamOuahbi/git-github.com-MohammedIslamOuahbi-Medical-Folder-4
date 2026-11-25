"""Exercise the real company HTTP route without starting or modifying the runtime.

Authentication is synthetic in this isolated app only. The actual CRUD barrier,
router, validation, repository, and exception handler are unchanged. PostgreSQL
read-only transactions and rollback-only sessions provide extra write protection.
Run from backend: venv/Scripts/python.exe -B safety_tests/reproduce_company_create.py
"""
from pathlib import Path
import hashlib
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.middleware.error_handler import http_exception_handler
from app.routers.companies import router


def snapshot():
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = connection.execute(text("SELECT to_jsonb(c)::text FROM companies c ORDER BY id")).scalars().all()
        return {"count": len(rows), "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest()}


def readonly_db():
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("SET TRANSACTION READ ONLY"))
        session = Session(bind=connection, join_transaction_mode="rollback_only")
        try:
            yield session
        finally:
            session.close()
            if transaction.is_active:
                transaction.rollback()


app = FastAPI()
app.include_router(router, prefix="/api/v1")
app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=-1)
app.dependency_overrides[get_db] = readonly_db
for exception_type in (HTTPException, RequestValidationError, Exception):
    app.add_exception_handler(exception_type, http_exception_handler)

def reproduce():
    before = snapshot()
    results = []
    with TestClient(app, raise_server_exceptions=False) as client:
        for label, email in (("form_empty_email", ""), ("normalized_optional_email", None)):
            response = client.post("/api/v1/companies", json={
                "name": "Synthetic company diagnostic", "code": "CMP-DIAGNOSTIC",
                "email": email, "phone": "", "address": "",
                "contract_start_date": "2026-10-01", "contract_end_date": "2027-10-01",
            })
            results.append({"case": label, "status": response.status_code, "body": response.json()})
    after = snapshot()
    print(json.dumps({"transport": "local HTTP TestClient, real route; synthetic authentication",
                      "responses": results, "companies_before": before, "companies_after": after,
                      "unchanged": before == after}, indent=2))
    assert before == after, "companies changed"
    assert results[0]["status"] == 422, results[0]
    assert results[1]["status"] == 423, results[1]
    assert results[1]["body"]["details"]["code"] == "OPERATION_SUSPENDED_FOR_DATA_SAFETY"


if __name__ == "__main__":
    if "--serve" in sys.argv:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8769, access_log=False)
    else:
        reproduce()
