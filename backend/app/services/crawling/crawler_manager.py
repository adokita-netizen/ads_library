"""Unified crawler manager for multi-platform ad collection."""

import asyncio
from typing import Optional

import structlog

from app.models.ad import AdPlatformEnum
from app.services.crawling.base_crawler import BaseCrawler, CrawledAd
from app.services.crawling.meta_crawler import MetaAdLibraryCrawler
from app.services.crawling.tiktok_crawler import TikTokAdCrawler
from app.services.crawling.youtube_crawler import YouTubeAdCrawler

logger = structlog.get_logger()


class CrawlerManager:
    """Manages multiple platform crawlers and provides unified interface."""

    def __init__(self):
        self._crawlers: dict[str, BaseCrawler] = {}

    def register_crawler(self, platform: str, crawler: BaseCrawler):
        self._crawlers[platform] = crawler

    @classmethod
    def create_default(
        cls,
        meta_token: Optional[str] = None,
        tiktok_token: Optional[str] = None,
        youtube_api_key: Optional[str] = None,
    ) -> "CrawlerManager":
        """Create manager with default crawlers for all platforms."""
        manager = cls()
        manager.register_crawler("facebook", MetaAdLibraryCrawler(access_token=meta_token))
        manager.register_crawler("instagram", MetaAdLibraryCrawler(access_token=meta_token))
        manager.register_crawler("youtube", YouTubeAdCrawler(api_key=youtube_api_key))
        manager.register_crawler("tiktok", TikTokAdCrawler(access_token=tiktok_token))
        return manager

    async def search_all_platforms(
        self,
        query: str,
        platforms: Optional[list[str]] = None,
        category: Optional[str] = None,
        limit_per_platform: int = 20,
    ) -> dict[str, list[CrawledAd]]:
        """Search across all registered platforms concurrently."""
        target_platforms = platforms or list(self._crawlers.keys())
        results: dict[str, list[CrawledAd]] = {}

        tasks = {}
        for platform in target_platforms:
            if platform in self._crawlers:
                tasks[platform] = self._crawlers[platform].search_ads(
                    query=query,
                    category=category,
                    limit=limit_per_platform,
                )

        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for platform, result in zip(tasks.keys(), gathered):
            if isinstance(result, Exception):
                logger.error("platform_search_failed", platform=platform, error=str(result))
                results[platform] = []
            else:
                results[platform] = result

        total = sum(len(ads) for ads in results.values())
        logger.info("multi_platform_search", query=query, total_results=total, platforms=list(results.keys()))

        return results

    async def search_competitor(
        self,
        competitor_name: str,
        platforms: Optional[list[str]] = None,
        limit_per_platform: int = 30,
    ) -> dict[str, list[CrawledAd]]:
        """Search for all ads by a specific competitor."""
        target_platforms = platforms or list(self._crawlers.keys())
        results: dict[str, list[CrawledAd]] = {}

        tasks = {}
        for platform in target_platforms:
            if platform in self._crawlers:
                tasks[platform] = self._crawlers[platform].get_advertiser_ads(
                    advertiser_name=competitor_name,
                    limit=limit_per_platform,
                )

        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for platform, result in zip(tasks.keys(), gathered):
            if isinstance(result, Exception):
                logger.error("competitor_search_failed", platform=platform, error=str(result))
                results[platform] = []
            else:
                results[platform] = result

        return results

    async def get_trending_ads(
        self,
        category: str,
        platforms: Optional[list[str]] = None,
        limit_per_platform: int = 20,
    ) -> dict[str, list[CrawledAd]]:
        """Get trending ads for a specific category."""
        category_queries = {
            "ec_d2c": "通販 D2C 広告",
            "beauty": "美容 コスメ 広告",
            "health": "健康 サプリ 広告",
            "app": "アプリ ダウンロード 広告",
            "finance": "金融 投資 広告",
            "education": "教育 スクール 広告",
            "gaming": "ゲーム アプリ 広告",
            "food": "食品 グルメ 広告",
        }

        query = category_queries.get(category, f"{category} 広告")
        return await self.search_all_platforms(
            query=query,
            platforms=platforms,
            category=category,
            limit_per_platform=limit_per_platform,
        )

    def to_platform_enum(self, platform: str) -> AdPlatformEnum:
        """Convert string platform to enum."""
        mapping = {
            "facebook": AdPlatformEnum.FACEBOOK,
            "instagram": AdPlatformEnum.INSTAGRAM,
            "youtube": AdPlatformEnum.YOUTUBE,
            "tiktok": AdPlatformEnum.TIKTOK,
            "x_twitter": AdPlatformEnum.X_TWITTER,
            "line": AdPlatformEnum.LINE,
            "yahoo": AdPlatformEnum.YAHOO,
        }
        return mapping.get(platform, AdPlatformEnum.OTHER)

    async def close_all(self):
        """Close all crawler connections."""
        for crawler in self._crawlers.values():
            await crawler.close()
