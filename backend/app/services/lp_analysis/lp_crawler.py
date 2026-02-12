"""LP Crawler - fetch, render, parse landing pages."""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class CrawledLP:
    """Raw crawled landing page data."""

    url: str
    final_url: str
    domain: str
    status_code: int
    html_content: str
    title: str = ""
    meta_description: str = ""
    og_image: str = ""
    headers: dict = field(default_factory=dict)
    redirect_chain: list[str] = field(default_factory=list)

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()


@dataclass
class ExtractedSection:
    """A section extracted from LP HTML."""

    order: int
    section_type: str
    heading: str = ""
    body_text: str = ""
    has_image: bool = False
    has_video: bool = False
    has_cta: bool = False
    cta_text: str = ""
    raw_html: str = ""


class LPCrawler:
    """Crawl and parse landing pages for analysis."""

    # CTA patterns for Japanese LPs
    CTA_PATTERNS_JA = [
        r"今すぐ[購入申込注文]",
        r"お?申[し]?込み",
        r"購入する",
        r"注文する",
        r"カートに入れ",
        r"無料で[始試]",
        r"詳[細し]く[見は]",
        r"資料請求",
        r"お問[い]?合[わせ]",
        r"LINE[でに]登録",
        r"ダウンロード",
        r"初回[限定特別]",
        r"定期[購入コース]",
        r"特別価格",
        r"送料無料",
        r"お試し",
    ]

    # Section type heuristics
    SECTION_KEYWORDS = {
        "hero": ["メイン", "ファーストビュー"],
        "problem": ["こんな悩み", "こんなお悩み", "お困り", "このような", "悩んで", "つらい"],
        "solution": ["解決", "だから", "そこで", "そんな方に", "おすすめ"],
        "features": ["特徴", "ポイント", "こだわり", "成分", "配合"],
        "benefits": ["効果", "メリット", "実感", "変化", "違い"],
        "authority": ["医師", "専門家", "監修", "特許", "認証", "受賞", "雑誌掲載", "メディア"],
        "testimonials": ["口コミ", "レビュー", "お客様の声", "体験談", "感想", "喜びの声"],
        "comparison": ["比較", "違い", "他社", "従来品", "vs"],
        "pricing": ["価格", "料金", "コース", "プラン", "定期", "初回", "特別", "円"],
        "guarantee": ["返金保証", "安心", "返品", "サポート"],
        "faq": ["よくある質問", "FAQ", "Q&A", "ご質問"],
        "cta": ["お申込み", "購入", "注文", "カート"],
    }

    # Testimonial patterns
    TESTIMONIAL_PATTERNS = [
        r"(\d{2})歳\s*[・/]\s*(女性|男性|主婦|会社員)",
        r"(女性|男性)\s*\d{2}歳",
        r"[A-Z]\.[A-Z]様",
        r"※個人の感想",
        r"★{3,5}",
    ]

    # Price patterns
    PRICE_PATTERNS = [
        r"[￥¥]\s*[\d,]+",
        r"(\d[\d,]*)\s*円",
        r"税込[み]?\s*(\d[\d,]*)",
        r"初回\s*[￥¥]?\s*([\d,]+)",
        r"(\d+)%\s*OFF",
        r"送料無料",
    ]

    def __init__(self, timeout: float = 30.0, max_redirects: int = 10):
        self.timeout = timeout
        self.max_redirects = max_redirects
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                max_redirects=self.max_redirects,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def crawl_lp(self, url: str) -> Optional[CrawledLP]:
        """Crawl a landing page URL and return structured data."""
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            parsed = urlparse(str(response.url))
            html = response.text

            # Extract meta tags
            title = self._extract_meta(html, "title")
            description = self._extract_meta(html, "description")
            og_image = self._extract_og_image(html)

            crawled = CrawledLP(
                url=url,
                final_url=str(response.url),
                domain=parsed.netloc,
                status_code=response.status_code,
                html_content=html,
                title=title,
                meta_description=description,
                og_image=og_image,
                headers=dict(response.headers),
                redirect_chain=[str(r.url) for r in response.history],
            )

            logger.info(
                "lp_crawled",
                url=url,
                final_url=crawled.final_url,
                title=crawled.title[:80] if crawled.title else "",
                html_size=len(html),
            )
            return crawled

        except Exception as e:
            logger.error("lp_crawl_failed", url=url, error=str(e))
            return None

    def extract_text_content(self, html: str) -> str:
        """Extract visible text from HTML (simple regex-based)."""
        # Remove script and style
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "\n", text)
        # Clean whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def extract_sections(self, html: str) -> list[ExtractedSection]:
        """Parse LP into logical sections."""
        sections: list[ExtractedSection] = []

        # Split by common section markers
        # Look for <section>, <div class="section">, or heading tags
        section_splits = re.split(
            r"(<(?:section|article|div\s+class=[\"'][^\"']*(?:section|block|area|wrap|container)[^\"']*[\"'])[^>]*>)",
            html,
            flags=re.IGNORECASE,
        )

        # Also try splitting by h1/h2 if not enough sections
        if len(section_splits) < 5:
            section_splits = re.split(r"(<h[12][^>]*>)", html, flags=re.IGNORECASE)

        order = 0
        for chunk in section_splits:
            if not chunk or chunk.startswith("<"):
                continue

            text = self.extract_text_content(chunk)
            if len(text.strip()) < 20:
                continue

            heading = self._extract_heading(chunk)
            section_type = self._classify_section(text, heading, order == 0)
            has_image = bool(re.search(r"<img\s", chunk, re.IGNORECASE))
            has_video = bool(re.search(r"<(?:video|iframe)", chunk, re.IGNORECASE))
            cta_text = self._extract_cta(chunk)

            sections.append(ExtractedSection(
                order=order,
                section_type=section_type,
                heading=heading,
                body_text=text[:3000],
                has_image=has_image,
                has_video=has_video,
                has_cta=bool(cta_text),
                cta_text=cta_text,
                raw_html=chunk[:5000],
            ))
            order += 1

        # If no sections found, treat entire page as one
        if not sections:
            text = self.extract_text_content(html)
            sections.append(ExtractedSection(
                order=0,
                section_type="hero",
                heading=self._extract_heading(html),
                body_text=text[:5000],
                has_image=bool(re.search(r"<img\s", html, re.IGNORECASE)),
                has_cta=True,
            ))

        return sections

    def extract_prices(self, html: str) -> list[dict]:
        """Extract pricing information from LP."""
        text = self.extract_text_content(html)
        prices = []

        for pattern in self.PRICE_PATTERNS:
            for match in re.finditer(pattern, text):
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end].strip()
                prices.append({
                    "matched_text": match.group(0),
                    "context": context,
                })

        return prices

    def extract_testimonials(self, html: str) -> list[dict]:
        """Extract testimonials/reviews from LP."""
        text = self.extract_text_content(html)
        testimonials = []

        for pattern in self.TESTIMONIAL_PATTERNS:
            for match in re.finditer(pattern, text):
                context_start = max(0, match.start() - 200)
                context_end = min(len(text), match.end() + 200)
                context = text[context_start:context_end].strip()
                testimonials.append({
                    "matched_pattern": match.group(0),
                    "context": context,
                })

        return testimonials

    def count_ctas(self, html: str) -> int:
        """Count CTA elements on the page."""
        count = 0
        text = self.extract_text_content(html)
        for pattern in self.CTA_PATTERNS_JA:
            count += len(re.findall(pattern, text))

        # Also count button-like elements
        count += len(re.findall(
            r"<(?:button|a\s[^>]*class=[\"'][^\"']*(?:btn|button|cta)[^\"']*[\"'])",
            html, re.IGNORECASE,
        ))
        return count

    def extract_page_metrics(self, html: str) -> dict:
        """Extract quantitative metrics from LP."""
        text = self.extract_text_content(html)
        return {
            "word_count": len(text),
            "image_count": len(re.findall(r"<img\s", html, re.IGNORECASE)),
            "video_embed_count": len(re.findall(r"<(?:video|iframe[^>]*(?:youtube|vimeo))", html, re.IGNORECASE)),
            "form_count": len(re.findall(r"<form\s", html, re.IGNORECASE)),
            "cta_count": self.count_ctas(html),
            "testimonial_count": len(self.extract_testimonials(html)),
            "link_count": len(re.findall(r"<a\s", html, re.IGNORECASE)),
            "heading_count": len(re.findall(r"<h[1-6]", html, re.IGNORECASE)),
            "estimated_read_time_seconds": max(60, len(text) // 5),  # ~5 chars/sec for Japanese
        }

    def _extract_meta(self, html: str, name: str) -> str:
        if name == "title":
            match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            return match.group(1).strip() if match else ""

        match = re.search(
            rf'<meta\s+(?:name|property)=["\'](?:og:)?{name}["\']\s+content=["\'](.*?)["\']',
            html, re.IGNORECASE,
        )
        if not match:
            match = re.search(
                rf'<meta\s+content=["\'](.*?)["\']\s+(?:name|property)=["\'](?:og:)?{name}["\']',
                html, re.IGNORECASE,
            )
        return match.group(1).strip() if match else ""

    def _extract_og_image(self, html: str) -> str:
        match = re.search(
            r'<meta\s+(?:property=["\']og:image["\']\s+content=["\'](.*?)["\']|content=["\'](.*?)["\']\s+property=["\']og:image["\'])',
            html, re.IGNORECASE,
        )
        if match:
            return (match.group(1) or match.group(2)).strip()
        return ""

    def _extract_heading(self, html: str) -> str:
        for level in range(1, 4):
            match = re.search(rf"<h{level}[^>]*>(.*?)</h{level}>", html, re.IGNORECASE | re.DOTALL)
            if match:
                text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                if len(text) > 3:
                    return text[:200]
        return ""

    def _extract_cta(self, html: str) -> str:
        text = self.extract_text_content(html)
        for pattern in self.CTA_PATTERNS_JA:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return ""

    def _classify_section(self, text: str, heading: str, is_first: bool) -> str:
        if is_first:
            return "hero"

        combined = (heading + " " + text[:500]).lower()
        best_type = "content"
        best_score = 0

        for section_type, keywords in self.SECTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_type = section_type

        return best_type
