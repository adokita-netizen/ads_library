#!/usr/bin/env python3
"""Custom ad-hoc query tool for the VAAP ad library.

Command-line tool for flexible querying with CSV, JSON, and table output.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/custom_query.py --genre skincare --min-score 70 --format csv
    python scripts/custom_query.py --advertiser "CompanyX" --format json
    python scripts/custom_query.py --hook question --cta urgency --top 20
    python scripts/custom_query.py --hit-only --top 50 --format csv
"""

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Metadata accessors
# ---------------------------------------------------------------------------

def _get_meta(ad):
    """Return ad_metadata dict, defaulting to empty dict."""
    return ad.ad_metadata or {}


def _get_score(ad):
    """Extract latest_hit_score from ad_metadata."""
    try:
        return float(_get_meta(ad).get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _get_genre(ad):
    """Extract fine_genre from ad_metadata."""
    return _get_meta(ad).get("fine_genre", "")


def _get_hit_level(ad):
    """Extract hit_level from ad_metadata."""
    return _get_meta(ad).get("hit_level", "")


def _get_hook(ad):
    """Extract hook_type from ad_metadata."""
    return _get_meta(ad).get("hook_type", "")


def _get_cta(ad):
    """Extract cta_type from ad_metadata."""
    return _get_meta(ad).get("cta_type", "")


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "id", "title", "advertiser", "genre", "score",
    "views", "spend", "hit_level", "first_seen",
]


def ad_to_dict(ad):
    """Convert an Ad row into a flat dictionary with the required output columns."""
    return {
        "id": ad.id,
        "title": ad.title or "",
        "advertiser": ad.advertiser_name or "",
        "genre": _get_genre(ad),
        "score": _get_score(ad),
        "views": ad.view_count or 0,
        "spend": ad.spend or 0,
        "hit_level": _get_hit_level(ad),
        "first_seen": str(ad.first_seen_at or ""),
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def output_table(results, output_file=None):
    """Print results as a formatted, column-aligned table."""
    if not results:
        print("No results found.")
        return

    # Compute column widths
    headers = OUTPUT_COLUMNS
    col_widths = {h: len(h) for h in headers}
    for row in results:
        for h in headers:
            val = str(row.get(h, ""))
            if len(val) > col_widths[h]:
                col_widths[h] = len(val)

    # Cap title width at 40 to keep table readable
    if col_widths.get("title", 0) > 40:
        col_widths["title"] = 40

    def fmt_row(row_data):
        parts = []
        for h in headers:
            val = str(row_data.get(h, ""))
            width = col_widths[h]
            if h in ("id", "score", "views", "spend"):
                parts.append(val.rjust(width))
            else:
                parts.append(val[:width].ljust(width))
        return "  ".join(parts)

    header_line = fmt_row({h: h.upper() for h in headers})
    separator = "  ".join("-" * col_widths[h] for h in headers)

    lines = [header_line, separator]
    for row in results:
        lines.append(fmt_row(row))
    lines.append(separator)
    lines.append(f"Total: {len(results)} results")

    text = "\n".join(lines)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Exported {len(results)} rows to {output_file}")
    else:
        print(text)


def output_csv(results, output_file=None):
    """Output results as CSV using csv.writer."""
    if not results:
        print("No results found.")
        return

    fieldnames = OUTPUT_COLUMNS

    if output_file:
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            for row in results:
                writer.writerow([row.get(h, "") for h in fieldnames])
        print(f"Exported {len(results)} rows to {output_file}")
    else:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(fieldnames)
        for row in results:
            writer.writerow([row.get(h, "") for h in fieldnames])
        print(buf.getvalue(), end="")


def output_json(results, output_file=None):
    """Output results as a JSON list of dicts."""
    if not results:
        print("No results found.")
        return

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"Exported {len(results)} results to {output_file}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser():
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Ad-hoc query tool for the VAAP ad library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/custom_query.py --genre skincare --min-score 70 --format csv
  python scripts/custom_query.py --advertiser "CompanyX" --format json
  python scripts/custom_query.py --hook question --cta urgency --top 20
  python scripts/custom_query.py --hit-only --top 50 --format csv
        """,
    )

    # Filter arguments
    parser.add_argument("--genre", type=str,
                        help="Filter by fine_genre in ad_metadata (exact match, case-insensitive)")
    parser.add_argument("--advertiser", type=str,
                        help="Filter by advertiser_name (partial match, case-insensitive)")
    parser.add_argument("--min-score", type=float,
                        help="Minimum latest_hit_score from ad_metadata")
    parser.add_argument("--max-score", type=float,
                        help="Maximum latest_hit_score from ad_metadata")
    parser.add_argument("--hook", type=str,
                        help="Filter by hook_type in ad_metadata (exact match, case-insensitive)")
    parser.add_argument("--cta", type=str,
                        help="Filter by cta_type in ad_metadata (exact match, case-insensitive)")
    parser.add_argument("--hit-only", action="store_true",
                        help="Only show ads with hit_level = hit or mega_hit")

    # Output control
    parser.add_argument("--top", type=int, default=20,
                        help="Limit number of results (default: 20)")
    parser.add_argument("--format", type=str, choices=["csv", "json", "table"],
                        default="table", help="Output format (default: table)")
    parser.add_argument("--output", type=str,
                        help="Output file path (default: stdout)")
    parser.add_argument("--sort", type=str, default="score",
                        choices=["score", "views", "spend", "date"],
                        help="Sort field (default: score)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    print("[custom_query] Running query...", file=sys.stderr)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[custom_query] Total ads in DB: {len(ads)}", file=sys.stderr)

        filtered = list(ads)

        # -- Apply filters --

        if args.genre:
            target = args.genre.lower()
            filtered = [ad for ad in filtered
                        if _get_genre(ad).lower() == target]

        if args.advertiser:
            search = args.advertiser.lower()
            filtered = [ad for ad in filtered
                        if ad.advertiser_name and search in ad.advertiser_name.lower()]

        if args.min_score is not None:
            filtered = [ad for ad in filtered
                        if _get_score(ad) >= args.min_score]

        if args.max_score is not None:
            filtered = [ad for ad in filtered
                        if _get_score(ad) <= args.max_score]

        if args.hook:
            target = args.hook.lower()
            filtered = [ad for ad in filtered
                        if _get_hook(ad).lower() == target]

        if args.cta:
            target = args.cta.lower()
            filtered = [ad for ad in filtered
                        if _get_cta(ad).lower() == target]

        if args.hit_only:
            filtered = [ad for ad in filtered
                        if _get_hit_level(ad).lower() in ("hit", "mega_hit")]

        print(f"[custom_query] After filtering: {len(filtered)} ads", file=sys.stderr)

        # -- Sort --
        sort_map = {
            "score": lambda ad: _get_score(ad),
            "views": lambda ad: ad.view_count or 0,
            "spend": lambda ad: ad.spend or 0,
            "date": lambda ad: ad.first_seen_at or datetime.min.replace(tzinfo=timezone.utc),
        }
        sort_fn = sort_map.get(args.sort, sort_map["score"])
        filtered.sort(key=sort_fn, reverse=True)

        # -- Limit --
        filtered = filtered[:args.top]

        # -- Convert to dicts --
        results = [ad_to_dict(ad) for ad in filtered]

        # -- Determine output file --
        output_file = args.output
        if output_file and not os.path.isabs(output_file):
            export_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "exports",
            )
            os.makedirs(export_dir, exist_ok=True)
            output_file = os.path.join(export_dir, output_file)

        # -- Output --
        if args.format == "csv":
            output_csv(results, output_file)
        elif args.format == "json":
            output_json(results, output_file)
        else:
            output_table(results, output_file)

        if not output_file:
            print(f"\n[custom_query] Returned {len(results)} results", file=sys.stderr)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
