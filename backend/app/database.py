from __future__ import annotations

import uuid as py_uuid
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, create_engine, event, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, declared_attr, mapped_column, sessionmaker
from starlette.requests import Request

from app.config import settings
from app.services.sync_safety import suspend_for_data_safety


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncMixin:
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default="synced",
        server_default=text("'synced'"),
        nullable=False,
    )
    local_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)


class SyncMetadataMixin:
    uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=py_uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    sync_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    origin_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    last_modified_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    origin_mission_session_uuid: Mapped[py_uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True), nullable=True, index=True
    )
    last_modified_mission_session_uuid: Mapped[py_uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True), nullable=True, index=True
    )
    central_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    central_sync_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="never_submitted",
        server_default=text("'never_submitted'"),
        index=True,
    )
    central_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    central_finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    central_server_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)


class LocalRuntimeConfigMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


STAGE3_GUARDED_TABLES = frozenset({
    "permissions", "users", "user_permissions", "companies", "branches",
    "drilling_sites", "medical_tests", "medical_campaigns", "workspaces",
    "workers", "campaign_workers", "campaign_tests", "doctor_campaigns",
    "assistant_campaigns", "medical_visits", "worker_tests", "prescriptions",
    "prescription_items", "orientation_certificates", "aptitude_certificates",
})


@event.listens_for(Session, "before_flush")
def enforce_stage_three_write_contract(session: Session, _flush_context, _instances) -> None:
    """Fail closed for every session, including direct service/sidecar calls."""
    if session.info.get("sync_apply_mode") or session.info.get("sync_bootstrap_mode"):
        return
    guarded = [
        instance
        for group in (session.new, session.dirty, session.deleted)
        for instance in group
        if inspect(instance).mapper.local_table.name in STAGE3_GUARDED_TABLES
        and (instance not in session.dirty or session.is_modified(instance, include_collections=False))
    ]
    if not guarded:
        return
    operation_uuid = session.info.get("local_operation_uuid")
    has_contract = bool(session.info.get("stage3_write_contract") and operation_uuid)
    if has_contract:
        has_contract = session.connection().execute(
            text("SELECT 1 FROM local_write_operations WHERE operation_uuid = :operation_uuid"),
            {"operation_uuid": operation_uuid},
        ).scalar_one_or_none() is not None
    if not has_contract:
        table = inspect(guarded[0]).mapper.local_table.name
        suspend_for_data_safety(f"unprotected_syncable_write:{table}")


engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def dispose_engine() -> None:
    engine.dispose()


def reset_session_factory() -> None:
    global SessionLocal
    dispose_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db(request: Request) -> Generator:
    db = SessionLocal()
    try:
        mission_credential = request.headers.get("X-Mission-Device-Credential")
        device_uuid = request.headers.get("X-Device-UUID")
        if mission_credential:
            db.info["mission_device_credential"] = mission_credential
        if device_uuid:
            db.info["sync_source_device_uuid"] = py_uuid.UUID(device_uuid)
        yield db
    finally:
        db.close()
