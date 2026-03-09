"""Add score_delta column to product_rankings

Revision ID: 005
Revises: 004
Create Date: 2026-03-07

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_rankings", sa.Column("score_delta", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("product_rankings", "score_delta")
