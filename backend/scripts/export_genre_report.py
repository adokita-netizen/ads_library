#!/usr/bin/env python3
"""Generate per-genre HTML reports of hit ad creatives & LP destinations.

For each genre:
  - Genre-level pattern analysis (common hooks, CTAs, emotions)
  - Top ads sorted by view_count
  - Ad creative (local image > remote URL > FB Ad Library link)
  - Creative analysis (hook, CTA, emotion, before/after, etc.)
  - LP destination URL + analysis (title, CTA, form, price, colors)
  - LP screenshot if available
  - Hit score breakdown

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/export_genre_report.py
"""
import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from html import escape

DB_PATH = "vaap_local.db"
OUTPUT_DIR = "genre_reports"

GENRE_DISPLAY_JP = {
    "medical_weight_loss": "\u533b\u7642\u75e9\u8eab",
    "diet_supplement": "\u30c0\u30a4\u30a8\u30c3\u30c8\u30b5\u30d7\u30ea",
    "beauty_clinic": "\u7f8e\u5bb9\u30af\u30ea\u30cb\u30c3\u30af",
    "skincare": "\u30b9\u30ad\u30f3\u30b1\u30a2",
    "hair_removal": "\u8131\u6bdb",
    "hair_growth_aga": "\u80b2\u6bdb\u30fbAGA",
    "fitness": "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",
    "yoga_pilates": "\u30e8\u30ac\u30fb\u30d4\u30e9\u30c6\u30a3\u30b9",
    "protein_supplement": "\u30d7\u30ed\u30c6\u30a4\u30f3",
    "health_food": "\u5065\u5eb7\u98df\u54c1",
    "ec_shopping": "EC\u901a\u8ca9",
    "app": "\u30a2\u30d7\u30ea",
    "finance_investment": "\u91d1\u878d\u30fb\u6295\u8cc7",
    "education_school": "\u6559\u80b2\u30fb\u30b9\u30af\u30fc\u30eb",
    "real_estate": "\u4e0d\u52d5\u7523",
    "jobs_recruitment": "\u8ee2\u8077\u30fb\u6c42\u4eba",
    "short_drama": "\u30b7\u30e7\u30fc\u30c8\u30c9\u30e9\u30de",
    "manga_webtoon": "\u30de\u30f3\u30ac\u30fb\u30a6\u30a7\u30d6\u30c8\u30a5\u30fc\u30f3",
    "gaming_entertainment": "\u30b2\u30fc\u30e0\u30fb\u30a8\u30f3\u30bf\u30e1",
    "other": "\u305d\u306e\u4ed6",
}

# Base path for media_cache (resolved at runtime)
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
:root { --primary: #4A7DFF; --bg: #0f1117; --card: #1a1d27; --text: #e4e4e7; --muted: #71717a; --border: #27272a; --green: #22c55e; --red: #ef4444; --purple: #8b5cf6; --amber: #f59e0b; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 20px; max-width: 1400px; margin: 0 auto; }
h1 { color: var(--primary); margin-bottom: 4px; font-size: 24px; }
h2 { color: var(--text); margin: 24px 0 12px; font-size: 18px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
h3 { color: var(--muted); font-size: 14px; margin-bottom: 8px; }
.summary { color: var(--muted); margin-bottom: 20px; font-size: 13px; }
.genre-nav { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }
.genre-nav a { padding: 4px 10px; background: var(--card); border: 1px solid var(--border); border-radius: 6px; color: var(--text); text-decoration: none; font-size: 11px; white-space: nowrap; }
.genre-nav a:hover, .genre-nav a.active { border-color: var(--primary); color: var(--primary); }

/* Pattern cards */
.pattern-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 24px; }
.pattern-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.pattern-card h4 { font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; }
.pattern-item { display: flex; justify-content: space-between; align-items: center; font-size: 12px; padding: 3px 0; }
.pattern-bar { height: 4px; border-radius: 2px; background: var(--primary); margin-top: 2px; }

/* Ad cards */
.ad-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px; }
.ad-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; transition: border-color 0.2s; }
.ad-card:hover { border-color: var(--primary); }
.ad-creative { width: 100%; aspect-ratio: 16/9; object-fit: cover; background: #000; display: block; cursor: pointer; }
.ad-creative-placeholder { width: 100%; aspect-ratio: 16/9; background: #1e2030; display: flex; align-items: center; justify-content: center; color: var(--primary); font-size: 12px; text-decoration: none; cursor: pointer; }
.ad-creative-placeholder:hover { background: #252836; }
.ad-body { padding: 12px; }
.ad-rank { display: inline-block; background: var(--primary); color: #fff; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-bottom: 6px; }
.ad-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ad-desc { font-size: 11px; color: var(--muted); margin-bottom: 8px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.ad-meta { font-size: 10px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.ad-meta span { background: #27272a; padding: 2px 6px; border-radius: 3px; }
.badge-hit { background: #22c55e22 !important; color: var(--green) !important; font-weight: 600; }
.badge-video { background: #8b5cf622 !important; color: var(--purple) !important; }
.badge-views { background: #3b82f622 !important; color: #60a5fa !important; }

/* Creative analysis */
.creative-analysis { border-top: 1px solid var(--border); padding: 10px 12px; }
.creative-analysis h4 { font-size: 11px; color: var(--amber); margin-bottom: 6px; }
.ca-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.ca-tag { font-size: 10px; padding: 2px 6px; border-radius: 3px; background: #27272a; }
.ca-hook { background: #f59e0b22; color: var(--amber); }
.ca-cta { background: #22c55e22; color: var(--green); }
.ca-emotion { background: #8b5cf622; color: var(--purple); }
.ca-feature { background: #3b82f622; color: #60a5fa; }

/* Score breakdown */
.score-bar { display: flex; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 6px; gap: 1px; }
.score-seg { height: 100%; }

/* LP section */
.lp-section { border-top: 1px solid var(--border); padding: 10px 12px; }
.lp-section h4 { font-size: 11px; color: #60a5fa; margin-bottom: 6px; }
.lp-url { font-size: 11px; color: #60a5fa; word-break: break-all; text-decoration: none; display: block; margin-bottom: 4px; }
.lp-url:hover { text-decoration: underline; }
.lp-detail { font-size: 11px; color: var(--muted); line-height: 1.5; }
.lp-detail strong { color: var(--text); }
.lp-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.lp-tag { font-size: 10px; padding: 2px 6px; border-radius: 3px; }
.lp-tag-yes { background: #22c55e22; color: var(--green); }
.lp-tag-no { background: #27272a; color: #404040; }
.lp-screenshot { width: 100%; max-height: 200px; object-fit: cover; object-position: top; border-radius: 6px; margin-top: 8px; border: 1px solid var(--border); }

/* Stats */
.stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; margin-bottom: 20px; }
.stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 10px; text-align: center; }
.stat-value { font-size: 22px; font-weight: 700; color: var(--primary); }
.stat-label { font-size: 10px; color: var(--muted); margin-top: 2px; }
.back-link { display: inline-block; margin-bottom: 12px; color: var(--primary); text-decoration: none; font-size: 12px; }
.fb-link { display: inline-block; font-size: 10px; color: #60a5fa; text-decoration: none; margin-top: 4px; }
.fb-link:hover { text-decoration: underline; }
"""


def format_views(n):
    if n is None or n == 0:
        return "-"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def get_local_image(ad_id):
    """Find best local image for an ad."""
    for path in [
        os.path.join(BASE_PATH, f"media_cache/images/{ad_id}.jpg"),
        os.path.join(BASE_PATH, f"media_cache/thumbnails/{ad_id}.jpg"),
    ]:
        if os.path.exists(path):
            return "file:///" + os.path.abspath(path).replace("\\", "/")
    return None


def get_lp_screenshot(ad_id, lp_data):
    """Find LP screenshot."""
    for path in [
        lp_data.get("screenshot_path", "") if lp_data else "",
        os.path.join(BASE_PATH, f"media_cache/lp_screenshots/{ad_id}.png"),
    ]:
        if path and os.path.exists(path):
            return "file:///" + os.path.abspath(path).replace("\\", "/")
        if path and os.path.exists(os.path.join(BASE_PATH, path)):
            return "file:///" + os.path.abspath(os.path.join(BASE_PATH, path)).replace("\\", "/")
    return None


def render_creative_analysis(ca):
    """Render creative analysis tags."""
    if not ca or not isinstance(ca, dict):
        return ""

    tags = []
    hook = ca.get("hook_type", "")
    if hook and hook != "none":
        tags.append(f'<span class="ca-tag ca-hook">Hook: {escape(hook)}</span>')

    cta = ca.get("cta_type", "")
    if cta and cta != "none":
        tags.append(f'<span class="ca-tag ca-cta">CTA: {escape(cta)}</span>')

    emotion = ca.get("emotion", "")
    if emotion and emotion != "neutral":
        tags.append(f'<span class="ca-tag ca-emotion">{escape(emotion)}</span>')

    offer = ca.get("offer_type", "")
    if offer and offer != "none":
        tags.append(f'<span class="ca-tag ca-feature">Offer: {escape(offer)}</span>')

    for feat, label in [
        ("has_before_after", "B/A"),
        ("has_testimonial", "Testimonial"),
        ("has_emoji", "Emoji"),
        ("has_numbers", "Numbers"),
    ]:
        if ca.get(feat):
            tags.append(f'<span class="ca-tag ca-feature">{label}</span>')

    text_len = ca.get("text_length", "")
    if text_len:
        tags.append(f'<span class="ca-tag">{escape(text_len)} copy</span>')

    if not tags:
        return ""

    return f"""
    <div class="creative-analysis">
        <h4>Creative Pattern</h4>
        <div class="ca-tags">{"".join(tags)}</div>
    </div>"""


def render_score_breakdown(meta):
    """Render hit score with breakdown bar."""
    score = meta.get("latest_hit_score")
    breakdown = meta.get("latest_score_breakdown", {})
    if not score:
        return ""

    colors = {
        "longevity": "#22c55e",
        "spend": "#3b82f6",
        "active_bonus": "#f59e0b",
        "creative": "#8b5cf6",
        "trend": "#ef4444",
    }
    total = sum(breakdown.values()) if breakdown else score
    segments = ""
    legend = []
    for key, color in colors.items():
        val = breakdown.get(key, 0)
        if val > 0 and total > 0:
            pct = val / total * 100
            segments += f'<div class="score-seg" style="width:{pct}%;background:{color}" title="{key}: {val:.0f}"></div>'
            legend.append(f'{key}:{val:.0f}')

    return f"""
    <div style="padding:0 12px 8px;font-size:10px;color:var(--muted)">
        Score: <strong style="color:var(--green)">{score:.0f}</strong> ({", ".join(legend)})
        <div class="score-bar">{segments}</div>
    </div>"""


def render_ad_card(ad, rank):
    """Render a single ad card HTML."""
    ad_id, title, desc, ctype, image_url, video_url, thumb_url, snapshot_url, \
        dest_url, advertiser, view_count, meta = ad

    title_esc = escape(title or "-")
    desc_esc = escape((desc or "")[:400])
    advertiser_esc = escape(advertiser or "-")

    # Creative image
    local_img = get_local_image(ad_id)
    img_src = local_img or image_url or thumb_url or ""

    fb_link = snapshot_url if snapshot_url and "facebook.com" in (snapshot_url or "") else ""

    if img_src:
        creative_html = (
            f'<a href="{escape(fb_link or img_src)}" target="_blank">'
            f'<img class="ad-creative" src="{escape(img_src)}" alt="" loading="lazy" '
            f'onerror="this.outerHTML=\'<div class=ad-creative-placeholder>Image unavailable</div>\'">'
            f'</a>'
        )
    elif fb_link:
        creative_html = f'<a class="ad-creative-placeholder" href="{escape(fb_link)}" target="_blank">View on Facebook Ad Library</a>'
    else:
        creative_html = '<div class="ad-creative-placeholder">No Image</div>'

    # Badges
    badges = []
    views_str = format_views(view_count)
    if views_str != "-":
        badges.append(f'<span class="badge-views">{views_str} views</span>')
    if ctype == "video":
        badges.append('<span class="badge-video">VIDEO</span>')

    hit_score = meta.get("latest_hit_score")
    if hit_score and hit_score >= 50:
        badges.append(f'<span class="badge-hit">HIT {hit_score:.0f}</span>')

    badges_html = "".join(badges)

    # FB link
    fb_html = ""
    if fb_link:
        fb_html = f'<a class="fb-link" href="{escape(fb_link)}" target="_blank">View on FB Ad Library &rarr;</a>'

    # Creative analysis
    ca_html = render_creative_analysis(meta.get("creative_analysis"))

    # Score breakdown
    score_html = render_score_breakdown(meta)

    # LP section
    lp_html = ""
    if dest_url and dest_url != "-":
        lp_data = meta.get("lp_data", {})
        lp_title = escape((lp_data.get("title", "") or "")[:120])
        lp_desc_text = escape((lp_data.get("meta_description", "") or "")[:200])
        dest_type = meta.get("destination_type", "") or lp_data.get("destination_type", "")

        # LP feature tags
        tags = []
        for feat, label in [
            ("has_form", "Form"), ("has_price", "Price"),
            ("has_testimonials", "Reviews"), ("has_video", "Video"),
            ("has_countdown", "Urgency"),
        ]:
            val = lp_data.get(feat, False)
            cls = "lp-tag-yes" if val else "lp-tag-no"
            tags.append(f'<span class="lp-tag {cls}">{label}</span>')
        tags_html = "".join(tags)

        # CTA buttons
        cta_buttons = lp_data.get("cta_buttons", [])
        cta_html = ""
        if cta_buttons:
            cta_html = f'<div style="margin-top:4px"><strong>CTA:</strong> {escape(", ".join(str(c) for c in cta_buttons[:5]))}</div>'

        # Color scheme
        colors = lp_data.get("color_scheme", [])
        color_html = ""
        if colors:
            swatches = "".join(
                f'<span style="display:inline-block;width:14px;height:14px;background:{escape(c)};'
                f'border-radius:2px;border:1px solid #333" title="{escape(c)}"></span>'
                for c in colors[:6]
            )
            color_html = f'<div style="margin-top:6px;display:flex;gap:3px;align-items:center"><span style="font-size:10px;color:var(--muted)">Colors:</span> {swatches}</div>'

        # LP screenshot
        lp_ss = get_lp_screenshot(ad_id, lp_data)
        screenshot_html = ""
        if lp_ss:
            screenshot_html = f'<img class="lp-screenshot" src="{lp_ss}" alt="LP" loading="lazy">'

        lp_html = f"""
        <div class="lp-section">
            <h4>LP Destination ({escape(dest_type)})</h4>
            <a class="lp-url" href="{escape(dest_url)}" target="_blank">{escape(dest_url[:100])}</a>
            <div class="lp-detail">
                {f'<div><strong>{lp_title}</strong></div>' if lp_title else ''}
                {f'<div>{lp_desc_text}</div>' if lp_desc_text else ''}
                {cta_html}
            </div>
            <div class="lp-tags">{tags_html}</div>
            {color_html}
            {screenshot_html}
        </div>"""

    return f"""
    <div class="ad-card">
        {creative_html}
        <div class="ad-body">
            <span class="ad-rank">#{rank}</span>
            <div class="ad-title">{title_esc}</div>
            <div class="ad-desc">{desc_esc}</div>
            <div class="ad-meta">{badges_html}<span>{advertiser_esc}</span></div>
            {fb_html}
        </div>
        {ca_html}
        {score_html}
        {lp_html}
    </div>"""


def compute_genre_patterns(ads):
    """Compute common creative patterns for a genre."""
    hooks = Counter()
    ctas = Counter()
    emotions = Counter()
    offers = Counter()
    features = Counter()
    dest_types = Counter()
    lp_features = Counter()

    for ad in ads:
        meta = ad[11]
        ca = meta.get("creative_analysis", {})
        if isinstance(ca, dict):
            h = ca.get("hook_type", "")
            if h and h != "none":
                hooks[h] += 1
            c = ca.get("cta_type", "")
            if c and c != "none":
                ctas[c] += 1
            e = ca.get("emotion", "")
            if e:
                emotions[e] += 1
            o = ca.get("offer_type", "")
            if o and o != "none":
                offers[o] += 1
            for feat in ["has_before_after", "has_testimonial", "has_emoji", "has_numbers"]:
                if ca.get(feat):
                    features[feat.replace("has_", "")] += 1

        dt = meta.get("destination_type", "")
        if dt:
            dest_types[dt] += 1

        lp = meta.get("lp_data", {})
        if isinstance(lp, dict):
            for feat in ["has_form", "has_price", "has_testimonials", "has_video", "has_countdown"]:
                if lp.get(feat):
                    lp_features[feat.replace("has_", "")] += 1

    return {
        "hooks": hooks.most_common(5),
        "ctas": ctas.most_common(5),
        "emotions": emotions.most_common(5),
        "offers": offers.most_common(5),
        "features": features.most_common(5),
        "dest_types": dest_types.most_common(5),
        "lp_features": lp_features.most_common(5),
    }


def render_pattern_card(title, items, total, color="var(--primary)"):
    """Render a pattern analysis card."""
    if not items:
        return ""
    rows = ""
    for label, count in items:
        pct = count / total * 100 if total else 0
        rows += f"""
        <div class="pattern-item">
            <span>{escape(label)}</span>
            <span style="color:{color};font-weight:600">{pct:.0f}%</span>
        </div>
        <div class="pattern-bar" style="width:{pct}%;background:{color}"></div>"""
    return f"""
    <div class="pattern-card">
        <h4>{title}</h4>
        {rows}
    </div>"""


def generate_genre_page(genre_slug, genre_jp, ads, all_genres):
    """Generate HTML page for a single genre."""
    ads.sort(key=lambda a: a[10] or 0, reverse=True)

    total = len(ads)
    with_image = sum(1 for a in ads if get_local_image(a[0]) or a[4] or a[6])
    with_lp = sum(1 for a in ads if a[8] and a[8] != "-")
    with_lp_data = sum(1 for a in ads if a[11].get("lp_data"))
    with_score = sum(1 for a in ads if a[11].get("latest_hit_score"))
    avg_views = sum(a[10] or 0 for a in ads) / total if total else 0

    # Pattern analysis
    patterns = compute_genre_patterns(ads)

    nav_links = " ".join(
        f'<a href="{slug}.html" {"class=active" if slug == genre_slug else ""}>'
        f'{GENRE_DISPLAY_JP.get(slug, slug)} ({cnt})</a>'
        for slug, cnt in sorted(all_genres.items(), key=lambda x: -x[1])
    )

    pattern_cards = "".join([
        render_pattern_card("Hook Type", patterns["hooks"], total, "#f59e0b"),
        render_pattern_card("CTA Type", patterns["ctas"], total, "#22c55e"),
        render_pattern_card("Emotion", patterns["emotions"], total, "#8b5cf6"),
        render_pattern_card("Ad Features", patterns["features"], total, "#3b82f6"),
        render_pattern_card("LP Destination", patterns["dest_types"], total, "#60a5fa"),
        render_pattern_card("LP Features", patterns["lp_features"], total, "#22c55e"),
    ])

    cards = "\n".join(render_ad_card(ad, i + 1) for i, ad in enumerate(ads))

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{genre_jp} - Hit Ad Creatives & LP Report</title>
<style>{CSS}</style>
</head>
<body>
<a class="back-link" href="index.html">&larr; All Genres</a>
<h1>{genre_jp}</h1>
<p class="summary">{genre_slug} | {total} ads | Avg views: {format_views(avg_views)}</p>

<div class="stats">
    <div class="stat-card"><div class="stat-value">{total}</div><div class="stat-label">Total Ads</div></div>
    <div class="stat-card"><div class="stat-value">{with_image}</div><div class="stat-label">With Creative</div></div>
    <div class="stat-card"><div class="stat-value">{with_lp}</div><div class="stat-label">LP URL</div></div>
    <div class="stat-card"><div class="stat-value">{with_lp_data}</div><div class="stat-label">LP Analyzed</div></div>
    <div class="stat-card"><div class="stat-value">{with_score}</div><div class="stat-label">Hit Scored</div></div>
</div>

<h2>Creative Patterns (this genre)</h2>
<p class="summary">Common hooks, CTAs, emotions, and LP features found in {genre_jp} ads</p>
<div class="pattern-grid">{pattern_cards}</div>

<div class="genre-nav">{nav_links}</div>

<h2>All Ads (by views)</h2>
<div class="ad-grid">{cards}</div>

</body>
</html>"""


def generate_index(all_genres, genre_stats):
    """Generate the index page."""
    rows = ""
    for slug, count in sorted(all_genres.items(), key=lambda x: -x[1]):
        jp = GENRE_DISPLAY_JP.get(slug, slug)
        stats = genre_stats.get(slug, {})
        views = format_views(stats.get("avg_views", 0))
        creative_pct = stats.get("creative_pct", 0)
        lp_pct = stats.get("lp_pct", 0)
        top_hook = stats.get("top_hook", "-")
        top_cta = stats.get("top_cta", "-")
        rows += f"""
        <tr onclick="window.location='{slug}.html'" style="cursor:pointer">
            <td style="font-weight:600;color:var(--primary)">{jp}</td>
            <td style="color:var(--muted)">{slug}</td>
            <td style="text-align:right">{count}</td>
            <td style="text-align:right">{views}</td>
            <td style="text-align:right">{creative_pct:.0f}%</td>
            <td style="text-align:right">{lp_pct:.0f}%</td>
            <td>{escape(top_hook)}</td>
            <td>{escape(top_cta)}</td>
        </tr>"""

    total_ads = sum(all_genres.values())

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VAAP - Hit Ad Creatives & LP Report by Genre</title>
<style>
{CSS}
table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 12px; overflow: hidden; }}
th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); font-size: 12px; }}
th {{ background: #1e2030; color: var(--muted); font-weight: 500; font-size: 10px; text-transform: uppercase; }}
tr:hover {{ background: #22252f; }}
</style>
</head>
<body>
<h1>VAAP - Hit Ad Creatives & LP Report</h1>
<p class="summary">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {total_ads} ads across {len(all_genres)} genres</p>
<p class="summary">Click a genre to browse hit ad creatives, LP destinations, creative patterns, and LP analysis.</p>

<div class="stats">
    <div class="stat-card"><div class="stat-value">{total_ads}</div><div class="stat-label">Total Ads</div></div>
    <div class="stat-card"><div class="stat-value">{len(all_genres)}</div><div class="stat-label">Genres</div></div>
</div>

<table>
<thead>
<tr>
    <th>Genre</th><th>Slug</th><th style="text-align:right">Ads</th>
    <th style="text-align:right">Avg Views</th><th style="text-align:right">Creative</th>
    <th style="text-align:right">LP</th><th>Top Hook</th><th>Top CTA</th>
</tr>
</thead>
<tbody>{rows}</tbody>
</table>
</body>
</html>"""


def main():
    print("=" * 60)
    print("Genre Report Generator (with Creative Patterns & LP Analysis)")
    print(f"Output: {OUTPUT_DIR}/")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, description, creative_type,
               image_url, video_url, thumbnail_url, snapshot_url,
               destination_url, advertiser_name, view_count, metadata
        FROM ads ORDER BY view_count DESC
    """)
    rows = cur.fetchall()
    conn.close()

    # Parse and group by genre
    genre_ads = defaultdict(list)
    for row in rows:
        meta_str = row[11]
        meta = json.loads(meta_str) if meta_str else {}
        # Parse creative_analysis if it's a string
        ca = meta.get("creative_analysis")
        if isinstance(ca, str):
            try:
                meta["creative_analysis"] = json.loads(ca.replace("'", '"'))
            except Exception:
                pass
        genre = meta.get("fine_genre_en", "other")
        ad = row[:11] + (meta,)
        genre_ads[genre].append(ad)

    all_genres = {g: len(ads) for g, ads in genre_ads.items()}
    print(f"\nGenres: {len(all_genres)}, Total ads: {sum(all_genres.values())}")

    genre_stats = {}
    for genre, ads in genre_ads.items():
        total = len(ads)
        with_creative = sum(1 for a in ads if get_local_image(a[0]) or a[4] or a[6])
        with_lp = sum(1 for a in ads if a[8] and a[8] != "-")
        avg_views = sum(a[10] or 0 for a in ads) / total if total else 0

        patterns = compute_genre_patterns(ads)
        top_hook = patterns["hooks"][0][0] if patterns["hooks"] else "-"
        top_cta = patterns["ctas"][0][0] if patterns["ctas"] else "-"

        genre_stats[genre] = {
            "avg_views": avg_views,
            "creative_pct": with_creative / total * 100 if total else 0,
            "lp_pct": with_lp / total * 100 if total else 0,
            "top_hook": top_hook,
            "top_cta": top_cta,
        }

        jp = GENRE_DISPLAY_JP.get(genre, genre)
        html = generate_genre_page(genre, jp, ads, all_genres)
        path = os.path.join(OUTPUT_DIR, f"{genre}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  {genre:<25s} {total:>4d} ads -> {path}")

    index_html = generate_index(all_genres, genre_stats)
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"\n  Index -> {index_path}")

    abs_index = os.path.abspath(index_path).replace("\\", "/")
    print(f"\nDone! Open in browser:")
    print(f"  file:///{abs_index}")


if __name__ == "__main__":
    main()
