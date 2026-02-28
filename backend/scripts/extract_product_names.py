#!/usr/bin/env python3
"""Extract product/brand names from ad titles and metadata.

Detects product and brand names using common Japanese ad title patterns
such as brackets, separators, and katakana sequences.  Stores the result
in ad_metadata["product_name"] and cross-references with advertiser_name.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/extract_product_names.py
"""

import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Patterns for product name extraction ──────────────────────────────────

# Bracket-enclosed brand: 【ブランド名】, [ブランド名], 「ブランド名」
RE_BRACKET_BRAND = re.compile(
    r"[\u3010\[]\s*(.+?)\s*[\u3011\]]"  # 【...】 or [...]
    r"|"
    r"[\u300c]\s*(.+?)\s*[\u300d]"       # 「...」
)

# Brand before separator: "ブランド名 - description", "ブランド名｜description"
# Japanese full-width pipe ｜, half-width |, em dash, hyphen with spaces
RE_SEPARATOR_BRAND = re.compile(
    r"^(.+?)\s*[|\uff5c\u2014\u2015\u2500\u2501\uff0d]\s*.+"
)

# Brand at start before space: two or more katakana words at the beginning
RE_KATAKANA_BRAND = re.compile(
    r"^([\u30a0-\u30ff\u30fc]+(?:\s+[\u30a0-\u30ff\u30fc]+)?)\s"
)

# English brand at start (2+ uppercase or CamelCase words)
RE_ENGLISH_BRAND = re.compile(
    r"^([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*)\s"
)

# Known drug/product names in Japanese medical/beauty ads
KNOWN_PRODUCTS = [
    # GLP-1 drugs
    "\u30de\u30f3\u30b8\u30e3\u30ed",    # マンジャロ
    "\u30a6\u30b4\u30fc\u30d3",          # ウゴービ
    "\u30aa\u30bc\u30f3\u30d4\u30c3\u30af",  # オゼンピック
    "\u30b5\u30af\u30bb\u30f3\u30c0",    # サクセンダ
    "\u30ea\u30d9\u30eb\u30b5\u30b9",    # リベルサス
    # AGA
    "\u30df\u30ce\u30ad\u30b7\u30b8\u30eb",  # ミノキシジル
    "\u30d5\u30a3\u30ca\u30b9\u30c6\u30ea\u30c9",  # フィナステリド
    "\u30c7\u30e5\u30bf\u30b9\u30c6\u30ea\u30c9",  # デュタステリド
    # Brands
    "RIZAP",
    "auravita",
]


def _clean_product_name(name: str) -> str | None:
    """Clean and validate an extracted product name."""
    if not name:
        return None

    name = name.strip()

    # Too short or too long
    if len(name) < 2 or len(name) > 60:
        return None

    # Skip pure numbers or generic words
    if name.isdigit():
        return None

    # Skip very generic Japanese words
    generic = {
        "\u516c\u5f0f",          # 公式
        "\u516c\u5f0f\u30b5\u30a4\u30c8",  # 公式サイト
        "\u8a73\u7d30",          # 詳細
        "\u7121\u6599",          # 無料
        "\u9650\u5b9a",          # 限定
        "\u7279\u5225",          # 特別
        "\u4eca\u3060\u3051",    # 今だけ
        "\u65b0\u767b\u5834",    # 新登場
        "\u304a\u5f97",          # お得
        "\u30ad\u30e3\u30f3\u30da\u30fc\u30f3",  # キャンペーン
        "\u521d\u56de",          # 初回
        "PR",
        "AD",
        "PR\u5e83\u544a",       # PR広告
    }
    if name in generic:
        return None

    return name


def extract_product_name(ad: Ad) -> str | None:
    """Extract product/brand name from ad title and metadata.

    Tries multiple extraction strategies in priority order:
    1. Known product names in text
    2. Bracket-enclosed names
    3. Separator-based names
    4. Katakana brand at start
    5. English brand at start
    6. Fallback to advertiser_name
    """
    title = ad.title or ""
    meta = ad.ad_metadata or {}
    body = meta.get("body", "") or ""
    link_title = meta.get("link_title", "") or ""
    full_text = " ".join(filter(None, [title, body, link_title]))

    # Strategy 1: Known product names
    for product in KNOWN_PRODUCTS:
        if product.lower() in full_text.lower():
            return product

    # Strategy 2: Bracket-enclosed names from title
    m = RE_BRACKET_BRAND.search(title)
    if m:
        name = m.group(1) or m.group(2)
        cleaned = _clean_product_name(name)
        if cleaned:
            return cleaned

    # Strategy 3: Separator-based (title before | or -)
    m = RE_SEPARATOR_BRAND.match(title)
    if m:
        cleaned = _clean_product_name(m.group(1))
        if cleaned:
            return cleaned

    # Strategy 4: Katakana brand at start of title
    m = RE_KATAKANA_BRAND.match(title)
    if m:
        cleaned = _clean_product_name(m.group(1))
        if cleaned and len(cleaned) >= 3:
            return cleaned

    # Strategy 5: English brand at start
    m = RE_ENGLISH_BRAND.match(title)
    if m:
        cleaned = _clean_product_name(m.group(1))
        if cleaned and len(cleaned) >= 3:
            return cleaned

    # Strategy 6: page_name from metadata (often the brand)
    page_name = meta.get("page_name", "")
    if page_name and page_name != ad.advertiser_name:
        cleaned = _clean_product_name(page_name)
        if cleaned:
            return cleaned

    # Strategy 7: advertiser_name as fallback
    if ad.advertiser_name:
        cleaned = _clean_product_name(ad.advertiser_name)
        if cleaned:
            return cleaned

    return None


def _validate_with_advertiser(product_name: str | None, advertiser_name: str | None) -> dict:
    """Cross-reference product name with advertiser name."""
    result = {
        "product_name": product_name,
        "advertiser_match": False,
        "confidence": "low",
    }

    if not product_name:
        return result

    if advertiser_name:
        adv_lower = advertiser_name.lower()
        prod_lower = product_name.lower()

        # Check if product name is part of advertiser name or vice versa
        if prod_lower in adv_lower or adv_lower in prod_lower:
            result["advertiser_match"] = True
            result["confidence"] = "high"
        elif len(set(prod_lower.split()) & set(adv_lower.split())) > 0:
            result["advertiser_match"] = True
            result["confidence"] = "medium"
    else:
        result["confidence"] = "medium"

    return result


def main() -> None:
    print("=" * 60)
    print("Product Name Extraction from Ad Titles")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        extracted_count = 0
        strategy_counter: Counter = Counter()
        confidence_counter: Counter = Counter()

        for ad in ads:
            product_name = extract_product_name(ad)
            validation = _validate_with_advertiser(product_name, ad.advertiser_name)

            meta = dict(ad.ad_metadata or {})
            if product_name:
                meta["product_name"] = product_name
                meta["product_name_confidence"] = validation["confidence"]
                meta["product_advertiser_match"] = validation["advertiser_match"]
                extracted_count += 1
                confidence_counter[validation["confidence"]] += 1
            else:
                meta["product_name"] = None
                meta["product_name_confidence"] = "none"

            meta["product_name_extracted_at"] = datetime.now(timezone.utc).isoformat()
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

        session.commit()
        print(f"\nExtracted {extracted_count} product names out of {total} ads.")
        not_extracted = total - extracted_count
        print(f"  Extracted:     {extracted_count} ({extracted_count / total * 100:.1f}%)")
        print(f"  Not extracted: {not_extracted} ({not_extracted / total * 100:.1f}%)")

        # Confidence distribution
        print(f"\n--- Confidence Distribution ---")
        for conf, count in sorted(confidence_counter.items(), key=lambda x: -x[1]):
            print(f"  {conf:<10s}: {count}")

        # Show 10 sample extractions
        print(f"\n--- Sample Extractions (first 10 with product_name) ---")
        sample_count = 0
        for ad in ads:
            m = ad.ad_metadata or {}
            pname = m.get("product_name")
            if pname and sample_count < 10:
                title_safe = (ad.title or "")[:50].encode("ascii", "replace").decode("ascii")
                pname_safe = pname.encode("ascii", "replace").decode("ascii")
                conf = m.get("product_name_confidence", "?")
                print(f"  ID={ad.id} product={pname_safe!r} conf={conf}")
                print(f"    title={title_safe!r}")
                sample_count += 1

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
