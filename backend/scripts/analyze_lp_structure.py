"""LP (Landing Page) structure analyzer.

Parses saved HTML from media_cache/lp_html/ to detect:
  - Form fields (name, email, phone, etc.) -> lead gen vs EC
  - CTA buttons and their text
  - Testimonial sections
  - Before/After images
  - Price display and discount indicators
  - FAQ sections
  - Timer/countdown elements
  - Social proof (review counts, star ratings)
  - Video embeds
  - Classify LP type: lead_gen, ec_purchase, line_add, app_install, info_page
  - Store in ad_metadata["lp_analysis"]

Run from the backend directory:
    cd backend
    python scripts/analyze_lp_structure.py
"""

import os
import sys
import re
import logging
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
BATCH_SIZE = 20

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
LP_HTML_DIR = os.path.join(CACHE_DIR, "lp_html")


def _count_pattern(html: str, pattern: str, flags: int = re.IGNORECASE) -> int:
    """Count occurrences of a regex pattern in HTML."""
    return len(re.findall(pattern, html, flags))


def detect_form_fields(html: str) -> dict:
    """Detect form fields and classify form type."""
    forms = re.findall(r"<form[^>]*>(.*?)</form>", html, re.IGNORECASE | re.DOTALL)
    if not forms:
        return {"has_form": False, "form_count": 0, "fields": [], "form_type": None}

    all_fields = []
    for form in forms:
        # Input fields
        inputs = re.findall(
            r'<input[^>]*(?:name|type|placeholder)=["\']([^"\']+)["\'][^>]*',
            form, re.IGNORECASE,
        )
        # Textarea
        textareas = re.findall(r"<textarea", form, re.IGNORECASE)
        # Select
        selects = re.findall(r"<select", form, re.IGNORECASE)

        all_fields.extend(inputs)

    # Classify form type based on fields
    fields_lower = " ".join(all_fields).lower()
    form_type = "unknown"

    # Lead gen indicators
    lead_gen_keywords = ["email", "phone", "tel", "name", "company", "inquiry"]
    lead_gen_score = sum(1 for k in lead_gen_keywords if k in fields_lower)

    # EC purchase indicators
    ec_keywords = ["card", "credit", "payment", "shipping", "address", "zip", "postal"]
    ec_score = sum(1 for k in ec_keywords if k in fields_lower)

    # Search/filter form
    search_keywords = ["search", "filter", "keyword", "query"]
    search_score = sum(1 for k in search_keywords if k in fields_lower)

    if ec_score >= 2:
        form_type = "purchase"
    elif lead_gen_score >= 2:
        form_type = "lead_gen"
    elif search_score >= 1:
        form_type = "search"
    elif len(all_fields) <= 2:
        form_type = "simple_signup"

    return {
        "has_form": True,
        "form_count": len(forms),
        "fields": all_fields[:20],
        "form_type": form_type,
    }


def detect_cta_buttons(html: str) -> list[str]:
    """Extract CTA button text."""
    cta_texts = []

    # Buttons and links with CTA-like classes
    patterns = [
        r'<(?:a|button)[^>]*class=["\'][^"\']*(?:cta|btn|button|submit|action)[^"\']*["\'][^>]*>(.*?)</(?:a|button)>',
        r'<input[^>]*type=["\']submit["\'][^>]*value=["\']([^"\']+)["\']',
        r'<button[^>]*>(.*?)</button>',
    ]

    for pat in patterns:
        matches = re.findall(pat, html, re.IGNORECASE | re.DOTALL)
        for m in matches:
            text = re.sub(r"<[^>]+>", "", m).strip()
            # Filter out empty or very long text
            if text and 2 <= len(text) <= 50:
                cta_texts.append(text)

    # Deduplicate while preserving order
    seen = set()
    unique_ctas = []
    for text in cta_texts:
        if text not in seen:
            seen.add(text)
            unique_ctas.append(text)

    return unique_ctas[:15]


def detect_testimonials(html: str) -> dict:
    """Detect testimonial/review sections."""
    html_lower = html.lower()

    patterns = [
        r"\u304a\u5ba2\u69d8\u306e\u58f0",           # "customer voice"
        r"\u53e3\u30b3\u30df",                         # "kuchikomi/reviews"
        r"\u4f53\u9a13\u8ac7",                         # "experience stories"
        r"\u611f\u60f3",                               # "impressions"
        r"\u30ec\u30d3\u30e5\u30fc",                   # "review" (katakana)
        r"testimonial",
        r"review",
        r"customer.?voice",
        r"user.?review",
    ]

    found_patterns = []
    for pat in patterns:
        if re.search(pat, html, re.IGNORECASE):
            found_patterns.append(pat)

    # Count star rating elements
    star_patterns = [
        r"\u2605",                                      # black star
        r"\u2606",                                      # white star
        r"star.?rating",
        r"rating",
        r'class=["\'][^"\']*star[^"\']*["\']',
    ]
    star_count = sum(1 for pat in star_patterns if re.search(pat, html, re.IGNORECASE))

    return {
        "has_testimonials": len(found_patterns) > 0,
        "testimonial_patterns": found_patterns[:5],
        "has_star_ratings": star_count > 0,
    }


def detect_before_after(html: str) -> bool:
    """Detect before/after comparison sections."""
    patterns = [
        r"before.?after",
        r"\u30d3\u30d5\u30a9\u30fc\u30a2\u30d5\u30bf\u30fc",  # "before-after" katakana
        r"\u4f7f\u7528\u524d.{0,5}\u4f7f\u7528\u5f8c",         # "before use...after use"
        r"\u5909\u5316",                                         # "change"
        r'class=["\'][^"\']*(?:before|after)[^"\']*["\']',
    ]
    return any(re.search(pat, html, re.IGNORECASE) for pat in patterns)


def detect_price_info(html: str) -> dict:
    """Detect price display and discount indicators."""
    # Price patterns
    yen_prices = re.findall(r"[\u00a5]?([\d,]+)\u5186", html)
    dollar_prices = re.findall(r"\$([\d,]+\.?\d*)", html)

    # Discount indicators
    discount_patterns = [
        r"\u5272\u5f15",           # "discount"
        r"\u30aa\u30d5",           # "off"
        r"\u7279\u4fa1",           # "special price"
        r"\u30bb\u30fc\u30eb",     # "sale"
        r"\u9650\u5b9a\u4fa1\u683c",  # "limited price"
        r"\u521d\u56de\u9650\u5b9a",  # "first time limited"
        r"\u901a\u5e38\u4fa1\u683c",  # "regular price"
        r"\d+%\s*(?:OFF|off|\u30aa\u30d5)",
        r"sale",
        r"discount",
        r"coupon",
    ]
    has_discount = any(re.search(pat, html, re.IGNORECASE) for pat in discount_patterns)

    # Free trial / free shipping
    free_patterns = [
        r"\u7121\u6599",           # "free"
        r"\u9001\u6599\u7121\u6599",  # "free shipping"
        r"\u304a\u8a66\u3057",     # "trial"
        r"free.?(?:trial|shipping|delivery)",
    ]
    has_free_offer = any(re.search(pat, html, re.IGNORECASE) for pat in free_patterns)

    return {
        "has_price": len(yen_prices) > 0 or len(dollar_prices) > 0,
        "price_count": len(yen_prices) + len(dollar_prices),
        "has_discount": has_discount,
        "has_free_offer": has_free_offer,
    }


def detect_faq(html: str) -> bool:
    """Detect FAQ sections."""
    patterns = [
        r"faq",
        r"frequently.?asked",
        r"\u3088\u304f\u3042\u308b\u8cea\u554f",  # "frequently asked questions" JP
        r"\u8cea\u554f",                             # "question" JP
        r"Q\s*[&.]\s*A",
        r"Q\.\s*\d+",
        r'class=["\'][^"\']*faq[^"\']*["\']',
    ]
    return any(re.search(pat, html, re.IGNORECASE) for pat in patterns)


def detect_countdown(html: str) -> bool:
    """Detect countdown/timer elements."""
    patterns = [
        r"countdown",
        r"timer",
        r"\u6b8b\u308a",              # "remaining"
        r"\u9650\u5b9a",              # "limited"
        r"\u7d42\u4e86\u307e\u3067",  # "until end"
        r"\u671f\u9593\u9650\u5b9a",  # "limited time"
        r"limited.?time",
        r"expires?\s*(?:in|at)",
        r'class=["\'][^"\']*(?:countdown|timer)[^"\']*["\']',
        r"setInterval|setTimeout.*(?:countdown|timer)",
    ]
    return any(re.search(pat, html, re.IGNORECASE) for pat in patterns)


def detect_social_proof(html: str) -> dict:
    """Detect social proof elements."""
    patterns = {
        "review_count": [r"([\d,]+)\s*\u4ef6?\s*(?:\u30ec\u30d3\u30e5\u30fc|\u53e3\u30b3\u30df|review)", r"([\d,]+)\s*reviews?"],
        "sales_count": [r"([\d,]+)\s*\u4ef6?\s*(?:\u8ca9\u58f2|\u500b?\u58f2\u308c|sold)", r"([\d,]+)\s*(?:sold|sales)"],
        "user_count": [r"([\d,]+)\s*\u4eba?\s*(?:\u304c\u4f7f\u7528|\u304c\u611b\u7528|users?)", r"([\d,]+)\s*users?"],
        "satisfaction": [r"(\d+(?:\.\d+)?)\s*%\s*(?:\u6e80\u8db3|satisfaction)", r"satisfaction.{0,20}(\d+(?:\.\d+)?)\s*%"],
    }

    result: dict = {"has_social_proof": False}
    for key, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                result[key] = m.group(1)
                result["has_social_proof"] = True
                break

    # Media mentions
    media_patterns = [
        r"\u30e1\u30c7\u30a3\u30a2\u63b2\u8f09",  # "media coverage"
        r"as seen (?:on|in)",
        r"\u96d1\u8a8c\u63b2\u8f09",                # "magazine coverage"
        r"featured (?:on|in)",
    ]
    result["has_media_mentions"] = any(re.search(pat, html, re.IGNORECASE) for pat in media_patterns)

    return result


def detect_video_embeds(html: str) -> dict:
    """Detect video embeds in the page."""
    video_tag = bool(re.search(r"<video[\s>]", html, re.IGNORECASE))
    youtube = bool(re.search(r"youtube\.com/embed|youtu\.be", html, re.IGNORECASE))
    vimeo = bool(re.search(r"vimeo\.com", html, re.IGNORECASE))
    wistia = bool(re.search(r"wistia", html, re.IGNORECASE))

    return {
        "has_video": video_tag or youtube or vimeo or wistia,
        "video_types": [
            t for t, v in [
                ("html5_video", video_tag),
                ("youtube", youtube),
                ("vimeo", vimeo),
                ("wistia", wistia),
            ] if v
        ],
    }


def classify_lp_type(analysis: dict) -> str:
    """Classify LP type based on analysis results.

    Returns one of: lead_gen, ec_purchase, line_add, app_install, info_page
    """
    dest_type = analysis.get("destination_type", "")

    # Direct classification from URL
    if dest_type == "LINE_add":
        return "line_add"
    if dest_type == "app_download":
        return "app_install"
    if dest_type == "EC_site":
        return "ec_purchase"

    # Form-based classification
    form_info = analysis.get("form_info", {})
    form_type = form_info.get("form_type")
    if form_type == "purchase":
        return "ec_purchase"
    if form_type in ("lead_gen", "simple_signup"):
        return "lead_gen"

    # Price + form = likely EC
    price_info = analysis.get("price_info", {})
    if price_info.get("has_price") and form_info.get("has_form"):
        return "ec_purchase"

    # Lead gen indicators
    if form_info.get("has_form"):
        return "lead_gen"

    return "info_page"


def analyze_single_lp(ad: Ad) -> dict | None:
    """Analyze a single LP from saved HTML."""
    html_path = os.path.join(LP_HTML_DIR, f"{ad.id}.html")
    if not os.path.exists(html_path):
        return None

    try:
        with open(html_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    except Exception as e:
        logger.debug("Failed to read HTML for ad %d: %s", ad.id, e)
        return None

    if not html or len(html) < 100:
        return None

    # Get destination type from existing lp_data or ad_metadata
    meta = ad.ad_metadata or {}
    lp_data = meta.get("lp_data", {})
    dest_type = lp_data.get("destination_type") or meta.get("destination_type", "official_site")

    # Run all detectors
    form_info = detect_form_fields(html)
    cta_buttons = detect_cta_buttons(html)
    testimonials = detect_testimonials(html)
    has_before_after = detect_before_after(html)
    price_info = detect_price_info(html)
    has_faq = detect_faq(html)
    has_countdown = detect_countdown(html)
    social_proof = detect_social_proof(html)
    video_info = detect_video_embeds(html)

    # Build analysis result
    analysis = {
        "destination_type": dest_type,
        "form_info": form_info,
        "cta_buttons": cta_buttons,
        "testimonials": testimonials,
        "has_before_after": has_before_after,
        "price_info": price_info,
        "has_faq": has_faq,
        "has_countdown": has_countdown,
        "social_proof": social_proof,
        "video_info": video_info,
        "page_length_chars": len(html),
    }

    # Classify LP type
    analysis["lp_type"] = classify_lp_type(analysis)

    # Compute LP quality score (0-100)
    score = 0
    if form_info.get("has_form"):
        score += 15
    if len(cta_buttons) >= 1:
        score += 10
    if len(cta_buttons) >= 3:
        score += 5
    if testimonials.get("has_testimonials"):
        score += 15
    if testimonials.get("has_star_ratings"):
        score += 5
    if has_before_after:
        score += 10
    if price_info.get("has_price"):
        score += 10
    if price_info.get("has_discount"):
        score += 5
    if price_info.get("has_free_offer"):
        score += 5
    if has_faq:
        score += 10
    if social_proof.get("has_social_proof"):
        score += 10
    if video_info.get("has_video"):
        score += 5
    if has_countdown:
        score += 5

    analysis["lp_quality_score"] = min(score, 100)

    return analysis


def main():
    print("=" * 60)
    print("  LP Structure Analyzer")
    print("=" * 60)

    if not os.path.isdir(LP_HTML_DIR):
        print(f"LP HTML directory not found: {LP_HTML_DIR}")
        print("Run crawl_landing_pages.py first.")
        return

    html_files = [f for f in os.listdir(LP_HTML_DIR) if f.endswith(".html")]
    print(f"HTML files available: {len(html_files)}")

    if not html_files:
        print("No HTML files to analyze. Run crawl_landing_pages.py first.")
        return

    session = SyncSessionLocal()
    try:
        # Get ads that have saved HTML
        ad_ids = []
        for f in html_files:
            try:
                ad_id = int(f.replace(".html", ""))
                ad_ids.append(ad_id)
            except ValueError:
                continue

        ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).order_by(Ad.id).all()
        print(f"Ads to analyze: {len(ads)}")

        analyzed = 0
        skipped = 0
        type_counts: dict[str, int] = defaultdict(int)
        avg_score = 0.0

        for i, ad in enumerate(ads):
            # Skip if already analyzed (unless FORCE_REANALYZE)
            meta = ad.ad_metadata or {}
            if meta.get("lp_analysis") and not os.environ.get("FORCE_REANALYZE"):
                skipped += 1
                continue

            analysis = analyze_single_lp(ad)
            if not analysis:
                skipped += 1
                continue

            # Store in ad_metadata
            meta = dict(ad.ad_metadata or {})
            meta["lp_analysis"] = analysis
            meta["destination_type"] = analysis.get("destination_type", "official_site")
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            lp_type = analysis.get("lp_type", "info_page")
            type_counts[lp_type] += 1
            avg_score += analysis.get("lp_quality_score", 0)
            analyzed += 1

            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"  Committed batch ({i + 1}/{len(ads)})...")

        session.commit()

        # ── Summary ──
        print(f"\n{'=' * 60}")
        print(f"  LP ANALYSIS RESULTS")
        print(f"{'=' * 60}")
        print(f"  Total HTML files:     {len(html_files)}")
        print(f"  Ads analyzed:         {analyzed}")
        print(f"  Skipped:              {skipped}")
        print()
        print(f"  LP Type Distribution:")
        for lp_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {lp_type}: {count}")
        print()
        if analyzed > 0:
            print(f"  Average LP quality score: {avg_score / analyzed:.1f}/100")
        print(f"{'=' * 60}")

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        logger.exception("analyze_lp_structure failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
