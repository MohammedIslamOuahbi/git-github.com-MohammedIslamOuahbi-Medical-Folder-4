from __future__ import annotations

import uuid
import logging
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.exceptions import UnauthorizedException
from app.services.central_sync_service import CentralSyncService

log = logging.getLogger("sync.transport.auth")


def require_sync_transport_device(
    x_sync_device_uuid: str | None = Header(default=None),
    x_sync_device_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_sync_device_uuid:
        raise UnauthorizedException("SYNC_DEVICE_AUTH_REQUIRED")
    try:
        device_uuid = uuid.UUID(x_sync_device_uuid)
    except ValueError as exc:
        raise UnauthorizedException("SYNC_DEVICE_AUTH_INVALID") from exc
    log.info("receive_auth_uuid uuid=%s database=%s", device_uuid, db.get_bind().url.database)
    device = CentralSyncService().authenticate_device(db, device_uuid=device_uuid, secret=x_sync_device_secret)
    return device
