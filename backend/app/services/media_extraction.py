"""Media extraction service: extract actual image/video URLs from ad snapshot pages."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()

# CI-118: Extractor version tracking
EXTRACTOR_VERSION = "1.3.0"
EXTRACTOR_CHANGELOG = {
    "1.0.0": "Initial: HTTP+BS4 extraction",
    "1.1.0": "Added Playwright fallback",
    "1.2.0": "render_ad URL parser, fbcdn image filter",
    "1.3.0": "CI-098 timeout presets, CI-064 health tracking",
}

# Limit concurrent Playwright browsers
_playwright_semaphore = asyncio.Semaphore(2)


@dataclass
class ExtractedMedia:
    """Result of media extraction from a snapshot URL."""

    creative_type: str = "unknown"  # video / image / carousel / unknown
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    thumbnail_url: Optional[str] = None
    ad_text: Optional[str] = None  # extracted ad body text
    ad_title: Optional[str] = None  # extracted ad title
    extractor_version: str = EXTRACTOR_VERSION  # CI-118: track which version extracted
    extraction_method: str = ""  # "http_bs4" or "playwright"


class MediaExtractor:
    """Extract actual media URLs from ad snapshot/preview pages.

    Two-stage approach:
    1. HTTP + BeautifulSoup (fast, lightweight) — parses og:image, og:video, <img>, <video>
    2. Playwright (reliable, heavy) — JS-rendered DOM analysis with semaphore concurrency control
    """

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def extract(self, snapshot_url: str, use_playwright: bool = True) -> ExtractedMedia:
        """Extract media from snapshot URL, trying HTTP first, then Playwright fallback."""
        result = await self._extract_via_http(snapshot_url)

        if result.creative_type == "unknown" and use_playwright:
            pw_result = await self._extract_via_playwright(snapshot_url)
            if pw_result.creative_type != "unknown":
                return pw_result
            # Merge any additional URLs found by Playwright
            if pw_result.image_urls or pw_result.video_urls:
                result.image_urls = list(set(result.image_urls + pw_result.image_urls))
                result.video_urls = list(set(result.video_urls + pw_result.video_urls))

        # Determine creative_type from extracted media if still unknown
        if result.creative_type == "unknown":
            if result.video_urls:
                result.creative_type = "video"
            elif len(result.image_urls) > 1:
                result.creative_type = "carousel"
            elif result.image_urls:
                result.creative_type = "image"

        return result

    async def _extract_via_http(self, url: str) -> ExtractedMedia:
        """Stage 1: Fast HTTP fetch + BeautifulSoup parsing."""
        result = ExtractedMedia()

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    )
                },
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            result = self._parse_html(soup)
            logger.info("media_http_extracted", url=url, type=result.creative_type,
                        images=len(result.image_urls), videos=len(result.video_urls))

        except Exception as e:
            logger.warning("media_http_extraction_failed", url=url, error=str(e), exc_info=True)

        return result

    async def _extract_via_playwright(self, url: str) -> ExtractedMedia:
        """Stage 2: Playwright JS-rendered extraction with concurrency limit."""
        result = ExtractedMedia()

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright_not_installed")
            return result

        async with _playwright_semaphore:
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                        ],
                    )
                    page = None
                    try:
                        context = await browser.new_context(
                            viewport={"width": 1920, "height": 1080},
                            user_agent=(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/121.0.0.0 Safari/537.36"
                            ),
                            locale="ja-JP",
                        )
                        page = await context.new_page()
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
                            await page.wait_for_timeout(5000)
                        except Exception:
                            logger.warning("page_load_timeout", url=url)

                        try:
                            html = await page.content()
                        except Exception:
                            logger.warning("page_content_failed_after_timeout", url=url)
                            return result
                        soup = BeautifulSoup(html, "html.parser")
                        if "/ads/archive/render_ad/" in url:
                            result = self._parse_render_ad_html(soup)
                        else:
                            result = self._parse_html(soup)
                    finally:
                        if page:
                            await page.close()
                        if context:
                            await context.close()
                        await browser.close()

                logger.info("media_playwright_extracted", url=url, type=result.creative_type,
                            images=len(result.image_urls), videos=len(result.video_urls))

            except Exception as e:
                logger.warning("media_playwright_extraction_failed", url=url, error=str(e), exc_info=True)

        return result

    def _parse_html(self, soup: BeautifulSoup) -> ExtractedMedia:
        """Parse HTML for media URLs using og tags and media elements."""
        result = ExtractedMedia()
        image_urls: list[str] = []
        video_urls: list[str] = []

        # Open Graph tags
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_urls.append(og_image["content"])

        og_video = soup.find("meta", property="og:video")
        if og_video and og_video.get("content"):
            video_urls.append(og_video["content"])

        og_video_url = soup.find("meta", property="og:video:url")
        if og_video_url and og_video_url.get("content"):
            video_urls.append(og_video_url["content"])

        # <video> elements
        for video_el in soup.find_all("video"):
            src = video_el.get("src")
            if src and src.startswith("http"):
                video_urls.append(src)
            poster = video_el.get("poster")
            if poster and poster.startswith("http"):
                result.thumbnail_url = poster
            # <source> children
            for source in video_el.find_all("source"):
                src = source.get("src")
                if src and src.startswith("http"):
                    video_urls.append(src)

        # <img> elements — filter out tracking pixels and icons
        for img_el in soup.find_all("img"):
            src = img_el.get("src") or img_el.get("data-src")
            if not src or not src.startswith("http"):
                continue
            # Skip tiny images (tracking pixels, icons)
            width = img_el.get("width")
            height = img_el.get("height")
            if width and height:
                try:
                    if int(width) < 50 or int(height) < 50:
                        continue
                except (ValueError, TypeError):
                    pass
            # Skip common tracking/icon patterns
            if any(skip in src.lower() for skip in [
                "pixel", "tracking", "beacon", "1x1", "spacer",
                "favicon", "logo", ".svg", "emoji",
            ]):
                continue
            image_urls.append(src)

        # Deduplicate while preserving order
        result.image_urls = list(dict.fromkeys(image_urls))
        result.video_urls = list(dict.fromkeys(video_urls))

        # Determine type
        if video_urls:
            result.creative_type = "video"
        elif len(result.image_urls) > 1:
            result.creative_type = "carousel"
        elif result.image_urls:
            result.creative_type = "image"

        # Set thumbnail from og:image if not set
        if not result.thumbnail_url and result.image_urls:
            result.thumbnail_url = result.image_urls[0]

        # ── Text extraction ──────────────────────────────────────
        # 1. og:description → ad body text
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            result.ad_text = og_desc["content"].strip()

        # 2. og:title → ad title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            result.ad_title = og_title["content"].strip()

        # 3. Fallback: extract visible body text if OG tags missing
        if not result.ad_text:
            body = soup.find("body")
            if body:
                # Remove non-content elements
                for tag in body.find_all(["script", "style", "nav", "header", "footer", "noscript"]):
                    tag.decompose()
                visible_text = body.get_text(separator="\n", strip=True)
                # Take first meaningful chunk (up to 2000 chars)
                if visible_text and len(visible_text) > 20:
                    result.ad_text = visible_text[:2000]

        return result

    def _parse_render_ad_html(self, soup: BeautifulSoup) -> ExtractedMedia:
        """Parse Facebook render_ad page (server-rendered, specific structure)."""
        result = ExtractedMedia()

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src or not src.startswith("http"):
                continue
            if "fbcdn.net" in src or "facebook.com" in src:
                width = img.get("width")
                if width:
                    try:
                        if int(width) < 100:
                            continue
                    except (ValueError, TypeError):
                        pass
                result.image_urls.append(src)

        for video in soup.find_all("video"):
            src = video.get("src")
            if src and src.startswith("http"):
                result.video_urls.append(src)
            for source in video.find_all("source"):
                src = source.get("src")
                if src and src.startswith("http"):
                    result.video_urls.append(src)

        result.image_urls = list(dict.fromkeys(result.image_urls))
        result.video_urls = list(dict.fromkeys(result.video_urls))

        if result.video_urls:
            result.creative_type = "video"
        elif len(result.image_urls) > 1:
            result.creative_type = "carousel"
        elif result.image_urls:
            result.creative_type = "image"

        if not result.thumbnail_url and result.image_urls:
            result.thumbnail_url = result.image_urls[0]

        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            result.ad_text = og_desc["content"].strip()

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            result.ad_title = og_title["content"].strip()

        return result
