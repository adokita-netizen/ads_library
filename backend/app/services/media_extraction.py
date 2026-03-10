"""Media extraction service: extract actual image/video URLs from ad snapshot pages."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional
import re
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()

# CI-118: Extractor version tracking
EXTRACTOR_VERSION = "2.0.0"
EXTRACTOR_CHANGELOG = {
    "1.0.0": "Initial: HTTP+BS4 extraction",
    "1.1.0": "Added Playwright fallback",
    "1.2.0": "render_ad URL parser, fbcdn image filter",
    "1.3.0": "CI-098 timeout presets, CI-064 health tracking",
    "1.4.0": "D-R2-3 aggressive video recovery with 4-step fallback",
    "1.5.0": "Network intercept, image validation, enhanced lazy-load handling",
    "1.6.0": "Target-ad isolation, URL validation, BS4 skip for Meta Library",
    "2.0.0": "Card-scoped intercept, aspect ratio filter, size-based dedup, creative asset registration",
}
_IMAGE_ATTRS = (
    "src",
    "data-src",
    "data-image-src",
    "data-img-src",
    "data-delayed-url",
    "data-original",
    "data-store",
)
_VIDEO_ATTRS = ("src", "data-src", "data-video-src", "data-store")
_DISCLAIMER_TEXTS = {
    "This ad ran without a required disclaimer.",
    "This ad was run by an account or Page we later disabled for not following our Advertising Standards.",
    "This content was removed because it didn't follow our Advertising Standards.",
    "この広告は必要な免責事項なしで配信されました。",
}
_LOGIN_REQUIRED_MARKERS = (
    "表示したい場合は、アカウントにログインする必要があります",
    "ログインする必要があります",
    "you must log in to view",
    "log in to view",
)


def get_extractor_version_snapshot() -> dict:
    return {
        "current_version": EXTRACTOR_VERSION,
        "changelog": dict(EXTRACTOR_CHANGELOG),
    }

# Limit concurrent Playwright browsers
_playwright_semaphore = asyncio.Semaphore(2)

_META_LIBRARY_CARD_EXTRACT_JS = r"""() => {
    const results = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const idElements = [];
    while (walker.nextNode()) {
        if ((walker.currentNode.textContent || '').includes('\u30e9\u30a4\u30d6\u30e9\u30eaID')) {
            idElements.push(walker.currentNode.parentElement);
        }
    }

    for (const el of idElements) {
        let card = el;
        for (let i = 0; i < 15; i++) {
            if (!card || !card.parentElement) break;
            card = card.parentElement;
            const text = card.innerText || '';
            if (text.includes('\u30e9\u30a4\u30d6\u30e9\u30eaID') &&
                text.includes('\u63b2\u8f09\u958b\u59cb\u65e5') &&
                text.includes('\u5e83\u544a\u306e\u8a73\u7d30\u3092\u898b\u308b')) {
                break;
            }
        }
        if (!card) continue;

        const text = card.innerText || '';
        const idMatch = text.match(/\u30e9\u30a4\u30d6\u30e9\u30eaID:\s*(\d+)/);
        const sponsorIdx = text.indexOf('\u30b9\u30dd\u30f3\u30b5\u30fc\u5e83\u544a');
        let advertiser = null;
        if (sponsorIdx > 0) {
            const before = text.slice(0, sponsorIdx).trim();
            const lines = before.split('\n').filter(l => l.trim());
            advertiser = lines.length ? lines[lines.length - 1].trim() : null;
        }

        let body = '';
        if (sponsorIdx > 0) {
            const after = text.slice(sponsorIdx + 7).trim();
            const bodyLines = after.split('\n').filter(l => l.trim() && !l.includes('\u5e83\u544a\u306e\u8a73\u7d30'));
            body = bodyLines.join('\n').slice(0, 2000);
        }

        const extLinks = [];
        for (const link of card.querySelectorAll('a[href]')) {
            const href = link.getAttribute('href') || '';
            if (href.includes('l.facebook.com/l.php')) {
                try {
                    const u = new URL(href).searchParams.get('u');
                    if (u && !extLinks.includes(decodeURIComponent(u))) extLinks.push(decodeURIComponent(u));
                } catch(e) {}
            } else if (
                href.startsWith('http') &&
                !href.includes('facebook.com') &&
                !href.includes('instagram.com') &&
                !href.includes('metastatus.com')
            ) {
                if (!extLinks.includes(href)) extLinks.push(href);
            }
        }

        const imageUrls = [];
        const imageMeta = [];
        for (const img of card.querySelectorAll('img')) {
            const src = img.getAttribute('src') || '';
            if (!src || src.startsWith('data:')) continue;
            const w = img.naturalWidth || img.width || parseInt(img.getAttribute('width') || '0');
            const h = img.naturalHeight || img.height || parseInt(img.getAttribute('height') || '0');
            if ((w > 0 && w < 50) || (h > 0 && h < 50)) continue;
            if (src.includes('emoji') || src.includes('rsrc.php') || src.includes('static.xx') || src.includes('platform-lookaside') || src.includes('profile_pic')) continue;
            if (!imageUrls.includes(src)) {
                imageUrls.push(src);
                imageMeta.push({url: src, w: w || 0, h: h || 0});
            }
        }

        const videoUrls = [];
        let posterUrl = null;
        for (const video of card.querySelectorAll('video')) {
            const src = video.getAttribute('src') || '';
            if (src && src.startsWith('http') && !videoUrls.includes(src)) videoUrls.push(src);
            const poster = video.getAttribute('poster') || '';
            if (!posterUrl && poster && poster.startsWith('http')) posterUrl = poster;
            for (const source of video.querySelectorAll('source')) {
                const sourceSrc = source.getAttribute('src') || '';
                if (sourceSrc && sourceSrc.startsWith('http') && !videoUrls.includes(sourceSrc)) videoUrls.push(sourceSrc);
            }
        }

        if (idMatch || advertiser || imageUrls.length || videoUrls.length) {
            results.push({
                ad_id: idMatch ? idMatch[1] : null,
                advertiser,
                body,
                destination_url: extLinks.length ? extLinks[0] : null,
                all_external_links: extLinks,
                image_urls: imageUrls,
                image_meta: imageMeta,
                video_urls: videoUrls,
                poster_url: posterUrl,
            });
        }
    }
    return results;
}"""

_META_LIBRARY_OPEN_DETAIL_JS = r"""(targetId) => {
    const clickLastDetail = (root) => {
        const controls = Array.from((root || document).querySelectorAll('button, [role="button"]'));
        const matches = controls.filter((el) => {
            const label = (el.innerText || el.getAttribute('aria-label') || '').trim();
            return /広告の詳細を見る|See ad details|View ad details/.test(label);
        });
        const last = matches[matches.length - 1];
        if (!last) return false;
        last.click();
        return true;
    };

    if (!targetId) return false;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let anchor = null;
    while (walker.nextNode()) {
        const text = (walker.currentNode.textContent || '').replace(/\s+/g, '');
        if (text.includes(String(targetId))) {
            anchor = walker.currentNode.parentElement;
            break;
        }
    }
    if (!anchor) return clickLastDetail(document);

    let card = anchor;
    for (let i = 0; i < 15; i++) {
        if (!card) break;
        const text = card.innerText || '';
        if (
            text.includes(String(targetId)) &&
            (text.includes('広告の詳細を見る') || text.includes('See ad details') || text.includes('View ad details'))
        ) {
            break;
        }
        card = card.parentElement;
    }
    if (!card) return clickLastDetail(document);

    return clickLastDetail(card) || clickLastDetail(document);
}"""

_META_LIBRARY_DIALOG_EXTRACT_JS = r"""() => {
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'));
    return dialogs.map((dialog, i) => {
        const text = (dialog.innerText || '').trim();
        const images = Array.from(dialog.querySelectorAll('img'))
            .map((img) => img.currentSrc || img.src || img.getAttribute('src') || '')
            .filter(Boolean);
        const videos = Array.from(dialog.querySelectorAll('video, source'))
            .map((node) => node.currentSrc || node.src || node.getAttribute('src') || '')
            .filter(Boolean);
        const links = Array.from(dialog.querySelectorAll('a[href]'))
            .map((a) => a.href || a.getAttribute('href') || '')
            .filter(Boolean);
        return {
            index: i,
            text: text.slice(0, 4000),
            images: Array.from(new Set(images)).slice(0, 20),
            videos: Array.from(new Set(videos)).slice(0, 20),
            links: Array.from(new Set(links)).slice(0, 20),
        };
    });
}"""

_META_LIBRARY_PAGE_STATE_JS = r"""() => {
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'));
    return {
        title: document.title || '',
        bodyText: (document.body?.innerText || '').slice(0, 8000),
        dialogCount: dialogs.length,
        dialogTexts: dialogs.map((dialog) => (dialog.innerText || '').slice(0, 2000)),
    };
}"""


@dataclass
class ExtractedMedia:
    """Result of media extraction from a snapshot URL."""

    creative_type: str = "unknown"  # video / image / carousel / unknown
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    thumbnail_url: Optional[str] = None
    ad_text: Optional[str] = None  # extracted ad body text
    ad_title: Optional[str] = None  # extracted ad title
    destination_url: Optional[str] = None
    destination_domain: Optional[str] = None
    extractor_version: str = EXTRACTOR_VERSION  # CI-118: track which version extracted
    extraction_method: str = ""  # "http_bs4" or "playwright"
    restriction_reason: Optional[str] = None
    debug_title: Optional[str] = None
    debug_excerpt: Optional[str] = None
    debug_dialog_count: int = 0
    debug_stage: Optional[str] = None
    screenshot_bytes: Optional[bytes] = None
    screenshot_content_type: Optional[str] = None


class MediaExtractor:
    """Extract actual media URLs from ad snapshot/preview pages.

    Two-stage approach:
    1. HTTP + BeautifulSoup (fast, lightweight) — parses og:image, og:video, <img>, <video>
    2. Playwright (reliable, heavy) — JS-rendered DOM analysis with semaphore concurrency control
    """

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    @staticmethod
    def _normalize_media_url(url: str | None) -> str | None:
        if not url:
            return None
        value = str(url).strip()
        if not value or value.startswith(("data:", "blob:")):
            return None
        for _ in range(2):
            decoded = unquote(value)
            if decoded == value:
                break
            value = decoded
        if value.startswith("//"):
            value = f"https:{value}"
        if not value.startswith(("http://", "https://")):
            return None
        return value

    @classmethod
    def _extract_url_from_style(cls, style_value: str | None) -> str | None:
        if not style_value:
            return None
        match = re.search(r"url\((['\"]?)(https?://[^)'\"]+)\1\)", style_value, flags=re.I)
        if not match:
            return None
        return cls._normalize_media_url(match.group(2))

    @classmethod
    def _candidate_urls_from_attrs(cls, element, attrs: tuple[str, ...]) -> list[str]:
        urls: list[str] = []
        for attr in attrs:
            raw = element.get(attr)
            if not raw:
                continue
            if attr == "data-store":
                try:
                    store = raw if isinstance(raw, dict) else json.loads(raw)
                except Exception:
                    store = {}
                if isinstance(store, dict):
                    for key in ("src", "imgSrc", "image", "imageURI", "videoSrc", "hdSrc", "sdSrc"):
                        normalized = cls._normalize_media_url(store.get(key))
                        if normalized:
                            urls.append(normalized)
                continue
            normalized = cls._normalize_media_url(raw)
            if normalized:
                urls.append(normalized)
        style_url = cls._extract_url_from_style(element.get("style"))
        if style_url:
            urls.append(style_url)
        return list(dict.fromkeys(urls))

    @classmethod
    def _should_keep_image(cls, url: str, *, width: int | None = None, height: int | None = None) -> bool:
        lowered = url.lower()
        if any(skip in lowered for skip in ("pixel", "tracking", "beacon", "1x1", "spacer", "favicon", "emoji", "rsrc.php")):
            return False
        if lowered.endswith(".svg"):
            return False
        if width and width < 50:
            return False
        if height and height < 50:
            return False
        return True

    @staticmethod
    def _is_valid_creative_url(url: str | None) -> bool:
        """Validate that a URL is an actual creative asset, not garbage."""
        if not url:
            return False
        lowered = url.lower()
        # Reject known garbage patterns
        _garbage = (
            "s2/favicons", "favicon", "google.com/s2/",
            "facebook.com/ads/library", "facebook.com/ads/archive",
            "og.png", "og__", "og_image",
            "/static/placeholders/",
        )
        if any(g in lowered for g in _garbage):
            return False
        # Must be an actual media CDN or known image host
        _valid_hosts = ("fbcdn", "scontent", "instagram", "cdninstagram",
                        ".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm",
                        "cdn/shop", "cloudfront", "amazonaws", "imgix")
        # Allow if it looks like an actual image/video URL
        if any(h in lowered for h in _valid_hosts):
            return True
        # Reject if it's just a webpage URL
        if "facebook.com" in lowered or "google.com" in lowered:
            return False
        return True

    @staticmethod
    def _is_placeholder_text(value: str | None) -> bool:
        return str(value or "").strip() in _DISCLAIMER_TEXTS

    @staticmethod
    def _detect_restriction_reason(text: str | None) -> str | None:
        lowered = str(text or "").lower()
        if any(marker.lower() in lowered for marker in _LOGIN_REQUIRED_MARKERS):
            return "login_required"
        return None

    @staticmethod
    def _normalize_destination_url(url: str | None) -> str | None:
        if not url:
            return None
        value = str(url).strip()
        if not value or value.startswith(("javascript:", "mailto:", "#")):
            return None

        for _ in range(2):
            decoded = unquote(value)
            if decoded == value:
                break
            value = decoded

        if not value.startswith(("http://", "https://")):
            if "." in value and " " not in value:
                value = f"https://{value.lstrip('/')}"
            else:
                return None

        parsed = urlparse(value)
        host = (parsed.netloc or "").lower()
        if not host:
            return None

        if "facebook.com" in host and parsed.path.startswith("/l.php"):
            qs = parse_qs(parsed.query)
            inner = qs.get("u", [None])[0] or qs.get("url", [None])[0]
            if inner:
                return MediaExtractor._normalize_destination_url(inner)

        blocked_hosts = ("facebook.com", "fb.com", "instagram.com", "cdninstagram.com", "fbcdn.net")
        if any(host == blocked or host.endswith(f".{blocked}") for blocked in blocked_hosts):
            return None

        return value

    def _extract_destination_url(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        candidates: list[str] = []
        for anchor in soup.find_all("a"):
            for attr in ("href", "data-href", "data-link", "data-lynx-uri"):
                raw = anchor.get(attr)
                if isinstance(raw, str) and raw.strip():
                    candidates.append(raw)

        refresh = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
        if refresh and refresh.get("content"):
            content = str(refresh.get("content"))
            match = re.search(r"url=(.+)$", content, flags=re.I)
            if match:
                candidates.append(match.group(1).strip())

        seen: set[str] = set()
        for raw in candidates:
            normalized = self._normalize_destination_url(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            return normalized, (urlparse(normalized).netloc or "").lower()
        return None, None

    @staticmethod
    def _target_external_id_from_url(url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        values = params.get("id") or params.get("ad_id")
        if not values:
            return None
        value = str(values[0]).strip()
        return value or None

    def _extract_meta_library_result(self, cards: list[dict], target_external_id: str | None) -> ExtractedMedia:
        result = ExtractedMedia()
        selected = None
        if target_external_id:
            for card in cards:
                if str(card.get("ad_id") or "").strip() == target_external_id:
                    selected = card
                    break
        # v1.6: Do NOT fall back to cards[0] if target ID is specified but not found
        if selected is None and cards and not target_external_id:
            selected = cards[0]
        if not selected:
            return result

        # v2.0: Filter images by size/quality — only keep creative-grade images
        raw_images = list(dict.fromkeys(selected.get("image_urls") or []))
        image_meta = selected.get("image_meta") or []
        meta_by_url = {m.get("url"): m for m in image_meta if m.get("url")}

        quality_images = []
        for img_url in raw_images:
            if not self._is_valid_creative_url(img_url):
                continue
            meta = meta_by_url.get(img_url, {})
            w, h = meta.get("w", 0), meta.get("h", 0)
            # Skip tiny UI elements (icons, buttons, avatars)
            if w > 0 and h > 0 and (w < 100 or h < 100):
                continue
            # Skip profile pictures and small avatars
            if w > 0 and h > 0 and w == h and w < 150:
                continue
            quality_images.append(img_url)

        # v2.0: Limit to reasonable count — a single ad has at most ~10 carousel cards
        if len(quality_images) > 10:
            # Prefer larger images (sort by content-length from meta if available)
            quality_images = quality_images[:10]

        result.image_urls = quality_images
        result.video_urls = list(dict.fromkeys(selected.get("video_urls") or []))
        result.thumbnail_url = selected.get("poster_url") or (result.image_urls[0] if result.image_urls else None)
        result.ad_text = selected.get("body") or None
        result.destination_url = self._normalize_destination_url(selected.get("destination_url"))
        result.destination_domain = (urlparse(result.destination_url).netloc or "").lower() if result.destination_url else None
        if result.video_urls:
            result.creative_type = "video"
        elif len(result.image_urls) > 1:
            result.creative_type = "carousel"
        elif result.image_urls:
            result.creative_type = "image"
        return result

    async def _open_meta_library_detail_dialog(self, page, target_external_id: str | None) -> bool:
        detail_pattern = re.compile(r"広告の詳細を見る|See ad details|View ad details", re.I)

        if target_external_id:
            try:
                id_locator = page.get_by_text(f"ライブラリID: {target_external_id}", exact=False)
                if await id_locator.count():
                    await id_locator.last.scroll_into_view_if_needed(timeout=3000)
                    card = id_locator.last.locator("xpath=ancestor::*[.//button or .//*[@role='button']][1]")
                    scoped_buttons = card.get_by_role("button", name=detail_pattern)
                    if await scoped_buttons.count():
                        await scoped_buttons.last.click(timeout=3000)
                        return True
            except Exception:
                pass

        try:
            detail_buttons = page.get_by_role("button", name=detail_pattern)
            if await detail_buttons.count():
                await detail_buttons.last.scroll_into_view_if_needed(timeout=3000)
                await detail_buttons.last.click(timeout=3000)
                return True
        except Exception:
            pass

        return False

    def _extract_from_dialog_payloads(self, dialogs: list[dict], target_external_id: str | None) -> ExtractedMedia:
        result = ExtractedMedia()
        if not dialogs:
            return result

        selected = None
        normalized_target = str(target_external_id or "").strip()
        for dialog in dialogs:
            text = str(dialog.get("text") or "")
            if normalized_target and normalized_target in text:
                selected = dialog
                break
        # v1.6: Only fall back to last dialog if no target ID specified
        if selected is None and not normalized_target:
            selected = dialogs[-1]

        result.image_urls = [
            url for url in (self._normalize_media_url(item) for item in (selected.get("images") or []))
            if url and self._should_keep_image(url)
        ]
        result.video_urls = [
            url for url in (self._normalize_video_url(item) for item in (selected.get("videos") or []))
            if url
        ]
        links = [self._normalize_destination_url(item) for item in (selected.get("links") or [])]
        links = [item for item in links if item]
        result.destination_url = links[0] if links else None
        result.destination_domain = (urlparse(result.destination_url).netloc or "").lower() if result.destination_url else None
        text = str(selected.get("text") or "")
        result.restriction_reason = self._detect_restriction_reason(text)
        result.debug_excerpt = text[:500] if text else None
        result.debug_dialog_count = len(dialogs)
        if result.video_urls:
            result.creative_type = "video"
        elif len(result.image_urls) > 1:
            result.creative_type = "carousel"
        elif result.image_urls:
            result.creative_type = "image"
        if not result.thumbnail_url and result.image_urls:
            result.thumbnail_url = result.image_urls[0]
        return result

    @staticmethod
    def _merge_debug_fields(base: ExtractedMedia, incoming: ExtractedMedia) -> ExtractedMedia:
        if not incoming.debug_title:
            incoming.debug_title = base.debug_title
        if not incoming.debug_excerpt:
            incoming.debug_excerpt = base.debug_excerpt
        if not incoming.debug_dialog_count:
            incoming.debug_dialog_count = base.debug_dialog_count
        if not incoming.debug_stage:
            incoming.debug_stage = base.debug_stage
        if not incoming.restriction_reason:
            incoming.restriction_reason = base.restriction_reason
        return incoming

    def _apply_dom_media(self, soup: BeautifulSoup, result: ExtractedMedia) -> ExtractedMedia:
        image_urls = list(result.image_urls)
        video_urls = list(result.video_urls)

        for video_el in soup.find_all(["video", "source"]):
            for candidate in self._candidate_urls_from_attrs(video_el, _VIDEO_ATTRS):
                normalized = self._normalize_video_url(candidate)
                if normalized:
                    video_urls.append(normalized)
            poster = self._normalize_media_url(video_el.get("poster"))
            if poster and not result.thumbnail_url:
                result.thumbnail_url = poster

        for img_el in soup.find_all(["img", "image"]):
            width = None
            height = None
            for attr_name, target in (("width", "width"), ("height", "height")):
                raw = img_el.get(attr_name)
                if raw:
                    try:
                        if target == "width":
                            width = int(raw)
                        else:
                            height = int(raw)
                    except (TypeError, ValueError):
                        pass
            for candidate in self._candidate_urls_from_attrs(img_el, _IMAGE_ATTRS):
                if self._should_keep_image(candidate, width=width, height=height):
                    image_urls.append(candidate)

        for node in soup.find_all(attrs={"style": True}):
            style_url = self._extract_url_from_style(node.get("style"))
            if style_url and self._should_keep_image(style_url):
                image_urls.append(style_url)

        result.image_urls = list(dict.fromkeys(image_urls))
        result.video_urls = list(dict.fromkeys(video_urls))
        if not result.thumbnail_url and result.image_urls:
            result.thumbnail_url = result.image_urls[0]
        return result

    @staticmethod
    def _normalize_video_url(url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("blob:"):
            return None
        if not url.startswith("http"):
            return None
        return url

    async def aggressive_video_recovery(
        self,
        external_id: str | None,
        snapshot_url: str | None,
        access_token: str | None = None,
    ) -> tuple[str | None, str]:
        """D-R2-3: recover video URL with ordered 4-step fallback."""
        methods = [
            ("meta_api", self._extract_video_via_meta_api(external_id, access_token)),
            ("render_ad", self._extract_video_via_render_ad(external_id, access_token)),
            ("og_tag", self._extract_video_via_og_tag(snapshot_url)),
            ("iframe", self._extract_video_via_iframe(snapshot_url)),
        ]
        for method, coro in methods:
            try:
                recovered = await coro
                normalized = self._normalize_video_url(recovered)
                if normalized:
                    logger.info("video_recovered", method=method, external_id=external_id)
                    return normalized, method
            except Exception as e:
                logger.warning("video_recovery_method_failed", method=method, error=str(e), external_id=external_id)
        return None, ""

    @staticmethod
    async def validate_image_url(url: str, timeout: float = 10.0) -> bool:
        """v1.5: HEAD request to verify URL returns actual image content."""
        if not url:
            return False
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as client:
                resp = await client.head(url)
                if resp.status_code >= 400:
                    return False
                ct = (resp.headers.get("content-type") or "").lower()
                return any(t in ct for t in ("image/", "video/"))
        except Exception:
            return False

    @staticmethod
    def build_ads_library_url(external_id: str) -> str:
        """v1.6: Build public Meta Ads Library URL with full params for reliable loading."""
        return (
            f"https://www.facebook.com/ads/library/?id={external_id}"
            f"&active_status=all&ad_type=all&country=ALL&media_type=all"
        )

    async def extract(self, snapshot_url: str, use_playwright: bool = True, external_id: str | None = None) -> ExtractedMedia:
        """Extract media from snapshot URL, trying HTTP first, then Playwright fallback.

        v1.6: Always prefer ads/library URL when external_id is available (render_ad tokens expire).
        """
        # v1.6: Use ads/library URL as primary when external_id is known
        primary_url = snapshot_url
        if external_id and use_playwright:
            primary_url = self.build_ads_library_url(external_id)

        result = await self._extract_via_http(primary_url)

        if result.creative_type == "unknown" and use_playwright:
            # v1.6: Use primary_url (ads/library with full params) for Playwright
            pw_result = await self._extract_via_playwright(primary_url)
            if pw_result.creative_type != "unknown":
                if pw_result.image_urls:
                    is_valid = await self.validate_image_url(pw_result.image_urls[0])
                    if not is_valid:
                        logger.warning("image_url_validation_failed", url=pw_result.image_urls[0])
                        pw_result.image_urls = [u for u in pw_result.image_urls if u != pw_result.image_urls[0]]
                        if not pw_result.image_urls and not pw_result.video_urls:
                            pw_result.creative_type = "unknown"
                if pw_result.creative_type != "unknown":
                    result = pw_result  # v1.6: go through sanitize, don't return early
            if result.creative_type == "unknown":
                result = self._merge_debug_fields(pw_result, result)
                if not result.restriction_reason:
                    result.restriction_reason = pw_result.restriction_reason
                if pw_result.image_urls or pw_result.video_urls:
                    result.image_urls = list(set(result.image_urls + pw_result.image_urls))
                    result.video_urls = list(set(result.video_urls + pw_result.video_urls))
                if pw_result.screenshot_bytes and not result.screenshot_bytes:
                    result.screenshot_bytes = pw_result.screenshot_bytes
                    result.screenshot_content_type = pw_result.screenshot_content_type

        # v1.6: Library fallback now handled by primary_url. Keep for legacy render_ad snapshots.
        if result.creative_type == "unknown" and external_id and "/render_ad/" in (snapshot_url or "") and primary_url == snapshot_url:
            library_url = self.build_ads_library_url(external_id)
            logger.info("trying_ads_library_fallback", external_id=external_id)
            lib_result = await self._extract_via_playwright(library_url)
            if lib_result.creative_type != "unknown":
                lib_result.extraction_method = "playwright_library_fallback"
                result = lib_result  # go through sanitize
            elif lib_result.image_urls or lib_result.video_urls:
                result.image_urls = list(set(result.image_urls + lib_result.image_urls))
                result.video_urls = list(set(result.video_urls + lib_result.video_urls))

        # v1.6: Sanitize — remove garbage URLs before returning
        result.image_urls = [u for u in result.image_urls if self._is_valid_creative_url(u)]
        result.video_urls = [u for u in result.video_urls if u and "facebook.com/ads/" not in u.lower()]
        if result.thumbnail_url and not self._is_valid_creative_url(result.thumbnail_url):
            result.thumbnail_url = result.image_urls[0] if result.image_urls else None

        # v1.6: If ad was not found on Meta Library page, discard all media
        # (they belong to unrelated ads shown on the page)
        if result.restriction_reason in ("ad_not_found", "ad_expired"):
            result.image_urls = []
            result.video_urls = []
            result.thumbnail_url = None
            result.creative_type = "unknown"

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
            if "/ads/archive/render_ad/" in url:
                result = self._parse_render_ad_html(soup)
            elif "facebook.com/ads/library/" not in url:
                result = self._parse_html(soup)
            else:
                result = ExtractedMedia()  # v2.0: Skip BS4 for Meta Library (handled by Playwright)
            result.extraction_method = "http_bs4"
            logger.info("media_http_extracted", url=url, type=result.creative_type,
                        images=len(result.image_urls), videos=len(result.video_urls))

        except Exception as e:
            logger.warning("media_http_extraction_failed", url=url, error=str(e), exc_info=True)

        return result

    async def _extract_video_via_meta_api(
        self,
        external_id: str | None,
        access_token: str | None,
    ) -> str | None:
        if not external_id or not access_token:
            return None
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
        ) as client:
            ad_resp = await client.get(
                f"https://graph.facebook.com/v19.0/{external_id}",
                params={
                    "fields": "creative{video_id,object_story_spec}",
                    "access_token": access_token,
                },
            )
            if ad_resp.status_code != 200:
                return None
            ad_data = ad_resp.json()
            creative = ad_data.get("creative") or {}
            video_id = creative.get("video_id")
            if not video_id:
                story_spec = creative.get("object_story_spec") or {}
                video_data = story_spec.get("video_data") or {}
                video_id = video_data.get("video_id")
            if not video_id:
                return None
            video_resp = await client.get(
                f"https://graph.facebook.com/v19.0/{video_id}",
                params={"fields": "source", "access_token": access_token},
            )
            if video_resp.status_code != 200:
                return None
            return (video_resp.json() or {}).get("source")

    async def _extract_video_via_render_ad(
        self,
        external_id: str | None,
        access_token: str | None,
    ) -> str | None:
        if not external_id:
            return None
        query = {"id": external_id}
        if access_token:
            query["access_token"] = access_token
        url = f"https://www.facebook.com/ads/archive/render_ad/?{urlencode(query)}"
        extracted = await self._extract_via_playwright(url)
        return extracted.video_urls[0] if extracted.video_urls else None

    async def _extract_video_via_og_tag(self, snapshot_url: str | None) -> str | None:
        if not snapshot_url:
            return None
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                )
            },
        ) as client:
            response = await client.get(snapshot_url)
            if response.status_code != 200:
                return None
            soup = BeautifulSoup(response.text, "html.parser")
            og_video = soup.find("meta", property="og:video")
            if og_video and og_video.get("content"):
                return og_video["content"]
            og_video_url = soup.find("meta", property="og:video:url")
            if og_video_url and og_video_url.get("content"):
                return og_video_url["content"]
        return None

    async def _extract_video_via_iframe(self, snapshot_url: str | None) -> str | None:
        if not snapshot_url:
            return None
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None

        async with _playwright_semaphore:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--single-process",
                    ],
                )
                page = None
                context = None
                try:
                    context = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        locale="ja-JP",
                    )
                    page = await context.new_page()
                    await page.goto(snapshot_url, wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
                    await page.wait_for_timeout(3000)

                    for frame in page.frames:
                        video = await frame.query_selector("video source, video")
                        if not video:
                            continue
                        src = await video.get_attribute("src")
                        normalized = self._normalize_video_url(src)
                        if normalized:
                            return normalized
                except Exception as e:
                    logger.warning("iframe_video_extraction_failed", url=snapshot_url, error=str(e))
                finally:
                    if page:
                        await page.close()
                    if context:
                        await context.close()
                    await browser.close()
        return None

    async def _extract_via_playwright(self, url: str) -> ExtractedMedia:
        """Stage 2: Playwright JS-rendered extraction with concurrency limit."""
        result = ExtractedMedia()
        result.debug_stage = "init"

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright_not_installed")
            result.debug_stage = "import_failed"
            result.debug_excerpt = "playwright_not_installed"
            return result

        async with _playwright_semaphore:
            try:
                async with async_playwright() as p:
                    result.debug_stage = "playwright_ready"
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                        ],
                    )
                    result.debug_stage = "browser_launched"
                    page = None
                    context = None
                    try:
                        context = await browser.new_context(
                            viewport={"width": 1920, "height": 1080},
                            user_agent=(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0.0.0 Safari/537.36"
                            ),
                            locale="ja-JP",
                        )
                        result.debug_stage = "context_created"
                        page = await context.new_page()
                        result.debug_stage = "page_created"

                        # ── v1.5: Network intercept for actual media URLs ──
                        intercepted_images: list[str] = []
                        intercepted_videos: list[str] = []
                        # Track content-length to distinguish creative images from UI assets
                        _intercepted_image_sizes: dict[str, int] = {}

                        def _on_response(response):
                            try:
                                resp_url = response.url
                                ct = (response.headers.get("content-type") or "").lower()
                                status = response.status
                                if status < 200 or status >= 400:
                                    return
                                # Skip UI resource images
                                _ui_skip = ("rsrc.php", "emoji", "pixel", "beacon", "1x1",
                                            "favicon", "static.xx", "/static/", "platform-lookaside",
                                            "profile_pic", "safe_image.php")
                                lowered = resp_url.lower()
                                if any(skip in lowered for skip in _ui_skip):
                                    return
                                if any(t in ct for t in ("image/jpeg", "image/png", "image/webp", "image/gif")):
                                    if self._should_keep_image(resp_url):
                                        if resp_url not in intercepted_images:
                                            intercepted_images.append(resp_url)
                                            # Track size for quality filtering
                                            cl = response.headers.get("content-length")
                                            if cl:
                                                try:
                                                    _intercepted_image_sizes[resp_url] = int(cl)
                                                except ValueError:
                                                    pass
                                elif any(t in ct for t in ("video/mp4", "video/webm", "video/quicktime")):
                                    if resp_url not in intercepted_videos:
                                        intercepted_videos.append(resp_url)
                            except Exception:
                                pass

                        page.on("response", _on_response)

                        try:
                            is_meta_library = "facebook.com/ads/library/" in url
                            result.debug_stage = "goto_started"
                            await page.goto(
                                url,
                                wait_until="load" if is_meta_library else "domcontentloaded",
                                timeout=max(int(self.timeout * 1000), 90000 if is_meta_library else int(self.timeout * 1000)),
                            )
                            result.debug_stage = "goto_completed"
                            await page.wait_for_timeout(5000 if is_meta_library else 3000)
                            result.debug_stage = "post_wait_completed"
                            if is_meta_library:
                                # Enhanced scroll: more iterations for lazy-load
                                for _ in range(4):
                                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                    await page.wait_for_timeout(1500)
                                # Scroll back to top to trigger viewport images
                                await page.evaluate("window.scrollTo(0, 0)")
                                await page.wait_for_timeout(1500)
                                result.debug_stage = "scroll_completed"

                            # v1.5: Wait for network to settle (images may still be loading)
                            try:
                                await page.wait_for_load_state("networkidle", timeout=10000)
                            except Exception:
                                pass  # Best-effort; don't fail if network stays busy

                        except Exception:
                            logger.warning("page_load_timeout", url=url)
                            result.debug_stage = "goto_timeout"
                            result.debug_excerpt = "page_load_timeout"

                        target_external_id = None
                        if "facebook.com/ads/library/" in url:
                            target_external_id = self._target_external_id_from_url(url)

                            # v1.5: Check page state for expired/unavailable ads
                            try:
                                page_text = await page.evaluate("() => document.body?.innerText || ''")
                                _expired_markers = (
                                    "この広告はご利用いただけません",
                                    "This ad is not available",
                                    "このページは利用できません",
                                    "This Page isn't available",
                                    "この広告は削除されました",
                                    "This ad has been removed",
                                    "結果がありません",
                                    "No results",
                                )
                                if any(marker in (page_text or "") for marker in _expired_markers):
                                    result.restriction_reason = "ad_expired"
                                    result.extraction_method = "playwright"
                                    result.debug_stage = "ad_expired_detected"
                                    result.debug_excerpt = (page_text or "")[:500]
                                    logger.info("meta_library_ad_expired", url=url, target_external_id=target_external_id)
                                    # Still check intercepted images before returning
                                    if intercepted_images:
                                        quality_intercepted = [
                                            img for img in intercepted_images
                                            if ("fbcdn" in img or "scontent" in img)
                                            and not any(skip in img.lower() for skip in ("emoji", "rsrc.php", "pixel", "favicon"))
                                        ]
                                        if quality_intercepted:
                                            result.image_urls = quality_intercepted
                                            result.thumbnail_url = quality_intercepted[0]
                                            result.creative_type = "image"
                                    return result
                            except Exception:
                                pass

                            try:
                                result.debug_stage = "card_extract_started"
                                debug_base = result
                                cards = await page.evaluate(_META_LIBRARY_CARD_EXTRACT_JS)
                                card_result = self._extract_meta_library_result(
                                    cards if isinstance(cards, list) else [],
                                    target_external_id,
                                )
                                result = self._merge_debug_fields(debug_base, card_result)
                                result.debug_stage = "card_extract_completed"

                                # v1.6: Only use network intercept if target ad was found on page
                                # (otherwise we'd capture images from unrelated ads)
                                if card_result.creative_type == "unknown" and intercepted_images and target_external_id:
                                    # Verify the target ad is actually on this page
                                    page_text_check = await page.evaluate("() => document.body?.innerText || ''")
                                    target_on_page = target_external_id in (page_text_check or "")
                                    if target_on_page:
                                        quality_intercepted = [
                                            img for img in intercepted_images
                                            if ("fbcdn" in img or "scontent" in img)
                                            and not any(skip in img.lower() for skip in ("emoji", "rsrc.php", "pixel", "favicon"))
                                        ]
                                        if quality_intercepted:
                                            result.image_urls = list(dict.fromkeys(result.image_urls + quality_intercepted))
                                            if not result.thumbnail_url:
                                                result.thumbnail_url = quality_intercepted[0]
                                            result.creative_type = "image" if len(result.image_urls) == 1 else "carousel"
                                            result.debug_stage = "network_intercept_fallback"
                                    else:
                                        result.debug_stage = "target_ad_not_on_page"
                                        result.restriction_reason = "ad_not_found"

                                if result.creative_type != "unknown" or result.destination_url:
                                    result.extraction_method = "playwright"
                                    logger.info(
                                        "media_playwright_meta_library_extracted",
                                        url=url,
                                        type=result.creative_type,
                                        images=len(result.image_urls),
                                        videos=len(result.video_urls),
                                    )
                                    return result
                            except Exception as e:
                                logger.warning("meta_library_card_extract_failed", url=url, error=str(e))

                            if target_external_id:
                                try:
                                    result.debug_stage = "detail_open_started"
                                    opened_detail = await self._open_meta_library_detail_dialog(page, target_external_id)
                                    if not opened_detail:
                                        opened_detail = await page.evaluate(_META_LIBRARY_OPEN_DETAIL_JS, target_external_id)
                                    if opened_detail:
                                        await page.wait_for_timeout(2000)
                                        result.debug_stage = "detail_open_completed"
                                        dialog_payloads = await page.evaluate(_META_LIBRARY_DIALOG_EXTRACT_JS)
                                        dialog_result = self._extract_from_dialog_payloads(
                                            dialog_payloads if isinstance(dialog_payloads, list) else [],
                                            target_external_id,
                                        )
                                        dialog_result = self._merge_debug_fields(result, dialog_result)
                                        dialog_result.debug_stage = "dialog_extract_completed"
                                        if (
                                            dialog_result.creative_type != "unknown"
                                            or dialog_result.destination_url
                                            or dialog_result.restriction_reason
                                        ):
                                            dialog_result.extraction_method = "playwright"
                                            logger.info(
                                                "media_playwright_meta_library_dialog_extracted",
                                                url=url,
                                                type=dialog_result.creative_type,
                                                restriction_reason=dialog_result.restriction_reason,
                                                images=len(dialog_result.image_urls),
                                                videos=len(dialog_result.video_urls),
                                            )
                                            return dialog_result
                                except Exception as e:
                                    logger.warning(
                                        "meta_library_open_detail_failed",
                                        url=url,
                                        target_external_id=target_external_id,
                                        error=str(e),
                                    )

                            try:
                                result.debug_stage = "page_state_started"
                                page_state = await page.evaluate(_META_LIBRARY_PAGE_STATE_JS)
                                result.debug_title = str((page_state or {}).get("title") or "")[:200] or None
                                result.debug_excerpt = str((page_state or {}).get("bodyText") or "")[:500] or None
                                result.debug_dialog_count = int((page_state or {}).get("dialogCount") or 0)
                                result.debug_stage = "page_state_completed"
                                state_text = "\n".join(
                                    [
                                        str((page_state or {}).get("title") or ""),
                                        str((page_state or {}).get("bodyText") or ""),
                                        "\n".join((page_state or {}).get("dialogTexts") or []),
                                    ]
                                )
                                restriction_reason = self._detect_restriction_reason(state_text)
                                if restriction_reason:
                                    result.restriction_reason = restriction_reason
                                    result.extraction_method = "playwright"
                                    logger.info(
                                        "media_playwright_meta_library_restricted",
                                        url=url,
                                        restriction_reason=restriction_reason,
                                        dialog_count=(page_state or {}).get("dialogCount"),
                                    )
                                    return result
                            except Exception as e:
                                result.debug_stage = "page_state_failed"
                                logger.warning("meta_library_page_state_failed", url=url, error=str(e))

                        try:
                            result.debug_stage = "content_started"
                            html = await page.content()
                        except Exception:
                            logger.warning("page_content_failed_after_timeout", url=url)
                            result.debug_stage = "content_failed"
                            result.debug_excerpt = "page_content_failed_after_timeout"
                            return result
                        soup = BeautifulSoup(html, "html.parser")
                        page_text = soup.get_text(separator="\n", strip=True)
                        # v1.6: Skip BS4 full-page parse for Meta Library pages
                        # — it picks up 100+ images from unrelated ads on the page
                        if "/ads/archive/render_ad/" in url:
                            parsed_result = self._parse_render_ad_html(soup)
                        elif "facebook.com/ads/library/" not in url:
                            parsed_result = self._parse_html(soup)
                        else:
                            parsed_result = ExtractedMedia()  # empty — rely on card/dialog/intercept only
                        result = self._merge_debug_fields(result, parsed_result)
                        if not result.debug_title:
                            title_text = soup.title.string.strip() if soup.title and soup.title.string else ""
                            result.debug_title = title_text[:200] or None
                        if not result.debug_excerpt and page_text:
                            result.debug_excerpt = page_text[:500]
                        if not result.restriction_reason:
                            result.restriction_reason = self._detect_restriction_reason(page_text)
                        result.extraction_method = "playwright"
                        result.debug_stage = "content_parsed"

                        # ── v1.6: Network intercept merge (only for non-Meta-Library or confirmed target) ──
                        _is_meta_lib = "facebook.com/ads/library/" in url
                        _use_intercept = True
                        if _is_meta_lib and target_external_id:
                            # For Meta Library: only use intercept if target ad is on the page
                            _use_intercept = target_external_id in (page_text or "")

                        if _use_intercept and (intercepted_images or intercepted_videos):
                            _min_creative_size = 5000
                            quality_intercepted = [
                                img for img in intercepted_images
                                if ("fbcdn" in img or "scontent" in img or "cdninstagram" in img)
                                and not any(skip in img.lower() for skip in (
                                    "emoji", "rsrc.php", "pixel", "beacon", "1x1", "favicon",
                                    "static.xx", "platform-lookaside", "profile_pic",
                                    "safe_image.php", "s75x75", "s100x100", "p50x50",
                                ))
                                and _intercepted_image_sizes.get(img, _min_creative_size + 1) >= _min_creative_size
                            ]
                            quality_intercepted.sort(
                                key=lambda u: _intercepted_image_sizes.get(u, 0), reverse=True
                            )
                            # v2.0: Limit to 10 — single ad never has more than ~10 carousel slides
                            quality_intercepted = quality_intercepted[:10]

                            if quality_intercepted:
                                valid_parsed = [u for u in result.image_urls if self._is_valid_creative_url(u) and "fbcdn" in u]
                                result.image_urls = list(dict.fromkeys(quality_intercepted + valid_parsed))
                                if not result.thumbnail_url or not self._is_valid_creative_url(result.thumbnail_url):
                                    result.thumbnail_url = quality_intercepted[0]

                            if intercepted_videos:
                                existing_v = set(result.video_urls)
                                for vid_url in intercepted_videos:
                                    if vid_url not in existing_v:
                                        result.video_urls.append(vid_url)
                                        existing_v.add(vid_url)

                            if result.video_urls:
                                result.creative_type = "video"
                            elif len(result.image_urls) > 1:
                                result.creative_type = "carousel"
                            elif result.image_urls:
                                result.creative_type = "image"
                            if not result.thumbnail_url and result.image_urls:
                                result.thumbnail_url = result.image_urls[0]
                            logger.info(
                                "media_network_intercept_primary",
                                url=url,
                                intercepted_images=len(quality_intercepted),
                                intercepted_videos=len(intercepted_videos),
                                total_images=len(result.image_urls),
                            )
                            result.debug_stage = "network_intercept_primary"

                        if (
                            not result.image_urls
                            and not result.video_urls
                            and not result.screenshot_bytes
                        ):
                            # v1.5: Enhanced screenshot — try element-specific capture first
                            try:
                                # Try to find the main creative container
                                creative_el = await page.query_selector(
                                    'img[src*="fbcdn"], img[src*="scontent"], '
                                    'video, [data-testid="ad_creative"], '
                                    '[class*="creative"], [class*="media"]'
                                )
                                if creative_el:
                                    result.screenshot_bytes = await creative_el.screenshot(
                                        type="jpeg", quality=85
                                    )
                                else:
                                    result.screenshot_bytes = await page.screenshot(
                                        type="jpeg", quality=75, full_page=False,
                                    )
                                result.screenshot_content_type = "image/jpeg"
                                if result.screenshot_bytes:
                                    result.debug_stage = "screenshot_captured"
                            except Exception as e:
                                # Fallback to full page screenshot
                                try:
                                    result.screenshot_bytes = await page.screenshot(
                                        type="jpeg", quality=75, full_page=False,
                                    )
                                    result.screenshot_content_type = "image/jpeg"
                                    if result.screenshot_bytes:
                                        result.debug_stage = "screenshot_captured"
                                except Exception as e2:
                                    logger.warning("media_playwright_screenshot_failed", url=url, error=str(e2))
                    finally:
                        if page:
                            await page.close()
                        if context:
                            await context.close()
                        await browser.close()

                logger.info("media_playwright_extracted", url=url, type=result.creative_type,
                            images=len(result.image_urls), videos=len(result.video_urls))

            except Exception as e:
                result.debug_stage = result.debug_stage or "outer_exception"
                result.debug_excerpt = str(e)[:500]
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

        result.image_urls = list(dict.fromkeys(image_urls))
        result.video_urls = list(dict.fromkeys(video_urls))
        result = self._apply_dom_media(soup, result)

        # Determine type
        if result.video_urls:
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

        if self._is_placeholder_text(result.ad_text):
            result.ad_text = None
        if self._is_placeholder_text(result.ad_title):
            result.ad_title = None

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
                    if self._is_placeholder_text(result.ad_text):
                        result.ad_text = None
                result.restriction_reason = self._detect_restriction_reason(visible_text)

        result.destination_url, result.destination_domain = self._extract_destination_url(soup)

        return result

    def _parse_render_ad_html(self, soup: BeautifulSoup) -> ExtractedMedia:
        """Parse Facebook render_ad page (server-rendered, specific structure)."""
        result = ExtractedMedia()
        result = self._apply_dom_media(soup, result)

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

        if self._is_placeholder_text(result.ad_text):
            result.ad_text = None
        if self._is_placeholder_text(result.ad_title):
            result.ad_title = None

        body = soup.find("body")
        if body:
            result.restriction_reason = self._detect_restriction_reason(body.get_text(separator="\n", strip=True))

        result.destination_url, result.destination_domain = self._extract_destination_url(soup)

        return result
