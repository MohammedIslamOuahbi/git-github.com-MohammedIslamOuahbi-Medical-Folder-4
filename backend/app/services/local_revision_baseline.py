"""Resumable, content-free baseline for records predating revision tracking.

Run only after the additive migration, with an explicitly verified database target.
The first observed version is a baseline, not reconstructed history.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.local_revision import LocalRevision
from app.sync.registry import SYNC_ENTITY_REGISTRY


def baseline_batch(db: Session, entity_type: str, after_uuid: uuid.UUID | None = None, limit: int = 100) -> tuple[int, uuid.UUID | None]:
    config = SYNC_ENTITY_REGISTRY[entity_type]
    if not 1 <= limit <= 1000:
        raise ValueError("INVALID_BASELINE_BATCH_LIMIT")
    query = select(config.model.uuid, config.model.sync_version).order_by(config.model.uuid).limit(limit)
    if after_uuid is not None:
        query = query.where(config.model.uuid > after_uuid)
    rows = db.execute(query).all()
    for entity_uuid, local_version in rows:
        if entity_uuid is None:
            continue
        db.execute(insert(LocalRevision).values(
            revision_uuid=uuid.uuid4(), entity_type=entity_type, entity_uuid=entity_uuid,
            parent_revision_uuid=None, local_version=max(1, int(local_version or 1)),
            kind="baseline", operation_uuid=None, created_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(constraint="uq_local_revision_version"))
    db.commit()
    return len(rows), rows[-1].uuid if rows else after_uuid
