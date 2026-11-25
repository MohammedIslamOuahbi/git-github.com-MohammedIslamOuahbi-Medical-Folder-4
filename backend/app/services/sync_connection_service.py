from __future__ import annotations

from app.services.sync_safety import suspend_for_data_safety

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.schemas.sync_connection import SyncStatusData


class SyncConnectionService:
    def get_status(self, db: Session) -> SyncStatusData:
        del db
        online = True
        return SyncStatusData(
            online=online,
            status="suspended_for_data_safety",
            pending_changes=0,
            last_synced_at=None,
            server_time=datetime.now(timezone.utc),
        )

    def run(self, db: Session) -> SyncStatusData:
        suspend_for_data_safety("legacy_sync_run")
        return self.get_status(db)
