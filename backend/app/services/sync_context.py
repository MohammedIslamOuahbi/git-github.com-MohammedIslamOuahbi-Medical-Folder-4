from __future__ import annotations

import uuid as py_uuid
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.models.user import User


def _normalize_uuid(value: object) -> py_uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, py_uuid.UUID):
        return value
    return py_uuid.UUID(str(value))


def set_sync_context(
    db: Session,
    *,
    user: User | None = None,
    source_user_uuid: py_uuid.UUID | str | None = None,
    source_device_uuid: py_uuid.UUID | str | None = None,
    mission_session_uuid: py_uuid.UUID | str | None = None,
    mission_server_uuid: py_uuid.UUID | str | None = None,
    bootstrap_mode: bool | None = None,
    sync_apply_mode: bool | None = None,
) -> None:
    if user is not None and source_user_uuid is None:
        source_user_uuid = getattr(user, "uuid", None)
    if source_user_uuid is not None:
        db.info["sync_source_user_uuid"] = _normalize_uuid(source_user_uuid)
    if source_device_uuid is not None:
        db.info["sync_source_device_uuid"] = _normalize_uuid(source_device_uuid)
    if mission_session_uuid is not None:
        db.info["sync_mission_session_uuid"] = _normalize_uuid(mission_session_uuid)
    if mission_server_uuid is not None:
        db.info["sync_mission_server_uuid"] = _normalize_uuid(mission_server_uuid)
    if bootstrap_mode is not None:
        db.info["sync_bootstrap_mode"] = bool(bootstrap_mode)
    if sync_apply_mode is not None:
        db.info["sync_apply_mode"] = bool(sync_apply_mode)


@contextmanager
def sync_apply_scope(db: Session) -> Iterator[None]:
    previous = bool(db.info.get("sync_apply_mode"))
    db.info["sync_apply_mode"] = True
    try:
        yield
    finally:
        if previous:
            db.info["sync_apply_mode"] = True
        else:
            db.info.pop("sync_apply_mode", None)
