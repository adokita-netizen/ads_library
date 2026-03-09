from app.services.crawling.base_crawler import CrawledAd
from app.tasks import crawl_tasks
from app.utils.text import ad_market_is_japanese


def test_japanese_market_detection_accepts_japan_landing_page_signals():
    assert ad_market_is_japanese(
        "Brightening Serum",
        "New arrival",
        urls=["https://www.kao-kirei.com/ja/official/sofina-ip/products/skintoningserum/?cid=ip_toningserum_insta_2602a"],
        metadata={"language": "unknown"},
    ) is True


def test_japanese_market_detection_accepts_delivery_region_metadata():
    assert ad_market_is_japanese(
        "Summer sale",
        "Limited offer",
        metadata={
            "delivery_by_region": [
                {"region": "Japan", "percentage": 100},
            ],
            "ad_reached_countries": ["JP"],
        },
    ) is True


def test_crawl_task_japanese_market_filter_keeps_jp_targeted_ads_without_japanese_copy():
    ad = CrawledAd(
        external_id="meta-1",
        platform="facebook",
        title="Summer campaign",
        description="Shop now",
        advertiser_name="Medicube Global",
        destination_url="https://example.com/ja-jp/storefront",
        metadata={
            "display_url": "example.com/ja-jp/storefront",
            "ad_reached_countries": ["JP"],
        },
    )

    ad.metadata["japanese_ratio"] = crawl_tasks._crawl_ad_japanese_ratio(ad)

    assert crawl_tasks._is_japanese_market_ad(ad) is True


def test_crawl_task_japanese_market_filter_rejects_clear_non_japanese_ads():
    ad = CrawledAd(
        external_id="meta-2",
        platform="facebook",
        title="Texas tax relief",
        description="Apply today",
        advertiser_name="US Finance Group",
        destination_url="https://us.example.com/apply",
        metadata={
            "language": "en",
            "ad_reached_countries": ["US"],
        },
    )

    ad.metadata["japanese_ratio"] = crawl_tasks._crawl_ad_japanese_ratio(ad)

    assert crawl_tasks._is_japanese_market_ad(ad) is False
