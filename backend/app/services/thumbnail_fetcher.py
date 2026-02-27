"""Thumbnail fetcher service: batch-fetch thumbnails for ads missing them.

3-stage fallback strategy:
1. Build snapshot_url from external_id if missing
2. Try Meta Graph API ad_snapshot_url (authenticated URL → higher OGP success rate)
3. Use MediaExtractor to extract thumbnail from snapshot URL (HTTP+BS4 → Playwright)
"""

import asyncio
import time
from typing import Optional

import httpx
import structlog

from app.models.ad import Ad
from app.services.media_extraction import MediaExtractor

logger = structlog.get_logger()


class ThumbnailFetcher:
    """Fetch thumbnails for ads that are missing thumbnail_url/image_url."""

    def __init__(
        self,
        meta_access_token: Optional[str] = None,
        use_playwright: bool = True,
    ):
        self.meta_access_token = meta_access_token
        self.use_playwright = use_playwright
        self._extractor = MediaExtractor()

    def fetch_all(
        self,
        session,
        batch_size: int = 10,
        delay: float = 1.5,
    ) -> dict:
        """Fetch thumbnails for all ads missing thumbnail_url.

        Idempotent: skips ads that already have thumbnail_url or thumbnail_s3_key.
        Returns stats dict: {total, success, failed, skipped}
        """
        ads = session.query(Ad).filter(
            Ad.thumbnail_url.is_(None),
            Ad.thumbnail_s3_key.is_(None),
        ).all()

        stats = {"total": len(ads), "success": 0, "failed": 0, "skipped": 0}
        logger.info("thumbnail_fetch_started", total=len(ads))

        for i, ad in enumerate(ads):
            try:
                result = self._process_single(session, ad)
                stats[result] += 1
            except Exception as e:
                logger.warning("thumbnail_fetch_error", ad_id=ad.id, error=str(e))
                stats["failed"] += 1

            # Commit in batches and rate-limit
            if (i + 1) % batch_size == 0:
                session.commit()
                if i + 1 < len(ads):
                    time.sleep(delay)

        session.commit()
        logger.info("thumbnail_fetch_completed", **stats)
        return stats

    def _process_single(self, session, ad: Ad) -> str:
        """Process a single ad. Returns 'success', 'failed', or 'skipped'."""
        # Step 1: Build snapshot_url from external_id if missing
        if not ad.snapshot_url and ad.external_id:
            ad.snapshot_url = (
                f"https://www.facebook.com/ads/library/?id={ad.external_id}"
            )
            logger.info(
                "snapshot_url_constructed",
                ad_id=ad.id,
                external_id=ad.external_id,
            )

        # Step 2: Try Meta Graph API for ad_snapshot_url (authenticated URL)
        api_snapshot_url = None
        if ad.external_id and self.meta_access_token:
            api_snapshot_url = self._get_api_snapshot_url(ad.external_id)

        # Step 3: Extract thumbnail using MediaExtractor
        # Try authenticated API URL first, then fall back to snapshot_url
        urls_to_try = []
        if api_snapshot_url:
            urls_to_try.append(api_snapshot_url)
        if ad.snapshot_url and ad.snapshot_url != api_snapshot_url:
            urls_to_try.append(ad.snapshot_url)

        if not urls_to_try:
            logger.info("thumbnail_no_url", ad_id=ad.id)
            return "failed"

        for target_url in urls_to_try:
            extracted = self._extract_thumbnail(target_url)
            if extracted and extracted.image_urls:
                ad.thumbnail_url = extracted.image_urls[0]
                ad.image_url = ad.image_url or extracted.image_urls[0]
                ad.media_extraction_status = "completed"
                if not ad.creative_type or ad.creative_type == "unknown":
                    ad.creative_type = extracted.creative_type
                logger.info(
                    "thumbnail_extracted",
                    ad_id=ad.id,
                    url=ad.thumbnail_url[:80] if ad.thumbnail_url else "",
                )
                return "success"

        ad.media_extraction_status = "failed"
        return "failed"

    def _extract_thumbnail(self, url: str):
        """Run MediaExtractor.extract() in a new event loop (sync context)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._extractor.extract(url, use_playwright=self.use_playwright)
            )
        except Exception as e:
            logger.warning("media_extract_failed", url=url[:80], error=str(e))
            return None
        finally:
            loop.close()

    def _get_api_snapshot_url(self, external_id: str) -> Optional[str]:
        """Call Meta Graph API to get ad_snapshot_url (authenticated URL)."""
        url = f"https://graph.facebook.com/v25.0/{external_id}"
        params = {
            "fields": "ad_snapshot_url",
            "access_token": self.meta_access_token,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                snapshot_url = data.get("ad_snapshot_url")
                if snapshot_url:
                    logger.info(
                        "meta_api_snapshot_url",
                        external_id=external_id,
                        url=snapshot_url[:80],
                    )
                return snapshot_url
        except Exception as e:
            logger.warning(
                "meta_api_snapshot_failed",
                external_id=external_id,
                error=str(e),
            )
            return None
