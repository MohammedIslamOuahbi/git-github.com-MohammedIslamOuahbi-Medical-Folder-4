"""create initial application schema

Revision ID: 20260606_01
Revises:
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op


revision = "20260606_01"
down_revision = None
branch_labels = None
depends_on = None


TABLES_OWNED_BY_LATER_REVISIONS = {
    "client_sync_changes",
    "client_local_sync_state",
    "client_local_sync_runs",
    "prescriptions",
    "prescription_items",
    "application_initialization",
    "medicine_imports",
    "medicines",
    "medicine_import_errors",

    # Introduced by 20261007_01_add_recovery_register.py
    "recovery_sources",
    "recovery_items",
    "recovery_identity_candidates",
    # Introduced by 20261007_02_add_local_revisions.py
    "local_revisions",
    "local_write_operations",
    "local_edit_attempts",

    # Transport tables are owned by the ordered 20261008 migrations.  Keeping
    # them out of Base.metadata.create_all is required because those revisions
    # create them with their historical constraints and indexes.
    "sync_event_inbox",
    "sync_event_deliveries",
    "sync_transport_cursors",
    "sync_transport_attempts",
    "sync_publication_counters",
    "sync_event_publications",
    "sync_publication_receipts",
    "sync_transport_events",
    "sync_relay_authorizations",
    # Stage 5A evaluation ledger is owned by 20261008_16.
    "sync_application_decisions",
    "sync_application_attempts",
    # Stage 5A transport capability ledger is owned by 20261008_17/22.
    "proof_transport_capabilities",
    "origin_proof_requests",
    "proof_trusted_keys",
    "proof_delegations",
    "proof_revocations",
    "proof_verification_results",
}

def upgrade() -> None:
    from app.database import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    base_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in TABLES_OWNED_BY_LATER_REVISIONS
    ]
    Base.metadata.create_all(bind=bind, tables=base_tables)


def downgrade() -> None:
    from app.database import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    base_tables = [
        table
        for table in reversed(Base.metadata.sorted_tables)
        if table.name not in TABLES_OWNED_BY_LATER_REVISIONS
    ]
    Base.metadata.drop_all(bind=bind, tables=base_tables)
