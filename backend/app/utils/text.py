"""Text analysis utilities."""

import json
import re
import unicodedata
from urllib.parse import parse_qs, urlparse


def japanese_text_ratio(text: str) -> float:
    """Return the ratio of Japanese characters in the given text (0.0–1.0).

    Counts Hiragana (U+3040-309F), Katakana (U+30A0-30FF),
    CJK Unified Ideographs / Kanji (U+4E00-9FFF),
    and Half-width Katakana (U+FF65-FF9F).

    Whitespace and punctuation are excluded from the denominator so that
    spacing-heavy text doesn't dilute the ratio.
    """
    if not text:
        return 0.0

    jp_count = 0
    char_count = 0

    for ch in text:
        cat = unicodedata.category(ch)
        # Skip whitespace (Zs, Zl, Zp) and control chars (Cc, Cf)
        if cat.startswith("Z") or cat.startswith("C"):
            continue
        char_count += 1

        cp = ord(ch)
        if (
            0x3040 <= cp <= 0x309F  # Hiragana
            or 0x30A0 <= cp <= 0x30FF  # Katakana
            or 0x4E00 <= cp <= 0x9FFF  # CJK Unified Ideographs (Kanji)
            or 0xFF65 <= cp <= 0xFF9F  # Half-width Katakana
        ):
            jp_count += 1

    if char_count == 0:
        return 0.0

    return jp_count / char_count


_JP_CHAR_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uff65-\uff9f]")
_JP_URL_SIGNAL_RE = re.compile(r"(^|[^a-z])(ja|jp|japan)([^a-z]|$)", re.IGNORECASE)


def normalize_language_tag(value: object) -> str | None:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    if raw in {"ja", "ja-jp", "jp", "japanese"} or raw.startswith("ja-"):
        return "ja"
    return raw


def is_japanese_like_text(
    text: str | None,
    *,
    min_ratio: float = 0.05,
    min_chars: int = 2,
) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    jp_chars = len(_JP_CHAR_RE.findall(raw))
    if jp_chars < min_chars:
        return False
    return japanese_text_ratio(raw) >= min_ratio or jp_chars >= 4


def url_has_japan_signal(url: str | None) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    except Exception:
        return False

    host = (parsed.netloc or parsed.path.split("/")[0] or "").lower()
    path = parsed.path.lower()
    query = parsed.query.lower()
    combined = " ".join(filter(None, [host, path, query, raw.lower()]))

    if host.endswith(".jp") or ".co.jp" in host:
        return True
    if any(token in combined for token in ("/ja/", "/jp/", "locale=ja", "lang=ja", "country=jp", "region=jp")):
        return True
    if _JP_URL_SIGNAL_RE.search(combined):
        return True

    params = parse_qs(parsed.query)
    for key, values in params.items():
        key_lower = key.lower()
        if key_lower in {"lang", "locale", "country", "region", "market"}:
            for value in values:
                normalized = normalize_language_tag(value)
                if normalized == "ja" or str(value or "").strip().upper() == "JP":
                    return True
    return False


def _value_contains_japan(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return any(_value_contains_japan(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_value_contains_japan(item) for item in value)

    text = str(value).strip()
    if not text:
        return False
    normalized = normalize_language_tag(text)
    if normalized == "ja":
        return True
    upper = text.upper()
    lower = text.lower()
    if upper == "JP" or lower == "japan" or "日本" in text:
        return True
    return False


def metadata_has_japan_signal(metadata: dict | None) -> bool:
    meta = metadata if isinstance(metadata, dict) else {}
    if not meta:
        return False

    if _value_contains_japan(meta.get("language")):
        return True
    if _value_contains_japan(meta.get("languages")):
        return True

    reached = meta.get("ad_reached_countries")
    if isinstance(reached, str):
        try:
            reached = json.loads(reached)
        except Exception:
            pass
    if _value_contains_japan(reached):
        return True

    if _value_contains_japan(meta.get("delivery_by_region")):
        return True

    url_candidates: list[str] = []
    for key in ("destination_url", "display_url", "link_url", "website_url"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            url_candidates.append(value)
    if isinstance(meta.get("all_external_links"), list):
        url_candidates.extend(str(item) for item in meta["all_external_links"] if isinstance(item, str))
    return any(url_has_japan_signal(candidate) for candidate in url_candidates)


def ad_market_is_japanese(
    *texts: str | None,
    urls: list[str | None] | tuple[str | None, ...] | None = None,
    metadata: dict | None = None,
) -> bool:
    for text in texts:
        if is_japanese_like_text(text):
            return True
    if urls and any(url_has_japan_signal(url) for url in urls):
        return True
    return metadata_has_japan_signal(metadata)
