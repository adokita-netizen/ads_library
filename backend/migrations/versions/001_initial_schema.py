"""Initial schema - create all VAAP tables

Revision ID: 001
Revises: None
Create Date: 2026-02-12

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Enum definitions
# ---------------------------------------------------------------------------

ad_platform_enum = sa.Enum(
    "youtube",
    "tiktok",
    "instagram",
    "facebook",
    "x_twitter",
    "line",
    "yahoo",
    "pinterest",
    "smartnews",
    "google_ads",
    "gunosy",
    "other",
    name="adplatformenum",
)

ad_status_enum = sa.Enum(
    "pending",
    "processing",
    "analyzed",
    "failed",
    name="adstatusenum",
)

ad_category_enum = sa.Enum(
    "ec_d2c",
    "app",
    "finance",
    "education",
    "beauty",
    "food",
    "gaming",
    "health",
    "technology",
    "real_estate",
    "travel",
    "other",
    name="adcategoryenum",
)

user_role_enum = sa.Enum(
    "admin",
    "analyst",
    "creator",
    "viewer",
    name="userrole",
)

lp_type_enum = sa.Enum(
    "article",
    "ec_direct",
    "lead_gen",
    "app_store",
    "brand",
    "other",
    name="lptypeenum",
)

lp_status_enum = sa.Enum(
    "pending",
    "crawling",
    "analyzing",
    "completed",
    "failed",
    name="lpstatusenum",
)

appeal_axis_enum = sa.Enum(
    "benefit",
    "problem_solution",
    "authority",
    "social_proof",
    "urgency",
    "price",
    "comparison",
    "emotional",
    "fear",
    "novelty",
    name="appealaxisenum",
)

creative_type_enum = sa.Enum(
    "video_script",
    "storyboard",
    "ad_copy",
    "banner",
    "lp_copy",
    "narration",
    name="creativetypeenum",
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", user_role_enum, server_default="viewer", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # ------------------------------------------------------------------
    # 2. ads
    # ------------------------------------------------------------------
    op.create_table(
        "ads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platform", ad_platform_enum, nullable=False),
        sa.Column("status", ad_status_enum, server_default="pending", nullable=False),
        sa.Column("category", ad_category_enum, nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.String(500), nullable=True),
        sa.Column("thumbnail_s3_key", sa.String(500), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("resolution_width", sa.Integer(), nullable=True),
        sa.Column("resolution_height", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("advertiser_name", sa.String(255), nullable=True),
        sa.Column("advertiser_url", sa.Text(), nullable=True),
        sa.Column("brand_name", sa.String(255), nullable=True),
        sa.Column("estimated_impressions", sa.BigInteger(), nullable=True),
        sa.Column("estimated_ctr", sa.Float(), nullable=True),
        sa.Column("estimated_cvr", sa.Float(), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("idx_ads_platform_created", "ads", ["platform", "created_at"])
    op.create_index("idx_ads_advertiser", "ads", ["advertiser_name"])
    op.create_index("idx_ads_category", "ads", ["category"])
    op.create_index("idx_ads_status", "ads", ["status"])

    # ------------------------------------------------------------------
    # 3. ad_frames
    # ------------------------------------------------------------------
    op.create_table(
        "ad_frames",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("frame_number", sa.Integer(), nullable=False),
        sa.Column("timestamp_seconds", sa.Float(), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("is_keyframe", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=True),
        sa.Column("brightness", sa.Float(), nullable=True),
        sa.Column("contrast", sa.Float(), nullable=True),
        sa.Column("dominant_colors", postgresql.JSONB(), nullable=True),
        sa.Column("composition_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_frames_ad_timestamp", "ad_frames", ["ad_id", "timestamp_seconds"])

    # ------------------------------------------------------------------
    # 4. ad_analyses
    # ------------------------------------------------------------------
    op.create_table(
        "ad_analyses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("total_scenes", sa.Integer(), nullable=True),
        sa.Column("avg_scene_duration", sa.Float(), nullable=True),
        sa.Column("scene_transitions", postgresql.JSONB(), nullable=True),
        sa.Column("face_closeup_ratio", sa.Float(), nullable=True),
        sa.Column("text_overlay_ratio", sa.Float(), nullable=True),
        sa.Column("product_display_ratio", sa.Float(), nullable=True),
        sa.Column("ui_display_ratio", sa.Float(), nullable=True),
        sa.Column("is_ugc_style", sa.Boolean(), nullable=True),
        sa.Column("has_narration", sa.Boolean(), nullable=True),
        sa.Column("has_bgm", sa.Boolean(), nullable=True),
        sa.Column("has_subtitles", sa.Boolean(), nullable=True),
        sa.Column("hook_type", sa.String(100), nullable=True),
        sa.Column("hook_text", sa.Text(), nullable=True),
        sa.Column("hook_score", sa.Float(), nullable=True),
        sa.Column("cta_text", sa.Text(), nullable=True),
        sa.Column("cta_timestamp", sa.Float(), nullable=True),
        sa.Column("cta_type", sa.String(100), nullable=True),
        sa.Column("overall_sentiment", sa.String(50), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("emotion_breakdown", postgresql.JSONB(), nullable=True),
        sa.Column("dominant_color_palette", postgresql.JSONB(), nullable=True),
        sa.Column("color_temperature", sa.String(50), nullable=True),
        sa.Column("full_transcript", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.JSONB(), nullable=True),
        sa.Column("topics", postgresql.JSONB(), nullable=True),
        sa.Column("winning_score", sa.Float(), nullable=True),
        sa.Column("raw_analysis", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ad_id"),
    )

    # ------------------------------------------------------------------
    # 5. detected_objects
    # ------------------------------------------------------------------
    op.create_table(
        "detected_objects",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.BigInteger(), nullable=False),
        sa.Column("frame_number", sa.Integer(), nullable=False),
        sa.Column("timestamp_seconds", sa.Float(), nullable=False),
        sa.Column("class_name", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("bbox_x", sa.Float(), nullable=False),
        sa.Column("bbox_y", sa.Float(), nullable=False),
        sa.Column("bbox_width", sa.Float(), nullable=False),
        sa.Column("bbox_height", sa.Float(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["analysis_id"], ["ad_analyses.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_detected_objects_analysis_class", "detected_objects", ["analysis_id", "class_name"])

    # ------------------------------------------------------------------
    # 6. text_detections
    # ------------------------------------------------------------------
    op.create_table(
        "text_detections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.BigInteger(), nullable=False),
        sa.Column("frame_number", sa.Integer(), nullable=False),
        sa.Column("timestamp_seconds", sa.Float(), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("bbox_x", sa.Float(), nullable=False),
        sa.Column("bbox_y", sa.Float(), nullable=False),
        sa.Column("bbox_width", sa.Float(), nullable=False),
        sa.Column("bbox_height", sa.Float(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["analysis_id"], ["ad_analyses.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_text_detections_analysis", "text_detections", ["analysis_id"])

    # ------------------------------------------------------------------
    # 7. transcriptions
    # ------------------------------------------------------------------
    op.create_table(
        "transcriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("start_time_ms", sa.Integer(), nullable=False),
        sa.Column("end_time_ms", sa.Integer(), nullable=False),
        sa.Column("speaker_id", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["analysis_id"], ["ad_analyses.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_transcriptions_analysis_time", "transcriptions", ["analysis_id", "start_time_ms"])

    # ------------------------------------------------------------------
    # 8. scene_boundaries
    # ------------------------------------------------------------------
    op.create_table(
        "scene_boundaries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.BigInteger(), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("start_time_seconds", sa.Float(), nullable=False),
        sa.Column("end_time_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("scene_type", sa.String(100), nullable=True),
        sa.Column("dominant_color", sa.String(50), nullable=True),
        sa.Column("has_text_overlay", sa.Boolean(), nullable=True),
        sa.Column("has_person", sa.Boolean(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["analysis_id"], ["ad_analyses.id"], ondelete="CASCADE"),
    )

    # ------------------------------------------------------------------
    # 9. sentiment_results
    # ------------------------------------------------------------------
    op.create_table(
        "sentiment_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.BigInteger(), nullable=False),
        sa.Column("segment_type", sa.String(50), nullable=False),
        sa.Column("segment_text", sa.Text(), nullable=True),
        sa.Column("start_time_ms", sa.Integer(), nullable=True),
        sa.Column("end_time_ms", sa.Integer(), nullable=True),
        sa.Column("sentiment", sa.String(50), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("emotion_breakdown", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["analysis_id"], ["ad_analyses.id"], ondelete="CASCADE"),
    )

    # ------------------------------------------------------------------
    # 10. campaigns
    # ------------------------------------------------------------------
    op.create_table(
        "campaigns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    # ------------------------------------------------------------------
    # 11. campaign_ads
    # ------------------------------------------------------------------
    op.create_table(
        "campaign_ads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )

    # ------------------------------------------------------------------
    # 12. generated_creatives
    # ------------------------------------------------------------------
    op.create_table(
        "generated_creatives",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("creative_type", creative_type_enum, nullable=False),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("product_description", sa.Text(), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("appeal_axis", sa.String(255), nullable=True),
        sa.Column("reference_ad_id", sa.BigInteger(), nullable=True),
        sa.Column("input_params", postgresql.JSONB(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_structured", postgresql.JSONB(), nullable=True),
        sa.Column("s3_key", sa.String(500), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("prompt_used", sa.Text(), nullable=True),
        sa.Column("generation_time_ms", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("variation_group_id", sa.String(100), nullable=True),
        sa.Column("variation_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reference_ad_id"], ["ads.id"]),
    )

    # ------------------------------------------------------------------
    # 13. creative_templates
    # ------------------------------------------------------------------
    op.create_table(
        "creative_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("creative_type", creative_type_enum, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template_content", postgresql.JSONB(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("winning_score", sa.Float(), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 14. performance_predictions
    # ------------------------------------------------------------------
    op.create_table(
        "performance_predictions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("predicted_ctr", sa.Float(), nullable=True),
        sa.Column("predicted_cvr", sa.Float(), nullable=True),
        sa.Column("predicted_cpa", sa.Float(), nullable=True),
        sa.Column("winning_probability", sa.Float(), nullable=True),
        sa.Column("optimal_duration_seconds", sa.Float(), nullable=True),
        sa.Column("ctr_confidence_low", sa.Float(), nullable=True),
        sa.Column("ctr_confidence_high", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("feature_importance", postgresql.JSONB(), nullable=True),
        sa.Column("improvement_suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )

    # ------------------------------------------------------------------
    # 15. ad_fatigue_logs
    # ------------------------------------------------------------------
    op.create_table(
        "ad_fatigue_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("fatigue_score", sa.Float(), nullable=False),
        sa.Column("days_active", sa.Integer(), nullable=False),
        sa.Column("performance_trend", sa.String(50), nullable=False),
        sa.Column("estimated_remaining_days", sa.Integer(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("replacement_suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("metrics_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )

    # ------------------------------------------------------------------
    # 16. landing_pages
    # ------------------------------------------------------------------
    op.create_table(
        "landing_pages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("og_image_url", sa.Text(), nullable=True),
        sa.Column("screenshot_s3_key", sa.String(500), nullable=True),
        sa.Column("full_page_screenshot_s3_key", sa.String(500), nullable=True),
        sa.Column("lp_type", lp_type_enum, server_default="article", nullable=False),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("advertiser_name", sa.String(255), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("video_embed_count", sa.Integer(), nullable=True),
        sa.Column("form_count", sa.Integer(), nullable=True),
        sa.Column("cta_count", sa.Integer(), nullable=True),
        sa.Column("testimonial_count", sa.Integer(), nullable=True),
        sa.Column("estimated_read_time_seconds", sa.Integer(), nullable=True),
        sa.Column("total_sections", sa.Integer(), nullable=True),
        sa.Column("scroll_depth_px", sa.Integer(), nullable=True),
        sa.Column("hero_headline", sa.Text(), nullable=True),
        sa.Column("hero_subheadline", sa.Text(), nullable=True),
        sa.Column("primary_cta_text", sa.String(255), nullable=True),
        sa.Column("full_text_content", sa.Text(), nullable=True),
        sa.Column("has_pricing", sa.Boolean(), nullable=True),
        sa.Column("price_text", sa.String(255), nullable=True),
        sa.Column("discount_text", sa.String(255), nullable=True),
        sa.Column("is_own", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("own_lp_label", sa.String(255), nullable=True),
        sa.Column("own_lp_version", sa.Integer(), nullable=True),
        sa.Column("status", lp_status_enum, server_default="pending", nullable=False),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_html_s3_key", sa.String(500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_lp_url_hash", "landing_pages", ["url_hash"], unique=True)
    op.create_index("idx_lp_ad_id", "landing_pages", ["ad_id"])
    op.create_index("idx_lp_advertiser", "landing_pages", ["advertiser_name"])
    op.create_index("idx_lp_genre", "landing_pages", ["genre"])
    op.create_index("idx_lp_type", "landing_pages", ["lp_type"])

    # ------------------------------------------------------------------
    # 17. lp_sections
    # ------------------------------------------------------------------
    op.create_table(
        "lp_sections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("landing_page_id", sa.BigInteger(), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("section_type", sa.String(100), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("has_image", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_video", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_cta", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("cta_text", sa.String(255), nullable=True),
        sa.Column("position_y_percent", sa.Float(), nullable=True),
        sa.Column("extracted_data", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["landing_page_id"], ["landing_pages.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_lp_sections_lp_order", "lp_sections", ["landing_page_id", "section_order"])

    # ------------------------------------------------------------------
    # 18. usp_patterns
    # ------------------------------------------------------------------
    op.create_table(
        "usp_patterns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("landing_page_id", sa.BigInteger(), nullable=False),
        sa.Column("usp_category", sa.String(100), nullable=False),
        sa.Column("usp_text", sa.Text(), nullable=False),
        sa.Column("usp_headline", sa.String(500), nullable=True),
        sa.Column("supporting_evidence", sa.Text(), nullable=True),
        sa.Column("prominence_score", sa.Float(), nullable=True),
        sa.Column("position_in_page", sa.String(50), nullable=True),
        sa.Column("keywords", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["landing_page_id"], ["landing_pages.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_usp_lp_id", "usp_patterns", ["landing_page_id"])
    op.create_index("idx_usp_category", "usp_patterns", ["usp_category"])

    # ------------------------------------------------------------------
    # 19. appeal_axis_analyses
    # ------------------------------------------------------------------
    op.create_table(
        "appeal_axis_analyses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("landing_page_id", sa.BigInteger(), nullable=False),
        sa.Column("appeal_axis", appeal_axis_enum, nullable=False),
        sa.Column("strength_score", sa.Float(), nullable=False),
        sa.Column("evidence_texts", postgresql.JSONB(), nullable=True),
        sa.Column("section_ids", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["landing_page_id"], ["landing_pages.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_appeal_lp_id", "appeal_axis_analyses", ["landing_page_id"])

    # ------------------------------------------------------------------
    # 20. lp_analyses
    # ------------------------------------------------------------------
    op.create_table(
        "lp_analyses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("landing_page_id", sa.BigInteger(), nullable=False),
        sa.Column("overall_quality_score", sa.Float(), nullable=True),
        sa.Column("conversion_potential_score", sa.Float(), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=True),
        sa.Column("urgency_score", sa.Float(), nullable=True),
        sa.Column("page_flow_pattern", sa.String(255), nullable=True),
        sa.Column("structure_summary", sa.Text(), nullable=True),
        sa.Column("inferred_target_gender", sa.String(50), nullable=True),
        sa.Column("inferred_target_age_range", sa.String(50), nullable=True),
        sa.Column("inferred_target_concerns", postgresql.JSONB(), nullable=True),
        sa.Column("target_persona_summary", sa.Text(), nullable=True),
        sa.Column("primary_appeal_axis", sa.String(100), nullable=True),
        sa.Column("secondary_appeal_axis", sa.String(100), nullable=True),
        sa.Column("appeal_strategy_summary", sa.Text(), nullable=True),
        sa.Column("competitive_positioning", sa.Text(), nullable=True),
        sa.Column("differentiation_points", postgresql.JSONB(), nullable=True),
        sa.Column("headline_effectiveness", sa.Float(), nullable=True),
        sa.Column("cta_effectiveness", sa.Float(), nullable=True),
        sa.Column("emotional_triggers", postgresql.JSONB(), nullable=True),
        sa.Column("power_words", postgresql.JSONB(), nullable=True),
        sa.Column("strengths", postgresql.JSONB(), nullable=True),
        sa.Column("weaknesses", postgresql.JSONB(), nullable=True),
        sa.Column("reusable_patterns", postgresql.JSONB(), nullable=True),
        sa.Column("improvement_suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("full_analysis_text", sa.Text(), nullable=True),
        sa.Column("raw_analysis", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["landing_page_id"], ["landing_pages.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("landing_page_id"),
    )

    # ------------------------------------------------------------------
    # 21. ad_daily_metrics
    # ------------------------------------------------------------------
    op.create_table(
        "ad_daily_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("view_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("view_count_increase", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("estimated_spend", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("estimated_spend_increase", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("like_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("comment_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("share_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("advertiser_name", sa.String(255), nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_adm_ad_date", "ad_daily_metrics", ["ad_id", "metric_date"], unique=True)
    op.create_index("idx_adm_date", "ad_daily_metrics", ["metric_date"])
    op.create_index("idx_adm_genre_date", "ad_daily_metrics", ["genre", "metric_date"])

    # ------------------------------------------------------------------
    # 22. product_rankings
    # ------------------------------------------------------------------
    op.create_table(
        "product_rankings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("advertiser_name", sa.String(255), nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("previous_rank", sa.Integer(), nullable=True),
        sa.Column("rank_change", sa.Integer(), nullable=True),
        sa.Column("total_view_increase", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_spend_increase", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("cumulative_views", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("cumulative_spend", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("is_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("hit_score", sa.Float(), nullable=True),
        sa.Column("trend_score", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_pr_period_genre_rank", "product_rankings", ["period", "genre", "rank_position"])
    op.create_index("idx_pr_period_rank", "product_rankings", ["period", "rank_position"])

    # ------------------------------------------------------------------
    # 23. notification_configs
    # ------------------------------------------------------------------
    op.create_table(
        "notification_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("api_token", sa.String(500), nullable=True),
        sa.Column("room_id", sa.String(100), nullable=True),
        sa.Column("notify_new_hit_ads", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notify_competitor_activity", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notify_ranking_change", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notify_fatigue_warning", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("watched_genres", postgresql.JSONB(), nullable=True),
        sa.Column("watched_advertisers", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_nc_user", "notification_configs", ["user_id"])

    # ------------------------------------------------------------------
    # 24. saved_items
    # ------------------------------------------------------------------
    op.create_table(
        "saved_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("folder", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_si_user_type", "saved_items", ["user_id", "item_type"])

    # ------------------------------------------------------------------
    # 25. spend_estimates
    # ------------------------------------------------------------------
    op.create_table(
        "spend_estimates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("estimate_date", sa.Date(), nullable=False),
        sa.Column("view_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("view_count_increase", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("cpm_platform_avg", sa.Float(), nullable=True),
        sa.Column("cpm_genre_avg", sa.Float(), nullable=True),
        sa.Column("cpm_seasonal_factor", sa.Float(), nullable=True),
        sa.Column("cpm_user_calibrated", sa.Float(), nullable=True),
        sa.Column("estimated_spend", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("spend_p10", sa.Float(), nullable=True),
        sa.Column("spend_p25", sa.Float(), nullable=True),
        sa.Column("spend_p50", sa.Float(), nullable=True),
        sa.Column("spend_p75", sa.Float(), nullable=True),
        sa.Column("spend_p90", sa.Float(), nullable=True),
        sa.Column("estimation_method", sa.String(50), nullable=True),
        sa.Column("confidence_level", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_se_ad_date", "spend_estimates", ["ad_id", "estimate_date"], unique=True)
    op.create_index("idx_se_date", "spend_estimates", ["estimate_date"])

    # ------------------------------------------------------------------
    # 26. cpm_calibrations
    # ------------------------------------------------------------------
    op.create_table(
        "cpm_calibrations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("actual_cpm", sa.Float(), nullable=True),
        sa.Column("actual_cpv", sa.Float(), nullable=True),
        sa.Column("actual_cpc", sa.Float(), nullable=True),
        sa.Column("data_period_start", sa.Date(), nullable=True),
        sa.Column("data_period_end", sa.Date(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_cpm_user_platform", "cpm_calibrations", ["user_id", "platform"])

    # ------------------------------------------------------------------
    # 27. ad_embeddings
    # ------------------------------------------------------------------
    op.create_table(
        "ad_embeddings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("visual_embedding", postgresql.JSONB(), nullable=True),
        sa.Column("text_embedding", postgresql.JSONB(), nullable=True),
        sa.Column("combined_embedding", postgresql.JSONB(), nullable=True),
        sa.Column("embedding_type", sa.String(50), server_default="multimodal", nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("auto_appeal_axes", postgresql.JSONB(), nullable=True),
        sa.Column("auto_expression_type", sa.String(100), nullable=True),
        sa.Column("auto_structure_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_ae_ad_id", "ad_embeddings", ["ad_id"], unique=True)
    op.create_index("idx_ae_type", "ad_embeddings", ["embedding_type"])

    # ------------------------------------------------------------------
    # 28. lp_fingerprints
    # ------------------------------------------------------------------
    op.create_table(
        "lp_fingerprints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("landing_page_id", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("structure_hash", sa.String(64), nullable=True),
        sa.Column("offer_fingerprint", sa.String(128), nullable=True),
        sa.Column("offer_cluster_id", sa.Integer(), nullable=True),
        sa.Column("cluster_similarity", sa.Float(), nullable=True),
        sa.Column("offer_price", sa.String(100), nullable=True),
        sa.Column("offer_discount_percent", sa.Float(), nullable=True),
        sa.Column("offer_trial_text", sa.String(255), nullable=True),
        sa.Column("offer_guarantee_text", sa.String(255), nullable=True),
        sa.Column("offer_bonus_items", postgresql.JSONB(), nullable=True),
        sa.Column("tokushoho_company", sa.String(255), nullable=True),
        sa.Column("previous_fingerprint_id", sa.BigInteger(), nullable=True),
        sa.Column("changes_detected", postgresql.JSONB(), nullable=True),
        sa.Column("change_magnitude", sa.Float(), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["landing_page_id"], ["landing_pages.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_lpf_lp_id", "lp_fingerprints", ["landing_page_id"])
    op.create_index("idx_lpf_content_hash", "lp_fingerprints", ["content_hash"])
    op.create_index("idx_lpf_offer_cluster", "lp_fingerprints", ["offer_cluster_id"])

    # ------------------------------------------------------------------
    # 29. alert_logs
    # ------------------------------------------------------------------
    op.create_table(
        "alert_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium", nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("entity_name", sa.String(255), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metric_before", sa.Float(), nullable=True),
        sa.Column("metric_after", sa.Float(), nullable=True),
        sa.Column("change_percent", sa.Float(), nullable=True),
        sa.Column("context_data", postgresql.JSONB(), nullable=True),
        sa.Column("is_notified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_dismissed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_al_type_date", "alert_logs", ["alert_type", "detected_at"])
    op.create_index("idx_al_entity", "alert_logs", ["entity_type", "entity_id"])
    op.create_index("idx_al_severity", "alert_logs", ["severity"])

    # ------------------------------------------------------------------
    # 30. ad_classification_tags
    # ------------------------------------------------------------------
    op.create_table(
        "ad_classification_tags",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("classification_status", sa.String(20), server_default="provisional", nullable=False),
        sa.Column("classified_by", sa.String(50), server_default="auto_fast", nullable=False),
        sa.Column("confirmed_by", sa.String(100), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("previous_value", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_act_ad_field", "ad_classification_tags", ["ad_id", "field_name"])
    op.create_index("idx_act_status", "ad_classification_tags", ["classification_status"])

    # ------------------------------------------------------------------
    # 31. lp_funnels
    # ------------------------------------------------------------------
    op.create_table(
        "lp_funnels",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("funnel_name", sa.String(255), nullable=True),
        sa.Column("root_domain", sa.String(255), nullable=True),
        sa.Column("advertiser_name", sa.String(255), nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("total_steps", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("funnel_type", sa.String(50), nullable=True),
        sa.Column("estimated_total_spend", sa.Float(), nullable=True),
        sa.Column("ad_count", sa.Integer(), nullable=True),
        sa.Column("advertiser_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lpf_root_domain", "lp_funnels", ["root_domain"])
    op.create_index("idx_lpf_advertiser", "lp_funnels", ["advertiser_name"])

    # ------------------------------------------------------------------
    # 32. funnel_steps
    # ------------------------------------------------------------------
    op.create_table(
        "funnel_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("funnel_id", sa.BigInteger(), nullable=False),
        sa.Column("landing_page_id", sa.BigInteger(), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("page_title", sa.String(500), nullable=True),
        sa.Column("estimated_dropoff_rate", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["funnel_id"], ["lp_funnels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["landing_page_id"], ["landing_pages.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_fs_funnel_order", "funnel_steps", ["funnel_id", "step_order"])

    # ------------------------------------------------------------------
    # 33. trend_predictions
    # ------------------------------------------------------------------
    op.create_table(
        "trend_predictions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=False),
        sa.Column("prediction_date", sa.Date(), nullable=False),
        sa.Column("view_velocity_1d", sa.Float(), nullable=True),
        sa.Column("view_velocity_3d", sa.Float(), nullable=True),
        sa.Column("view_velocity_7d", sa.Float(), nullable=True),
        sa.Column("view_acceleration", sa.Float(), nullable=True),
        sa.Column("spend_velocity_1d", sa.Float(), nullable=True),
        sa.Column("spend_velocity_3d", sa.Float(), nullable=True),
        sa.Column("spend_velocity_7d", sa.Float(), nullable=True),
        sa.Column("spend_acceleration", sa.Float(), nullable=True),
        sa.Column("growth_phase", sa.String(30), nullable=True),
        sa.Column("days_since_first_seen", sa.Integer(), nullable=True),
        sa.Column("estimated_peak_date", sa.Date(), nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("genre_avg_velocity", sa.Float(), nullable=True),
        sa.Column("genre_percentile", sa.Float(), nullable=True),
        sa.Column("predicted_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("hit_probability", sa.Float(), nullable=True),
        sa.Column("predicted_peak_spend", sa.Float(), nullable=True),
        sa.Column("momentum_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_tp_ad_date", "trend_predictions", ["ad_id", "prediction_date"])
    op.create_index("idx_tp_predicted_hit", "trend_predictions", ["predicted_hit", "prediction_date"])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table("trend_predictions")
    op.drop_table("funnel_steps")
    op.drop_table("lp_funnels")
    op.drop_table("ad_classification_tags")
    op.drop_table("alert_logs")
    op.drop_table("lp_fingerprints")
    op.drop_table("ad_embeddings")
    op.drop_table("cpm_calibrations")
    op.drop_table("spend_estimates")
    op.drop_table("saved_items")
    op.drop_table("notification_configs")
    op.drop_table("product_rankings")
    op.drop_table("ad_daily_metrics")
    op.drop_table("lp_analyses")
    op.drop_table("appeal_axis_analyses")
    op.drop_table("usp_patterns")
    op.drop_table("lp_sections")
    op.drop_table("landing_pages")
    op.drop_table("ad_fatigue_logs")
    op.drop_table("performance_predictions")
    op.drop_table("creative_templates")
    op.drop_table("generated_creatives")
    op.drop_table("campaign_ads")
    op.drop_table("campaigns")
    op.drop_table("sentiment_results")
    op.drop_table("scene_boundaries")
    op.drop_table("transcriptions")
    op.drop_table("text_detections")
    op.drop_table("detected_objects")
    op.drop_table("ad_analyses")
    op.drop_table("ad_frames")
    op.drop_table("ads")
    op.drop_table("users")

    # Drop all enum types
    ad_platform_enum.drop(op.get_bind(), checkfirst=True)
    ad_status_enum.drop(op.get_bind(), checkfirst=True)
    ad_category_enum.drop(op.get_bind(), checkfirst=True)
    user_role_enum.drop(op.get_bind(), checkfirst=True)
    lp_type_enum.drop(op.get_bind(), checkfirst=True)
    lp_status_enum.drop(op.get_bind(), checkfirst=True)
    appeal_axis_enum.drop(op.get_bind(), checkfirst=True)
    creative_type_enum.drop(op.get_bind(), checkfirst=True)
