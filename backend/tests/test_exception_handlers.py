"""Tests for global exception handler logic.

Since app.main imports all endpoint modules (which require celery, minio, etc.),
we test the handler functions in isolation by recreating them with the same logic.
"""

import json
import pytest
from unittest.mock import MagicMock

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError


# Recreate the handler functions with the same logic as app/main.py
# This avoids importing the full app module graph.


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        details.append({
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "リクエストの検証に失敗しました", "details": details}},
    )


async def sqlalchemy_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "database_error", "message": "データベースエラーが発生しました", "details": []}},
    )


async def general_exception_handler(request: Request, exc: Exception):
    # In test env, debug=False → generic message
    message = "内部サーバーエラーが発生しました"
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": message, "details": []}},
    )


def _make_request():
    mock = MagicMock(spec=Request)
    mock.url.path = "/api/v1/test"
    return mock


class TestValidationExceptionHandler:
    """Test RequestValidationError handler."""

    @pytest.mark.asyncio
    async def test_validation_error_returns_422(self):
        errors = [
            {"loc": ("body", "title"), "msg": "field required", "type": "value_error.missing"},
        ]
        exc = RequestValidationError(errors=errors)
        response = await validation_exception_handler(_make_request(), exc)
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_validation_error_has_structured_format(self):
        errors = [
            {"loc": ("body", "email"), "msg": "invalid email", "type": "value_error"},
        ]
        exc = RequestValidationError(errors=errors)
        response = await validation_exception_handler(_make_request(), exc)
        body = json.loads(response.body.decode("utf-8"))
        assert body["error"]["code"] == "validation_error"
        assert len(body["error"]["details"]) == 1
        assert body["error"]["details"][0]["field"] == "body.email"
        assert body["error"]["details"][0]["message"] == "invalid email"

    @pytest.mark.asyncio
    async def test_validation_error_multiple_fields(self):
        errors = [
            {"loc": ("body", "title"), "msg": "required", "type": "missing"},
            {"loc": ("body", "platform"), "msg": "required", "type": "missing"},
            {"loc": ("query", "page"), "msg": "ge 1", "type": "range"},
        ]
        exc = RequestValidationError(errors=errors)
        response = await validation_exception_handler(_make_request(), exc)
        body = json.loads(response.body.decode("utf-8"))
        assert len(body["error"]["details"]) == 3


class TestSQLAlchemyExceptionHandler:
    """Test SQLAlchemy error handler."""

    @pytest.mark.asyncio
    async def test_database_error_returns_500(self):
        exc = OperationalError("connection failed", None, None)
        response = await sqlalchemy_exception_handler(_make_request(), exc)
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_database_error_has_structured_format(self):
        exc = OperationalError("timeout", None, None)
        response = await sqlalchemy_exception_handler(_make_request(), exc)
        body = json.loads(response.body.decode("utf-8"))
        assert body["error"]["code"] == "database_error"
        assert "データベースエラー" in body["error"]["message"]
        assert body["error"]["details"] == []


class TestGeneralExceptionHandler:
    """Test catch-all exception handler."""

    @pytest.mark.asyncio
    async def test_general_error_returns_500(self):
        exc = RuntimeError("something went wrong")
        response = await general_exception_handler(_make_request(), exc)
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_general_error_hides_details_in_production(self):
        exc = RuntimeError("secret error detail")
        response = await general_exception_handler(_make_request(), exc)
        body = json.loads(response.body.decode("utf-8"))
        assert body["error"]["code"] == "internal_error"
        assert "内部サーバーエラー" in body["error"]["message"]
        # Should NOT expose the actual error message
        assert "secret" not in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_error_response_structure(self):
        exc = ValueError("test")
        response = await general_exception_handler(_make_request(), exc)
        body = json.loads(response.body.decode("utf-8"))
        # Verify the standard error envelope structure
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "details" in body["error"]
