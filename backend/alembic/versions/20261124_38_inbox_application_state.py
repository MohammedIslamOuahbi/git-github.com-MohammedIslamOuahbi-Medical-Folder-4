"""durable inbox application lifecycle"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261124_38"
down_revision = "20261008_37"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("sync_event_inbox")}
    additions = [
        ("application_attempt_count", sa.Column("application_attempt_count", sa.Integer(), nullable=False, server_default="0")),
        ("application_lease_uuid", sa.Column("application_lease_uuid", postgresql.UUID(as_uuid=True), nullable=True)),
        ("application_lease_expires_at", sa.Column("application_lease_expires_at", sa.DateTime(timezone=True), nullable=True)),
        ("application_error_code", sa.Column("application_error_code", sa.String(120), nullable=True)),
        ("application_error_message", sa.Column("application_error_message", sa.Text(), nullable=True)),
        ("applied_at", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True)),
    ]
    for name, column in additions:
        if name not in cols:
            op.add_column("sync_event_inbox", column)

def downgrade():
    for name in ("applied_at", "application_error_message", "application_error_code", "application_lease_expires_at", "application_lease_uuid", "application_attempt_count"):
        op.drop_column("sync_event_inbox", name)
