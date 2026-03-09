from app.services.crawling.youtube_crawler import _candidate_search_urls


def test_youtube_candidate_search_urls_prefers_root_then_legacy():
    urls = _candidate_search_urls("パーソナルジム", "JP")

    assert urls[0].startswith("https://adstransparency.google.com/?")
    assert "query=%E3%83%91%E3%83%BC%E3%82%BD%E3%83%8A%E3%83%AB%E3%82%B8%E3%83%A0" in urls[0]
    assert "region=JP" in urls[0]
    assert urls[1].startswith("https://adstransparency.google.com/advertiser?")
