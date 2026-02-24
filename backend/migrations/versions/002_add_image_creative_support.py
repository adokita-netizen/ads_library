"""Add image creative support columns to ads table

Revision ID: 002
Revises: 001
Create Date: 2026-02-24

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("creative_type", sa.String(50), nullable=True))
    op.add_column("ads", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("image_s3_key", sa.String(500), nullable=True))
    op.add_column("ads", sa.Column("image_s3_keys", sa.JSON(), nullable=True))
    op.add_column("ads", sa.Column("snapshot_url", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("media_extraction_status", sa.String(50), nullable=True))

    op.create_index("idx_ads_creative_type", "ads", ["creative_type"])


def downgrade() -> None:
    op.drop_index("idx_ads_creative_type", table_name="ads")

    op.drop_column("ads", "media_extraction_status")
    op.drop_column("ads", "snapshot_url")
    op.drop_column("ads", "image_s3_keys")
    op.drop_column("ads", "image_s3_key")
    op.drop_column("ads", "image_url")
    op.drop_column("ads", "creative_type")
