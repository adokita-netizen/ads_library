from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_timeout_policy_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/timeout-policy")
    assert res.status_code == 200
    data = res.json()

    assert "policies" in data
    assert "max_page_size" in data
    assert "max_export_rows" in data
    assert "list_get" in data["policies"]
    assert "timeout_seconds" in data["policies"]["list_get"]
    assert "retry" in data["policies"]["list_get"]


def test_score_parameter_ab_review_contract_shape():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/score-parameter-ab-review",
        json={"ad_ids": [999999], "candidate": {"weights": {"trend": 1.1}}},
    )
    assert res.status_code == 200
    data = res.json()

    assert "baseline" in data
    assert "candidate" in data
    assert "summary" in data
    assert "distribution" in data
    assert "changed_ads" in data
    assert "items" in data
    assert "baseline_avg_score" in data["summary"]
    assert "candidate_hit_count" in data["summary"]
    assert "baseline" in data["distribution"]
    assert "candidate" in data["distribution"]
    assert "promoted_ids" in data["changed_ads"]
    assert "demoted_ids" in data["changed_ads"]


def test_rate_limit_policy_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/rate-limit-policy")
    assert res.status_code == 200
    data = res.json()

    assert "count" in data
    assert "lanes" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "lane" in item
        assert "path" in item
        assert "policy_setting" in item
        assert "configured_policy" in item
        assert "default_requests" in item
        assert "default_window_seconds" in item
        assert "burst_behavior" in item
        assert "goal" in item


def test_trace_propagation_policy_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/trace-propagation-policy")
    assert res.status_code == 200
    data = res.json()

    assert "count" in data
    assert "lanes" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "lane" in item
        assert "path" in item
        assert "goal" in item
        assert "transport" in item
        assert "outputs" in item


def test_fail_soft_policy_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/fail-soft-policy")
    assert res.status_code == 200
    data = res.json()

    assert "count" in data
    assert "reason_codes" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "path" in item
        assert "mode" in item
        assert "fallback_order" in item
        assert "degraded_reason_codes" in item
        assert "stale_cache_allowed" in item
        assert "empty_payload_factory" in item


def test_error_code_dictionary_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/error-codes")
    assert res.status_code == 200
    data = res.json()

    assert "count" in data
    assert "categories" in data
    assert "scopes" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "code" in item
        assert "category" in item
        assert "scope" in item
        assert "http_status" in item
        assert "message" in item
        assert "operator_action" in item
        assert "severity" in item
        assert "owner" in item
        assert "runbook" in item
        assert "first_response" in item


def test_api_compatibility_review_process_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/api-compatibility-review-process")
    assert res.status_code == 200
    data = res.json()

    assert "review_ready" in data
    assert "manifest_version" in data
    assert "guideline_path" in data
    assert "required_sections" in data
    assert "required_review_questions" in data
    assert "critical_contract_tests" in data
    assert "missing_sections" in data
    assert "missing_contract_tests" in data
    assert "review_process" in data


def test_search_contract_language_taxonomy_fields():
    client = _build_client()
    res = client.get("/api/v1/rankings/search", params={"q": "test"})
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    if data["results"]:
        ad_items = [item for item in data["results"] if item.get("type") == "ad"]
        if ad_items:
            item = ad_items[0]
            assert "language" in item
            assert "language_status" in item
            assert "language_confidence" in item
            assert "language_source" in item
            assert "product_category" in item
            assert "product_subcategory" in item
            assert "exclude_from_analysis" in item
            assert "exclude_reason" in item
            assert "metric_source" in item
            assert "creative_source" in item
            assert "lp_source" in item
            assert "freshness_status" in item
            assert "meta_quality_state" in item


def test_meta_freshness_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/meta-freshness-contract")
    assert res.status_code == 200
    data = res.json()

    assert "metric_source_vocab" in data
    assert "creative_source_vocab" in data
    assert "lp_source_vocab" in data
    assert "quality_state_vocab" in data
    assert "freshness_status_vocab" in data
    assert "required_fields" in data


def test_bedrock_classification_gateway_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/bedrock-classification-gateway-contract")
    assert res.status_code == 200
    data = res.json()

    assert "required_fields" in data
    assert "status_vocab" in data
    assert "source_priority" in data
    assert "timeout_behavior" in data
    assert "partial_behavior" in data


def test_bedrock_decision_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/bedrock-decision-contract")
    assert res.status_code == 200
    data = res.json()

    assert "required_fields" in data
    assert "source_priority" in data
    assert "confidence_bands" in data
    assert "fallback_behavior" in data
    assert "prompt_registry" in data


def test_bedrock_prompt_registry_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/bedrock-prompt-registry")
    assert res.status_code == 200
    data = res.json()

    assert "default_prompt_version" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "prompt_version" in item
        assert "model_name" in item
        assert "task" in item
        assert "required_output_fields" in item


def test_bedrock_review_queue_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/bedrock-review-queue")
    assert res.status_code == 200
    data = res.json()

    assert "total" in data
    assert "limit" in data
    assert "filters" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "priority_score" in item
        assert "review_required" in item
        assert "review_reason" in item
        assert "confidence_band" in item
        assert "provenance" in item
        assert "provenance_summary" in item


def test_high_priority_actual_metrics_contract_shape():
    client = _build_client()
    res = client.get("/api/v1/rankings/high-priority-actual-metrics")
    assert res.status_code == 200
    data = res.json()

    assert "total" in data
    assert "limit" in data
    assert "filters" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "priority_score" in item
        assert "actual_metrics_present" in item
        assert "actual_metrics_focus" in item
        assert "provenance" in item


def test_rankings_strict_input_schema_422_shape():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/top-hit-quality-review",
        json={"limit": "30"},
    )
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)


def test_dashboard_summary_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/dashboard-summary")
    assert res.status_code == 200
    data = res.json()

    base_keys = {
        "total_ads",
        "active_ads",
        "hit_count",
        "mega_hit_count",
        "avg_score",
        "avg_days_running",
        "top_genre",
        "top_creative_type",
    }
    assert base_keys.issubset(set(data.keys()))
    if data["total_ads"] > 0:
        assert "avg_hit_score" in data
        assert "fresh_ads_count" in data
        assert "media_cache_rate" in data
        assert "top_genres" in data and isinstance(data["top_genres"], list)
        assert "top_hooks" in data and isinstance(data["top_hooks"], list)
        assert "top_ctas" in data and isinstance(data["top_ctas"], list)


def test_score_distribution_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/score-distribution")
    assert res.status_code == 200
    data = res.json()

    base_keys = {
        "total_ads",
        "distribution",
        "stats",
        "by_genre",
    }
    assert base_keys.issubset(set(data.keys()))
    assert isinstance(data["distribution"], list)
    assert isinstance(data["stats"], dict)
    assert isinstance(data["by_genre"], dict)
    if data["total_ads"] > 0:
        extended_keys = {
            "dynamic_thresholds",
            "mean",
            "median",
            "p25",
            "p50",
            "p75",
            "p90",
            "hit_count",
            "mega_hit_count",
            "still_running_count",
        }
        assert extended_keys.issubset(set(data.keys()))
        assert isinstance(data["dynamic_thresholds"], dict)


def test_search_simple_contract_uses_scalar_hit_score_and_meta_statuses():
    client = _build_client()
    res = client.get("/api/v1/rankings/search-simple?q=&page=1&page_size=3")
    assert res.status_code == 200
    data = res.json()

    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        item = data["items"][0]
        assert isinstance(item["hit_score"], (int, float))
        assert item["metric_status"] in {"real", "estimated", "missing", "stale"}
        assert item["creative_status"] in {"real", "estimated", "missing", "stale"}
        assert item["lp_status"] in {"real", "estimated", "missing", "stale"}
        assert item["freshness_status"] in {"fresh", "stale", "missing"}
        assert "meta_quality_state" in item
