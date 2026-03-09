"""A-LP-0303-1/2: LP metadata normalization + quality gate tagging.

Normalizes LP-related metadata for ads and records LP quality issues.

Usage:
    python -m scripts.normalize_lp_metadata
    python -m scripts.normalize_lp_metadata --fix --json-report exports/lp_metadata_report.json
"""

import argparse
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LP_HTML_DIR = os.path.join(BASE_DIR, "media_cache", "lp_html")

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_LANG_RE = re.compile(r"<html[^>]*\slang=[\"']([^\"']+)[\"']", re.IGNORECASE)
_H1_RE = re.compile(r"<h1\b[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_SUCCESSFUL_LP_PREFIXES = ("2", "3")
_LP_TINY_BODY_HARD_THRESHOLD = 80
_LP_TINY_BODY_SOFT_THRESHOLD = 120


def _extract_html_features(ad_id: int) -> dict:
    path = os.path.join(LP_HTML_DIR, f"{ad_id}.html")
    if not os.path.exists(path):
        return {
            "has_html": False,
            "lp_html_path": path,
            "lp_html_length": None,
            "lp_text_length": None,
            "title": None,
            "lang": None,
            "h1_count": None,
        }

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
    except OSError:
        return {
            "has_html": False,
            "lp_html_path": path,
            "lp_html_length": None,
            "lp_text_length": None,
            "title": None,
            "lang": None,
            "h1_count": None,
        }

    title_match = _TITLE_RE.search(html)
    lang_match = _LANG_RE.search(html)
    text = _SPACE_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()

    return {
        "has_html": True,
        "lp_html_path": path,
        "lp_html_length": len(html),
        "lp_text_length": len(text),
        "title": title_match.group(1).strip()[:500] if title_match else None,
        "lang": (lang_match.group(1).strip().lower() if lang_match else None),
        "h1_count": len(_H1_RE.findall(html)),
    }


def _normalize_url(raw: str | None) -> tuple[str | None, str | None, str | None]:
    value = str(raw or "").strip()
    if not value:
        return None, None, None
    parsed = urlparse(value)
    if not parsed.scheme:
        parsed = urlparse(f"https://{value}")
    if not parsed.netloc:
        return None, None, None
    final_url = parsed.geturl()
    domain = parsed.netloc.lower()
    path = parsed.path or "/"
    return final_url, domain, path


def _lp_status_is_success(meta: dict) -> bool:
    lp_status = str(meta.get("lp_status") or meta.get("lp_fetch_status") or "").strip().lower()
    return any(lp_status.startswith(prefix) for prefix in _SUCCESSFUL_LP_PREFIXES)


def _should_flag_tiny_body(meta: dict, html_features: dict) -> bool:
    text_len = html_features.get("lp_text_length")
    if not isinstance(text_len, int) or text_len <= 0:
        return False
    if not _lp_status_is_success(meta):
        return False
    if text_len < _LP_TINY_BODY_HARD_THRESHOLD:
        return True

    has_title = bool((html_features.get("title") or "").strip())
    has_h1 = int(html_features.get("h1_count") or 0) > 0
    return text_len < _LP_TINY_BODY_SOFT_THRESHOLD and not (has_title or has_h1)


def _detect_lp_quality_issues(meta: dict, html_features: dict) -> list[str]:
    issues: set[str] = set()

    lp_status = str(meta.get("lp_status") or meta.get("lp_fetch_status") or "").strip().lower()
    lp_reason = str(meta.get("lp_fetch_reason") or "").strip().lower()
    if lp_status == "too_many_redirects" or lp_reason == "redirect_loop":
        issues.add("redirect_loop")

    if html_features.get("has_html"):
        if (html_features.get("lp_html_length") or 0) == 0:
            issues.add("empty_html")
        if _should_flag_tiny_body(meta, html_features):
            issues.add("tiny_body")

    return sorted(issues)


def main():
    parser = argparse.ArgumentParser(description="Normalize LP metadata and tag LP quality issues")
    parser.add_argument("--fix", action="store_true", help="Persist normalized metadata")
    parser.add_argument("--ad-id", type=int, help="Process only one ad_id")
    parser.add_argument("--limit", type=int, default=0, help="Max ads to process (0 = no limit)")
    parser.add_argument("--json-report", type=str, help="Write summary report to JSON")
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        query = (
            session.query(Ad)
            .filter(Ad.destination_url.isnot(None))
            .filter(Ad.destination_url != "")
            .order_by(Ad.id.asc())
        )
        if args.ad_id:
            query = query.filter(Ad.id == args.ad_id)
        if args.limit and args.limit > 0:
            query = query.limit(args.limit)

        ads = query.all()
        total = len(ads)
        updated = 0
        issue_counts = {"empty_html": 0, "tiny_body": 0, "redirect_loop": 0}

        samples = []
        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            html_features = _extract_html_features(int(ad.id))

            final_url, domain, path = _normalize_url(
                meta.get("lp_final_url") or meta.get("final_url") or ad.destination_url
            )

            lp_normalized = dict(meta.get("lp_normalized") or {})
            lp_normalized.update(
                {
                    "final_url": final_url,
                    "domain": domain,
                    "path": path,
                    "lang": html_features.get("lang"),
                    "title": html_features.get("title"),
                    "h1_count": html_features.get("h1_count"),
                    "normalized_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Flat keys kept for backward compatibility with existing scripts/UI.
            meta["final_url"] = final_url
            meta["domain"] = domain
            meta["path"] = path
            if html_features.get("lang") is not None:
                meta["lang"] = html_features.get("lang")
            if html_features.get("title") is not None:
                meta["title"] = html_features.get("title")
            if html_features.get("h1_count") is not None:
                meta["h1_count"] = html_features.get("h1_count")
            meta["lp_html_length"] = html_features.get("lp_html_length")
            meta["lp_text_length"] = html_features.get("lp_text_length")
            meta["lp_normalized"] = lp_normalized

            issues = _detect_lp_quality_issues(meta, html_features)
            existing_issues = meta.get("lp_quality_issue") or []
            if not isinstance(existing_issues, list):
                existing_issues = [str(existing_issues)]
            merged_issues = sorted({str(x) for x in existing_issues if str(x).strip()} | set(issues))
            meta["lp_quality_issue"] = merged_issues

            for k in issues:
                issue_counts[k] = issue_counts.get(k, 0) + 1

            changed = meta != (ad.ad_metadata or {})
            if changed and args.fix:
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1

            if len(samples) < 20 and issues:
                samples.append({"ad_id": ad.id, "issues": issues, "final_url": final_url})

        if args.fix and updated:
            session.commit()

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "updated_ads": updated,
            "issue_counts": issue_counts,
            "samples": samples,
        }

        print(f"Processed ads: {total}")
        print(f"Updated ads:   {updated}")
        print(f"Issue counts:  {issue_counts}")

        if args.json_report:
            out_dir = os.path.dirname(args.json_report) or "."
            os.makedirs(out_dir, exist_ok=True)
            with open(args.json_report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"Report: {args.json_report}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
