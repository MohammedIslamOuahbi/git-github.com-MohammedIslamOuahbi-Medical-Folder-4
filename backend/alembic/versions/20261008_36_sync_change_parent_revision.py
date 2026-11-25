"""store parent revision on local journal changes"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_36'; down_revision='20261008_35'; branch_labels=None; depends_on=None
def upgrade():
    # 20261008_01 already creates this nullable column on fresh databases.
    # Keep the later compatibility migration idempotent for partially seeded
    # recovery databases that still advertise the pre-36 revision.
    if "parent_revision_uuid" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sync_changes")}:
        op.add_column("sync_changes", sa.Column("parent_revision_uuid", postgresql.UUID(as_uuid=True), nullable=True))

def downgrade():
    if "parent_revision_uuid" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sync_changes")}:
        op.drop_column("sync_changes", "parent_revision_uuid")
