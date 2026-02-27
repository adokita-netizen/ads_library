"""Add thumbnail_url, destination_url, and operational metrics columns

Revision ID: 003
Revises: 002
Create Date: 2026-02-27

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("destination_url", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("spend", sa.Float(), nullable=True))
    op.add_column("ads", sa.Column("impressions", sa.BigInteger(), nullable=True))
    op.add_column("ads", sa.Column("reach", sa.BigInteger(), nullable=True))
    op.add_column("ads", sa.Column("cpc", sa.Float(), nullable=True))
    op.add_column("ads", sa.Column("cpm", sa.Float(), nullable=True))
    op.add_column("ads", sa.Column("frequency", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("ads", "frequency")
    op.drop_column("ads", "cpm")
    op.drop_column("ads", "cpc")
    op.drop_column("ads", "reach")
    op.drop_column("ads", "impressions")
    op.drop_column("ads", "spend")
    op.drop_column("ads", "destination_url")
    op.drop_column("ads", "thumbnail_url")
