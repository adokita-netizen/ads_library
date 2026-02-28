# Agent D Task: Landing Page Deep Crawler & Analyzer

## Goal
Crawl and analyze every LP (landing page) that ads link to. Understand WHAT makes a good LP.

## What to do

### 1. LP crawler script
`backend/scripts/crawl_landing_pages.py`
- For each ad with destination_url:
  - Fetch the LP with requests (follow redirects)
  - Save HTML to `media_cache/lp_html/{ad_id}.html`
  - Take screenshot with Playwright -> `media_cache/lp_screenshots/{ad_id}.png`
  - Measure: load_time, page_size, redirect_count, final_url
  - Extract: title, meta description, og:image, canonical URL
  - Store in ad_metadata["lp_data"]:
    ```json
    {
      "final_url": "https://...",
      "load_time_ms": 1234,
      "page_size_kb": 456,
      "redirect_count": 2,
      "title": "...",
      "meta_description": "...",
      "og_image": "...",
      "has_form": true,
      "has_video": false,
      "has_testimonials": true,
      "has_price": true,
      "has_countdown": false,
      "cta_buttons": ["今すぐ購入", "無料で試す"],
      "color_scheme": ["#FF0000", "#FFFFFF"],
      "screenshot_path": "media_cache/lp_screenshots/123.png"
    }
    ```

### 2. LP structure analyzer
`backend/scripts/analyze_lp_structure.py`
- Parse saved HTML to detect:
  - Form fields (name, email, phone, etc.) -> lead gen vs EC
  - CTA buttons and their text
  - Testimonial sections (detect patterns like "お客様の声")
  - Before/After images
  - Price display and discount indicators
  - FAQ sections
  - Timer/countdown elements
  - Social proof (review counts, star ratings)
  - Video embeds
- Classify LP type: lead_gen, ec_purchase, line_add, app_install, info_page
- Store in ad_metadata["lp_analysis"]

### 3. LP screenshot serving
Add to media.py:
`GET /media/lp-screenshot/{ad_id}` - serve LP screenshot
`GET /media/lp-html/{ad_id}` - serve saved LP HTML (iframe viewable)

### 4. LP comparison
`backend/scripts/compare_lps.py`
- Compare LPs of hit ads vs non-hit ads
- What elements appear more in hit ad LPs?
- Export to `backend/exports/lp_comparison.json`

## Constraints
- English-only print, no rankings.py/frontend changes
- Use Playwright for screenshots (skip if not installed)
- Rate limit: 1 request per second to LPs
- Timeout: 30s per LP
