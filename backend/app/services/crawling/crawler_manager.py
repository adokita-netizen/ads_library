"""Unified crawler manager for multi-platform ad collection."""

import asyncio
from typing import Optional

import structlog

from app.models.ad import AdPlatformEnum
from app.services.crawling.base_crawler import BaseCrawler, CrawledAd
from app.services.crawling.meta_crawler import MetaAdLibraryCrawler
from app.services.crawling.tiktok_crawler import TikTokAdCrawler
from app.services.crawling.youtube_crawler import YouTubeAdCrawler
from app.services.crawling.yahoo_crawler import YahooAdCrawler
from app.services.crawling.x_twitter_crawler import XTwitterAdCrawler
from app.services.crawling.line_crawler import LineAdCrawler
from app.services.crawling.pinterest_crawler import PinterestAdCrawler
from app.services.crawling.smartnews_crawler import SmartNewsAdCrawler
from app.services.crawling.google_ads_crawler import GoogleAdsCrawler
from app.services.crawling.gunosy_crawler import GunosyAdCrawler

logger = structlog.get_logger()


class CrawlerManager:
    """Manages multiple platform crawlers and provides unified interface."""

    def __init__(self):
        self._crawlers: dict[str, BaseCrawler] = {}

    def register_crawler(self, platform: str, crawler: BaseCrawler):
        self._crawlers[platform] = crawler

    @property
    def registered_platforms(self) -> list[str]:
        """Return list of registered platform names."""
        return list(self._crawlers.keys())

    @classmethod
    def create_default(
        cls,
        meta_token: Optional[str] = None,
        tiktok_token: Optional[str] = None,
        youtube_api_key: Optional[str] = None,
        x_twitter_bearer: Optional[str] = None,
        line_token: Optional[str] = None,
        yahoo_api_key: Optional[str] = None,
        yahoo_api_secret: Optional[str] = None,
        pinterest_token: Optional[str] = None,
        smartnews_api_key: Optional[str] = None,
        google_ads_developer_token: Optional[str] = None,
        google_ads_client_id: Optional[str] = None,
        google_ads_client_secret: Optional[str] = None,
        google_ads_refresh_token: Optional[str] = None,
        gunosy_api_key: Optional[str] = None,
    ) -> "CrawlerManager":
        """Create manager with default crawlers for all supported platforms.

        All crawlers work in scraping-fallback mode even without API tokens.
        Providing tokens enables richer API-based data collection.
        """
        manager = cls()

        # Meta (Facebook + Instagram)
        manager.register_crawler("facebook", MetaAdLibraryCrawler(access_token=meta_token))
        manager.register_crawler("instagram", MetaAdLibraryCrawler(access_token=meta_token))

        # YouTube (Google Ads Transparency - video only)
        manager.register_crawler("youtube", YouTubeAdCrawler(api_key=youtube_api_key))

        # TikTok
        manager.register_crawler("tiktok", TikTokAdCrawler(access_token=tiktok_token))

        # Yahoo! JAPAN
        manager.register_crawler("yahoo", YahooAdCrawler(
            api_key=yahoo_api_key,
            api_secret=yahoo_api_secret,
        ))

        # X (Twitter)
        manager.register_crawler("x_twitter", XTwitterAdCrawler(bearer_token=x_twitter_bearer))

        # LINE
        manager.register_crawler("line", LineAdCrawler(access_token=line_token))

        # Pinterest
        manager.register_crawler("pinterest", PinterestAdCrawler(access_token=pinterest_token))

        # SmartNews
        manager.register_crawler("smartnews", SmartNewsAdCrawler(api_key=smartnews_api_key))

        # Google Ads (search/display/shopping - non-YouTube)
        manager.register_crawler("google_ads", GoogleAdsCrawler(
            developer_token=google_ads_developer_token,
            client_id=google_ads_client_id,
            client_secret=google_ads_client_secret,
            refresh_token=google_ads_refresh_token,
        ))

        # Gunosy
        manager.register_crawler("gunosy", GunosyAdCrawler(api_key=gunosy_api_key))

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
            "pinterest": AdPlatformEnum.PINTEREST,
            "smartnews": AdPlatformEnum.SMARTNEWS,
            "google_ads": AdPlatformEnum.GOOGLE_ADS,
            "gunosy": AdPlatformEnum.GUNOSY,
        }
        return mapping.get(platform, AdPlatformEnum.OTHER)

    async def close_all(self):
        """Close all crawler connections."""
        for crawler in self._crawlers.values():
            await crawler.close()
