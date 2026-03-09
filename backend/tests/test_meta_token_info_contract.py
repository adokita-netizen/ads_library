import pytest

from app.api.endpoints import settings as settings_endpoint


class _DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


class _DummyAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return self._response


class _DummyExecuteResult:
    def __init__(self, row=None):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _DummyDB:
    def __init__(self):
        self.saved_key = None

    async def execute(self, *args, **kwargs):
        return _DummyExecuteResult(self.saved_key)

    def add(self, value):
        self.saved_key = value


@pytest.mark.asyncio
async def test_meta_token_info_returns_health_payload_with_debug_token(monkeypatch):
    async def _fake_runtime(db):
        return {
            "token": "meta-token",
            "token_source": "db",
            "runtime_source": "db",
            "fallback_used": False,
            "fallback_reason": None,
            "source_priority": ["db", "env", "missing"],
        }

    async def _fake_get_meta_key(db, key_name):
        return {
            "app_id": "app-id",
            "app_secret": "app-secret",
            "access_token": None,
        }.get(key_name)

    monkeypatch.setattr(settings_endpoint.MetaTokenManager, "get_token_runtime_source", _fake_runtime)
    monkeypatch.setattr(settings_endpoint, "_get_meta_key", _fake_get_meta_key)
    monkeypatch.setattr(
        settings_endpoint.httpx,
        "AsyncClient",
        lambda timeout=30: _DummyAsyncClient(
            _DummyResponse(
                200,
                {
                    "data": {
                        "is_valid": True,
                        "app_id": "app-id",
                        "type": "USER",
                        "expires_at": 4102444800,
                        "scopes": ["ads_read"],
                    }
                },
            )
        ),
    )

    payload = await settings_endpoint.get_meta_token_info(db=None)

    assert payload["has_token"] is True
    assert payload["token_source"] == "db"
    assert payload["runtime_source"] == "db"
    assert payload["fallback_used"] is False
    assert payload["is_valid"] is True
    assert payload["type"] == "USER"
    assert payload["days_remaining"] is not None
    assert payload["last_validation_error"] is None


@pytest.mark.asyncio
async def test_meta_token_info_returns_missing_contract(monkeypatch):
    async def _fake_runtime(db):
        return {
            "token": None,
            "token_source": "missing",
            "runtime_source": "missing",
            "fallback_used": False,
            "fallback_reason": None,
            "source_priority": ["db", "env", "missing"],
        }

    async def _fake_get_meta_key(db, key_name):
        return None

    monkeypatch.setattr(settings_endpoint.MetaTokenManager, "get_token_runtime_source", _fake_runtime)
    monkeypatch.setattr(settings_endpoint, "_get_meta_key", _fake_get_meta_key)

    payload = await settings_endpoint.get_meta_token_info(db=None)

    assert payload["has_token"] is False
    assert payload["token_source"] == "missing"
    assert payload["runtime_source"] == "missing"
    assert payload["is_valid"] is False
    assert payload["last_validation_error"]


@pytest.mark.asyncio
async def test_meta_token_info_prefers_env_fallback_contract(monkeypatch):
    async def _fake_runtime(db):
        return {
            "token": "env-meta-token",
            "token_source": "env",
            "runtime_source": "env",
            "fallback_used": True,
            "fallback_reason": "db_missing",
            "source_priority": ["db", "env", "missing"],
        }

    async def _fake_get_meta_key(db, key_name):
        return {
            "app_id": None,
            "app_secret": None,
            "access_token": None,
        }.get(key_name)

    monkeypatch.setattr(settings_endpoint.MetaTokenManager, "get_token_runtime_source", _fake_runtime)
    monkeypatch.setattr(settings_endpoint, "_get_meta_key", _fake_get_meta_key)
    monkeypatch.setattr(
        settings_endpoint.httpx,
        "AsyncClient",
        lambda timeout=30: _DummyAsyncClient(_DummyResponse(200, {"id": "user-1", "name": "Env User"})),
    )

    payload = await settings_endpoint.get_meta_token_info(db=None)

    assert payload["has_token"] is True
    assert payload["token_source"] == "env"
    assert payload["runtime_source"] == "env"
    assert payload["fallback_used"] is True
    assert payload["fallback_reason"] == "db_missing"
    assert payload["is_valid"] is True
    assert payload["user_id"] == "user-1"
    assert payload["is_expiring"] is False
    assert payload["last_validation_error"] is None


@pytest.mark.asyncio
async def test_meta_token_info_detects_invalid_db_token_and_env_fallback(monkeypatch):
    async def _fake_runtime(db):
        return {
            "token": "db-token",
            "token_source": "db",
            "runtime_source": "db",
            "fallback_used": False,
            "fallback_reason": None,
            "source_priority": ["db", "env", "missing"],
        }

    async def _fake_get_meta_key(db, key_name):
        return {
            "app_id": "app-id",
            "app_secret": "app-secret",
            "access_token": None,
        }.get(key_name)

    monkeypatch.setattr(settings_endpoint.MetaTokenManager, "get_token_runtime_source", _fake_runtime)
    monkeypatch.setattr(settings_endpoint.MetaTokenManager, "_get_env_access_token", lambda: "env-fallback-token")
    monkeypatch.setattr(settings_endpoint, "_get_meta_key", _fake_get_meta_key)
    monkeypatch.setattr(
        settings_endpoint.httpx,
        "AsyncClient",
        lambda timeout=30: _DummyAsyncClient(
            _DummyResponse(400, {"error": {"message": "Error validating access token"}})
        ),
    )

    payload = await settings_endpoint.get_meta_token_info(db=None)

    assert payload["token_source"] == "db"
    assert payload["runtime_source"] == "env"
    assert payload["fallback_used"] is True
    assert payload["fallback_reason"] == "db_invalid_fallback_env"
    assert payload["is_valid"] is False


@pytest.mark.asyncio
async def test_meta_exchange_token_returns_fixed_contract(monkeypatch):
    db = _DummyDB()

    async def _fake_get_meta_key(db, key_name):
        return {
            "app_id": "app-id",
            "app_secret": "app-secret",
            "access_token": "short-lived-token",
        }.get(key_name)

    monkeypatch.setattr(settings_endpoint, "_get_meta_key", _fake_get_meta_key)
    monkeypatch.setattr(
        settings_endpoint.httpx,
        "AsyncClient",
        lambda timeout=30: _DummyAsyncClient(
            _DummyResponse(200, {"access_token": "long-lived-token", "token_type": "bearer"})
        ),
    )

    payload = await settings_endpoint.exchange_meta_token(db=db)

    assert payload["status"] == "ok"
    assert payload["token_type"] == "bearer"
    assert payload["token_source"] == "db"
    assert payload["saved_to"] == "db"
    assert payload["source_priority"] == ["db", "env", "missing"]
    assert payload["exchanged"] is True
