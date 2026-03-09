from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_api_compatibility_review_process_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/api-compatibility-review-process")
    assert res.status_code == 200
    data = res.json()

    assert data["review_ready"] is True
    assert data["missing_sections"] == []
    assert data["missing_contract_tests"] == []
    assert "Review Checklist" in data["required_sections"]
    assert "Which endpoints changed?" in data["required_review_questions"]
    assert data["review_process"] == [
        "classify_change",
        "answer_review_questions",
        "update_contract_tests",
        "update_docs_and_operator_notes",
        "confirm_rollout_policy",
    ]
