# D-R2-4: LP Crawler (D12)
# 優先度: P1 | 前提: なし | ブロック: なし

## 目的
destination_url (LP) に対してPlaywright でアクセスし、
スクリーンショット + メタ情報を取得する。

## 対象ファイル (全て Agent D 専有)
- 新規: `backend/app/services/crawling/lp_crawler.py`
- 新規: `backend/scripts/crawl_landing_pages.py`

## 実装

### LPCrawler サービス
```python
# backend/app/services/crawling/lp_crawler.py

import asyncio
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class LPCrawler:
    async def crawl_lp(self, url: str, ad_id: int) -> dict:
        """LP をクロールし、メタ情報 + スクリーンショットを取得"""
        result = {
            "url": url,
            "ad_id": ad_id,
            "status": "unknown",
            "title": None,
            "description": None,
            "og_image": None,
            "screenshot_path": None,
            "redirect_url": None,
            "status_code": None,
            "load_time_ms": None,
            "error": None,
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--single-process"]
            )
            try:
                page = await browser.new_page(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                import time
                start = time.time()

                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)  # JS rendering wait

                load_time = int((time.time() - start) * 1000)
                result["load_time_ms"] = load_time
                result["status_code"] = response.status if response else None
                result["redirect_url"] = page.url if page.url != url else None

                if response and response.status < 400:
                    result["status"] = "alive"

                    # メタ情報取得
                    result["title"] = await page.title()
                    result["description"] = await page.evaluate("""
                        () => {
                            const meta = document.querySelector('meta[name="description"]') ||
                                         document.querySelector('meta[property="og:description"]');
                            return meta ? meta.content : null;
                        }
                    """)
                    result["og_image"] = await page.evaluate("""
                        () => {
                            const meta = document.querySelector('meta[property="og:image"]');
                            return meta ? meta.content : null;
                        }
                    """)

                    # スクリーンショット
                    screenshot_path = f"/tmp/lp_screenshot_{ad_id}.png"
                    await page.screenshot(path=screenshot_path, full_page=False)
                    result["screenshot_path"] = screenshot_path

                elif response and response.status == 404:
                    result["status"] = "dead"
                elif response and response.status in (301, 302):
                    result["status"] = "redirect"
                else:
                    result["status"] = "error"

            except Exception as e:
                result["status"] = "unreachable"
                result["error"] = str(e)
                logger.warning(f"LP crawl failed for ad_id={ad_id}: {e}")
            finally:
                await browser.close()

        return result
```

### バッチスクリプト
```python
# backend/scripts/crawl_landing_pages.py

import sys
import asyncio
sys.path.insert(0, ".")

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.services.crawling.lp_crawler import LPCrawler
from sqlalchemy.orm.attributes import flag_modified

async def main():
    session = SyncSessionLocal()
    crawler = LPCrawler()

    # destination_url があり、lp_status が未設定の広告
    ads = session.query(Ad).filter(
        Ad.destination_url != None,
        Ad.destination_url != '',
    ).all()

    # 既にチェック済みをスキップ
    ads_to_check = []
    for ad in ads:
        meta = ad.ad_metadata or {}
        if not meta.get("lp_crawled"):
            ads_to_check.append(ad)

    print(f"LPs to crawl: {len(ads_to_check)} / {len(ads)}")

    success = 0
    failed = 0

    for i, ad in enumerate(ads_to_check):
        print(f"[{i+1}/{len(ads_to_check)}] Crawling LP for ad_id={ad.id}: {ad.destination_url[:60]}...")

        result = await crawler.crawl_lp(ad.destination_url, ad.id)

        # ad_metadata に結果を保存
        meta = dict(ad.ad_metadata or {})
        meta["lp_crawled"] = True
        meta["lp_status"] = result["status"]
        meta["lp_title"] = result["title"]
        meta["lp_description"] = result["description"]
        meta["lp_og_image"] = result["og_image"]
        meta["lp_load_time_ms"] = result["load_time_ms"]
        meta["lp_status_code"] = result["status_code"]
        if result["redirect_url"]:
            meta["lp_redirect_url"] = result["redirect_url"]
        if result["error"]:
            meta["lp_error"] = result["error"]

        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

        # TODO: スクリーンショットを S3 にアップロード
        # if result["screenshot_path"]:
        #     s3_key = upload_to_s3(result["screenshot_path"], f"lp/{ad.id}.png")
        #     meta["lp_screenshot_s3_key"] = s3_key

        if result["status"] == "alive":
            success += 1
        else:
            failed += 1

        # Rate limiting: 2秒間隔
        await asyncio.sleep(2)

        # 10件ごとにコミット
        if (i + 1) % 10 == 0:
            session.commit()
            print(f"  Committed {i+1} records")

    session.commit()
    session.close()

    print(f"\nResults: {success} alive, {failed} failed/dead/unreachable")

if __name__ == "__main__":
    asyncio.run(main())
```

## 実行
```bash
cd C:/Users/ishit/ads_library/backend
python -m scripts.crawl_landing_pages
```

## 完了条件
- [ ] LPCrawler が Playwright で LP にアクセスできる
- [ ] title, description, og:image が取得される
- [ ] スクリーンショットが取得される
- [ ] ステータス (alive/dead/redirect/unreachable) が ad_metadata に記録される
- [ ] バッチスクリプトが全広告を処理できる
- [ ] status.md に結果記録 (alive/dead/redirect/unreachable の件数)
