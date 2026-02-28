"""Generate representative SVG thumbnails for scenario archetypes.

Creates simple SVG graphics showing the scenario flow for each archetype
(Hook -> Problem -> Solution -> Proof -> CTA). These are used as visual
icons in the scenario builder UI.

Usage:
    cd backend
    python scripts/generate_scenario_thumbnails.py
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMBNAIL_DIR = os.path.join(CACHE_DIR, "scenario_thumbnails")

# ── Archetype definitions ────────────────────────────────────────
ARCHETYPES = {
    "before_after": {
        "title": "Before / After",
        "steps": ["Hook", "Before", "After", "Proof", "CTA"],
        "color": "#4CAF50",
        "accent": "#81C784",
        "icon_shape": "split",
    },
    "testimonial": {
        "title": "Testimonial",
        "steps": ["Hook", "Problem", "Voice", "Result", "CTA"],
        "color": "#2196F3",
        "accent": "#64B5F6",
        "icon_shape": "quote",
    },
    "problem_solution": {
        "title": "Problem-Solution",
        "steps": ["Hook", "Problem", "Solution", "Proof", "CTA"],
        "color": "#FF9800",
        "accent": "#FFB74D",
        "icon_shape": "lightbulb",
    },
    "demonstration": {
        "title": "Demonstration",
        "steps": ["Hook", "Setup", "Demo", "Result", "CTA"],
        "color": "#9C27B0",
        "accent": "#BA68C8",
        "icon_shape": "play",
    },
    "urgency_scarcity": {
        "title": "Urgency / Scarcity",
        "steps": ["Hook", "Value", "Urgency", "Offer", "CTA"],
        "color": "#F44336",
        "accent": "#EF5350",
        "icon_shape": "clock",
    },
    "educational": {
        "title": "Educational",
        "steps": ["Hook", "Question", "Lesson", "Insight", "CTA"],
        "color": "#00BCD4",
        "accent": "#4DD0E1",
        "icon_shape": "book",
    },
    "comparison": {
        "title": "Comparison",
        "steps": ["Hook", "Option A", "Option B", "Winner", "CTA"],
        "color": "#795548",
        "accent": "#A1887F",
        "icon_shape": "scale",
    },
    "storytelling": {
        "title": "Storytelling",
        "steps": ["Hook", "Setup", "Conflict", "Resolution", "CTA"],
        "color": "#607D8B",
        "accent": "#90A4AE",
        "icon_shape": "story",
    },
}


def _generate_icon_svg(shape: str, cx: float, cy: float, color: str) -> str:
    """Generate a small icon SVG element for the archetype."""
    if shape == "split":
        # Two halves (before/after)
        return (
            f'<rect x="{cx-15}" y="{cy-12}" width="12" height="24" rx="2" fill="{color}" opacity="0.5"/>'
            f'<rect x="{cx+3}" y="{cy-12}" width="12" height="24" rx="2" fill="{color}"/>'
            f'<line x1="{cx}" y1="{cy-14}" x2="{cx}" y2="{cy+14}" stroke="{color}" stroke-width="1.5" stroke-dasharray="3,2"/>'
        )
    elif shape == "quote":
        return (
            f'<text x="{cx-8}" y="{cy+8}" font-family="Georgia,serif" font-size="28" fill="{color}" opacity="0.8">'
            f'&#8220;</text>'
        )
    elif shape == "lightbulb":
        return (
            f'<circle cx="{cx}" cy="{cy-4}" r="10" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<line x1="{cx-4}" y1="{cy+8}" x2="{cx+4}" y2="{cy+8}" stroke="{color}" stroke-width="2"/>'
            f'<line x1="{cx-3}" y1="{cy+11}" x2="{cx+3}" y2="{cy+11}" stroke="{color}" stroke-width="1.5"/>'
            f'<line x1="{cx}" y1="{cy-14}" x2="{cx}" y2="{cy-8}" stroke="{color}" stroke-width="1.5"/>'
        )
    elif shape == "play":
        return (
            f'<circle cx="{cx}" cy="{cy}" r="14" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<polygon points="{cx-4},{cy-8} {cx-4},{cy+8} {cx+8},{cy}" fill="{color}"/>'
        )
    elif shape == "clock":
        return (
            f'<circle cx="{cx}" cy="{cy}" r="13" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy-8}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
            f'<line x1="{cx}" y1="{cy}" x2="{cx+6}" y2="{cy+2}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        )
    elif shape == "book":
        return (
            f'<rect x="{cx-12}" y="{cy-10}" width="24" height="20" rx="2" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<line x1="{cx}" y1="{cy-10}" x2="{cx}" y2="{cy+10}" stroke="{color}" stroke-width="1.5"/>'
            f'<line x1="{cx-8}" y1="{cy-4}" x2="{cx-3}" y2="{cy-4}" stroke="{color}" stroke-width="1" opacity="0.6"/>'
            f'<line x1="{cx-8}" y1="{cy}" x2="{cx-3}" y2="{cy}" stroke="{color}" stroke-width="1" opacity="0.6"/>'
            f'<line x1="{cx+3}" y1="{cy-4}" x2="{cx+8}" y2="{cy-4}" stroke="{color}" stroke-width="1" opacity="0.6"/>'
            f'<line x1="{cx+3}" y1="{cy}" x2="{cx+8}" y2="{cy}" stroke="{color}" stroke-width="1" opacity="0.6"/>'
        )
    elif shape == "scale":
        return (
            f'<line x1="{cx}" y1="{cy-12}" x2="{cx}" y2="{cy+10}" stroke="{color}" stroke-width="2"/>'
            f'<line x1="{cx-14}" y1="{cy-6}" x2="{cx+14}" y2="{cy-6}" stroke="{color}" stroke-width="2"/>'
            f'<circle cx="{cx-14}" cy="{cy-6}" r="3" fill="{color}" opacity="0.5"/>'
            f'<circle cx="{cx+14}" cy="{cy-6}" r="3" fill="{color}"/>'
            f'<rect x="{cx-6}" y="{cy+8}" width="12" height="4" rx="1" fill="{color}"/>'
        )
    else:  # story
        return (
            f'<path d="M{cx-10},{cy-8} Q{cx},{cy-16} {cx+10},{cy-8} L{cx+10},{cy+8} Q{cx},{cy+16} {cx-10},{cy+8} Z" '
            f'fill="none" stroke="{color}" stroke-width="2"/>'
            f'<line x1="{cx-4}" y1="{cy-3}" x2="{cx+4}" y2="{cy-3}" stroke="{color}" stroke-width="1" opacity="0.5"/>'
            f'<line x1="{cx-4}" y1="{cy+1}" x2="{cx+4}" y2="{cy+1}" stroke="{color}" stroke-width="1" opacity="0.5"/>'
            f'<line x1="{cx-4}" y1="{cy+5}" x2="{cx+2}" y2="{cy+5}" stroke="{color}" stroke-width="1" opacity="0.5"/>'
        )


def generate_thumbnail(archetype_key: str, info: dict) -> str:
    """Generate an SVG thumbnail for a scenario archetype.

    Returns the SVG content as a string.
    """
    width = 320
    height = 200
    color = info["color"]
    accent = info["accent"]
    title = info["title"]
    steps = info["steps"]
    icon_shape = info["icon_shape"]

    # Build SVG
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )

    # Background with subtle gradient
    parts.append(
        f'<defs>'
        f'  <linearGradient id="bg_{archetype_key}" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'    <stop offset="0%" style="stop-color:#fafafa"/>'
        f'    <stop offset="100%" style="stop-color:#f0f0f0"/>'
        f'  </linearGradient>'
        f'</defs>'
    )
    parts.append(
        f'<rect width="{width}" height="{height}" rx="8" '
        f'fill="url(#bg_{archetype_key})" stroke="#e0e0e0" stroke-width="1"/>'
    )

    # Top accent bar
    parts.append(
        f'<rect width="{width}" height="4" rx="0" fill="{color}"/>'
        f'<rect width="{width}" height="4" rx="8" ry="8" fill="{color}"/>'
    )

    # Title
    parts.append(
        f'<text x="{width/2}" y="28" text-anchor="middle" '
        f'font-family="Arial,sans-serif" font-size="14" font-weight="bold" '
        f'fill="#333">{title}</text>'
    )

    # Icon in top-right area
    icon_svg = _generate_icon_svg(icon_shape, width - 35, 24, accent)
    parts.append(icon_svg)

    # Flow steps (horizontal timeline)
    step_count = len(steps)
    margin_x = 30
    usable_w = width - 2 * margin_x
    step_spacing = usable_w / (step_count - 1) if step_count > 1 else 0
    y_center = 90

    # Draw connecting line
    parts.append(
        f'<line x1="{margin_x}" y1="{y_center}" '
        f'x2="{margin_x + usable_w}" y2="{y_center}" '
        f'stroke="{accent}" stroke-width="2" opacity="0.5"/>'
    )

    # Draw step nodes
    for i, step in enumerate(steps):
        cx = margin_x + i * step_spacing
        node_r = 14

        # Node circle
        opacity = "1" if i == 0 or i == step_count - 1 else "0.85"
        fill = color if i == step_count - 1 else accent
        parts.append(
            f'<circle cx="{cx}" cy="{y_center}" r="{node_r}" '
            f'fill="{fill}" opacity="{opacity}"/>'
        )

        # Step number
        parts.append(
            f'<text x="{cx}" y="{y_center + 5}" text-anchor="middle" '
            f'font-family="Arial,sans-serif" font-size="12" font-weight="bold" '
            f'fill="white">{i+1}</text>'
        )

        # Step label below
        parts.append(
            f'<text x="{cx}" y="{y_center + 30}" text-anchor="middle" '
            f'font-family="Arial,sans-serif" font-size="10" fill="#666">{step}</text>'
        )

        # Arrow between nodes (except last)
        if i < step_count - 1:
            arrow_x = cx + step_spacing / 2
            parts.append(
                f'<polygon points="{arrow_x-3},{y_center-3} {arrow_x+3},{y_center} {arrow_x-3},{y_center+3}" '
                f'fill="{accent}" opacity="0.6"/>'
            )

    # Bottom label
    parts.append(
        f'<text x="{width/2}" y="{height - 18}" text-anchor="middle" '
        f'font-family="Arial,sans-serif" font-size="11" fill="#999">'
        f'Scenario Flow</text>'
    )

    # Bottom accent line
    parts.append(
        f'<rect x="0" y="{height-4}" width="{width}" height="4" rx="0" fill="{color}" opacity="0.3"/>'
    )

    parts.append('</svg>')
    return "\n".join(parts)


def generate_all_thumbnails():
    """Generate thumbnails for all scenario archetypes."""
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)

    print("Generating scenario thumbnails in: %s" % THUMBNAIL_DIR)
    print("")

    for key, info in ARCHETYPES.items():
        svg_content = generate_thumbnail(key, info)
        out_path = os.path.join(THUMBNAIL_DIR, f"{key}.svg")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        size_kb = len(svg_content.encode("utf-8")) / 1024
        print("  Created: %s (%.1f KB) - %s" % (
            f"{key}.svg", size_kb, info["title"]
        ))

    # Generate index JSON
    index = {
        "archetypes": {}
    }
    for key, info in ARCHETYPES.items():
        index["archetypes"][key] = {
            "title": info["title"],
            "steps": info["steps"],
            "color": info["color"],
            "thumbnail_url": f"/api/v1/media/scenario-thumbnail/{key}",
        }

    index_path = os.path.join(THUMBNAIL_DIR, "scenario_archetypes.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print("")
    print("Generated %d scenario thumbnails" % len(ARCHETYPES))
    print("Index file: %s" % index_path)


if __name__ == "__main__":
    generate_all_thumbnails()
