from __future__ import annotations

import uuid as py_uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class SyncTransportEvent(Base):
    """Canonical durable transport source; local changes and verified inbox events share it."""
    __tablename__ = "sync_transport_events"
    __table_args__ = (UniqueConstraint("event_uuid", name="uq_sync_transport_event_uuid"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, unique=True)
    source_clinic_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    revision_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    parent_revision_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    origin_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    origin_inbox_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class SyncRelayAuthorization(Base):
    __tablename__ = "sync_relay_authorizations"
    __table_args__ = (UniqueConstraint("carrier_device_uuid", "origin_device_uuid", "origin_generation_uuid", "destination_device_uuid", "channel", name="uq_sync_relay_scope"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    carrier_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    origin_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    origin_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    destination_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyncEventInbox(Base):
    __tablename__ = "sync_event_inbox"
    __table_args__ = (UniqueConstraint("event_uuid", name="uq_sync_event_inbox_event"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, unique=True)
    source_clinic_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    revision_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    parent_revision_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True, default="received")
    application_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    application_lease_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    application_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    application_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class SyncPublicationReceipt(Base):
    __tablename__ = "sync_publication_receipts"
    __table_args__ = (
        UniqueConstraint("event_uuid", "peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid", name="uq_sync_publication_receipt_publisher_scope"),
        UniqueConstraint("peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel", "publish_sequence", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid", name="uq_sync_publication_receipt_position_publisher_scope"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    peer_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    source_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    source_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    publish_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    publisher_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    publisher_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    clinic_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    historical_scope_status: Mapped[str] = mapped_column(String(30), nullable=False, default="current")


class SyncEventDelivery(Base):
    __tablename__ = "sync_event_deliveries"
    __table_args__ = (
        UniqueConstraint("event_uuid", "peer_device_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid", name="uq_sync_event_delivery_publisher_scope"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    peer_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publisher_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    publisher_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    clinic_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    historical_scope_status: Mapped[str] = mapped_column(String(30), nullable=False, default="current")


class SyncTransportCursor(Base):
    __tablename__ = "sync_transport_cursors"
    __table_args__ = (
        UniqueConstraint("peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid", name="uq_sync_transport_cursor_publisher_scope"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    peer_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    source_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    source_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    last_source_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_event_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    last_publish_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_publication_event_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    publisher_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    publisher_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    clinic_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    historical_scope_status: Mapped[str] = mapped_column(String(30), nullable=False, default="current")


class SyncTransportAttempt(Base):
    __tablename__ = "sync_transport_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    peer_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class SyncPublicationCounter(Base):
    __tablename__ = "sync_publication_counters"
    __table_args__ = (UniqueConstraint("clinic_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel", name="uq_sync_pub_counter_publisher_scope"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    source_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    next_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    publisher_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    publisher_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    clinic_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)

class SyncEventPublication(Base):
    __tablename__ = "sync_event_publications"
    __table_args__ = (
        UniqueConstraint("event_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel", name="uq_sync_event_publication_publisher_scope"),
        UniqueConstraint("publisher_device_uuid", "publisher_generation_uuid", "channel", "publish_sequence", name="uq_sync_event_publication_publisher_position"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    source_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    publish_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    publisher_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    publisher_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
