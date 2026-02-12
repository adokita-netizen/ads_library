"""Tests for all 11 platform crawlers - import, instantiation, interface compliance."""

import pytest

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd
from app.services.crawling.youtube_crawler import YouTubeAdCrawler
from app.services.crawling.tiktok_crawler import TikTokAdCrawler
from app.services.crawling.meta_crawler import MetaAdLibraryCrawler
from app.services.crawling.yahoo_crawler import YahooAdCrawler
from app.services.crawling.x_twitter_crawler import XTwitterAdCrawler
from app.services.crawling.line_crawler import LineAdCrawler
from app.services.crawling.pinterest_crawler import PinterestAdCrawler
from app.services.crawling.smartnews_crawler import SmartNewsAdCrawler
from app.services.crawling.google_ads_crawler import GoogleAdsCrawler
from app.services.crawling.gunosy_crawler import GunosyAdCrawler
from app.services.crawling.crawler_manager import CrawlerManager


class TestCrawlerImports:
    """Verify all crawlers can be imported without errors."""

    def test_import_base_crawler(self):
        assert BaseCrawler is not None
        assert CrawledAd is not None

    def test_import_youtube(self):
        assert YouTubeAdCrawler is not None

    def test_import_tiktok(self):
        assert TikTokAdCrawler is not None

    def test_import_meta(self):
        assert MetaAdLibraryCrawler is not None

    def test_import_yahoo(self):
        assert YahooAdCrawler is not None

    def test_import_x_twitter(self):
        assert XTwitterAdCrawler is not None

    def test_import_line(self):
        assert LineAdCrawler is not None

    def test_import_pinterest(self):
        assert PinterestAdCrawler is not None

    def test_import_smartnews(self):
        assert SmartNewsAdCrawler is not None

    def test_import_google_ads(self):
        assert GoogleAdsCrawler is not None

    def test_import_gunosy(self):
        assert GunosyAdCrawler is not None

    def test_import_crawler_manager(self):
        assert CrawlerManager is not None


class TestCrawlerInstantiation:
    """Test crawler instantiation with and without API keys."""

    def test_youtube_no_key(self):
        crawler = YouTubeAdCrawler()
        assert isinstance(crawler, BaseCrawler)
        assert crawler.api_key is None

    def test_youtube_with_key(self):
        crawler = YouTubeAdCrawler(api_key="test_key")
        assert crawler.api_key == "test_key"

    def test_tiktok_no_token(self):
        crawler = TikTokAdCrawler()
        assert isinstance(crawler, BaseCrawler)
        assert crawler.access_token is None

    def test_meta_no_token(self):
        crawler = MetaAdLibraryCrawler()
        assert isinstance(crawler, BaseCrawler)

    def test_yahoo_no_key(self):
        crawler = YahooAdCrawler()
        assert isinstance(crawler, BaseCrawler)
        assert crawler.api_key is None

    def test_yahoo_with_key(self):
        crawler = YahooAdCrawler(api_key="key", api_secret="secret")
        assert crawler.api_key == "key"
        assert crawler.api_secret == "secret"

    def test_x_twitter_no_token(self):
        crawler = XTwitterAdCrawler()
        assert isinstance(crawler, BaseCrawler)
        assert crawler.bearer_token is None

    def test_line_no_token(self):
        crawler = LineAdCrawler()
        assert isinstance(crawler, BaseCrawler)

    def test_pinterest_no_token(self):
        crawler = PinterestAdCrawler()
        assert isinstance(crawler, BaseCrawler)

    def test_smartnews_no_key(self):
        crawler = SmartNewsAdCrawler()
        assert isinstance(crawler, BaseCrawler)
        assert crawler.api_key is None

    def test_google_ads_no_token(self):
        crawler = GoogleAdsCrawler()
        assert isinstance(crawler, BaseCrawler)
        assert crawler.developer_token is None

    def test_gunosy_no_key(self):
        crawler = GunosyAdCrawler()
        assert isinstance(crawler, BaseCrawler)
        assert crawler.api_key is None


class TestCrawlerInterface:
    """Verify all crawlers implement the required abstract methods."""

    @pytest.fixture(params=[
        YouTubeAdCrawler,
        TikTokAdCrawler,
        MetaAdLibraryCrawler,
        YahooAdCrawler,
        XTwitterAdCrawler,
        LineAdCrawler,
        PinterestAdCrawler,
        SmartNewsAdCrawler,
        GoogleAdsCrawler,
        GunosyAdCrawler,
    ])
    def crawler_cls(self, request):
        return request.param

    def test_has_search_ads(self, crawler_cls):
        crawler = crawler_cls()
        assert hasattr(crawler, "search_ads")
        assert callable(crawler.search_ads)

    def test_has_get_ad_details(self, crawler_cls):
        crawler = crawler_cls()
        assert hasattr(crawler, "get_ad_details")
        assert callable(crawler.get_ad_details)

    def test_has_get_advertiser_ads(self, crawler_cls):
        crawler = crawler_cls()
        assert hasattr(crawler, "get_advertiser_ads")
        assert callable(crawler.get_advertiser_ads)

    def test_has_download_video(self, crawler_cls):
        crawler = crawler_cls()
        assert hasattr(crawler, "download_video")

    def test_has_close(self, crawler_cls):
        crawler = crawler_cls()
        assert hasattr(crawler, "close")


class TestCrawledAd:
    """Test the CrawledAd dataclass."""

    def test_create_crawled_ad(self):
        ad = CrawledAd(
            external_id="test_123",
            platform="youtube",
            title="Test Ad",
            description="Test description",
            advertiser_name="Test Co",
        )
        assert ad.external_id == "test_123"
        assert ad.platform == "youtube"
        assert ad.tags == []
        assert ad.metadata == {}

    def test_unique_hash(self):
        ad1 = CrawledAd(external_id="123", platform="youtube")
        ad2 = CrawledAd(external_id="123", platform="youtube")
        ad3 = CrawledAd(external_id="123", platform="tiktok")

        assert ad1.unique_hash == ad2.unique_hash
        assert ad1.unique_hash != ad3.unique_hash

    def test_default_values(self):
        ad = CrawledAd(external_id="x", platform="test")
        assert ad.title is None
        assert ad.video_url is None
        assert ad.view_count is None
        assert ad.duration_seconds is None


class TestCrawlerManager:
    """Test CrawlerManager functionality."""

    def test_create_default_manager(self):
        manager = CrawlerManager.create_default()
        assert isinstance(manager, CrawlerManager)

    def test_all_platforms_registered(self):
        manager = CrawlerManager.create_default()
        platforms = manager.registered_platforms
        assert "facebook" in platforms
        assert "instagram" in platforms
        assert "youtube" in platforms
        assert "tiktok" in platforms
        assert "yahoo" in platforms
        assert "x_twitter" in platforms
        assert "line" in platforms
        assert "pinterest" in platforms
        assert "smartnews" in platforms
        assert "google_ads" in platforms
        assert "gunosy" in platforms

    def test_platform_count(self):
        manager = CrawlerManager.create_default()
        # 11 platforms (facebook + instagram share Meta, but registered separately)
        assert len(manager.registered_platforms) == 11

    def test_to_platform_enum(self):
        from app.models.ad import AdPlatformEnum
        manager = CrawlerManager.create_default()

        assert manager.to_platform_enum("youtube") == AdPlatformEnum.YOUTUBE
        assert manager.to_platform_enum("pinterest") == AdPlatformEnum.PINTEREST
        assert manager.to_platform_enum("smartnews") == AdPlatformEnum.SMARTNEWS
        assert manager.to_platform_enum("google_ads") == AdPlatformEnum.GOOGLE_ADS
        assert manager.to_platform_enum("gunosy") == AdPlatformEnum.GUNOSY
        assert manager.to_platform_enum("unknown") == AdPlatformEnum.OTHER

    def test_register_custom_crawler(self):
        manager = CrawlerManager()
        crawler = YouTubeAdCrawler()
        manager.register_crawler("custom_platform", crawler)
        assert "custom_platform" in manager.registered_platforms
