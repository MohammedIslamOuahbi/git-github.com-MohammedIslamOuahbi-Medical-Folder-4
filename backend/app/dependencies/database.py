from __future__ import annotations

from collections.abc import Generator

from starlette.requests import Request

from app.database import SessionLocal


def get_db(request: Request) -> Generator:
    db = SessionLocal()
    try:
        mission_credential = request.headers.get("X-Mission-Device-Credential")
        device_uuid = request.headers.get("X-Device-UUID")
        if mission_credential:
            db.info["mission_device_credential"] = mission_credential
        if device_uuid:
            import uuid as py_uuid

            db.info["sync_source_device_uuid"] = py_uuid.UUID(device_uuid)
        yield db
    finally:
        db.close()

__all__ = ["get_db"]
