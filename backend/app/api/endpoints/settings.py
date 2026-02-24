"""Settings API endpoints — API key management & database connection."""

from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_async_session, is_in_memory_mode, get_connection_error, reconnect
from app.models.api_key import PlatformAPIKey
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])
logger = structlog.get_logger()

# ── Platform definitions ────────────────────────────────────────

PLATFORM_KEY_DEFINITIONS: list[dict] = [
    {
        "platform": "youtube",
        "label": "YouTube",
        "keys": [
            {"key_name": "api_key", "label": "YouTube Data API Key", "placeholder": "AIzaSy..."},
        ],
        "docs_url": "https://console.cloud.google.com/apis/credentials",
        "setup_guide": "Google Cloud Console → APIとサービス → 認証情報 → APIキーを作成 → YouTube Data API v3を有効化",
    },
    {
        "platform": "meta",
        "label": "Meta (Facebook / Instagram)",
        "keys": [
            {"key_name": "access_token", "label": "Meta Graph API アクセストークン", "placeholder": "EAAGm0PX..."},
            {"key_name": "app_id", "label": "Meta App ID", "placeholder": "123456789012345"},
            {"key_name": "app_secret", "label": "Meta App Secret", "placeholder": "abcdef1234567890..."},
        ],
        "docs_url": "https://developers.facebook.com/tools/explorer/",
        "setup_guide": "Meta for Developers → Graph APIエクスプローラー → アクセストークンを生成 → ads_read権限を付与",
    },
    {
        "platform": "tiktok",
        "label": "TikTok",
        "keys": [
            {"key_name": "access_token", "label": "TikTok Marketing API トークン", "placeholder": ""},
        ],
        "docs_url": "https://business-api.tiktok.com/portal/docs",
        "setup_guide": "TikTok for Business → Marketing API → アプリ作成 → アクセストークン取得",
    },
    {
        "platform": "x_twitter",
        "label": "X (Twitter)",
        "keys": [
            {"key_name": "bearer_token", "label": "Bearer Token", "placeholder": "AAAAAAAAAA..."},
        ],
        "docs_url": "https://developer.x.com/en/portal/dashboard",
        "setup_guide": "X Developer Portal → Projects & Apps → キーとトークン → Bearer Tokenを生成",
    },
    {
        "platform": "line",
        "label": "LINE",
        "keys": [
            {"key_name": "access_token", "label": "LINE Ads API アクセストークン", "placeholder": ""},
        ],
        "docs_url": "https://developers.line.biz/",
        "setup_guide": "LINE Developers → LINE公式アカウント → Messaging APIチャネル → チャネルアクセストークン発行",
    },
    {
        "platform": "yahoo",
        "label": "Yahoo!広告",
        "keys": [
            {"key_name": "api_key", "label": "Yahoo! Ads API アプリケーションID", "placeholder": ""},
            {"key_name": "api_secret", "label": "Yahoo! Ads API シークレット", "placeholder": ""},
        ],
        "docs_url": "https://ads-developers.yahoo.co.jp/",
        "setup_guide": "Yahoo!デベロッパーネットワーク → アプリケーション登録 → Client IDとSecretを取得",
    },
    {
        "platform": "pinterest",
        "label": "Pinterest",
        "keys": [
            {"key_name": "access_token", "label": "Pinterest API アクセストークン", "placeholder": "pina_..."},
        ],
        "docs_url": "https://developers.pinterest.com/",
        "setup_guide": "Pinterest for Business → アプリ作成 → OAuth認証フロー → アクセストークン取得",
    },
    {
        "platform": "smartnews",
        "label": "SmartNews",
        "keys": [
            {"key_name": "api_key", "label": "SmartNews Ads API キー", "placeholder": ""},
        ],
        "docs_url": "https://developers.smartnews.com/",
        "setup_guide": "SmartNews Ads → パートナーAPI申請 → APIキー発行",
    },
    {
        "platform": "google_ads",
        "label": "Google Ads",
        "keys": [
            {"key_name": "developer_token", "label": "開発者トークン", "placeholder": ""},
            {"key_name": "client_id", "label": "OAuth Client ID", "placeholder": "xxx.apps.googleusercontent.com"},
            {"key_name": "client_secret", "label": "OAuth Client Secret", "placeholder": ""},
            {"key_name": "refresh_token", "label": "OAuth Refresh Token", "placeholder": "1//0..."},
        ],
        "docs_url": "https://developers.google.com/google-ads/api/docs/get-started/introduction",
        "setup_guide": "Google Ads API Center → 開発者トークン申請 → Google Cloud Console → OAuth 2.0クライアント作成 → Refresh Token取得",
    },
    {
        "platform": "gunosy",
        "label": "Gunosy",
        "keys": [
            {"key_name": "api_key", "label": "Gunosy Ads API キー", "placeholder": ""},
        ],
        "docs_url": "https://gunosy.co.jp/ad/",
        "setup_guide": "Gunosy Ads → 広告APIアクセス申請 → APIキー発行",
    },
    {
        "platform": "openai",
        "label": "OpenAI (AI分析用)",
        "keys": [
            {"key_name": "api_key", "label": "OpenAI API Key", "placeholder": "sk-..."},
        ],
        "docs_url": "https://platform.openai.com/api-keys",
        "setup_guide": "OpenAI Platform → API Keys → Create new secret key",
    },
    {
        "platform": "anthropic",
        "label": "Anthropic (AI分析用)",
        "keys": [
            {"key_name": "api_key", "label": "Anthropic API Key", "placeholder": "sk-ant-..."},
        ],
        "docs_url": "https://console.anthropic.com/settings/keys",
        "setup_guide": "Anthropic Console → API Keys → Create Key",
    },
]


# ── Schemas ─────────────────────────────────────────────────────

class APIKeySetRequest(BaseModel):
    platform: str
    key_name: str
    key_value: str


class APIKeyDeleteRequest(BaseModel):
    platform: str
    key_name: str


class APIKeyStatus(BaseModel):
    platform: str
    key_name: str
    is_set: bool
    masked_value: Optional[str] = None
    updated_at: Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────────

@router.get("/api-keys/platforms")
async def get_platform_definitions():
    """Return platform definitions with key names, labels, setup guides."""
    return {"platforms": PLATFORM_KEY_DEFINITIONS}


@router.get("/api-keys")
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all configured API keys (masked values)."""
    result = await db.execute(
        select(PlatformAPIKey).where(PlatformAPIKey.is_active == True)
    )
    keys = result.scalars().all()

    statuses = []
    for key in keys:
        masked = _mask_value(key.key_value)
        statuses.append(APIKeyStatus(
            platform=key.platform,
            key_name=key.key_name,
            is_set=True,
            masked_value=masked,
            updated_at=key.updated_at.isoformat() if key.updated_at else None,
        ))

    return {"keys": [s.model_dump() for s in statuses]}


@router.post("/api-keys")
async def set_api_key(
    request: APIKeySetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Set or update an API key for a platform."""
    if not request.key_value.strip():
        raise HTTPException(status_code=400, detail="key_value must not be empty")

    # Check existing
    result = await db.execute(
        select(PlatformAPIKey).where(
            PlatformAPIKey.platform == request.platform,
            PlatformAPIKey.key_name == request.key_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.key_value = request.key_value.strip()
        existing.is_active = True
    else:
        new_key = PlatformAPIKey(
            platform=request.platform,
            key_name=request.key_name,
            key_value=request.key_value.strip(),
            is_active=True,
        )
        db.add(new_key)

    logger.info("api_key_set", platform=request.platform, key_name=request.key_name)
    return {"status": "ok", "message": f"{request.platform}/{request.key_name} を保存しました"}


@router.delete("/api-keys")
async def delete_api_key(
    request: APIKeyDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete an API key."""
    result = await db.execute(
        select(PlatformAPIKey).where(
            PlatformAPIKey.platform == request.platform,
            PlatformAPIKey.key_name == request.key_name,
        )
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(existing)
    logger.info("api_key_deleted", platform=request.platform, key_name=request.key_name)
    return {"status": "ok", "message": f"{request.platform}/{request.key_name} を削除しました"}


@router.post("/api-keys/test")
async def test_api_key(
    request: APIKeySetRequest,
    current_user: User = Depends(get_current_user),
):
    """Test if an API key is valid (basic validation only)."""
    value = request.key_value.strip()
    if not value:
        return {"valid": False, "message": "キーが空です"}

    # Basic format checks per platform
    checks = {
        "youtube": lambda v: v.startswith("AIza") and len(v) > 20,
        "meta": lambda v: len(v) > 20,
        "tiktok": lambda v: len(v) > 10,
        "x_twitter": lambda v: len(v) > 20,
        "openai": lambda v: v.startswith("sk-") and len(v) > 20,
        "anthropic": lambda v: v.startswith("sk-ant-") and len(v) > 20,
    }

    checker = checks.get(request.platform)
    if checker:
        if checker(value):
            return {"valid": True, "message": "キーのフォーマットは正しいです"}
        else:
            return {"valid": False, "message": "キーのフォーマットが正しくないようです"}

    # No specific check — assume valid if non-empty
    return {"valid": True, "message": "キーが設定されています"}


# ── Meta token management ────────────────────────────────────────

META_GRAPH_API_BASE = "https://graph.facebook.com/v25.0"


async def _get_meta_key(db: AsyncSession, key_name: str) -> Optional[str]:
    """Fetch a single Meta platform key value from DB."""
    result = await db.execute(
        select(PlatformAPIKey).where(
            PlatformAPIKey.platform == "meta",
            PlatformAPIKey.key_name == key_name,
            PlatformAPIKey.is_active == True,
        )
    )
    row = result.scalar_one_or_none()
    return row.key_value if row else None


@router.post("/meta/exchange-token")
async def exchange_meta_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Exchange a short-lived Meta token for a long-lived (60-day) token.

    Reads app_id, app_secret, access_token from DB, calls the Meta OAuth
    endpoint, and saves the new long-lived token back to DB.
    """
    app_id = await _get_meta_key(db, "app_id")
    app_secret = await _get_meta_key(db, "app_secret")
    access_token = await _get_meta_key(db, "access_token")

    if not app_id or not app_secret:
        raise HTTPException(
            status_code=400,
            detail="Meta App ID と App Secret を先に設定してください",
        )
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Meta アクセストークンを先に設定してください",
        )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH_API_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": access_token,
            },
        )

    if resp.status_code != 200:
        error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        error_msg = error_data.get("error", {}).get("message", resp.text)
        logger.warning("meta_token_exchange_failed", status=resp.status_code, error=error_msg)
        raise HTTPException(
            status_code=400,
            detail=f"トークン交換に失敗しました: {error_msg}",
        )

    data = resp.json()
    new_token = data.get("access_token")
    if not new_token:
        raise HTTPException(status_code=500, detail="レスポンスにアクセストークンが含まれていません")

    # Save the new long-lived token to DB
    result = await db.execute(
        select(PlatformAPIKey).where(
            PlatformAPIKey.platform == "meta",
            PlatformAPIKey.key_name == "access_token",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.key_value = new_token
        existing.is_active = True
    else:
        db.add(PlatformAPIKey(
            platform="meta", key_name="access_token",
            key_value=new_token, is_active=True,
        ))

    logger.info("meta_token_exchanged", token_type=data.get("token_type"))
    return {
        "status": "ok",
        "message": "長期トークンに変換しました（有効期限: 約60日）",
        "token_type": data.get("token_type"),
    }


@router.get("/meta/token-info")
async def get_meta_token_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Return information about the current Meta access token (expiry, scopes, type)."""
    app_id = await _get_meta_key(db, "app_id")
    app_secret = await _get_meta_key(db, "app_secret")
    access_token = await _get_meta_key(db, "access_token")

    if not access_token:
        return {"has_token": False, "message": "アクセストークンが設定されていません"}

    # If app_id + app_secret are set, use debug_token for detailed info
    if app_id and app_secret:
        app_token = f"{app_id}|{app_secret}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{META_GRAPH_API_BASE}/debug_token",
                params={
                    "input_token": access_token,
                    "access_token": app_token,
                },
            )

        if resp.status_code == 200:
            info = resp.json().get("data", {})
            return {
                "has_token": True,
                "is_valid": info.get("is_valid", False),
                "app_id": info.get("app_id"),
                "type": info.get("type"),
                "expires_at": info.get("expires_at"),  # unix timestamp, 0 = never
                "scopes": info.get("scopes", []),
            }

    # Fallback: minimal check without app credentials
    return {
        "has_token": True,
        "message": "App ID と App Secret を設定すると、トークンの詳細情報を確認できます",
    }


# ── Helpers ─────────────────────────────────────────────────────

def _mask_value(value: str) -> str:
    """Mask API key value showing only first 4 and last 4 characters."""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


# ── Utility: load keys from DB for crawler usage ────────────────

def load_api_keys_from_db() -> dict[str, dict[str, str]]:
    """Load all active API keys from the database (sync, for use in crawlers).

    Returns: { platform: { key_name: key_value, ... }, ... }
    """
    from app.core.database import SyncSessionLocal

    session = SyncSessionLocal()
    try:
        keys = session.query(PlatformAPIKey).filter(
            PlatformAPIKey.is_active == True
        ).all()

        result: dict[str, dict[str, str]] = {}
        for key in keys:
            if key.platform not in result:
                result[key.platform] = {}
            result[key.platform][key.key_name] = key.key_value

        return result
    finally:
        session.close()


# ── Database connection management ───────────────────────────────

class DatabaseConnectRequest(BaseModel):
    database_url: str


@router.get("/database/status")
async def get_database_status():
    """Get current database connection status."""
    return {
        "in_memory_mode": is_in_memory_mode(),
        "connection_error": get_connection_error(),
    }


@router.post("/database/connect")
async def connect_database(request: DatabaseConnectRequest):
    """Test and connect to a new DATABASE_URL at runtime."""
    url = request.database_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="DATABASE_URL must not be empty")

    result = reconnect(url)
    if result["ok"]:
        logger.info("database_reconnected_via_api")
        return {"status": "ok", "message": "データベースに接続しました。テーブルを作成しました。"}
    else:
        return {"status": "error", "message": result["error"]}
