import json

from app.core.response_case import with_dual_case_keys


def test_with_dual_case_keys_adds_camel_alias_for_snake_keys():
    payload = {"request_id": "abc", "hit_score": 80}
    out = with_dual_case_keys(payload)

    assert out["request_id"] == "abc"
    assert out["requestId"] == "abc"
    assert out["hit_score"] == 80
    assert out["hitScore"] == 80


def test_with_dual_case_keys_adds_snake_alias_for_camel_keys():
    payload = {"requestId": "abc", "hitScore": 80}
    out = with_dual_case_keys(payload)

    assert out["requestId"] == "abc"
    assert out["request_id"] == "abc"
    assert out["hitScore"] == 80
    assert out["hit_score"] == 80


def test_with_dual_case_keys_is_recursive_for_nested_structures():
    payload = {
        "job_status": {
            "savedAdsCount": 3,
            "failed_items": [{"failure_reason": "timeout"}],
        }
    }
    out = with_dual_case_keys(payload)

    assert out["jobStatus"]["savedAdsCount"] == 3
    assert out["jobStatus"]["saved_ads_count"] == 3
    assert out["jobStatus"]["failedItems"][0]["failureReason"] == "timeout"


def test_with_dual_case_keys_does_not_override_existing_keys():
    payload = {"hit_score": 10, "hitScore": 20}
    out = with_dual_case_keys(payload)

    assert out["hit_score"] == 10
    assert out["hitScore"] == 20
