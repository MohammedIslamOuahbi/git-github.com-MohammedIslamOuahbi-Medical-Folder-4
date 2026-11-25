"""merge migration heads

Revision ID: 2f42145e22d3
Revises: 20260702_01, a35f2e1ca37c
Create Date: 2026-07-02 09:08:51.982351
"""
from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = '2f42145e22d3'
down_revision = ('20260702_01', 'a35f2e1ca37c')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
