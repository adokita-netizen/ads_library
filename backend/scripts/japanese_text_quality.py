#!/usr/bin/env python3
"""Check Japanese text quality in ad titles and descriptions.

Detects encoding issues, non-Japanese text, truncated content, and
assigns language tags.

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/japanese_text_quality.py
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


# ── Detection Functions ──────────────────────────────────────────────────

# Japanese character ranges
JP_PATTERN = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF]")
ASCII_WORD_PATTERN = re.compile(r"[A-Za-z]{3,}")
ENCODING_ISSUE_PATTERN = re.compile(r"[\ufffd\u00ef\u00bf\u00bd]+|\\x[0-9a-f]{2}")


def detect_language(text: str) -> str:
    """Detect if text is Japanese, English, or mixed."""
    if not text:
        return "empty"

    jp_chars = len(JP_PATTERN.findall(text))
    ascii_words = len(ASCII_WORD_PATTERN.findall(text))
    total_chars = len(text.strip())

    if total_chars == 0:
        return "empty"

    jp_ratio = jp_chars / total_chars

    if jp_ratio > 0.3:
        if ascii_words > 5:
            return "mixed"
        return "ja"
    elif ascii_words > 3:
        return "en"
    else:
        return "unknown"


def check_encoding_issues(text: str) -> list[str]:
    """Check for encoding problems."""
    issues = []
    if not text:
        return issues

    # Replacement characters
    if "\ufffd" in text:
        issues.append("replacement_char")

    # Mojibake patterns
    if ENCODING_ISSUE_PATTERN.search(text):
        issues.append("encoding_issue")

    # Double-encoded
    if "\\u" in text or "&#" in text:
        issues.append("escaped_unicode")

    return issues


def check_truncation(text: str) -> bool:
    """Check if text appears truncated."""
    if not text:
        return False

    # Common truncation indicators
    if text.endswith("...") or text.endswith("…"):
        return True
    if text.endswith("..") and not text.endswith("..."):
        return True
    # Ends mid-sentence (no period/exclamation/question)
    if len(text) > 100 and not re.search(r"[。！？!?\n]$", text.strip()):
        return True

    return False


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[japanese_text_quality] Total ads: {len(ads)}")

        lang_counts = Counter()
        encoding_issues_count = 0
        truncated_count = 0
        empty_title = 0
        empty_desc = 0
        updated = 0

        for ad in ads:
            title = ad.title or ""
            desc = ad.description or ""
            full_text = f"{title} {desc}"

            # Language detection
            lang = detect_language(full_text)
            lang_counts[lang] += 1

            # Encoding issues
            title_issues = check_encoding_issues(title)
            desc_issues = check_encoding_issues(desc)
            all_issues = list(set(title_issues + desc_issues))
            if all_issues:
                encoding_issues_count += 1

            # Truncation
            is_truncated = check_truncation(title) or check_truncation(desc)
            if is_truncated:
                truncated_count += 1

            # Empty checks
            if not title.strip():
                empty_title += 1
            if not desc.strip():
                empty_desc += 1

            # Store in metadata
            meta = dict(ad.ad_metadata or {})
            meta["text_quality"] = {
                "language": lang,
                "encoding_issues": all_issues if all_issues else None,
                "is_truncated": is_truncated,
                "title_length": len(title),
                "description_length": len(desc),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

        session.commit()

        print(f"\n  Language distribution:")
        for lang, count in lang_counts.most_common():
            pct = count / len(ads) * 100
            print(f"    {lang}: {count} ({pct:.1f}%)")

        print(f"\n  Quality issues:")
        print(f"    Encoding issues: {encoding_issues_count}")
        print(f"    Truncated text: {truncated_count}")
        print(f"    Empty title: {empty_title}")
        print(f"    Empty description: {empty_desc}")
        print(f"\n  Updated: {updated} ads")

    finally:
        session.close()


if __name__ == "__main__":
    main()
