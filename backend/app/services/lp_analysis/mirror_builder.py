"""LP Mirror Builder — creates sanitised static mirrors of landing pages.

Takes an LPSnapshot's raw HTML (dom_text), strips all executable content
(scripts, event handlers, tracking pixels, forms, meta-refresh),
rewrites asset URLs, and stores a safe static copy to S3 for iframe preview.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.database import SyncSessionLocal, sync_session_scope
from app.core.storage import get_storage_client
from app.models.brand_registry import LPAsset, LPMirror, LPMirrorLinkMap, LPSnapshot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRACKING_DOMAINS = [
    "google-analytics.com",
    "googletagmanager.com",
    "facebook.net",
    "doubleclick.net",
    "analytics",
    "beacon",
    "pixel",
    "tag.js",
    "gtag",
    "fbevents",
    "clarity.ms",
    "hotjar.com",
]

EVENT_HANDLER_RE = re.compile(r"\bon\w+=", re.IGNORECASE)

# Attributes that are JavaScript event handlers
EVENT_HANDLER_ATTRS = {
    "onclick", "ondblclick", "onmousedown", "onmouseup", "onmouseover",
    "onmousemove", "onmouseout", "onkeypress", "onkeydown", "onkeyup",
    "onfocus", "onblur", "onchange", "onsubmit", "onreset", "onselect",
    "onload", "onunload", "onerror", "onabort", "onresize", "onscroll",
    "oncontextmenu", "oninput", "oninvalid", "onsearch", "ontouchstart",
    "ontouchend", "ontouchmove", "onanimationend", "ontransitionend",
    "onwheel", "onpointerdown", "onpointerup",
}

# Tags to completely remove (with all content)
STRIP_TAGS = {"script", "noscript", "iframe"}

# Safe HTML shell template
SAFE_HTML_SHELL = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<base target="_blank">
<style>
  /* Mirror safety overrides */
  body {{ overflow-x: hidden; }}
  a {{ cursor: default; }}
  form {{ pointer-events: none; opacity: 0.7; }}
</style>
{head_content}
</head>
<body>
{body_content}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTML Sanitiser
# ---------------------------------------------------------------------------

def _is_tracking_url(url: str) -> bool:
    """Check if a URL belongs to a known tracking / analytics domain."""
    if not url:
        return False
    lower = url.lower()
    for domain in TRACKING_DOMAINS:
        if domain in lower:
            return True
    return False


def _is_tracking_pixel(tag: str, attrs: dict) -> bool:
    """Detect 1x1 tracking pixels and beacon images."""
    if tag != "img":
        return False
    width = attrs.get("width", "")
    height = attrs.get("height", "")
    src = attrs.get("src", "")
    # 1x1 pixel
    if width in ("1", "0") and height in ("1", "0"):
        return True
    if _is_tracking_url(src):
        return True
    # Hidden pixel via style
    style = attrs.get("style", "").lower()
    if "display:none" in style.replace(" ", "") or "visibility:hidden" in style.replace(" ", ""):
        if width in ("1", "0", "") and height in ("1", "0", ""):
            return True
    return False


def _is_meta_refresh(tag: str, attrs: dict) -> bool:
    """Detect <meta http-equiv='refresh'> tags."""
    if tag != "meta":
        return False
    http_equiv = attrs.get("http-equiv", "").lower()
    return http_equiv == "refresh"


def sanitize_html(raw_html: str, snapshot_id: int) -> tuple[str, dict]:
    """Sanitise raw HTML for safe static mirror display.

    Returns:
        (sanitised_html, stats_dict)
    """
    if not raw_html:
        return "", {"error": "empty_html"}

    stats = {
        "scripts_removed": 0,
        "event_handlers_removed": 0,
        "tracking_pixels_removed": 0,
        "forms_sandboxed": 0,
        "links_disabled": 0,
        "meta_refresh_removed": 0,
        "images_found": 0,
        "stylesheets_found": 0,
    }

    # Phase 1: Remove <script>, <noscript>, <iframe> blocks entirely
    for tag in STRIP_TAGS:
        pattern = re.compile(
            rf"<{tag}[\s>].*?</{tag}>",
            re.IGNORECASE | re.DOTALL,
        )
        matches = pattern.findall(raw_html)
        stats["scripts_removed"] += len(matches)
        raw_html = pattern.sub("", raw_html)

    # Also remove self-closing <script .../> variants
    raw_html = re.sub(r"<script\b[^>]*/\s*>", "", raw_html, flags=re.IGNORECASE)

    # Phase 2: Remove tracking/analytics script tags that might have been
    # inline (already removed above, but catch any remnants)
    # Remove any remaining <script ...> without closing tag (malformed)
    raw_html = re.sub(r"<script\b[^>]*>", "", raw_html, flags=re.IGNORECASE)

    # Phase 3: Remove event handler attributes (onclick, onload, etc.)
    def _remove_event_handlers(match: re.Match) -> str:
        tag_text = match.group(0)
        original = tag_text
        for attr in EVENT_HANDLER_ATTRS:
            # Match attr="..." or attr='...' or attr=value
            pattern = re.compile(
                rf'\s+{attr}\s*=\s*(?:"[^"]*"|\'[^\']*\'|\S+)',
                re.IGNORECASE,
            )
            if pattern.search(tag_text):
                stats["event_handlers_removed"] += 1
                tag_text = pattern.sub("", tag_text)
        return tag_text

    raw_html = re.sub(r"<[a-zA-Z][^>]*>", _remove_event_handlers, raw_html)

    # Phase 4: Remove tracking pixels (1x1 images, beacon URLs)
    def _handle_img(match: re.Match) -> str:
        tag_text = match.group(0)
        # Extract attributes roughly
        attrs = {}
        for attr_match in re.finditer(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))', tag_text):
            key = attr_match.group(1).lower()
            val = attr_match.group(2) or attr_match.group(3) or attr_match.group(4) or ""
            attrs[key] = val

        if _is_tracking_pixel("img", attrs):
            stats["tracking_pixels_removed"] += 1
            return ""  # Remove entirely
        stats["images_found"] += 1
        return tag_text

    raw_html = re.sub(r"<img\b[^>]*\/?>", _handle_img, raw_html, flags=re.IGNORECASE)

    # Phase 5: Remove meta refresh tags
    def _handle_meta(match: re.Match) -> str:
        tag_text = match.group(0)
        if re.search(r'http-equiv\s*=\s*["\']?refresh', tag_text, re.IGNORECASE):
            stats["meta_refresh_removed"] += 1
            return ""
        return tag_text

    raw_html = re.sub(r"<meta\b[^>]*\/?>", _handle_meta, raw_html, flags=re.IGNORECASE)

    # Phase 6: Sandbox forms — remove action, add sandbox display
    def _handle_form(match: re.Match) -> str:
        tag_text = match.group(0)
        # Remove action attribute
        tag_text = re.sub(
            r'\s+action\s*=\s*(?:"[^"]*"|\'[^\']*\'|\S+)',
            "",
            tag_text,
            flags=re.IGNORECASE,
        )
        # Add data-sandboxed attribute
        tag_text = tag_text.rstrip(">") + ' data-sandboxed="true">'
        stats["forms_sandboxed"] += 1
        return tag_text

    raw_html = re.sub(r"<form\b[^>]*>", _handle_form, raw_html, flags=re.IGNORECASE)

    # Phase 7: Disable links — set href="#" with data-original-href
    def _handle_link(match: re.Match) -> str:
        tag_text = match.group(0)
        # Extract current href
        href_match = re.search(
            r'href\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))',
            tag_text,
            re.IGNORECASE,
        )
        if href_match:
            original_href = href_match.group(1) or href_match.group(2) or href_match.group(3) or ""
            # Replace href with # and store original
            tag_text = re.sub(
                r'href\s*=\s*(?:"[^"]*"|\'[^\']*\'|\S+)',
                f'href="#" data-original-href="{original_href}"',
                tag_text,
                count=1,
                flags=re.IGNORECASE,
            )
            stats["links_disabled"] += 1
        return tag_text

    raw_html = re.sub(r"<a\b[^>]*>", _handle_link, raw_html, flags=re.IGNORECASE)

    # Phase 8: Count stylesheets
    stylesheet_count = len(re.findall(
        r'<link\b[^>]*rel\s*=\s*["\']?stylesheet',
        raw_html,
        re.IGNORECASE,
    ))
    stats["stylesheets_found"] = stylesheet_count

    # Phase 9: Remove analytics/tag manager inline patterns
    # Remove Google Tag Manager noscript blocks that might remain
    raw_html = re.sub(
        r'<!--\s*Google\s+Tag\s+Manager.*?-->.*?<!--\s*End\s+Google\s+Tag\s+Manager.*?-->',
        "",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return raw_html, stats


def _extract_head_body(html: str) -> tuple[str, str]:
    """Split HTML into head content and body content."""
    # Extract <head> content
    head_match = re.search(r"<head[^>]*>(.*?)</head>", html, re.IGNORECASE | re.DOTALL)
    head_content = head_match.group(1) if head_match else ""

    # Extract <body> content
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.IGNORECASE | re.DOTALL)
    body_content = body_match.group(1) if body_match else html

    # Remove title/meta charset from head (we provide our own)
    head_content = re.sub(r"<meta\b[^>]*charset[^>]*\/?>", "", head_content, flags=re.IGNORECASE)
    head_content = re.sub(r"<meta\b[^>]*viewport[^>]*\/?>", "", head_content, flags=re.IGNORECASE)
    head_content = re.sub(r"<base\b[^>]*\/?>", "", head_content, flags=re.IGNORECASE)

    return head_content.strip(), body_content.strip()


# ---------------------------------------------------------------------------
# Fidelity Scoring
# ---------------------------------------------------------------------------

def compute_fidelity(
    html: str,
    stats: dict,
) -> tuple[float, str]:
    """Compute a simplified fidelity score for the mirror.

    Returns:
        (score: 0.0-1.0, level: FULL_STATIC | PARTIAL_STATIC | SCREENSHOT_ONLY)
    """
    html_len = len(html) if html else 0

    # DOM completeness: based on HTML length
    if html_len > 1000:
        dom_completeness = 1.0
    elif html_len > 200:
        dom_completeness = 0.5
    else:
        dom_completeness = 0.0

    # Critical asset completeness
    images_found = stats.get("images_found", 0)
    stylesheets_found = stats.get("stylesheets_found", 0)
    total_critical = images_found + stylesheets_found
    # For now, we treat all found assets as "available" since we keep
    # their original URLs. In a full implementation we'd verify each.
    if total_critical > 0:
        critical_asset_completeness = 1.0
    else:
        # No external assets is fine for simple pages
        critical_asset_completeness = 0.5 if html_len > 500 else 0.0

    # Weighted score
    score = round(dom_completeness * 0.6 + critical_asset_completeness * 0.4, 3)

    # Determine level
    if score >= 0.7:
        level = "FULL_STATIC"
    elif score >= 0.3:
        level = "PARTIAL_STATIC"
    else:
        level = "SCREENSHOT_ONLY"

    return score, level


# ---------------------------------------------------------------------------
# Main Builder
# ---------------------------------------------------------------------------

def build_mirror(snapshot_id: int, session: Optional[Session] = None) -> dict:
    """Build a sanitised static mirror from an LPSnapshot.

    Args:
        snapshot_id: ID of the LPSnapshot record.
        session: Optional existing SQLAlchemy session (caller-managed).
                 If None, creates its own session.

    Returns:
        dict with mirror build results.
    """
    own_session = session is None
    if own_session:
        session = SyncSessionLocal()

    try:
        # 1. Load snapshot
        snapshot = session.query(LPSnapshot).filter(LPSnapshot.id == snapshot_id).first()
        if not snapshot:
            return {"error": f"Snapshot {snapshot_id} not found", "status": "failed"}

        raw_html = snapshot.dom_text
        if not raw_html:
            return {"error": f"Snapshot {snapshot_id} has no dom_text", "status": "failed"}

        # 2. Get or create LPMirror record
        mirror = session.query(LPMirror).filter(LPMirror.snapshot_id == snapshot_id).first()
        if not mirror:
            mirror = LPMirror(snapshot_id=snapshot_id, mirror_status="building")
            session.add(mirror)
            session.flush()
        else:
            mirror.mirror_status = "building"
            session.flush()

        logger.info("mirror_build_start", snapshot_id=snapshot_id, html_len=len(raw_html))

        # 3. Sanitise HTML
        sanitised_html, stats = sanitize_html(raw_html, snapshot_id)

        # 4. Extract head/body and wrap in safe shell
        head_content, body_content = _extract_head_body(sanitised_html)
        final_html = SAFE_HTML_SHELL.format(
            head_content=head_content,
            body_content=body_content,
        )

        # 5. Upload to S3
        s3_prefix = f"mirrors/{snapshot_id}"
        s3_key = f"{s3_prefix}/index.html"
        html_bytes = final_html.encode("utf-8")

        try:
            storage = get_storage_client()
            storage.upload_bytes(s3_key, html_bytes, content_type="text/html; charset=utf-8")
        except Exception as e:
            logger.error("mirror_s3_upload_failed", snapshot_id=snapshot_id, error=str(e))
            mirror.mirror_status = "failed"
            mirror.build_log_json = {"error": str(e), "stats": stats}
            if own_session:
                session.commit()
            return {"error": f"S3 upload failed: {e}", "status": "failed"}

        # 6. Compute fidelity
        fidelity_score, fidelity_level = compute_fidelity(raw_html, stats)

        # 7. Update mirror record
        mirror.mirror_status = "completed"
        mirror.mirror_root_uri = s3_prefix
        mirror.index_html_uri = s3_key
        mirror.fidelity_score = fidelity_score
        mirror.fidelity_level = fidelity_level
        mirror.build_log_json = stats
        mirror.asset_count = stats.get("images_found", 0) + stats.get("stylesheets_found", 0)
        mirror.total_byte_size = len(html_bytes)
        mirror.updated_at = datetime.now(timezone.utc)

        if own_session:
            session.commit()

        logger.info(
            "mirror_build_complete",
            snapshot_id=snapshot_id,
            fidelity_score=fidelity_score,
            fidelity_level=fidelity_level,
            byte_size=len(html_bytes),
        )

        return {
            "status": "completed",
            "snapshot_id": snapshot_id,
            "mirror_id": mirror.id,
            "s3_key": s3_key,
            "fidelity_score": fidelity_score,
            "fidelity_level": fidelity_level,
            "byte_size": len(html_bytes),
            "stats": stats,
        }

    except Exception as e:
        logger.exception("mirror_build_error", snapshot_id=snapshot_id)
        if own_session:
            session.rollback()
        # Try to update mirror status to failed
        try:
            if mirror:
                mirror.mirror_status = "failed"
                mirror.build_log_json = {"error": str(e)}
                if own_session:
                    session.commit()
        except Exception:
            pass
        return {"error": str(e), "status": "failed"}
    finally:
        if own_session:
            session.close()


def batch_build_mirrors(session: Session, limit: int = 50) -> dict:
    """Build mirrors for snapshots that have dom_text but no mirror yet.

    Args:
        session: SQLAlchemy session (caller-managed).
        limit: Maximum number of snapshots to process.

    Returns:
        dict with batch results.
    """
    from sqlalchemy import and_

    # Find snapshots with dom_text that don't have a mirror yet
    existing_mirror_ids = (
        session.query(LPMirror.snapshot_id)
        .filter(LPMirror.mirror_status == "completed")
        .subquery()
    )

    snapshots = (
        session.query(LPSnapshot)
        .filter(
            LPSnapshot.dom_text.isnot(None),
            LPSnapshot.dom_text != "",
            ~LPSnapshot.id.in_(existing_mirror_ids),
        )
        .order_by(LPSnapshot.id)
        .limit(limit)
        .all()
    )

    results = {"total": len(snapshots), "completed": 0, "failed": 0, "details": []}

    for snapshot in snapshots:
        result = build_mirror(snapshot.id, session=session)
        if result.get("status") == "completed":
            results["completed"] += 1
        else:
            results["failed"] += 1
        results["details"].append({
            "snapshot_id": snapshot.id,
            "status": result.get("status"),
            "fidelity_score": result.get("fidelity_score"),
            "error": result.get("error"),
        })

    session.flush()
    return results
