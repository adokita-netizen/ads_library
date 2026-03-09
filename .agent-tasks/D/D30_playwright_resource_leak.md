# D30: Playwright ブラウザリソースリーク修正

## 問題
- `media_extraction.py` の例外パスで `browser.close()` が呼ばれない → プロセスゾンビ化
- HTTP事前チェック (20s) と Playwright (20s) のタイムアウトが同じ → HTTP失敗後にPlaywright試行で合計40s
- コンテキスト（ブラウザタブ）の close 漏れ

## 対象ファイル
- `backend/app/services/media_extraction.py`

## 修正

### 1. try-finally での確実な close
```python
async def _extract_with_playwright(self, url: str) -> dict:
    browser = None
    context = None
    try:
        browser = await self.playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, timeout=30000)
        # ... extraction logic ...
        return result
    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
```

### 2. タイムアウトの最適化
```python
# HTTP事前チェック: 短めに（失敗前提で素早くPlaywrightへ移行）
HTTP_TIMEOUT = 10  # 20s → 10s

# Playwright: 十分な時間を確保
PLAYWRIGHT_TIMEOUT = 30000  # 20s → 30s（動画読み込み考慮）

# 全体タイムアウト: Lambda/ECSの制限に余裕を持たせる
TOTAL_TIMEOUT = 50  # HTTP(10) + Playwright(30) + 余裕(10)
```

### 3. Playwright コンテキストマネージャ化
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _browser_session(self):
    """ブラウザセッションを安全に管理"""
    browser = await self.playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    )
    try:
        context = await browser.new_context()
        try:
            yield context
        finally:
            await context.close()
    finally:
        await browser.close()
```

## 制約
- `media_extraction.py` のみ修正
- 抽出ロジック自体は変更しない（リソース管理のみ）
