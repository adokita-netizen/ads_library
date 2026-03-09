# D-R2-3: Media Precision — Aggressive Recovery (D14)
# 優先度: P1 | 前提: D-R2-1 | ブロック: なし

## 目的
video_url = NULL の動画広告に対して、複数手法で URL を回収する。
目標: 動画広告の90%以上で video_url を取得。

## 対象ファイル (全て Agent D 専有)
- `backend/scripts/extract_missing_videos.py` (修正)
- `backend/app/services/media_extraction.py` (修正)

## 現状
- 176件中: video=98件, image=78件
- video_url が取得済み: 98件
- creative_type=video だが video_url=NULL: 要確認

## 抽出手法 (優先度順)

### Method 1: Meta API 直接取得
```python
# Meta Graph API から ad_creative の video_url を取得
# GET /{ad_id}/adcreatives?fields=video_id,effective_object_story_id

async def extract_via_meta_api(ad_id: str, access_token: str) -> str | None:
    url = f"https://graph.facebook.com/v19.0/{ad_id}"
    params = {
        "fields": "creative{video_id,image_url,object_story_spec}",
        "access_token": access_token
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            video_id = data.get("creative", {}).get("video_id")
            if video_id:
                # video_id → video URL
                video_resp = await client.get(
                    f"https://graph.facebook.com/v19.0/{video_id}",
                    params={"fields": "source", "access_token": access_token},
                    timeout=10
                )
                return video_resp.json().get("source")
    return None
```

### Method 2: Facebook render_ad ページ (Playwright)
```python
# D26 で _parse_render_ad_html() 実装済み
# render_ad URL: https://www.facebook.com/ads/archive/render_ad/?id=XXXXX

async def extract_via_render_ad(ad_external_id: str) -> str | None:
    url = f"https://www.facebook.com/ads/archive/render_ad/?id={ad_external_id}"
    # Playwright で開く
    # video タグの src を取得
    # blob: URL の場合はスキップ
    ...
```

### Method 3: OG:video メタタグ
```python
# snapshot_url (Ad Library ページ) から OG メタタグを取得

async def extract_via_og_tag(snapshot_url: str) -> str | None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(snapshot_url, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            # og:video or og:video:url を探す
            import re
            match = re.search(r'<meta\s+property="og:video(?::url)?"\s+content="([^"]+)"', resp.text)
            if match:
                return match.group(1)
    return None
```

### Method 4: iframe 内 video タグ (Playwright)
```python
# Ad Library ページを Playwright で開き、iframe 内の video を取得

async def extract_via_iframe(snapshot_url: str) -> str | None:
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    try:
        await page.goto(snapshot_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # iframe 内の video タグを探す
        frames = page.frames
        for frame in frames:
            video = await frame.query_selector("video source")
            if video:
                src = await video.get_attribute("src")
                if src and not src.startswith("blob:"):
                    return src
    finally:
        await browser.close()
    return None
```

### 統合: 多段フォールバック
```python
async def aggressive_video_recovery(ad) -> str | None:
    """4つの手法を順番に試す"""
    methods = [
        ("meta_api", lambda: extract_via_meta_api(ad.external_id, get_token())),
        ("render_ad", lambda: extract_via_render_ad(ad.external_id)),
        ("og_tag", lambda: extract_via_og_tag(ad.snapshot_url)),
        ("iframe", lambda: extract_via_iframe(ad.snapshot_url)),
    ]

    for method_name, method_fn in methods:
        try:
            result = await method_fn()
            if result:
                logger.info(f"Video recovered via {method_name}: ad_id={ad.id}")
                meta = dict(ad.ad_metadata or {})
                meta["extraction_method"] = method_name
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                return result
        except Exception as e:
            logger.warning(f"{method_name} failed for ad_id={ad.id}: {e}")

    return None
```

## 実行
```bash
cd C:/Users/ishit/ads_library/backend
python -m scripts.extract_missing_videos --aggressive
```

## 完了条件
- [ ] 4つの抽出手法が実装されている
- [ ] 多段フォールバックで順番に試す
- [ ] 抽出成功時に extraction_method を ad_metadata に記録
- [ ] 動画広告の video_url 取得率: 90%以上
- [ ] 回収率レポートを status.md に記録
