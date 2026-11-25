"""add orientation_date to orientation_certificates

Revision ID: 49b38b083e84
Revises: 284539bd89b2
Create Date: 2026-06-19 10:18:33.626045
"""
from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = '49b38b083e84'
down_revision = '284539bd89b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The current schema already preserves orientation tables through the initial revision.
    pass


def downgrade() -> None:
    pass
