"""Text analysis utilities."""

import unicodedata


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
