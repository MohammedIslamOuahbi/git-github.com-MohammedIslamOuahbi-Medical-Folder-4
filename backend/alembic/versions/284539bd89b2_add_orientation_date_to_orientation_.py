"""add orientation_date to orientation_certificates

Revision ID: 284539bd89b2
Revises: 20260610_02
Create Date: 2026-06-18 23:48:19.526604
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '284539bd89b2'
down_revision = '20260610_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This revision was historically generated as a destructive drop migration.
    # The schema is now established in the initial revision and preserved for fresh installs.
    pass


def downgrade() -> None:
    pass
