"""Add video_s3_key column to ads table

Revision ID: 004
Revises: 003
Create Date: 2026-03-01

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("video_s3_key", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("ads", "video_s3_key")
