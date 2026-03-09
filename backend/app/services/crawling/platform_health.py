"""Platform reachability checks for crawl pre-flight decisions."""

from __future__ import annotations

import httpx


class PlatformHealth:
    HEALTH_URLS = {
        "meta": "https://www.facebook.com/ads/library/",
        "youtube": "https://www.youtube.com/",
        "tiktok": "https://www.tiktok.com/",
        "google": "https://adstransparency.google.com/",
    }

    async def check_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), follow_redirects=True) as client:
            for platform, url in self.HEALTH_URLS.items():
                try:
                    response = await client.head(url)
                    results[platform] = response.status_code < 400
                except Exception:
                    results[platform] = False
        return results

