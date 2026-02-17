--
-- PostgreSQL database dump
--

\restrict LY0QRmHB0DRLpo49CmnLwE1NhMeOknxQmarqahCsPGWRBBdzLTlZliRKsLB2IXP

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: adcategoryenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.adcategoryenum AS ENUM (
    'EC_D2C',
    'APP',
    'FINANCE',
    'EDUCATION',
    'BEAUTY',
    'FOOD',
    'GAMING',
    'HEALTH',
    'TECHNOLOGY',
    'REAL_ESTATE',
    'TRAVEL',
    'OTHER'
);


--
-- Name: adplatformenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.adplatformenum AS ENUM (
    'YOUTUBE',
    'TIKTOK',
    'INSTAGRAM',
    'FACEBOOK',
    'X_TWITTER',
    'LINE',
    'YAHOO',
    'PINTEREST',
    'SMARTNEWS',
    'GOOGLE_ADS',
    'GUNOSY',
    'OTHER'
);


--
-- Name: adstatusenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.adstatusenum AS ENUM (
    'PENDING',
    'PROCESSING',
    'ANALYZED',
    'FAILED'
);


--
-- Name: appealaxisenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.appealaxisenum AS ENUM (
    'BENEFIT',
    'PROBLEM_SOLUTION',
    'AUTHORITY',
    'SOCIAL_PROOF',
    'URGENCY',
    'PRICE',
    'COMPARISON',
    'EMOTIONAL',
    'FEAR',
    'NOVELTY'
);


--
-- Name: creativetypeenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.creativetypeenum AS ENUM (
    'VIDEO_SCRIPT',
    'STORYBOARD',
    'AD_COPY',
    'BANNER',
    'LP_COPY',
    'NARRATION'
);


--
-- Name: lpstatusenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.lpstatusenum AS ENUM (
    'PENDING',
    'CRAWLING',
    'ANALYZING',
    'COMPLETED',
    'FAILED'
);


--
-- Name: lptypeenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.lptypeenum AS ENUM (
    'ARTICLE',
    'EC_DIRECT',
    'LEAD_GEN',
    'APP_STORE',
    'BRAND',
    'OTHER'
);


--
-- Name: userrole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.userrole AS ENUM (
    'ADMIN',
    'ANALYST',
    'CREATOR',
    'VIEWER'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ad_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ad_analyses (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    total_scenes integer,
    avg_scene_duration double precision,
    scene_transitions jsonb,
    face_closeup_ratio double precision,
    text_overlay_ratio double precision,
    product_display_ratio double precision,
    ui_display_ratio double precision,
    is_ugc_style boolean,
    has_narration boolean,
    has_bgm boolean,
    has_subtitles boolean,
    hook_type character varying(100),
    hook_text text,
    hook_score double precision,
    cta_text text,
    cta_timestamp double precision,
    cta_type character varying(100),
    overall_sentiment character varying(50),
    sentiment_score double precision,
    emotion_breakdown jsonb,
    dominant_color_palette jsonb,
    color_temperature character varying(50),
    full_transcript text,
    keywords jsonb,
    topics jsonb,
    winning_score double precision,
    raw_analysis jsonb,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: ad_analyses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ad_analyses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ad_analyses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ad_analyses_id_seq OWNED BY public.ad_analyses.id;


--
-- Name: ad_classification_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ad_classification_tags (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    field_name character varying(100) NOT NULL,
    value character varying(500) NOT NULL,
    confidence double precision NOT NULL,
    classification_status character varying(20) NOT NULL,
    classified_by character varying(50) NOT NULL,
    confirmed_by character varying(100),
    confirmed_at timestamp with time zone,
    previous_value character varying(500),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: ad_classification_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ad_classification_tags_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ad_classification_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ad_classification_tags_id_seq OWNED BY public.ad_classification_tags.id;


--
-- Name: ad_daily_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ad_daily_metrics (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    metric_date date NOT NULL,
    view_count bigint NOT NULL,
    view_count_increase bigint NOT NULL,
    estimated_spend double precision NOT NULL,
    estimated_spend_increase double precision NOT NULL,
    like_count bigint NOT NULL,
    comment_count bigint NOT NULL,
    share_count bigint NOT NULL,
    engagement_rate double precision,
    ctr double precision,
    genre character varying(100),
    product_name character varying(255),
    advertiser_name character varying(255),
    platform character varying(50),
    created_at timestamp with time zone NOT NULL
);


--
-- Name: ad_daily_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ad_daily_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ad_daily_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ad_daily_metrics_id_seq OWNED BY public.ad_daily_metrics.id;


--
-- Name: ad_embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ad_embeddings (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    visual_embedding jsonb,
    text_embedding jsonb,
    combined_embedding jsonb,
    embedding_type character varying(50) NOT NULL,
    embedding_dim integer,
    model_version character varying(100),
    auto_appeal_axes jsonb,
    auto_expression_type character varying(100),
    auto_structure_type character varying(100),
    created_at timestamp with time zone NOT NULL
);


--
-- Name: ad_embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ad_embeddings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ad_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ad_embeddings_id_seq OWNED BY public.ad_embeddings.id;


--
-- Name: ad_fatigue_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ad_fatigue_logs (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    fatigue_score double precision NOT NULL,
    days_active integer NOT NULL,
    performance_trend character varying(50) NOT NULL,
    estimated_remaining_days integer,
    recommendation text,
    replacement_suggestions jsonb,
    metrics_snapshot jsonb,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: ad_fatigue_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ad_fatigue_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ad_fatigue_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ad_fatigue_logs_id_seq OWNED BY public.ad_fatigue_logs.id;


--
-- Name: ad_frames; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ad_frames (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    frame_number integer NOT NULL,
    timestamp_seconds double precision NOT NULL,
    s3_key character varying(500) NOT NULL,
    is_keyframe boolean NOT NULL,
    scene_id integer,
    brightness double precision,
    contrast double precision,
    dominant_colors jsonb,
    composition_metadata jsonb,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: ad_frames_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ad_frames_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ad_frames_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ad_frames_id_seq OWNED BY public.ad_frames.id;


--
-- Name: ads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ads (
    id bigint NOT NULL,
    external_id character varying(255),
    title character varying(500),
    description text,
    platform public.adplatformenum NOT NULL,
    status public.adstatusenum NOT NULL,
    category public.adcategoryenum,
    video_url text,
    s3_key character varying(500),
    thumbnail_s3_key character varying(500),
    duration_seconds double precision,
    resolution_width integer,
    resolution_height integer,
    file_size_bytes bigint,
    advertiser_name character varying(255),
    advertiser_url text,
    brand_name character varying(255),
    estimated_impressions bigint,
    estimated_ctr double precision,
    estimated_cvr double precision,
    view_count bigint,
    like_count bigint,
    first_seen_at timestamp with time zone,
    last_seen_at timestamp with time zone,
    metadata jsonb,
    tags jsonb,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: ads_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ads_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ads_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ads_id_seq OWNED BY public.ads.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: alert_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alert_logs (
    id bigint NOT NULL,
    alert_type character varying(50) NOT NULL,
    severity character varying(20) NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id bigint,
    entity_name character varying(255),
    title character varying(500) NOT NULL,
    description text,
    metric_before double precision,
    metric_after double precision,
    change_percent double precision,
    context_data jsonb,
    is_notified boolean NOT NULL,
    is_dismissed boolean NOT NULL,
    detected_at timestamp with time zone NOT NULL
);


--
-- Name: alert_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alert_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alert_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alert_logs_id_seq OWNED BY public.alert_logs.id;


--
-- Name: appeal_axis_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appeal_axis_analyses (
    id bigint NOT NULL,
    landing_page_id bigint NOT NULL,
    appeal_axis public.appealaxisenum NOT NULL,
    strength_score double precision NOT NULL,
    evidence_texts jsonb,
    section_ids jsonb
);


--
-- Name: appeal_axis_analyses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.appeal_axis_analyses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: appeal_axis_analyses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.appeal_axis_analyses_id_seq OWNED BY public.appeal_axis_analyses.id;


--
-- Name: campaign_ads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.campaign_ads (
    id bigint NOT NULL,
    campaign_id bigint NOT NULL,
    ad_id bigint NOT NULL,
    notes text,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: campaign_ads_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.campaign_ads_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: campaign_ads_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.campaign_ads_id_seq OWNED BY public.campaign_ads.id;


--
-- Name: campaigns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.campaigns (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    user_id integer NOT NULL,
    metadata jsonb,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: campaigns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.campaigns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: campaigns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.campaigns_id_seq OWNED BY public.campaigns.id;


--
-- Name: cpm_calibrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cpm_calibrations (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    platform character varying(50) NOT NULL,
    genre character varying(100),
    actual_cpm double precision,
    actual_cpv double precision,
    actual_cpc double precision,
    data_period_start date,
    data_period_end date,
    sample_size integer,
    notes text,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: cpm_calibrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cpm_calibrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cpm_calibrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cpm_calibrations_id_seq OWNED BY public.cpm_calibrations.id;


--
-- Name: creative_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.creative_templates (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    creative_type public.creativetypeenum NOT NULL,
    description text,
    template_content jsonb NOT NULL,
    category character varying(100),
    winning_score double precision,
    usage_count integer NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: creative_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.creative_templates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: creative_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.creative_templates_id_seq OWNED BY public.creative_templates.id;


--
-- Name: detected_objects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.detected_objects (
    id bigint NOT NULL,
    analysis_id bigint NOT NULL,
    frame_number integer NOT NULL,
    timestamp_seconds double precision NOT NULL,
    class_name character varying(100) NOT NULL,
    confidence double precision NOT NULL,
    bbox_x double precision NOT NULL,
    bbox_y double precision NOT NULL,
    bbox_width double precision NOT NULL,
    bbox_height double precision NOT NULL,
    metadata jsonb
);


--
-- Name: detected_objects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.detected_objects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: detected_objects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.detected_objects_id_seq OWNED BY public.detected_objects.id;


--
-- Name: funnel_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.funnel_steps (
    id bigint NOT NULL,
    funnel_id bigint NOT NULL,
    landing_page_id bigint,
    step_order integer NOT NULL,
    step_type character varying(50) NOT NULL,
    url text,
    page_title character varying(500),
    estimated_dropoff_rate double precision,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: funnel_steps_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.funnel_steps_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: funnel_steps_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.funnel_steps_id_seq OWNED BY public.funnel_steps.id;


--
-- Name: generated_creatives; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.generated_creatives (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    creative_type public.creativetypeenum NOT NULL,
    product_name character varying(255),
    product_description text,
    target_audience text,
    appeal_axis character varying(255),
    reference_ad_id bigint,
    input_params jsonb,
    title character varying(500),
    content text NOT NULL,
    content_structured jsonb,
    s3_key character varying(500),
    model_used character varying(100),
    prompt_used text,
    generation_time_ms integer,
    quality_score double precision,
    variation_group_id character varying(100),
    variation_number integer,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: generated_creatives_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.generated_creatives_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: generated_creatives_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.generated_creatives_id_seq OWNED BY public.generated_creatives.id;


--
-- Name: landing_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.landing_pages (
    id bigint NOT NULL,
    ad_id bigint,
    url text NOT NULL,
    url_hash character varying(64) NOT NULL,
    final_url text,
    domain character varying(255),
    title character varying(500),
    meta_description text,
    og_image_url text,
    screenshot_s3_key character varying(500),
    full_page_screenshot_s3_key character varying(500),
    lp_type public.lptypeenum NOT NULL,
    genre character varying(100),
    advertiser_name character varying(255),
    product_name character varying(255),
    word_count integer,
    image_count integer,
    video_embed_count integer,
    form_count integer,
    cta_count integer,
    testimonial_count integer,
    estimated_read_time_seconds integer,
    total_sections integer,
    scroll_depth_px integer,
    hero_headline text,
    hero_subheadline text,
    primary_cta_text character varying(255),
    full_text_content text,
    has_pricing boolean,
    price_text character varying(255),
    discount_text character varying(255),
    is_own boolean NOT NULL,
    own_lp_label character varying(255),
    own_lp_version integer,
    status public.lpstatusenum NOT NULL,
    crawled_at timestamp with time zone,
    analyzed_at timestamp with time zone,
    raw_html_s3_key character varying(500),
    metadata jsonb,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: landing_pages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.landing_pages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: landing_pages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.landing_pages_id_seq OWNED BY public.landing_pages.id;


--
-- Name: lp_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lp_analyses (
    id bigint NOT NULL,
    landing_page_id bigint NOT NULL,
    overall_quality_score double precision,
    conversion_potential_score double precision,
    trust_score double precision,
    urgency_score double precision,
    page_flow_pattern character varying(255),
    structure_summary text,
    inferred_target_gender character varying(50),
    inferred_target_age_range character varying(50),
    inferred_target_concerns jsonb,
    target_persona_summary text,
    primary_appeal_axis character varying(100),
    secondary_appeal_axis character varying(100),
    appeal_strategy_summary text,
    competitive_positioning text,
    differentiation_points jsonb,
    headline_effectiveness double precision,
    cta_effectiveness double precision,
    emotional_triggers jsonb,
    power_words jsonb,
    strengths jsonb,
    weaknesses jsonb,
    reusable_patterns jsonb,
    improvement_suggestions jsonb,
    full_analysis_text text,
    raw_analysis jsonb,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: lp_analyses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lp_analyses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lp_analyses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lp_analyses_id_seq OWNED BY public.lp_analyses.id;


--
-- Name: lp_fingerprints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lp_fingerprints (
    id bigint NOT NULL,
    landing_page_id bigint NOT NULL,
    content_hash character varying(64),
    structure_hash character varying(64),
    offer_fingerprint character varying(128),
    offer_cluster_id integer,
    cluster_similarity double precision,
    offer_price character varying(100),
    offer_discount_percent double precision,
    offer_trial_text character varying(255),
    offer_guarantee_text character varying(255),
    offer_bonus_items jsonb,
    tokushoho_company character varying(255),
    previous_fingerprint_id bigint,
    changes_detected jsonb,
    change_magnitude double precision,
    snapshot_date date NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: lp_fingerprints_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lp_fingerprints_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lp_fingerprints_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lp_fingerprints_id_seq OWNED BY public.lp_fingerprints.id;


--
-- Name: lp_funnels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lp_funnels (
    id bigint NOT NULL,
    funnel_name character varying(255),
    root_domain character varying(255),
    advertiser_name character varying(255),
    genre character varying(100),
    product_name character varying(255),
    total_steps integer NOT NULL,
    funnel_type character varying(50),
    estimated_total_spend double precision,
    ad_count integer,
    advertiser_count integer,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: lp_funnels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lp_funnels_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lp_funnels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lp_funnels_id_seq OWNED BY public.lp_funnels.id;


--
-- Name: lp_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lp_sections (
    id bigint NOT NULL,
    landing_page_id bigint NOT NULL,
    section_order integer NOT NULL,
    section_type character varying(100) NOT NULL,
    heading text,
    body_text text,
    has_image boolean NOT NULL,
    has_video boolean NOT NULL,
    has_cta boolean NOT NULL,
    cta_text character varying(255),
    position_y_percent double precision,
    extracted_data jsonb
);


--
-- Name: lp_sections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lp_sections_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lp_sections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lp_sections_id_seq OWNED BY public.lp_sections.id;


--
-- Name: notification_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_configs (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    channel_type character varying(50) NOT NULL,
    webhook_url text,
    api_token character varying(500),
    room_id character varying(100),
    notify_new_hit_ads boolean NOT NULL,
    notify_competitor_activity boolean NOT NULL,
    notify_ranking_change boolean NOT NULL,
    notify_fatigue_warning boolean NOT NULL,
    watched_genres jsonb,
    watched_advertisers jsonb,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: notification_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notification_configs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notification_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notification_configs_id_seq OWNED BY public.notification_configs.id;


--
-- Name: performance_predictions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.performance_predictions (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    predicted_ctr double precision,
    predicted_cvr double precision,
    predicted_cpa double precision,
    winning_probability double precision,
    optimal_duration_seconds double precision,
    ctr_confidence_low double precision,
    ctr_confidence_high double precision,
    model_version character varying(100),
    feature_importance jsonb,
    improvement_suggestions jsonb,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: performance_predictions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.performance_predictions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: performance_predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.performance_predictions_id_seq OWNED BY public.performance_predictions.id;


--
-- Name: platform_api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_api_keys (
    id integer NOT NULL,
    platform character varying(50) NOT NULL,
    key_name character varying(100) NOT NULL,
    key_value text NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: platform_api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.platform_api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: platform_api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.platform_api_keys_id_seq OWNED BY public.platform_api_keys.id;


--
-- Name: product_rankings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_rankings (
    id bigint NOT NULL,
    period character varying(20) NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    ad_id bigint NOT NULL,
    product_name character varying(255),
    advertiser_name character varying(255),
    genre character varying(100),
    platform character varying(50),
    rank_position integer NOT NULL,
    previous_rank integer,
    rank_change integer,
    total_view_increase bigint NOT NULL,
    total_spend_increase double precision NOT NULL,
    cumulative_views bigint NOT NULL,
    cumulative_spend double precision NOT NULL,
    is_hit boolean NOT NULL,
    hit_score double precision,
    trend_score double precision,
    metadata jsonb,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: product_rankings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_rankings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_rankings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_rankings_id_seq OWNED BY public.product_rankings.id;


--
-- Name: saved_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.saved_items (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    item_type character varying(50) NOT NULL,
    item_id bigint NOT NULL,
    label character varying(255),
    notes text,
    folder character varying(100),
    created_at timestamp with time zone NOT NULL
);


--
-- Name: saved_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.saved_items_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: saved_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.saved_items_id_seq OWNED BY public.saved_items.id;


--
-- Name: scene_boundaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scene_boundaries (
    id bigint NOT NULL,
    analysis_id bigint NOT NULL,
    scene_number integer NOT NULL,
    start_time_seconds double precision NOT NULL,
    end_time_seconds double precision NOT NULL,
    duration_seconds double precision NOT NULL,
    scene_type character varying(100),
    dominant_color character varying(50),
    has_text_overlay boolean,
    has_person boolean,
    description text,
    metadata jsonb
);


--
-- Name: scene_boundaries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scene_boundaries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scene_boundaries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scene_boundaries_id_seq OWNED BY public.scene_boundaries.id;


--
-- Name: sentiment_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentiment_results (
    id bigint NOT NULL,
    analysis_id bigint NOT NULL,
    segment_type character varying(50) NOT NULL,
    segment_text text,
    start_time_ms integer,
    end_time_ms integer,
    sentiment character varying(50) NOT NULL,
    score double precision NOT NULL,
    emotion_breakdown jsonb
);


--
-- Name: sentiment_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentiment_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentiment_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentiment_results_id_seq OWNED BY public.sentiment_results.id;


--
-- Name: spend_estimates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.spend_estimates (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    estimate_date date NOT NULL,
    view_count bigint NOT NULL,
    view_count_increase bigint NOT NULL,
    platform character varying(50),
    genre character varying(100),
    cpm_platform_avg double precision,
    cpm_genre_avg double precision,
    cpm_seasonal_factor double precision,
    cpm_user_calibrated double precision,
    estimated_spend double precision NOT NULL,
    spend_p10 double precision,
    spend_p25 double precision,
    spend_p50 double precision,
    spend_p75 double precision,
    spend_p90 double precision,
    estimation_method character varying(50),
    confidence_level double precision,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: spend_estimates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.spend_estimates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: spend_estimates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.spend_estimates_id_seq OWNED BY public.spend_estimates.id;


--
-- Name: text_detections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.text_detections (
    id bigint NOT NULL,
    analysis_id bigint NOT NULL,
    frame_number integer NOT NULL,
    timestamp_seconds double precision NOT NULL,
    text character varying(1000) NOT NULL,
    confidence double precision NOT NULL,
    language character varying(10),
    bbox_x double precision NOT NULL,
    bbox_y double precision NOT NULL,
    bbox_width double precision NOT NULL,
    bbox_height double precision NOT NULL,
    metadata jsonb
);


--
-- Name: text_detections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.text_detections_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: text_detections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.text_detections_id_seq OWNED BY public.text_detections.id;


--
-- Name: transcriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcriptions (
    id bigint NOT NULL,
    analysis_id bigint NOT NULL,
    text text NOT NULL,
    language character varying(10),
    start_time_ms integer NOT NULL,
    end_time_ms integer NOT NULL,
    speaker_id character varying(50),
    confidence double precision NOT NULL
);


--
-- Name: transcriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transcriptions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transcriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transcriptions_id_seq OWNED BY public.transcriptions.id;


--
-- Name: trend_predictions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trend_predictions (
    id bigint NOT NULL,
    ad_id bigint NOT NULL,
    prediction_date date NOT NULL,
    view_velocity_1d double precision,
    view_velocity_3d double precision,
    view_velocity_7d double precision,
    view_acceleration double precision,
    spend_velocity_1d double precision,
    spend_velocity_3d double precision,
    spend_velocity_7d double precision,
    spend_acceleration double precision,
    growth_phase character varying(30),
    days_since_first_seen integer,
    estimated_peak_date date,
    genre character varying(100),
    genre_avg_velocity double precision,
    genre_percentile double precision,
    predicted_hit boolean NOT NULL,
    hit_probability double precision,
    predicted_peak_spend double precision,
    momentum_score double precision,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: trend_predictions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trend_predictions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trend_predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trend_predictions_id_seq OWNED BY public.trend_predictions.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    full_name character varying(255) NOT NULL,
    role public.userrole NOT NULL,
    is_active boolean NOT NULL,
    company character varying(255),
    avatar_url text,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: usp_patterns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usp_patterns (
    id bigint NOT NULL,
    landing_page_id bigint NOT NULL,
    usp_category character varying(100) NOT NULL,
    usp_text text NOT NULL,
    usp_headline character varying(500),
    supporting_evidence text,
    prominence_score double precision,
    position_in_page character varying(50),
    keywords jsonb
);


--
-- Name: usp_patterns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usp_patterns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usp_patterns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usp_patterns_id_seq OWNED BY public.usp_patterns.id;


--
-- Name: ad_analyses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_analyses ALTER COLUMN id SET DEFAULT nextval('public.ad_analyses_id_seq'::regclass);


--
-- Name: ad_classification_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_classification_tags ALTER COLUMN id SET DEFAULT nextval('public.ad_classification_tags_id_seq'::regclass);


--
-- Name: ad_daily_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_daily_metrics ALTER COLUMN id SET DEFAULT nextval('public.ad_daily_metrics_id_seq'::regclass);


--
-- Name: ad_embeddings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_embeddings ALTER COLUMN id SET DEFAULT nextval('public.ad_embeddings_id_seq'::regclass);


--
-- Name: ad_fatigue_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_fatigue_logs ALTER COLUMN id SET DEFAULT nextval('public.ad_fatigue_logs_id_seq'::regclass);


--
-- Name: ad_frames id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_frames ALTER COLUMN id SET DEFAULT nextval('public.ad_frames_id_seq'::regclass);


--
-- Name: ads id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ads ALTER COLUMN id SET DEFAULT nextval('public.ads_id_seq'::regclass);


--
-- Name: alert_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_logs ALTER COLUMN id SET DEFAULT nextval('public.alert_logs_id_seq'::regclass);


--
-- Name: appeal_axis_analyses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appeal_axis_analyses ALTER COLUMN id SET DEFAULT nextval('public.appeal_axis_analyses_id_seq'::regclass);


--
-- Name: campaign_ads id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaign_ads ALTER COLUMN id SET DEFAULT nextval('public.campaign_ads_id_seq'::regclass);


--
-- Name: campaigns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns ALTER COLUMN id SET DEFAULT nextval('public.campaigns_id_seq'::regclass);


--
-- Name: cpm_calibrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpm_calibrations ALTER COLUMN id SET DEFAULT nextval('public.cpm_calibrations_id_seq'::regclass);


--
-- Name: creative_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.creative_templates ALTER COLUMN id SET DEFAULT nextval('public.creative_templates_id_seq'::regclass);


--
-- Name: detected_objects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.detected_objects ALTER COLUMN id SET DEFAULT nextval('public.detected_objects_id_seq'::regclass);


--
-- Name: funnel_steps id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funnel_steps ALTER COLUMN id SET DEFAULT nextval('public.funnel_steps_id_seq'::regclass);


--
-- Name: generated_creatives id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_creatives ALTER COLUMN id SET DEFAULT nextval('public.generated_creatives_id_seq'::regclass);


--
-- Name: landing_pages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_pages ALTER COLUMN id SET DEFAULT nextval('public.landing_pages_id_seq'::regclass);


--
-- Name: lp_analyses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_analyses ALTER COLUMN id SET DEFAULT nextval('public.lp_analyses_id_seq'::regclass);


--
-- Name: lp_fingerprints id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_fingerprints ALTER COLUMN id SET DEFAULT nextval('public.lp_fingerprints_id_seq'::regclass);


--
-- Name: lp_funnels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_funnels ALTER COLUMN id SET DEFAULT nextval('public.lp_funnels_id_seq'::regclass);


--
-- Name: lp_sections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_sections ALTER COLUMN id SET DEFAULT nextval('public.lp_sections_id_seq'::regclass);


--
-- Name: notification_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_configs ALTER COLUMN id SET DEFAULT nextval('public.notification_configs_id_seq'::regclass);


--
-- Name: performance_predictions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_predictions ALTER COLUMN id SET DEFAULT nextval('public.performance_predictions_id_seq'::regclass);


--
-- Name: platform_api_keys id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_api_keys ALTER COLUMN id SET DEFAULT nextval('public.platform_api_keys_id_seq'::regclass);


--
-- Name: product_rankings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_rankings ALTER COLUMN id SET DEFAULT nextval('public.product_rankings_id_seq'::regclass);


--
-- Name: saved_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saved_items ALTER COLUMN id SET DEFAULT nextval('public.saved_items_id_seq'::regclass);


--
-- Name: scene_boundaries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scene_boundaries ALTER COLUMN id SET DEFAULT nextval('public.scene_boundaries_id_seq'::regclass);


--
-- Name: sentiment_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentiment_results ALTER COLUMN id SET DEFAULT nextval('public.sentiment_results_id_seq'::regclass);


--
-- Name: spend_estimates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spend_estimates ALTER COLUMN id SET DEFAULT nextval('public.spend_estimates_id_seq'::regclass);


--
-- Name: text_detections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_detections ALTER COLUMN id SET DEFAULT nextval('public.text_detections_id_seq'::regclass);


--
-- Name: transcriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions ALTER COLUMN id SET DEFAULT nextval('public.transcriptions_id_seq'::regclass);


--
-- Name: trend_predictions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trend_predictions ALTER COLUMN id SET DEFAULT nextval('public.trend_predictions_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: usp_patterns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usp_patterns ALTER COLUMN id SET DEFAULT nextval('public.usp_patterns_id_seq'::regclass);


--
-- Name: ad_analyses ad_analyses_ad_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_analyses
    ADD CONSTRAINT ad_analyses_ad_id_key UNIQUE (ad_id);


--
-- Name: ad_analyses ad_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_analyses
    ADD CONSTRAINT ad_analyses_pkey PRIMARY KEY (id);


--
-- Name: ad_classification_tags ad_classification_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_classification_tags
    ADD CONSTRAINT ad_classification_tags_pkey PRIMARY KEY (id);


--
-- Name: ad_daily_metrics ad_daily_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_daily_metrics
    ADD CONSTRAINT ad_daily_metrics_pkey PRIMARY KEY (id);


--
-- Name: ad_embeddings ad_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_embeddings
    ADD CONSTRAINT ad_embeddings_pkey PRIMARY KEY (id);


--
-- Name: ad_fatigue_logs ad_fatigue_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_fatigue_logs
    ADD CONSTRAINT ad_fatigue_logs_pkey PRIMARY KEY (id);


--
-- Name: ad_frames ad_frames_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_frames
    ADD CONSTRAINT ad_frames_pkey PRIMARY KEY (id);


--
-- Name: ads ads_external_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ads
    ADD CONSTRAINT ads_external_id_key UNIQUE (external_id);


--
-- Name: ads ads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ads
    ADD CONSTRAINT ads_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: alert_logs alert_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_logs
    ADD CONSTRAINT alert_logs_pkey PRIMARY KEY (id);


--
-- Name: appeal_axis_analyses appeal_axis_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appeal_axis_analyses
    ADD CONSTRAINT appeal_axis_analyses_pkey PRIMARY KEY (id);


--
-- Name: campaign_ads campaign_ads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaign_ads
    ADD CONSTRAINT campaign_ads_pkey PRIMARY KEY (id);


--
-- Name: campaigns campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_pkey PRIMARY KEY (id);


--
-- Name: cpm_calibrations cpm_calibrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpm_calibrations
    ADD CONSTRAINT cpm_calibrations_pkey PRIMARY KEY (id);


--
-- Name: creative_templates creative_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.creative_templates
    ADD CONSTRAINT creative_templates_pkey PRIMARY KEY (id);


--
-- Name: detected_objects detected_objects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.detected_objects
    ADD CONSTRAINT detected_objects_pkey PRIMARY KEY (id);


--
-- Name: funnel_steps funnel_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funnel_steps
    ADD CONSTRAINT funnel_steps_pkey PRIMARY KEY (id);


--
-- Name: generated_creatives generated_creatives_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_creatives
    ADD CONSTRAINT generated_creatives_pkey PRIMARY KEY (id);


--
-- Name: landing_pages landing_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_pages
    ADD CONSTRAINT landing_pages_pkey PRIMARY KEY (id);


--
-- Name: lp_analyses lp_analyses_landing_page_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_analyses
    ADD CONSTRAINT lp_analyses_landing_page_id_key UNIQUE (landing_page_id);


--
-- Name: lp_analyses lp_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_analyses
    ADD CONSTRAINT lp_analyses_pkey PRIMARY KEY (id);


--
-- Name: lp_fingerprints lp_fingerprints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_fingerprints
    ADD CONSTRAINT lp_fingerprints_pkey PRIMARY KEY (id);


--
-- Name: lp_funnels lp_funnels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_funnels
    ADD CONSTRAINT lp_funnels_pkey PRIMARY KEY (id);


--
-- Name: lp_sections lp_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_sections
    ADD CONSTRAINT lp_sections_pkey PRIMARY KEY (id);


--
-- Name: notification_configs notification_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_configs
    ADD CONSTRAINT notification_configs_pkey PRIMARY KEY (id);


--
-- Name: performance_predictions performance_predictions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_predictions
    ADD CONSTRAINT performance_predictions_pkey PRIMARY KEY (id);


--
-- Name: platform_api_keys platform_api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_api_keys
    ADD CONSTRAINT platform_api_keys_pkey PRIMARY KEY (id);


--
-- Name: product_rankings product_rankings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_rankings
    ADD CONSTRAINT product_rankings_pkey PRIMARY KEY (id);


--
-- Name: saved_items saved_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saved_items
    ADD CONSTRAINT saved_items_pkey PRIMARY KEY (id);


--
-- Name: scene_boundaries scene_boundaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scene_boundaries
    ADD CONSTRAINT scene_boundaries_pkey PRIMARY KEY (id);


--
-- Name: sentiment_results sentiment_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentiment_results
    ADD CONSTRAINT sentiment_results_pkey PRIMARY KEY (id);


--
-- Name: spend_estimates spend_estimates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spend_estimates
    ADD CONSTRAINT spend_estimates_pkey PRIMARY KEY (id);


--
-- Name: text_detections text_detections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_detections
    ADD CONSTRAINT text_detections_pkey PRIMARY KEY (id);


--
-- Name: transcriptions transcriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_pkey PRIMARY KEY (id);


--
-- Name: trend_predictions trend_predictions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trend_predictions
    ADD CONSTRAINT trend_predictions_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: usp_patterns usp_patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usp_patterns
    ADD CONSTRAINT usp_patterns_pkey PRIMARY KEY (id);


--
-- Name: idx_act_ad_field; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_act_ad_field ON public.ad_classification_tags USING btree (ad_id, field_name);


--
-- Name: idx_act_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_act_status ON public.ad_classification_tags USING btree (classification_status);


--
-- Name: idx_adm_ad_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_adm_ad_date ON public.ad_daily_metrics USING btree (ad_id, metric_date);


--
-- Name: idx_adm_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_adm_date ON public.ad_daily_metrics USING btree (metric_date);


--
-- Name: idx_adm_genre_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_adm_genre_date ON public.ad_daily_metrics USING btree (genre, metric_date);


--
-- Name: idx_ads_advertiser; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ads_advertiser ON public.ads USING btree (advertiser_name);


--
-- Name: idx_ads_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ads_category ON public.ads USING btree (category);


--
-- Name: idx_ads_platform_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ads_platform_created ON public.ads USING btree (platform, created_at);


--
-- Name: idx_ads_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ads_status ON public.ads USING btree (status);


--
-- Name: idx_ae_ad_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_ae_ad_id ON public.ad_embeddings USING btree (ad_id);


--
-- Name: idx_ae_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ae_type ON public.ad_embeddings USING btree (embedding_type);


--
-- Name: idx_al_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_al_entity ON public.alert_logs USING btree (entity_type, entity_id);


--
-- Name: idx_al_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_al_severity ON public.alert_logs USING btree (severity);


--
-- Name: idx_al_type_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_al_type_date ON public.alert_logs USING btree (alert_type, detected_at);


--
-- Name: idx_appeal_lp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appeal_lp_id ON public.appeal_axis_analyses USING btree (landing_page_id);


--
-- Name: idx_cpm_user_platform; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpm_user_platform ON public.cpm_calibrations USING btree (user_id, platform);


--
-- Name: idx_detected_objects_analysis_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_detected_objects_analysis_class ON public.detected_objects USING btree (analysis_id, class_name);


--
-- Name: idx_frames_ad_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_frames_ad_timestamp ON public.ad_frames USING btree (ad_id, timestamp_seconds);


--
-- Name: idx_fs_funnel_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fs_funnel_order ON public.funnel_steps USING btree (funnel_id, step_order);


--
-- Name: idx_lp_ad_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lp_ad_id ON public.landing_pages USING btree (ad_id);


--
-- Name: idx_lp_advertiser; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lp_advertiser ON public.landing_pages USING btree (advertiser_name);


--
-- Name: idx_lp_genre; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lp_genre ON public.landing_pages USING btree (genre);


--
-- Name: idx_lp_sections_lp_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lp_sections_lp_order ON public.lp_sections USING btree (landing_page_id, section_order);


--
-- Name: idx_lp_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lp_type ON public.landing_pages USING btree (lp_type);


--
-- Name: idx_lp_url_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_lp_url_hash ON public.landing_pages USING btree (url_hash);


--
-- Name: idx_lpf_advertiser; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lpf_advertiser ON public.lp_funnels USING btree (advertiser_name);


--
-- Name: idx_lpf_content_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lpf_content_hash ON public.lp_fingerprints USING btree (content_hash);


--
-- Name: idx_lpf_lp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lpf_lp_id ON public.lp_fingerprints USING btree (landing_page_id);


--
-- Name: idx_lpf_offer_cluster; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lpf_offer_cluster ON public.lp_fingerprints USING btree (offer_cluster_id);


--
-- Name: idx_lpf_root_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lpf_root_domain ON public.lp_funnels USING btree (root_domain);


--
-- Name: idx_nc_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nc_user ON public.notification_configs USING btree (user_id);


--
-- Name: idx_pr_period_genre_rank; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pr_period_genre_rank ON public.product_rankings USING btree (period, genre, rank_position);


--
-- Name: idx_pr_period_rank; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pr_period_rank ON public.product_rankings USING btree (period, rank_position);


--
-- Name: idx_se_ad_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_se_ad_date ON public.spend_estimates USING btree (ad_id, estimate_date);


--
-- Name: idx_se_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_se_date ON public.spend_estimates USING btree (estimate_date);


--
-- Name: idx_si_user_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_si_user_type ON public.saved_items USING btree (user_id, item_type);


--
-- Name: idx_text_detections_analysis; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_text_detections_analysis ON public.text_detections USING btree (analysis_id);


--
-- Name: idx_tp_ad_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tp_ad_date ON public.trend_predictions USING btree (ad_id, prediction_date);


--
-- Name: idx_tp_predicted_hit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tp_predicted_hit ON public.trend_predictions USING btree (predicted_hit, prediction_date);


--
-- Name: idx_transcriptions_analysis_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcriptions_analysis_time ON public.transcriptions USING btree (analysis_id, start_time_ms);


--
-- Name: idx_usp_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_usp_category ON public.usp_patterns USING btree (usp_category);


--
-- Name: idx_usp_lp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_usp_lp_id ON public.usp_patterns USING btree (landing_page_id);


--
-- Name: ix_platform_api_keys_platform; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_platform_api_keys_platform ON public.platform_api_keys USING btree (platform);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ad_analyses ad_analyses_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_analyses
    ADD CONSTRAINT ad_analyses_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: ad_classification_tags ad_classification_tags_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_classification_tags
    ADD CONSTRAINT ad_classification_tags_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: ad_daily_metrics ad_daily_metrics_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_daily_metrics
    ADD CONSTRAINT ad_daily_metrics_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: ad_embeddings ad_embeddings_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_embeddings
    ADD CONSTRAINT ad_embeddings_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: ad_fatigue_logs ad_fatigue_logs_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_fatigue_logs
    ADD CONSTRAINT ad_fatigue_logs_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: ad_frames ad_frames_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_frames
    ADD CONSTRAINT ad_frames_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: appeal_axis_analyses appeal_axis_analyses_landing_page_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appeal_axis_analyses
    ADD CONSTRAINT appeal_axis_analyses_landing_page_id_fkey FOREIGN KEY (landing_page_id) REFERENCES public.landing_pages(id) ON DELETE CASCADE;


--
-- Name: campaign_ads campaign_ads_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaign_ads
    ADD CONSTRAINT campaign_ads_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: campaign_ads campaign_ads_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaign_ads
    ADD CONSTRAINT campaign_ads_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id) ON DELETE CASCADE;


--
-- Name: campaigns campaigns_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: cpm_calibrations cpm_calibrations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpm_calibrations
    ADD CONSTRAINT cpm_calibrations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: detected_objects detected_objects_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.detected_objects
    ADD CONSTRAINT detected_objects_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.ad_analyses(id) ON DELETE CASCADE;


--
-- Name: funnel_steps funnel_steps_funnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funnel_steps
    ADD CONSTRAINT funnel_steps_funnel_id_fkey FOREIGN KEY (funnel_id) REFERENCES public.lp_funnels(id) ON DELETE CASCADE;


--
-- Name: funnel_steps funnel_steps_landing_page_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funnel_steps
    ADD CONSTRAINT funnel_steps_landing_page_id_fkey FOREIGN KEY (landing_page_id) REFERENCES public.landing_pages(id) ON DELETE SET NULL;


--
-- Name: generated_creatives generated_creatives_reference_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_creatives
    ADD CONSTRAINT generated_creatives_reference_ad_id_fkey FOREIGN KEY (reference_ad_id) REFERENCES public.ads(id);


--
-- Name: generated_creatives generated_creatives_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_creatives
    ADD CONSTRAINT generated_creatives_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: landing_pages landing_pages_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_pages
    ADD CONSTRAINT landing_pages_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE SET NULL;


--
-- Name: lp_analyses lp_analyses_landing_page_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_analyses
    ADD CONSTRAINT lp_analyses_landing_page_id_fkey FOREIGN KEY (landing_page_id) REFERENCES public.landing_pages(id) ON DELETE CASCADE;


--
-- Name: lp_fingerprints lp_fingerprints_landing_page_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_fingerprints
    ADD CONSTRAINT lp_fingerprints_landing_page_id_fkey FOREIGN KEY (landing_page_id) REFERENCES public.landing_pages(id) ON DELETE CASCADE;


--
-- Name: lp_sections lp_sections_landing_page_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lp_sections
    ADD CONSTRAINT lp_sections_landing_page_id_fkey FOREIGN KEY (landing_page_id) REFERENCES public.landing_pages(id) ON DELETE CASCADE;


--
-- Name: notification_configs notification_configs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_configs
    ADD CONSTRAINT notification_configs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: performance_predictions performance_predictions_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_predictions
    ADD CONSTRAINT performance_predictions_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: product_rankings product_rankings_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_rankings
    ADD CONSTRAINT product_rankings_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: saved_items saved_items_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saved_items
    ADD CONSTRAINT saved_items_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: scene_boundaries scene_boundaries_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scene_boundaries
    ADD CONSTRAINT scene_boundaries_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.ad_analyses(id) ON DELETE CASCADE;


--
-- Name: sentiment_results sentiment_results_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentiment_results
    ADD CONSTRAINT sentiment_results_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.ad_analyses(id) ON DELETE CASCADE;


--
-- Name: spend_estimates spend_estimates_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spend_estimates
    ADD CONSTRAINT spend_estimates_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: text_detections text_detections_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_detections
    ADD CONSTRAINT text_detections_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.ad_analyses(id) ON DELETE CASCADE;


--
-- Name: transcriptions transcriptions_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.ad_analyses(id) ON DELETE CASCADE;


--
-- Name: trend_predictions trend_predictions_ad_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trend_predictions
    ADD CONSTRAINT trend_predictions_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES public.ads(id) ON DELETE CASCADE;


--
-- Name: usp_patterns usp_patterns_landing_page_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usp_patterns
    ADD CONSTRAINT usp_patterns_landing_page_id_fkey FOREIGN KEY (landing_page_id) REFERENCES public.landing_pages(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict LY0QRmHB0DRLpo49CmnLwE1NhMeOknxQmarqahCsPGWRBBdzLTlZliRKsLB2IXP

