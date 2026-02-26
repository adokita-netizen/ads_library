"""Meta access token management — retrieval, validation, and refresh."""

from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.api_key import PlatformAPIKey
from app.services.meta_marketing.client import GRAPH_API_BASE, MetaMarketingAPIError
from app.utils.crypto import decrypt_value, encrypt_value

logger = structlog.get_logger()

REQUIRED_SCOPES_READ = {"ads_read", "business_management"}
REQUIRED_SCOPES_MANAGEMENT = {"ads_read", "ads_management", "business_management"}

# Token is considered expiring if less than 7 days remain
TOKEN_EXPIRY_WARNING_DAYS = 7


class MetaTokenManager:
    """Manage Meta access tokens stored in PlatformAPIKey table."""

    @staticmethod
    async def get_access_token(db: AsyncSession) -> Optional[str]:
        """Get the Meta access token from DB, falling back to environment variable."""
        result = await db.execute(
            select(PlatformAPIKey).where(
                PlatformAPIKey.platform == "meta",
                PlatformAPIKey.key_name == "access_token",
                PlatformAPIKey.is_active == True,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            try:
                return decrypt_value(row.key_value)
            except (ValueError, Exception):
                return row.key_value  # Legacy plaintext

        # Fallback to environment variable
        settings = get_settings()
        token = getattr(settings, "meta_access_token", None)
        return token if token and token.strip() else None

    @staticmethod
    async def _get_meta_key(db: AsyncSession, key_name: str) -> Optional[str]:
        """Get a specific Meta key from DB."""
        result = await db.execute(
            select(PlatformAPIKey).where(
                PlatformAPIKey.platform == "meta",
                PlatformAPIKey.key_name == key_name,
                PlatformAPIKey.is_active == True,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        try:
            return decrypt_value(row.key_value)
        except (ValueError, Exception):
            return row.key_value

    @staticmethod
    async def validate_token(db: AsyncSession, token: Optional[str] = None) -> dict:
        """Validate a Meta access token using the debug_token endpoint.

        Returns dict with: is_valid, scopes, expires_at, type, app_id, user_id
        """
        if token is None:
            token = await MetaTokenManager.get_access_token(db)

        if not token:
            return {"is_valid": False, "error": "トークンが設定されていません"}

        app_id = await MetaTokenManager._get_meta_key(db, "app_id")
        app_secret = await MetaTokenManager._get_meta_key(db, "app_secret")

        if not app_id or not app_secret:
            # Can't debug without app credentials, do a basic /me check
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{GRAPH_API_BASE}/me",
                        params={"access_token": token, "fields": "id,name"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return {
                            "is_valid": True,
                            "user_id": data.get("id"),
                            "user_name": data.get("name"),
                            "scopes": [],
                            "expires_at": None,
                            "note": "App IDとApp Secretを設定すると詳細なトークン情報を確認できます",
                        }
                    else:
                        error = resp.json().get("error", {})
                        return {"is_valid": False, "error": error.get("message", "Token validation failed")}
            except Exception as e:
                return {"is_valid": False, "error": str(e)}

        # Use debug_token for full details
        app_token = f"{app_id}|{app_secret}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{GRAPH_API_BASE}/debug_token",
                    params={"input_token": token, "access_token": app_token},
                )
                if resp.status_code != 200:
                    error = resp.json().get("error", {})
                    return {"is_valid": False, "error": error.get("message", "Token debug failed")}

                info = resp.json().get("data", {})
                expires_at = info.get("expires_at", 0)

                # Calculate days until expiry
                days_remaining = None
                is_expiring = False
                if expires_at and expires_at > 0:
                    expiry_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
                    delta = expiry_dt - datetime.now(timezone.utc)
                    days_remaining = max(0, delta.days)
                    is_expiring = days_remaining <= TOKEN_EXPIRY_WARNING_DAYS

                return {
                    "is_valid": info.get("is_valid", False),
                    "app_id": info.get("app_id"),
                    "type": info.get("type"),
                    "user_id": info.get("user_id"),
                    "scopes": info.get("scopes", []),
                    "expires_at": expires_at,
                    "days_remaining": days_remaining,
                    "is_expiring": is_expiring,
                }
        except Exception as e:
            return {"is_valid": False, "error": str(e)}

    @staticmethod
    def check_required_scopes(scopes: list[str], require_management: bool = False) -> dict:
        """Check if token has the required scopes.

        Returns dict with: has_required, missing_scopes, has_management
        """
        scope_set = set(scopes)
        required = REQUIRED_SCOPES_MANAGEMENT if require_management else REQUIRED_SCOPES_READ
        missing = required - scope_set

        return {
            "has_required": len(missing) == 0,
            "missing_scopes": list(missing),
            "has_management": "ads_management" in scope_set,
            "available_scopes": scopes,
        }

    @staticmethod
    async def refresh_if_needed(db: AsyncSession) -> dict:
        """Check token expiry and exchange for long-lived token if expiring soon.

        Returns dict with: refreshed, message, days_remaining
        """
        token = await MetaTokenManager.get_access_token(db)
        if not token:
            return {"refreshed": False, "message": "トークンが設定されていません"}

        validation = await MetaTokenManager.validate_token(db, token)
        if not validation.get("is_valid"):
            return {"refreshed": False, "message": f"トークンが無効です: {validation.get('error', '')}"}

        days_remaining = validation.get("days_remaining")
        if days_remaining is None:
            return {"refreshed": False, "message": "有効期限を確認できません", "days_remaining": None}

        if days_remaining > TOKEN_EXPIRY_WARNING_DAYS:
            return {"refreshed": False, "message": "トークンはまだ有効です", "days_remaining": days_remaining}

        # Token is expiring — attempt exchange
        app_id = await MetaTokenManager._get_meta_key(db, "app_id")
        app_secret = await MetaTokenManager._get_meta_key(db, "app_secret")

        if not app_id or not app_secret:
            return {
                "refreshed": False,
                "message": f"トークンの有効期限が残り{days_remaining}日です。App IDとApp Secretを設定して自動更新を有効にしてください。",
                "days_remaining": days_remaining,
            }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{GRAPH_API_BASE}/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": app_id,
                        "client_secret": app_secret,
                        "fb_exchange_token": token,
                    },
                )

            if resp.status_code != 200:
                error_msg = resp.json().get("error", {}).get("message", resp.text)
                return {
                    "refreshed": False,
                    "message": f"トークン更新に失敗: {error_msg}",
                    "days_remaining": days_remaining,
                }

            new_token = resp.json().get("access_token")
            if not new_token:
                return {"refreshed": False, "message": "レスポンスにトークンが含まれていません", "days_remaining": days_remaining}

            # Save new token
            encrypted = encrypt_value(new_token)
            result = await db.execute(
                select(PlatformAPIKey).where(
                    PlatformAPIKey.platform == "meta",
                    PlatformAPIKey.key_name == "access_token",
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.key_value = encrypted
                existing.is_active = True
            else:
                db.add(PlatformAPIKey(
                    platform="meta", key_name="access_token",
                    key_value=encrypted, is_active=True,
                ))

            logger.info("meta_token_refreshed", old_days_remaining=days_remaining)
            return {"refreshed": True, "message": "長期トークンに更新しました（有効期限: 約60日）", "days_remaining": 60}

        except Exception as e:
            logger.error("meta_token_refresh_failed", error=str(e))
            return {"refreshed": False, "message": f"トークン更新エラー: {e}", "days_remaining": days_remaining}
