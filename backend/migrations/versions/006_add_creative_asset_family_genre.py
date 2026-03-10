"""Add creative_asset, creative_family, genre_taxonomy, ad_genre_tags tables.

Also adds hit_proxy_score and active_days columns to ads table.

Revision ID: 006
Revises: 005
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Genre taxonomy
    op.create_table(
        "genre_taxonomy",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("parent_genre_id", sa.BigInteger(), nullable=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name_ja", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_genre_id"], ["genre_taxonomy.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("code", name="uq_genre_code"),
    )
    op.create_index("idx_genre_parent", "genre_taxonomy", ["parent_genre_id"])
    op.create_index("idx_genre_level", "genre_taxonomy", ["level"])

    # Creative families
    op.create_table(
        "creative_families",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("canonical_advertiser_name", sa.String(255), nullable=True),
        sa.Column("family_title", sa.String(500), nullable=True),
        sa.Column("primary_genre_code", sa.String(100), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platform_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("variant_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("hit_proxy_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("review_status", sa.String(20), nullable=True),
        sa.Column("family_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_family_advertiser", "creative_families", ["canonical_advertiser_name"])
    op.create_index("idx_family_genre", "creative_families", ["primary_genre_code"])
    op.create_index("idx_family_hit_proxy", "creative_families", ["hit_proxy_score"])
    op.create_index("idx_family_active_days", "creative_families", ["active_days"])

    # Creative assets
    op.create_table(
        "creative_assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("phash", sa.String(64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("aspect_ratio", sa.String(10), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("has_audio", sa.Boolean(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("asr_text", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("is_representative", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("extraction_method", sa.String(50), nullable=True),
        sa.Column("family_id", sa.BigInteger(), nullable=True),
        sa.Column("family_membership_score", sa.Float(), nullable=True),
        sa.Column("asset_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["family_id"], ["creative_families.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_asset_ad", "creative_assets", ["ad_id"])
    op.create_index("idx_asset_type", "creative_assets", ["asset_type"])
    op.create_index("idx_asset_sha256", "creative_assets", ["sha256"])
    op.create_index("idx_asset_aspect", "creative_assets", ["aspect_ratio"])
    op.create_index("idx_asset_quality", "creative_assets", ["quality_score"])

    # Ad genre tags (multi-label)
    op.create_table(
        "ad_genre_tags",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("genre_code", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("source", sa.String(50), nullable=False, server_default="'keyword'"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ad_id", "genre_code", name="uq_ad_genre"),
    )
    op.create_index("idx_adgenre_ad", "ad_genre_tags", ["ad_id"])
    op.create_index("idx_adgenre_code", "ad_genre_tags", ["genre_code"])
    op.create_index("idx_adgenre_primary", "ad_genre_tags", ["is_primary"])

    # Add hit_proxy_score and active_days to ads table
    with op.batch_alter_table("ads") as batch_op:
        batch_op.add_column(sa.Column("hit_proxy_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("active_days", sa.Integer(), nullable=True))
        batch_op.create_index("idx_ads_hit_proxy", ["hit_proxy_score"])
        batch_op.create_index("idx_ads_active_days", ["active_days"])


def downgrade() -> None:
    with op.batch_alter_table("ads") as batch_op:
        batch_op.drop_index("idx_ads_hit_proxy")
        batch_op.drop_index("idx_ads_active_days")
        batch_op.drop_column("hit_proxy_score")
        batch_op.drop_column("active_days")
    op.drop_table("ad_genre_tags")
    op.drop_table("creative_assets")
    op.drop_table("creative_families")
    op.drop_table("genre_taxonomy")
