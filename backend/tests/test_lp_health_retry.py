from types import SimpleNamespace

import requests

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from scripts import check_lp_health, normalize_lp_metadata, validate_metadata_schema


def _response(status_code: int, url: str = "https://example.com/final"):
    return SimpleNamespace(status_code=status_code, url=url, history=[], close=lambda: None)


def test_check_url_health_falls_back_to_get_when_head_blocked(monkeypatch):
    monkeypatch.setattr(check_lp_health.requests, "head", lambda *args, **kwargs: _response(405))
    monkeypatch.setattr(check_lp_health.requests, "get", lambda *args, **kwargs: _response(200))

    result = check_lp_health.check_url_health("https://example.com/lp")

    assert result["lp_status"] == "200"
    assert result["check_method"] == "GET"
    assert result["attempts"] == 1


def test_check_url_health_retries_transient_timeout(monkeypatch):
    calls = {"head": 0}

    def _head(*args, **kwargs):
        calls["head"] += 1
        if calls["head"] == 1:
            raise requests.exceptions.Timeout()
        return _response(200)

    monkeypatch.setattr(check_lp_health.requests, "head", _head)
    monkeypatch.setattr(check_lp_health.requests, "get", lambda *args, **kwargs: _response(200))
    monkeypatch.setattr(check_lp_health.time, "sleep", lambda *_args, **_kwargs: None)

    result = check_lp_health.check_url_health("https://example.com/lp")

    assert result["lp_status"] == "200"
    assert result["check_method"] == "HEAD"
    assert result["attempts"] == 2


def test_normalize_lp_metadata_tiny_body_thresholds_are_tuned():
    success_meta = {"lp_status": "200"}

    assert normalize_lp_metadata._should_flag_tiny_body(
        success_meta,
        {"lp_text_length": 90, "title": "LP title", "h1_count": 0},
    ) is False
    assert normalize_lp_metadata._should_flag_tiny_body(
        success_meta,
        {"lp_text_length": 60, "title": "", "h1_count": 0},
    ) is True
    assert normalize_lp_metadata._should_flag_tiny_body(
        {"lp_status": "404"},
        {"lp_text_length": 40, "title": "", "h1_count": 0},
    ) is False


def test_validate_ad_skips_tiny_body_gate_for_non_success_lp_status():
    ad = Ad(
        external_id="lp-gate-1",
        title="LP gate check",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "fine_genre_en": "other",
            "creative_analysis": {},
            "ranking_metrics": {},
            "estimated_metrics": {},
            "latest_hit_score": 10.0,
            "is_still_running": False,
            "days_running": 1,
            "creative_quality": {},
            "longevity_class": "flash",
            "source": "test",
            "lp_status": "404",
            "lp_text_length": 40,
            "lp_quality_issue": [],
        },
    )

    result = validate_metadata_schema.validate_ad(ad)

    assert "lp_tiny_body" not in result["gate_violations"]
