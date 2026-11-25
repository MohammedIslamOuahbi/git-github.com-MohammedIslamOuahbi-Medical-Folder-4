from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SystemBackupStatusResponse(BaseModel):
    state: str
    operation: str | None = None
    stage: str | None = None
    message: str | None = None
    started_at: datetime | None = None
    elapsed_seconds: int = 0
    last_completed_at: datetime | None = None
    last_error: str | None = None
    safety_backup_filename: str | None = None
    server_mode: bool
    can_backup: bool
    can_restore: bool
    pg_dump_available: bool
    pg_restore_available: bool


class SystemBackupRestoreResponse(BaseModel):
    success: bool = True
    message: str
    safety_backup_filename: str
    migration_status: str
