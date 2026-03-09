from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.services.media_extraction import MediaExtractor
from scripts.backfill_media_urls import _access_tier as backfill_access_tier
from scripts.backfill_media_urls import _classify_reason
from scripts.update_media_status import _determine_status
from bs4 import BeautifulSoup


def _build_ad(**overrides) -> Ad:
    base = {
        "platform": AdPlatformEnum.FACEBOOK,
        "status": AdStatusEnum.PENDING,
    }
    base.update(overrides)
    return Ad(**base)


def test_backfill_access_tier_snapshot_only() -> None:
    ad = _build_ad(snapshot_url="https://example.com/snapshot")
    assert backfill_access_tier(ad) == "snapshot_only"


def test_backfill_access_tier_downloadable_with_lp() -> None:
    ad = _build_ad(image_s3_key="images/a.jpg", destination_url="https://lp.example.com")
    assert backfill_access_tier(ad) == "downloadable_with_lp"


def test_determine_status_failed_for_blocked_without_snapshot() -> None:
    ad = _build_ad(ad_metadata={"creative_fetch_reason": "blocked_or_expired"})
    assert _determine_status(ad) == "failed"


def test_classify_reason_maps_forbidden_to_blocked() -> None:
    assert _classify_reason("403 Forbidden") == "blocked_or_expired"


def test_media_extractor_selects_target_meta_card() -> None:
    extractor = MediaExtractor()
    result = extractor._extract_meta_library_result(
        [
            {"ad_id": "1", "image_urls": ["https://example.com/a.jpg"]},
            {
                "ad_id": "2",
                "image_urls": ["https://example.com/b.jpg"],
                "video_urls": ["https://example.com/b.mp4"],
                "poster_url": "https://example.com/b-poster.jpg",
                "destination_url": "https://lp.example.com",
                "body": "hello",
            },
        ],
        "2",
    )
    assert result.creative_type == "video"
    assert result.thumbnail_url == "https://example.com/b-poster.jpg"
    assert result.destination_url == "https://lp.example.com"


def test_parse_render_ad_html_extracts_style_and_data_store_media() -> None:
    extractor = MediaExtractor()
    soup = BeautifulSoup(
        """
        <html><body>
          <div style="background-image:url('https://cdn.example.com/bg.jpg')"></div>
          <img data-store='{"imgSrc":"https://cdn.example.com/card.jpg"}' width="400" height="400" />
          <video data-store='{"videoSrc":"https://cdn.example.com/movie.mp4"}' poster="https://cdn.example.com/poster.jpg"></video>
          <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Flp.example.com%2Foffer"></a>
        </body></html>
        """,
        "html.parser",
    )

    result = extractor._parse_render_ad_html(soup)

    assert result.creative_type == "video"
    assert "https://cdn.example.com/card.jpg" in result.image_urls
    assert "https://cdn.example.com/bg.jpg" in result.image_urls
    assert result.video_urls == ["https://cdn.example.com/movie.mp4"]
    assert result.thumbnail_url == "https://cdn.example.com/poster.jpg"
    assert result.destination_url == "https://lp.example.com/offer"


def test_parse_html_ignores_meta_disclaimer_text() -> None:
    extractor = MediaExtractor()
    soup = BeautifulSoup(
        """
        <html>
          <head>
            <meta property="og:title" content="This ad ran without a required disclaimer." />
            <meta property="og:description" content="This ad ran without a required disclaimer." />
          </head>
          <body></body>
        </html>
        """,
        "html.parser",
    )

    result = extractor._parse_html(soup)

    assert result.ad_title is None
    assert result.ad_text is None


def test_parse_render_ad_html_detects_login_required_gate() -> None:
    extractor = MediaExtractor()
    soup = BeautifulSoup(
        """
        <html><body>
          <div>表示したい場合は、アカウントにログインする必要があります。</div>
        </body></html>
        """,
        "html.parser",
    )

    result = extractor._parse_render_ad_html(soup)

    assert result.restriction_reason == "login_required"


def test_extract_from_dialog_payloads_detects_login_required_gate() -> None:
    extractor = MediaExtractor()

    result = extractor._extract_from_dialog_payloads(
        [
            {
                "text": "広告の詳細\nライブラリID: 198021363096557\n表示したい場合は、アカウントにログインする必要があります。",
                "images": ["https://cdn.example.com/thumb.jpg"],
                "videos": [],
                "links": ["https://www.facebook.com/login/"],
            }
        ],
        "198021363096557",
    )

    assert result.restriction_reason == "login_required"
    assert result.image_urls == ["https://cdn.example.com/thumb.jpg"]
