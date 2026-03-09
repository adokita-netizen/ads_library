from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_search_invalid_scope_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/search", params={"q": "test", "search_scope": "invalid"})
    assert res.status_code == 400
    assert "search_scope" in str(res.json())


def test_search_blank_query_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/search", params={"q": "   "})
    assert res.status_code == 400
    assert "q" in str(res.json())


def test_search_invalid_date_from_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/search", params={"q": "test", "date_from": "not-a-date"})
    assert res.status_code == 400
    assert "date_from" in str(res.json())


def test_search_facets_invalid_period_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/search/facets", params={"period": "13d"})
    assert res.status_code == 400
    assert "period" in str(res.json())


def test_search_advanced_invalid_sort_dir_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/search/advanced", params={"sort_dir": "down"})
    assert res.status_code == 400
    assert "sort_dir" in str(res.json())


def test_autocomplete_blank_query_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/autocomplete", params={"q": "   "})
    assert res.status_code == 400
    assert "q" in str(res.json())


def test_autocomplete_invalid_field_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/autocomplete", params={"q": "test", "field": "unknown"})
    assert res.status_code == 400
    assert "field" in str(res.json())


def test_smart_autocomplete_blank_query_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/smart-autocomplete", params={"query": "   "})
    assert res.status_code == 400
    assert "query" in str(res.json())


def test_search_suggest_blank_query_returns_400():
    client = _build_client()
    res = client.get("/api/v1/rankings/search/suggest", params={"q": "   "})
    assert res.status_code == 400
    assert "q" in str(res.json())


def test_advanced_search_invalid_date_range_shape_returns_400():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/advanced-search",
        json={
            "query": "",
            "filters": {"date_range": ["2026-01-01T00:00:00"]},
            "sort": {"field": "score", "direction": "desc"},
            "page": 1,
            "page_size": 20,
        },
    )
    assert res.status_code == 400
    assert "date_range" in str(res.json())


def test_advanced_search_invalid_score_range_type_returns_400():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/advanced-search",
        json={
            "query": "",
            "filters": {"score_range": ["low", 90]},
            "sort": {"field": "score", "direction": "desc"},
            "page": 1,
            "page_size": 20,
        },
    )
    assert res.status_code == 400
    assert "score_range" in str(res.json())
