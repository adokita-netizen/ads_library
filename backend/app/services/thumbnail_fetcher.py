"""Thumbnail fetcher service: batch-fetch thumbnails for ads missing them.

Multi-stage fallback strategy:
1. Build snapshot_url from external_id if missing
2. Try Meta Graph API ad_snapshot_url (authenticated URL)
3. Use MediaExtractor to extract thumbnail from snapshot URL (HTTP+BS4 → Playwright)
4. Page profile picture (public Facebook API)
5. Destination URL og:image (LP landing page)
6. ads_archive API search by advertiser name → page_id → profile picture
7. Google Favicon as last resort
"""

import asyncio
import time
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from app.models.ad import Ad, MediaExtractionStatus
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
        self._loop: Optional[asyncio.AbstractEventLoop] = None

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

        # Reuse a single event loop for all async extractions instead of
        # creating/destroying one per asyncio.run() call.
        self._loop = asyncio.new_event_loop()
        try:
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
        finally:
            self._loop.close()
            self._loop = None

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

        for target_url in urls_to_try:
            extracted = self._extract_thumbnail(target_url)
            if extracted and extracted.image_urls:
                ad.thumbnail_url = extracted.image_urls[0]
                ad.image_url = ad.image_url or extracted.image_urls[0]
                ad.media_extraction_status = MediaExtractionStatus.COMPLETED
                if not ad.creative_type or ad.creative_type == "unknown":
                    ad.creative_type = extracted.creative_type
                # Also save extracted text if missing
                if extracted.ad_text and not ad.description:
                    ad.description = extracted.ad_text
                if extracted.ad_title and not ad.title:
                    ad.title = extracted.ad_title
                logger.info(
                    "thumbnail_extracted",
                    ad_id=ad.id,
                    url=ad.thumbnail_url[:80] if ad.thumbnail_url else "",
                )
                return "success"

        # Step 4: Fallback to page profile picture
        page_pic = self._get_page_profile_picture(ad)
        if page_pic:
            ad.thumbnail_url = page_pic
            ad.image_url = ad.image_url or page_pic
            ad.media_extraction_status = MediaExtractionStatus.ENRICHED
            logger.info("thumbnail_from_page_picture", ad_id=ad.id)
            return "success"

        # Step 5: Destination URL og:image (LP landing page)
        og_image = self._get_destination_og_image(ad)
        if og_image:
            ad.thumbnail_url = og_image
            ad.image_url = ad.image_url or og_image
            ad.media_extraction_status = MediaExtractionStatus.ENRICHED
            logger.info("thumbnail_from_og_image", ad_id=ad.id)
            return "success"

        # Step 6: ads_archive API search by advertiser name → page profile pic
        api_pic = self._search_advertiser_page_pic(ad)
        if api_pic:
            ad.thumbnail_url = api_pic
            ad.image_url = ad.image_url or api_pic
            ad.media_extraction_status = MediaExtractionStatus.ENRICHED
            logger.info("thumbnail_from_api_search", ad_id=ad.id)
            return "success"

        # Step 7: Google Favicon as last resort
        favicon = self._get_favicon(ad)
        if favicon:
            ad.thumbnail_url = favicon
            ad.image_url = ad.image_url or favicon
            ad.media_extraction_status = MediaExtractionStatus.ENRICHED
            logger.info("thumbnail_from_favicon", ad_id=ad.id)
            return "success"

        ad.media_extraction_status = MediaExtractionStatus.FAILED
        return "failed"

    def _extract_thumbnail(self, url: str):
        """Run MediaExtractor.extract() using the shared event loop (sync context)."""
        try:
            loop = self._loop or asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self._extractor.extract(url, use_playwright=self.use_playwright)
                )
            finally:
                # Only close if we created a one-off loop (fallback path)
                if not self._loop:
                    loop.close()
        except Exception as e:
            logger.warning("media_extract_failed", url=url[:80], error=str(e))
            return None

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

    def _get_destination_og_image(self, ad: "Ad") -> Optional[str]:
        """Extract og:image from the ad's destination URL (landing page)."""
        metadata = ad.ad_metadata or {}
        dest_url = ad.destination_url or metadata.get("destination_url")
        if not dest_url or not dest_url.startswith("http"):
            return None

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(dest_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    og_img = soup.find("meta", property="og:image")
                    if og_img and og_img.get("content"):
                        img_url = og_img["content"]
                        if img_url.startswith("http"):
                            return img_url
        except Exception as e:
            logger.debug("og_image_failed", ad_id=ad.id, error=str(e)[:60])
        return None

    def _search_advertiser_page_pic(self, ad: "Ad") -> Optional[str]:
        """Search ads_archive by advertiser name → get page_id → profile picture."""
        if not self.meta_access_token or not ad.advertiser_name:
            return None

        search_name = ad.advertiser_name.split(" スポンサー")[0].strip()
        api_url = "https://graph.facebook.com/v25.0/ads_archive"
        params = {
            "search_terms": search_name,
            "ad_reached_countries": '["JP"]',
            "fields": "id,page_id,page_name",
            "limit": 5,
            "access_token": self.meta_access_token,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(api_url, params=params)
                if resp.status_code != 200:
                    return None
                data = resp.json().get("data", [])
                if not data:
                    return None

                # Prefer exact ad match, otherwise use first result
                page_id = None
                for item in data:
                    if item.get("id") == ad.external_id:
                        page_id = item.get("page_id")
                        break
                if not page_id:
                    page_id = data[0].get("page_id")

                if page_id:
                    pic_url = f"https://graph.facebook.com/{page_id}/picture?type=large&redirect=false"
                    pic_resp = client.get(pic_url)
                    if pic_resp.status_code == 200:
                        return pic_resp.json().get("data", {}).get("url")
        except Exception as e:
            logger.debug("api_search_failed", ad_id=ad.id, error=str(e)[:60])
        return None

    def _get_favicon(self, ad: "Ad") -> Optional[str]:
        """Get Google Favicon for the ad's destination domain as last resort."""
        metadata = ad.ad_metadata or {}
        dest_url = ad.destination_url or metadata.get("destination_url", "")
        display_url = metadata.get("display_url", "")
        if display_url and not display_url.startswith("http"):
            display_url = "https://" + display_url

        for url in [dest_url, display_url]:
            if not url or not url.startswith("http"):
                continue
            try:
                domain = urlparse(url).netloc
                if domain:
                    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            except Exception:
                pass
        return None

    def _get_page_profile_picture(self, ad: "Ad") -> Optional[str]:
        """Get the Facebook page's profile picture as thumbnail fallback.

        Works without special permissions — public endpoint.
        """
        metadata = ad.ad_metadata or {}
        page_id = metadata.get("page_id")
        if not page_id:
            return None

        # Facebook's public page picture endpoint — do NOT attach access_token
        # (some tokens cause 403 on this endpoint; public access works fine)
        url = f"https://graph.facebook.com/{page_id}/picture?type=large&redirect=false"

        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                pic_url = data.get("data", {}).get("url")
                if pic_url:
                    logger.info("page_profile_picture", ad_id=ad.id, page_id=page_id)
                    return pic_url
        except Exception as e:
            logger.warning("page_picture_failed", ad_id=ad.id, page_id=page_id, error=str(e))

        return None
