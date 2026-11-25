from __future__ import annotations

from app.services.sync_safety import suspend_for_data_safety

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.sync_repository import SyncRepository
from app.schemas.sync import (
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncResolveConflictRequest,
    SyncStatusResponse,
)


class SyncService:
    def __init__(self, repository: SyncRepository | None = None) -> None:
        self.repository = repository or SyncRepository()

    def push(self, db: Session, payload: SyncPushRequest) -> SyncPushResponse:
        suspend_for_data_safety("legacy_sync_push")
        del db
        response = self.repository.push_changes(payload.changes.model_dump())
        return SyncPushResponse(**response)

    def pull(self, db: Session, device_id: str, last_sync_at: str | None) -> SyncPullResponse:
        del device_id, last_sync_at
        response = self.repository.pull_changes()
        response["server_time"] = datetime.now(timezone.utc)
        response["changes"] = self.repository.pull_from_db(db)
        return SyncPullResponse(**response)

    def resolve_conflict(self, db: Session, payload: SyncResolveConflictRequest) -> dict[str, bool]:
        suspend_for_data_safety("legacy_conflict_resolution")
        del db, payload.merged_data, payload.resolution
        self.repository.resolve_conflict(payload.entity_type, payload.entity_id)
        return {"success": True}

    def status(self, db: Session) -> SyncStatusResponse:
        del db
        return SyncStatusResponse(**self.repository.get_status())
