from fastapi import Request

from app.core.gateway_auth import (
    extract_request_api_key,
    is_gateway_authorized,
    is_protected_path,
    parse_csv_list,
)


def _make_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v2/version",
        "headers": [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()],
    }
    return Request(scope)


def test_parse_csv_list():
    assert parse_csv_list("a,b, c") == ["a", "b", "c"]
    assert parse_csv_list("") == []


def test_is_protected_path():
    assert is_protected_path("/api/v2/version", ["/api/v2", "/api/v1/graphql"])
    assert is_protected_path("/api/v1/graphql", ["/api/v2", "/api/v1/graphql"])
    assert not is_protected_path("/api/v1/health", ["/api/v2", "/api/v1/graphql"])


def test_extract_request_api_key_x_api_key_header():
    req = _make_request({"x-api-key": "demo-key"})
    assert extract_request_api_key(req) == "demo-key"


def test_extract_request_api_key_bearer_fallback():
    req = _make_request({"authorization": "Bearer token-123"})
    assert extract_request_api_key(req) == "token-123"


def test_is_gateway_authorized():
    req_ok = _make_request({"x-api-key": "k1"})
    req_ng = _make_request({"x-api-key": "k2"})
    assert is_gateway_authorized(req_ok, ["k1", "k3"])
    assert not is_gateway_authorized(req_ng, ["k1", "k3"])

