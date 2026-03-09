from app.api.endpoints.rankings import (
    _SHORT_TTL_CACHE,
    _short_cache_get,
    _short_cache_set,
)


def test_short_cache_set_get_and_expire():
    key = "rankings:test"
    payload = {"ok": True}
    _short_cache_set(key, payload)
    assert _short_cache_get(key) == payload

    # Force-expire
    _SHORT_TTL_CACHE[key] = (0.0, payload)
    assert _short_cache_get(key) is None

