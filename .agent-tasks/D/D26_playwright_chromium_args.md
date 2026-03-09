# D26: media_extraction.py Playwright Docker Tuning & Video DL

## Status: READY TO EXECUTE (Step 1 - parallel with A/C)

## Prerequisites
- A29 Dockerfile.worker: ALREADY DONE (Playwright + Chromium installed)
- B33 dispatcher.py fix: ALREADY DONE (send_kwargs pattern)

## Target Files
- `backend/app/services/media_extraction.py` (4 changes)
- `backend/app/tasks/media_tasks.py` (1 change)

---

## Task 1: Chromium args (media_extraction.py L106-108)

**Current code (L106-108):**
```python
browser = await p.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-dev-shm-usage"],
)
```

**Change to:**
```python
browser = await p.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--single-process",
    ],
)
```

**Why:** `--disable-gpu` prevents GPU errors in headless containers. `--single-process` reduces memory in ECS Fargate (256MB-512MB tasks).

---

## Task 2: Page load strategy (media_extraction.py L111)

**Current code (L111):**
```python
await page.goto(url, wait_until="networkidle", timeout=int(self.timeout * 1000))
```

**Change to:**
```python
try:
    await page.goto(url, wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
    await page.wait_for_timeout(3000)
except Exception:
    logger.warning("page_load_timeout", url=url)
```

**Why:** Facebook render_ad pages have persistent background requests that prevent `networkidle` from ever completing. `domcontentloaded` + 3s wait is enough for media content to render.

---

## Task 3: render_ad parser (media_extraction.py - new method)

Add a new method `_parse_render_ad_html()` AFTER `_parse_html()` (after L221):

```python
def _parse_render_ad_html(self, soup: BeautifulSoup) -> ExtractedMedia:
    """Parse Facebook render_ad page (server-rendered, specific structure)."""
    result = ExtractedMedia()

    # render_ad page images: <img> with fbcdn.net src
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src or not src.startswith("http"):
            continue
        if "fbcdn.net" in src or "facebook.com" in src:
            width = img.get("width")
            if width:
                try:
                    if int(width) < 100:
                        continue
                except (ValueError, TypeError):
                    pass
            result.image_urls.append(src)

    # Video in render_ad
    for video in soup.find_all("video"):
        src = video.get("src")
        if src and src.startswith("http"):
            result.video_urls.append(src)
        for source in video.find_all("source"):
            src = source.get("src")
            if src and src.startswith("http"):
                result.video_urls.append(src)

    # Deduplicate
    result.image_urls = list(dict.fromkeys(result.image_urls))
    result.video_urls = list(dict.fromkeys(result.video_urls))

    # Determine type
    if result.video_urls:
        result.creative_type = "video"
    elif len(result.image_urls) > 1:
        result.creative_type = "carousel"
    elif result.image_urls:
        result.creative_type = "image"

    # Text extraction (same as _parse_html)
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        result.ad_text = og_desc["content"].strip()
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        result.ad_title = og_title["content"].strip()

    if not result.thumbnail_url and result.image_urls:
        result.thumbnail_url = result.image_urls[0]

    return result
```

Then update `_extract_via_playwright()` to use it. Change L114-115:

**Current (L113-115):**
```python
html = await page.content()
soup = BeautifulSoup(html, "html.parser")
result = self._parse_html(soup)
```

**Change to:**
```python
html = await page.content()
soup = BeautifulSoup(html, "html.parser")
if "/ads/archive/render_ad/" in url:
    result = self._parse_render_ad_html(soup)
else:
    result = self._parse_html(soup)
```

---

## Task 4: Video download & S3 upload (media_tasks.py)

Add video download AFTER image download block (after L138, before L140).

Insert this code between the image download block and the thumbnail auto-set:

```python
# Download and store video
if extracted.video_urls and not ad.video_s3_key:
    try:
        video_data = _download_sync(extracted.video_urls[0], timeout=60.0)
        if video_data and len(video_data) < 100 * 1024 * 1024:  # 100MB limit
            from app.core.storage import get_storage_client
            storage = get_storage_client()
            url_hash = hashlib.md5(extracted.video_urls[0].encode()).hexdigest()[:12]
            s3_key = f"videos/{uuid.uuid4()}_{url_hash}.mp4"
            storage.upload_bytes(s3_key, video_data, content_type="video/mp4")
            ad.video_s3_key = s3_key
            _save_to_local_cache(video_data, "videos", ad_id)
            logger.info("video_uploaded_to_storage", ad_id=ad_id, s3_key=s3_key, size_mb=round(len(video_data)/1024/1024, 1))
    except Exception as e:
        logger.warning("video_upload_failed", ad_id=ad_id, error=str(e))
```

**NOTE:** `_download_sync` already accepts `timeout` parameter (L424). Pass `timeout=60.0` for video (larger files).

Also: `ad.video_s3_key` column may not exist yet in the Ad model. Check `backend/app/models/ad.py` first. If missing, this is Agent A's responsibility to add (Agent D: read-only on ad.py model structure, but can write to existing media columns).

---

## Constraints
- Edit ONLY `media_extraction.py` and `media_tasks.py`
- Do NOT modify `_parse_html()` (add new `_parse_render_ad_html()` instead)
- Video DL limit: 100MB
- Print statements: English only (cp932 safe)
- Do NOT touch runner.py, dispatcher.py, lambda_handler.py (Agent C's scope)

## Verification
After all 4 tasks, run:
```bash
cd backend && python -c "
from app.services.media_extraction import MediaExtractor
print('MediaExtractor imported OK')
print('Has _parse_render_ad_html:', hasattr(MediaExtractor, '_parse_render_ad_html'))
"
```
