"""Meta Graph API v21.0 client with rate limiting, pagination, and error handling."""

import asyncio
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class MetaMarketingAPIError(Exception):
    """Base error for Meta Marketing API."""

    def __init__(self, message: str, code: int | None = None, subcode: int | None = None):
        self.code = code
        self.subcode = subcode
        super().__init__(message)


class RateLimitError(MetaMarketingAPIError):
    """Raised when Meta API rate limit is hit (error code 17 or 32)."""
    pass


class AuthenticationError(MetaMarketingAPIError):
    """Raised when token is invalid or expired (error code 190)."""
    pass


class PermissionError(MetaMarketingAPIError):
    """Raised when required permissions are missing (error code 10 or 200)."""
    pass


class MetaMarketingClient:
    """Async client for Meta Graph API v21.0.

    Handles pagination, rate limit backoff, and structured error classification.
    """

    MAX_RETRIES = 3
    INITIAL_BACKOFF = 2.0  # seconds

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=GRAPH_API_BASE,
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── Core HTTP methods ────────────────────────────────────────

    async def get(self, path: str, params: dict | None = None) -> dict:
        """GET request with automatic retry on rate limits."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, data: dict | None = None, files: dict | None = None) -> dict:
        """POST request with automatic retry on rate limits."""
        return await self._request("POST", path, data=data, files=files)

    async def delete(self, path: str, params: dict | None = None) -> dict:
        """DELETE request with automatic retry on rate limits."""
        return await self._request("DELETE", path, params=params)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
    ) -> dict:
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                if method == "GET":
                    resp = await client.get(path, params=params)
                elif method == "POST":
                    if files:
                        resp = await client.post(path, data=data, files=files)
                    else:
                        resp = await client.post(path, data=data)
                elif method == "DELETE":
                    resp = await client.delete(path, params=params)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                body = resp.json() if resp.text else {}

                if resp.status_code == 200:
                    return body

                # Handle API errors
                error = body.get("error", {})
                error_code = error.get("code")
                error_subcode = error.get("error_subcode")
                error_msg = error.get("message", resp.text)

                # Rate limit (code 17 = app-level, 32 = account-level)
                if error_code in (17, 32):
                    backoff = self.INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "meta_api_rate_limit",
                        code=error_code,
                        attempt=attempt + 1,
                        backoff=backoff,
                    )
                    last_error = RateLimitError(error_msg, code=error_code, subcode=error_subcode)
                    await asyncio.sleep(backoff)
                    continue

                # Authentication error (expired/invalid token)
                if error_code == 190:
                    raise AuthenticationError(error_msg, code=error_code, subcode=error_subcode)

                # Permission errors
                if error_code in (10, 200):
                    raise PermissionError(error_msg, code=error_code, subcode=error_subcode)

                # Transient server errors
                if resp.status_code >= 500:
                    backoff = self.INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning("meta_api_server_error", status=resp.status_code, attempt=attempt + 1)
                    last_error = MetaMarketingAPIError(error_msg, code=error_code, subcode=error_subcode)
                    await asyncio.sleep(backoff)
                    continue

                raise MetaMarketingAPIError(error_msg, code=error_code, subcode=error_subcode)

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                backoff = self.INITIAL_BACKOFF * (2 ** attempt)
                logger.warning("meta_api_connection_error", error=str(e), attempt=attempt + 1)
                last_error = MetaMarketingAPIError(f"Connection error: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    continue
                raise last_error

        raise last_error or MetaMarketingAPIError("Max retries exceeded")

    # ── Paginated fetch ──────────────────────────────────────────

    async def get_paginated(self, path: str, params: dict | None = None, max_pages: int = 50) -> list[dict]:
        """Fetch all pages from a paginated endpoint.

        Returns concatenated list of items from data field across pages.
        """
        all_items: list[dict] = []
        current_params = dict(params) if params else {}
        current_path = path
        pages = 0

        while pages < max_pages:
            result = await self.get(current_path, params=current_params if pages == 0 else None)
            data = result.get("data", [])
            all_items.extend(data)
            pages += 1

            # Check for next page
            paging = result.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break

            # For subsequent pages, use the full next URL
            current_path = next_url.replace(GRAPH_API_BASE, "")
            current_params = {}  # params are encoded in the next URL

        logger.info("meta_api_paginated_fetch", path=path, total_items=len(all_items), pages=pages)
        return all_items

    # ── High-level API methods ───────────────────────────────────

    async def get_ad_accounts(self) -> list[dict]:
        """Get all ad accounts accessible by the current token."""
        return await self.get_paginated(
            "/me/adaccounts",
            params={
                "fields": "id,account_id,name,business_name,currency,timezone_name,"
                          "account_status,amount_spent,balance",
                "limit": 100,
            },
        )

    async def get_account_info(self, account_id: str) -> dict:
        """Get detailed info for a specific ad account."""
        return await self.get(
            f"/act_{account_id}",
            params={
                "fields": "id,account_id,name,business_name,currency,timezone_name,"
                          "account_status,amount_spent,balance,owner,"
                          "funding_source_details,spend_cap",
            },
        )

    async def get_creative_thumbnail(self, creative_id: str) -> Optional[str]:
        """Fetch thumbnail URL for a creative. Returns URL or None."""
        try:
            result = await self.get(
                f"/{creative_id}",
                params={"fields": "thumbnail_url,effective_image_url,image_url"},
            )
            return (
                result.get("effective_image_url")
                or result.get("thumbnail_url")
                or result.get("image_url")
            )
        except MetaMarketingAPIError:
            return None

    async def debug_token(self, token: str, app_token: str) -> dict:
        """Debug a token to get its type, scopes, and expiry."""
        client = await self._get_client()
        resp = await client.get(
            "/debug_token",
            params={"input_token": token, "access_token": app_token},
        )
        body = resp.json()
        if resp.status_code != 200:
            error_msg = body.get("error", {}).get("message", resp.text)
            raise MetaMarketingAPIError(f"Token debug failed: {error_msg}")
        return body.get("data", {})
