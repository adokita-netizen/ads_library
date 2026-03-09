from datetime import date
from contextlib import contextmanager

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, AdCategoryEnum
from app.models.ad_metrics import AdDailyMetrics


def _import_rankings_helpers():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints.rankings import (
        _compute_view_increase_map,
        _get_ad_cpm_details,
        _normalize_ad_format,
        _resolve_is_affiliate,
        _resolve_transition_type,
    )
    return _compute_view_increase_map, _get_ad_cpm_details, _normalize_ad_format, _resolve_is_affiliate, _resolve_transition_type


def _import_topic_helpers():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints.rankings import (
        _extract_topic_signals,
        _infer_topic_signals,
        _metadata_query_match,
        _topic_matches_filter,
    )
    return _extract_topic_signals, _infer_topic_signals, _metadata_query_match, _topic_matches_filter


def _import_language_helpers():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints.rankings import (
        _is_japanese_ad,
        _is_japanese_text,
        _is_quality_ad,
    )
    return _is_japanese_ad, _is_japanese_text, _is_quality_ad


def _import_crawl_diag_helpers():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints.rankings import (
        _build_low_volume_recovery_queries,
        _build_platform_expansion_queries,
        _build_recovery_platform_batches,
        _compute_platform_limit_map,
        _classify_zero_save_cause,
        _ensure_platform_list,
        _get_learned_recovery_queries,
        _platform_fetch_counts,
        _record_platform_query_learning,
    )
    return (
        _build_low_volume_recovery_queries,
        _build_platform_expansion_queries,
        _classify_zero_save_cause,
        _ensure_platform_list,
        _platform_fetch_counts,
        _build_recovery_platform_batches,
        _compute_platform_limit_map,
        _record_platform_query_learning,
        _get_learned_recovery_queries,
    )


def _import_learning_prune_helpers():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints.rankings import (
        _count_learning_entries,
        _prune_platform_query_learnings,
    )
    return _count_learning_entries, _prune_platform_query_learnings


def _mk_ad(**kwargs) -> Ad:
    return Ad(
        external_id=kwargs.get("external_id"),
        platform=kwargs.get("platform", AdPlatformEnum.YOUTUBE),
        status=kwargs.get("status", AdStatusEnum.PENDING),
        title=kwargs.get("title", "test"),
        creative_type=kwargs.get("creative_type"),
        video_url=kwargs.get("video_url"),
        destination_url=kwargs.get("destination_url"),
        ad_metadata=kwargs.get("ad_metadata", {}),
    )


def test_normalize_ad_format_video_banner_carousel():
    _, _, _normalize_ad_format, _, _ = _import_rankings_helpers()
    assert _normalize_ad_format(_mk_ad(creative_type="video")) == "video"
    assert _normalize_ad_format(_mk_ad(creative_type="image")) == "banner"
    assert _normalize_ad_format(_mk_ad(creative_type="carousel")) == "carousel"
    assert _normalize_ad_format(_mk_ad(video_url="https://example.com/v.mp4")) == "video"


def test_resolve_transition_type_prefers_metadata_then_fallback():
    _, _, _, _, _resolve_transition_type = _import_rankings_helpers()
    ad_meta = _mk_ad(ad_metadata={"transition_type": "survey_lp"})
    assert _resolve_transition_type(ad_meta, "article_lp") == "survey_lp"

    ad_meta_alias = _mk_ad(ad_metadata={"transition_type": "questionnaire"})
    assert _resolve_transition_type(ad_meta_alias, "article_lp") == "survey_lp"
    ad_meta_other = _mk_ad(ad_metadata={"transition_type": "official_site"})
    assert _resolve_transition_type(ad_meta_other, "article_lp") == "other"

    ad_plain = _mk_ad()
    assert _resolve_transition_type(ad_plain, "article_lp") == "article_lp"
    assert _resolve_transition_type(ad_plain, "manga_lp") == "manga_lp"
    assert _resolve_transition_type(ad_plain, "official_site") == "other"


def test_resolve_is_affiliate_from_bool_and_string():
    _, _, _, _resolve_is_affiliate, _ = _import_rankings_helpers()
    assert _resolve_is_affiliate(_mk_ad(ad_metadata={"is_affiliate": True})) is True
    assert _resolve_is_affiliate(_mk_ad(ad_metadata={"is_affiliate": "false"})) is False
    assert _resolve_is_affiliate(_mk_ad(ad_metadata={"affiliate": "yes"})) is True
    assert _resolve_is_affiliate(_mk_ad(ad_metadata={})) is None


def test_is_japanese_text_requires_actual_japanese_signal():
    _, _is_japanese_text, _ = _import_language_helpers()
    assert _is_japanese_text("GLP-1 medical diet campaign") is False
    assert _is_japanese_text("GLP-1 医療ダイエット campaign") is True


def test_is_quality_ad_accepts_japanese_description_even_if_title_is_english():
    _is_japanese_ad, _, _is_quality_ad = _import_language_helpers()
    ad = _mk_ad(
        title="Summer GLP-1 Campaign",
        ad_metadata={},
    )
    ad.description = "医療ダイエットの無料カウンセリング"

    assert _is_japanese_ad(ad) is True
    assert _is_quality_ad(ad) is True


def test_is_quality_ad_rejects_non_japanese_when_language_metadata_is_missing():
    _is_japanese_ad, _, _is_quality_ad = _import_language_helpers()
    ad = _mk_ad(
        title="Summer GLP-1 Campaign",
        ad_metadata={},
    )
    ad.description = "Free consultation and before after photos"

    assert _is_japanese_ad(ad) is False
    assert _is_quality_ad(ad) is False


def test_compute_view_increase_map_uses_current_minus_previous_snapshot(session):
    _compute_view_increase_map, _, _, _, _ = _import_rankings_helpers()
    ad = _mk_ad(external_id="dpro_delta_001")
    session.add(ad)
    session.flush()

    session.add_all(
        [
            AdDailyMetrics(ad_id=ad.id, metric_date=date(2026, 2, 20), view_count=1000),
            AdDailyMetrics(ad_id=ad.id, metric_date=date(2026, 2, 28), view_count=1800),
            AdDailyMetrics(ad_id=ad.id, metric_date=date(2026, 3, 2), view_count=2500),
        ]
    )
    session.flush()

    result = _compute_view_increase_map(
        session=session,
        ad_ids=[ad.id],
        current_date=date(2026, 3, 2),
        previous_date=date(2026, 2, 28),
    )
    assert result[ad.id] == 700


def test_get_ad_cpm_details_prefers_metadata_value():
    _, _get_ad_cpm_details, _, _, _ = _import_rankings_helpers()
    ad = _mk_ad(platform=AdPlatformEnum.FACEBOOK, ad_metadata={"estimated_cpm_jpy": 1234})
    info = _get_ad_cpm_details(ad)
    assert info["value"] == 1234.0
    assert info["source"] == "metadata_estimated_cpm"
    assert info["confidence"] >= 0.8


def test_get_ad_cpm_details_uses_dynamic_model_when_missing():
    _, _get_ad_cpm_details, _, _, _ = _import_rankings_helpers()
    ad = _mk_ad(platform=AdPlatformEnum.FACEBOOK, ad_metadata={})
    ad.category = AdCategoryEnum.FINANCE
    info = _get_ad_cpm_details(ad)
    assert info["source"] == "platform_season_category_model"
    assert 400 <= info["value"] <= 2400
    assert info["confidence"] == 0.6


def test_extract_topic_signals_normalizes_fields():
    _extract_topic_signals, _, _, _ = _import_topic_helpers()
    ad = _mk_ad(
        ad_metadata={
            "topic_label": "medical_diet",
            "topic_confidence": "0.91",
            "matched_terms": ["GLP-1", "自由診療"],
            "needs_topic_review": "false",
        }
    )
    topic = _extract_topic_signals(ad)
    assert topic["topic_label"] == "medical_diet"
    assert topic["topic_confidence"] == 0.91
    assert topic["matched_terms"] == ["GLP-1", "自由診療"]
    assert topic["needs_topic_review"] is False


def test_topic_matches_filter_checks_label_terms_and_fallback_text():
    _, _, _, _topic_matches_filter = _import_topic_helpers()
    ad = _mk_ad(
        title="話題のGLP-1ダイエット",
        description="オンライン診療で相談",
        ad_metadata={
            "topic_label": "medical_diet",
            "matched_terms": ["GLP-1", "医療ダイエット"],
        },
    )
    assert _topic_matches_filter(ad, "medical_diet") is True
    assert _topic_matches_filter(ad, "glp-1") is True
    assert _topic_matches_filter(ad, "ダイエット") is True
    assert _topic_matches_filter(ad, "aga") is False


def test_infer_topic_signals_detects_medical_diet_and_aga_keywords():
    _, _infer_topic_signals, _, _ = _import_topic_helpers()
    glp = _infer_topic_signals(
        title="GLP-1で医療ダイエット",
        description="オンライン診療で始める",
        advertiser_name="ClinicX",
        query="GLP-1",
        metadata={},
    )
    assert glp["topic_label"] == "medical_diet"
    assert glp["topic_confidence"] >= 0.5
    assert "glp-1" in [t.lower() for t in glp["matched_terms"]]

    aga = _infer_topic_signals(
        title="AGA治療で発毛",
        description="薄毛の悩みに",
        advertiser_name="Hair Clinic",
        query="AGA",
        metadata={},
    )
    assert aga["topic_label"] == "aga"
    assert aga["topic_confidence"] >= 0.5


def test_metadata_query_match_uses_crawl_query_and_topic_terms():
    _, _, _metadata_query_match, _ = _import_topic_helpers()
    meta = {
        "crawl_query": "GLP-1 ダイエット",
        "topic_label": "medical_diet",
        "matched_terms": ["自由診療", "オンライン診療"],
    }
    assert _metadata_query_match(meta, "GLP-1") is True
    assert _metadata_query_match(meta, "medical") is True
    assert _metadata_query_match(meta, "AGA") is False


def test_classify_zero_save_cause_cases():
    _, _, _classify_zero_save_cause, _, _, _, _, _, _ = _import_crawl_diag_helpers()
    assert _classify_zero_save_cause({"fetched_ads_count": 0, "saved_ads_count": 0}) == "no_fetch_results"
    assert _classify_zero_save_cause({"fetched_ads_count": 5, "saved_ads_count": 0, "skipped_invalid_count": 5}) == "invalid_payload_only"
    assert _classify_zero_save_cause({"fetched_ads_count": 6, "saved_ads_count": 0, "dropped_after_filter_count": 6}) == "filtered_out"
    assert _classify_zero_save_cause({"fetched_ads_count": 3, "saved_ads_count": 2}) == "saved"


def test_ensure_platform_list_normalizes_values():
    _, _, _, _ensure_platform_list, _, _, _, _, _ = _import_crawl_diag_helpers()
    assert _ensure_platform_list([" Facebook ", "instagram", "", None]) == ["facebook", "instagram"]
    assert _ensure_platform_list("facebook") == []


def test_platform_fetch_counts_and_recovery_batches():
    _, _, _, _, _platform_fetch_counts, _build_recovery_platform_batches, _, _, _ = _import_crawl_diag_helpers()
    counts = _platform_fetch_counts({"facebook": [1, 2], "instagram": [], "tiktok": None})
    assert counts == {"facebook": 2, "instagram": 0, "tiktok": 0}

    batches = _build_recovery_platform_batches(
        ["facebook", "instagram", "tiktok"],
        {"facebook": 3, "instagram": 0, "tiktok": 1},
    )
    assert batches[0] == ["instagram"]
    assert ["facebook", "instagram", "tiktok"] in batches


def test_compute_platform_limit_map_increases_for_low_success():
    _, _, _, _, _, _, _compute_platform_limit_map, _, _ = _import_crawl_diag_helpers()

    class _Job:
        def __init__(self, platforms, saved):
            self.platforms = platforms
            self.progress_detail = {"saved_ads_count": saved}
            self.status = type("S", (), {"value": "completed"})()

    class _Query:
        def __init__(self, items):
            self._items = items
        def filter(self, *_args, **_kwargs):
            return self
        def order_by(self, *_args, **_kwargs):
            return self
        def limit(self, *_args, **_kwargs):
            return self
        def all(self):
            return self._items

    class _Session:
        def __init__(self, items):
            self._items = items
        def query(self, *_args, **_kwargs):
            return _Query(self._items)

    jobs = [_Job(["facebook"], 5) for _ in range(3)] + [_Job(["instagram"], 0) for _ in range(3)]
    limits = _compute_platform_limit_map(_Session(jobs), ["facebook", "instagram"], 20, lookback_hours=24)
    assert limits["facebook"] <= 20
    assert limits["instagram"] >= 25


def test_platform_query_learning_prioritizes_successful_queries():
    (
        _build_low_volume_recovery_queries,
        _build_platform_expansion_queries,
        _classify_zero_save_cause,
        _ensure_platform_list,
        _platform_fetch_counts,
        _build_recovery_platform_batches,
        _compute_platform_limit_map,
        _record_platform_query_learning,
        _get_learned_recovery_queries,
    ) = _import_crawl_diag_helpers()
    _ = _classify_zero_save_cause, _ensure_platform_list, _platform_fetch_counts, _build_recovery_platform_batches, _compute_platform_limit_map, _build_platform_expansion_queries

    learning = {"platforms": {}}
    _record_platform_query_learning(
        learning,
        base_query="GLP-1",
        recovery_query="医療ダイエット",
        platform="instagram",
        success=True,
    )
    _record_platform_query_learning(
        learning,
        base_query="GLP-1",
        recovery_query="美容",
        platform="instagram",
        success=False,
    )
    learned = _get_learned_recovery_queries(learning, "GLP-1", "instagram", max_items=3)
    assert learned[0] == "医療ダイエット"

    merged = _build_low_volume_recovery_queries("GLP-1", learned_queries=learned)
    assert merged[0] == "医療ダイエット"


def test_platform_expansion_queries_included_in_fallback_merge():
    (
        _build_low_volume_recovery_queries,
        _build_platform_expansion_queries,
        _classify_zero_save_cause,
        _ensure_platform_list,
        _platform_fetch_counts,
        _build_recovery_platform_batches,
        _compute_platform_limit_map,
        _record_platform_query_learning,
        _get_learned_recovery_queries,
    ) = _import_crawl_diag_helpers()
    _ = _classify_zero_save_cause, _ensure_platform_list, _platform_fetch_counts, _build_recovery_platform_batches, _compute_platform_limit_map, _record_platform_query_learning, _get_learned_recovery_queries
    platform_queries = _build_platform_expansion_queries("GLP-1", "instagram")
    assert "メディカルダイエット" in platform_queries
    merged = _build_low_volume_recovery_queries("GLP-1", learned_queries=["医療ダイエット"], platform_queries=platform_queries)
    assert merged[0] == "医療ダイエット"
    assert any(q in merged for q in platform_queries)


def test_prune_platform_query_learnings_removes_weak_and_stale_entries():
    _count_learning_entries, _prune_platform_query_learnings = _import_learning_prune_helpers()
    learning_data = {
        "platforms": {
            "instagram": {
                "glp-1": {
                    "医療ダイエット": {
                        "attempts": 6,
                        "success": 0,
                    },
                    "痩身クリニック": {
                        "attempts": 4,
                        "success": 2,
                        "last_success_at": "2099-01-01T00:00:00+00:00",
                    },
                }
            }
        }
    }
    assert _count_learning_entries(learning_data) == 2
    pruned, stats = _prune_platform_query_learnings(
        learning_data,
        min_attempts=3,
        min_success_rate=0.15,
        stale_days=14,
    )
    assert stats["removed"] >= 1
    assert _count_learning_entries(pruned) == 1
