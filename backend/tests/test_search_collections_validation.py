from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from app.core import database as db


def _import_sanitizer():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints.rankings import _sanitize_search_collection_filters
    return _sanitize_search_collection_filters


def test_sanitize_search_collection_filters_normalizes_known_values():
    sanitize = _import_sanitizer()
    out = sanitize(
        {
            "period": "14D",
            "transitionType": "questionnaire",
            "adFormat": "IMAGE",
            "isAffiliate": "FALSE",
            "column_sort": {"field": "rank", "direction": "DOWN"},
            "unknown_key": "ignored",
        }
    )
    assert out["period"] == "14d"
    assert out["transitionType"] == "all"
    assert out["adFormat"] == "all"
    assert out["isAffiliate"] == "false"
    assert out["column_sort"]["direction"] == "asc"
    assert "unknown_key" not in out


def test_sanitize_search_collection_filters_allows_supported_values():
    sanitize = _import_sanitizer()
    out = sanitize(
        {
            "transitionType": "article_lp",
            "adFormat": "banner",
            "isAffiliate": "all",
            "period": "2d",
        }
    )
    assert out["transitionType"] == "article_lp"
    assert out["adFormat"] == "banner"
    assert out["isAffiliate"] == "all"
    assert out["period"] == "2d"


def test_sanitize_search_collection_filters_rejects_non_string_scalar_fields():
    sanitize = _import_sanitizer()
    with pytest.raises(HTTPException) as exc:
        sanitize({"period": 14, "query": ["bad"]})
    assert exc.value.status_code == 400
    assert "filters.query" in exc.value.detail


def test_sanitize_search_collection_filters_rejects_invalid_nested_shapes():
    sanitize = _import_sanitizer()
    with pytest.raises(HTTPException) as exc:
        sanitize({"column_sort": {"field": "rank", "direction": 1}})
    assert exc.value.status_code == 400
    assert "filters.column_sort.direction" in exc.value.detail
