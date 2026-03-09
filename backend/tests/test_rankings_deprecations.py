from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_deprecation_registry_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/deprecations")
    assert res.status_code == 200
    data = res.json()

    assert data["count"] >= 1
    assert isinstance(data["items"], list)
    first = data["items"][0]
    assert {"path", "replacement", "sunset_date", "migration_doc", "status", "note"}.issubset(first.keys())


def test_deprecation_registry_filter_matches_ai_chat():
    client = _build_client()
    res = client.get("/api/v1/rankings/deprecations", params={"path": "/api/v1/ai-chat/message"})
    assert res.status_code == 200
    data = res.json()

    assert data["count"] == 1
    item = data["items"][0]
    assert item["replacement"] == "/api/v2/ai-chat/message"
    assert item["status"] == "active_deprecation"


def test_guideline_mentions_deprecation_registry_fields():
    repo_root = Path(__file__).resolve().parents[2]
    guideline = (repo_root / "docs" / "API_COMPATIBILITY_GUIDELINES.md").read_text(encoding="utf-8")

    assert "Deprecation Policy" in guideline
    assert "publish the affected path, replacement, and migration note" in guideline
    assert "Minimum deprecation registry fields" in guideline
