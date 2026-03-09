"""Landing page crawler service used by batch LP crawl scripts/tasks."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright


class LPCrawler:
    """Playwright-based LP crawler that captures page metadata and screenshot."""

    DEFAULT_VIEWPORT = {"width": 1280, "height": 800}
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    async def crawl_lp(self, url: str, ad_id: int, screenshot_dir: str | None = None) -> dict[str, Any]:
        """Crawl one landing page and return normalized metadata."""
        result: dict[str, Any] = {
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

        if not url:
            result["status"] = "unreachable"
            result["error"] = "empty_url"
            return result

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
            )
            try:
                page = await browser.new_page(
                    viewport=self.DEFAULT_VIEWPORT,
                    user_agent=self.DEFAULT_USER_AGENT,
                    locale="ja-JP",
                )

                start = time.time()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                result["load_time_ms"] = int((time.time() - start) * 1000)
                result["status_code"] = response.status if response else None

                if page.url != url:
                    result["redirect_url"] = page.url

                status_code = result["status_code"]
                if status_code is None:
                    result["status"] = "error"
                elif status_code < 400:
                    result["status"] = "alive"
                elif status_code == 404:
                    result["status"] = "dead"
                elif status_code in (301, 302, 307, 308):
                    result["status"] = "redirect"
                else:
                    result["status"] = "error"

                if result["status"] == "alive":
                    result["title"] = await page.title()
                    result["description"] = await page.evaluate(
                        """() => {
                            const meta = document.querySelector('meta[name="description"]')
                                || document.querySelector('meta[property="og:description"]');
                            return meta ? meta.content : null;
                        }"""
                    )
                    result["og_image"] = await page.evaluate(
                        """() => {
                            const meta = document.querySelector('meta[property="og:image"]');
                            return meta ? meta.content : null;
                        }"""
                    )

                    if screenshot_dir:
                        Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
                        screenshot_path = os.path.join(screenshot_dir, f"{ad_id}.png")
                    else:
                        screenshot_path = f"/tmp/lp_screenshot_{ad_id}.png"
                    await page.screenshot(path=screenshot_path, full_page=False)
                    result["screenshot_path"] = screenshot_path

            except Exception as exc:  # pragma: no cover - runtime/network dependent
                result["status"] = "unreachable"
                result["error"] = str(exc)
            finally:
                await browser.close()

        return result
