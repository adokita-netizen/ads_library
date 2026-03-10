"""Add brand registry, ad cards, angle facts, LP snapshots, video timelines, genre keyword packs.

Revision ID: 007
Revises: 006
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Brand Registry ──
    op.create_table(
        "brand_registry",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("vertical", sa.String(100), nullable=True),
        sa.Column("country_codes", sa.JSON, nullable=True),
        sa.Column("aliases", sa.JSON, nullable=True),
        sa.Column("meta_page_ids", sa.JSON, nullable=True),
        sa.Column("domains", sa.JSON, nullable=True),
        sa.Column("total_ad_count", sa.Integer, default=0, nullable=False),
        sa.Column("total_active_ads", sa.Integer, default=0, nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avg_hit_proxy_score", sa.Float, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("brand_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("canonical_name", name="uq_brand_canonical"),
    )
    op.create_index("idx_brand_vertical", "brand_registry", ["vertical"])
    op.create_index("idx_brand_active", "brand_registry", ["is_active"])

    # ── Ad Cards ──
    op.create_table(
        "ad_cards",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ad_id", sa.BigInteger, sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", sa.BigInteger, sa.ForeignKey("brand_registry.id", ondelete="SET NULL"), nullable=True),
        sa.Column("card_index", sa.Integer, nullable=False, default=0),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column("link_title", sa.String(500), nullable=True),
        sa.Column("link_description", sa.Text, nullable=True),
        sa.Column("call_to_action", sa.String(100), nullable=True),
        sa.Column("media_type", sa.String(20), nullable=True),
        sa.Column("aspect_ratio", sa.String(10), nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("image_s3_key", sa.String(500), nullable=True),
        sa.Column("video_url", sa.Text, nullable=True),
        sa.Column("video_s3_key", sa.String(500), nullable=True),
        sa.Column("screenshot_uri", sa.Text, nullable=True),
        sa.Column("destination_url_initial", sa.Text, nullable=True),
        sa.Column("destination_url_final", sa.Text, nullable=True),
        sa.Column("destination_domain", sa.String(255), nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("asr_text", sa.Text, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("card_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ad_id", "card_index", name="uq_ad_card_index"),
    )
    op.create_index("idx_card_ad", "ad_cards", ["ad_id"])
    op.create_index("idx_card_brand", "ad_cards", ["brand_id"])
    op.create_index("idx_card_media_type", "ad_cards", ["media_type"])
    op.create_index("idx_card_cta", "ad_cards", ["call_to_action"])

    # ── Angle Facts ──
    op.create_table(
        "angle_facts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("card_id", sa.BigInteger, sa.ForeignKey("ad_cards.id", ondelete="CASCADE"), nullable=True),
        sa.Column("family_id", sa.BigInteger, sa.ForeignKey("creative_families.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ad_id", sa.BigInteger, sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("hook_type", sa.String(50), nullable=True),
        sa.Column("pain_points", sa.JSON, nullable=True),
        sa.Column("promises", sa.JSON, nullable=True),
        sa.Column("offer_types", sa.JSON, nullable=True),
        sa.Column("proof_types", sa.JSON, nullable=True),
        sa.Column("urgency_types", sa.JSON, nullable=True),
        sa.Column("audience_hints", sa.JSON, nullable=True),
        sa.Column("creative_styles", sa.JSON, nullable=True),
        sa.Column("lp_pattern", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float, default=0.0, nullable=False),
        sa.Column("extracted_from", sa.String(50), nullable=False, default="ocr"),
        sa.Column("angle_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_angle_card", "angle_facts", ["card_id"])
    op.create_index("idx_angle_family", "angle_facts", ["family_id"])
    op.create_index("idx_angle_hook_type", "angle_facts", ["hook_type"])
    op.create_index("idx_angle_confidence", "angle_facts", ["confidence"])

    # ── LP Snapshots ──
    op.create_table(
        "lp_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("card_id", sa.BigInteger, sa.ForeignKey("ad_cards.id", ondelete="CASCADE"), nullable=True),
        sa.Column("landing_page_id", sa.BigInteger, sa.ForeignKey("landing_pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial_url", sa.Text, nullable=True),
        sa.Column("final_url", sa.Text, nullable=True),
        sa.Column("final_domain", sa.String(255), nullable=True),
        sa.Column("redirect_chain", sa.JSON, nullable=True),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("mobile_screenshot_uri", sa.Text, nullable=True),
        sa.Column("desktop_screenshot_uri", sa.Text, nullable=True),
        sa.Column("fullpage_screenshot_uri", sa.Text, nullable=True),
        sa.Column("mobile_html_uri", sa.Text, nullable=True),
        sa.Column("desktop_html_uri", sa.Text, nullable=True),
        sa.Column("dom_text", sa.Text, nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("primary_cta", sa.String(255), nullable=True),
        sa.Column("form_fields", sa.JSON, nullable=True),
        sa.Column("extracted_json", sa.JSON, nullable=True),
        sa.Column("snapshot_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_lps_card", "lp_snapshots", ["card_id"])
    op.create_index("idx_lps_domain", "lp_snapshots", ["final_domain"])
    op.create_index("idx_lps_observed", "lp_snapshots", ["observed_at"])

    # ── Genre Keyword Packs ──
    op.create_table(
        "genre_keyword_packs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("genre_code", sa.String(100), nullable=False),
        sa.Column("search_keywords_ja", sa.JSON, nullable=True),
        sa.Column("search_keywords_en", sa.JSON, nullable=True),
        sa.Column("appeal_keywords", sa.JSON, nullable=True),
        sa.Column("negative_keywords", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_ads_discovered", sa.Integer, default=0, nullable=False),
        sa.Column("pack_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_gkp_genre", "genre_keyword_packs", ["genre_code"])
    op.create_index("idx_gkp_active", "genre_keyword_packs", ["is_active"])

    # ── Video Timelines ──
    op.create_table(
        "video_timelines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ad_id", sa.BigInteger, sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.BigInteger, sa.ForeignKey("creative_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("timeline", sa.JSON, nullable=True),
        sa.Column("opening_hook", sa.Text, nullable=True),
        sa.Column("opening_hook_type", sa.String(50), nullable=True),
        sa.Column("proof_sequence", sa.JSON, nullable=True),
        sa.Column("cta_endcard", sa.Text, nullable=True),
        sa.Column("total_duration_ms", sa.Integer, nullable=True),
        sa.Column("keyframe_count", sa.Integer, nullable=True),
        sa.Column("unique_ocr_texts", sa.Integer, nullable=True),
        sa.Column("has_asr", sa.Boolean, default=False, nullable=False),
        sa.Column("timeline_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_vt_ad", "video_timelines", ["ad_id"])
    op.create_index("idx_vt_asset", "video_timelines", ["asset_id"])

    # ── Add brand_id FK to ads table ──
    op.add_column("ads", sa.Column("brand_id", sa.BigInteger, nullable=True))
    op.create_index("idx_ads_brand", "ads", ["brand_id"])


def downgrade() -> None:
    op.drop_index("idx_ads_brand", table_name="ads")
    op.drop_column("ads", "brand_id")
    op.drop_table("video_timelines")
    op.drop_table("genre_keyword_packs")
    op.drop_table("lp_snapshots")
    op.drop_table("angle_facts")
    op.drop_table("ad_cards")
    op.drop_table("brand_registry")
