"""Fix ads with NULL or empty titles.

For each ad missing a title, generate one using these rules (in priority order):
  a. First meaningful line of description (strip URLs, leading emojis, bullet points, cap at 80 chars)
  b. advertiser_name + " - " + creative_type (if description is also empty)
  c. advertiser_name + " 広告" as last resort
  d. "Ad #<id>" as absolute fallback

Run from the backend directory:
    cd backend
    python scripts/fix_titles.py
"""

import re
import sys
import unicodedata

sys.path.insert(0, ".")

from sqlalchemy import or_

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Emoji / decoration stripping ────────────────────────────────────

# Regex to match most emoji characters (Unicode emoji blocks)
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # ZWJ
    "\U00000020\U000000A0"   # spaces (handled separately too)
    "]+",
    re.UNICODE,
)

# Leading decorations: bullet points, arrows, stars, dashes, numbers with dots
_LEADING_DECO_RE = re.compile(
    r"^[\s・•▶▷►➤➡→⇒★☆◆◇■□●○▪▫–—\-\#\*\>\|\~\:\/\\]+",
    re.UNICODE,
)

# URL pattern
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

# Numbered prefix like "1." or "① "
_NUMBERED_RE = re.compile(r"^[\d①②③④⑤⑥⑦⑧⑨⑩]+[\.\)）\s]+")

# Hashtag-only lines
_HASHTAG_LINE_RE = re.compile(r"^[#＃][^\s]+(\s+[#＃][^\s]+)*\s*$")


def _strip_leading_emoji(text: str) -> str:
    """Remove leading emoji characters from text."""
    result = text.lstrip()
    while result:
        ch = result[0]
        cat = unicodedata.category(ch)
        # Symbol categories: So (other symbol), Sk (modifier symbol), Sc (currency)
        if cat.startswith("So") or cat.startswith("Sk") or ord(ch) > 0x1F000:
            result = result[1:].lstrip()
            continue
        # Also check explicit emoji regex at start
        m = _EMOJI_RE.match(result)
        if m:
            result = result[m.end():].lstrip()
            continue
        break
    return result


def _clean_line(line: str) -> str:
    """Clean a single line for use as a title."""
    # Remove URLs
    line = _URL_RE.sub("", line)
    # Strip leading emoji
    line = _strip_leading_emoji(line)
    # Strip leading decorations (bullets, arrows, etc.)
    line = _LEADING_DECO_RE.sub("", line)
    # Strip numbered prefixes
    line = _NUMBERED_RE.sub("", line)
    # Collapse whitespace
    line = re.sub(r"\s+", " ", line).strip()
    return line


def _is_meaningful(line: str) -> bool:
    """Check if a line is meaningful enough to be a title."""
    if len(line) <= 5:
        return False
    # Skip hashtag-only lines
    if _HASHTAG_LINE_RE.match(line):
        return False
    # Skip lines that are just URLs after cleaning
    if not line or line.isspace():
        return False
    return True


def generate_title(ad: Ad) -> str:
    """Generate a title for an ad based on available data."""
    # Priority a: First meaningful line of description
    if ad.description and ad.description.strip():
        lines = ad.description.strip().splitlines()
        for raw_line in lines:
            cleaned = _clean_line(raw_line)
            if _is_meaningful(cleaned):
                # Cap at 80 characters
                if len(cleaned) > 80:
                    # Try to break at a word boundary
                    truncated = cleaned[:80]
                    last_space = truncated.rfind(" ")
                    if last_space > 40:
                        truncated = truncated[:last_space]
                    return truncated.rstrip(".,;:!?、。！？…") + "..."
                return cleaned

    # Priority b: advertiser_name + " - " + creative_type
    if ad.advertiser_name and ad.advertiser_name.strip():
        if ad.creative_type and ad.creative_type.strip():
            return f"{ad.advertiser_name.strip()} - {ad.creative_type.strip()}"

        # Priority c: advertiser_name + " Ad"
        return f"{ad.advertiser_name.strip()} Ad"

    # Absolute fallback
    return f"Ad #{ad.id}"


def main():
    session = SyncSessionLocal()
    try:
        # Count before
        null_count_before = (
            session.query(Ad)
            .filter(or_(Ad.title == None, Ad.title == ""))  # noqa: E711
            .count()
        )
        total_count = session.query(Ad).count()
        print(f"Total ads: {total_count}")
        print(f"Ads with NULL/empty title (before): {null_count_before}")

        if null_count_before == 0:
            print("No ads to fix. Exiting.")
            return

        # Fetch all ads with NULL/empty title
        ads = (
            session.query(Ad)
            .filter(or_(Ad.title == None, Ad.title == ""))  # noqa: E711
            .all()
        )

        fixed = 0
        for ad in ads:
            new_title = generate_title(ad)
            ad.title = new_title
            fixed += 1
            if fixed <= 20:
                # Show first 20 for review
                print(f"  [{ad.id}] -> {repr(new_title)}")
            elif fixed == 21:
                print(f"  ... (showing first 20 of {null_count_before})")

        session.commit()
        print(f"\nFixed {fixed} ads.")

        # Verify
        null_count_after = (
            session.query(Ad)
            .filter(or_(Ad.title == None, Ad.title == ""))  # noqa: E711
            .count()
        )
        print(f"Ads with NULL/empty title (after): {null_count_after}")

        if null_count_after == 0:
            print("All ads now have titles!")
        else:
            print(f"WARNING: {null_count_after} ads still have NULL/empty titles.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
