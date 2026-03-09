from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.services.meta_creative_extraction_ops import (
    build_extraction_audit_row,
    build_meta_creative_extraction_report,
    queue_low_quality_reextractions,
)


def _mk_ad(external_id: str, title: str, metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        advertiser_name="広告主",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_a47_build_extraction_audit_row_normalizes_source_and_flags_low_quality():
    ad = _mk_ad(
        "a47_1",
        "広告",
        metadata={
            "creative_fetch_source": "meta_api",
            "extract_quality_score": 20,
            "image_width": 200,
            "image_height": 200,
            "creative_fetch_reason": "download_failed",
        },
    )
    row = build_extraction_audit_row(ad)
    assert row["extract_source"] == "api_render_ad"
    assert row["needs_reextract"] is True
    assert row["failure_reason"] == "download_failed"


def test_a47_queue_low_quality_reextractions_marks_retry(session):
    low = _mk_ad(
        "a47_low",
        "広告",
        metadata={"extract_quality_score": 15, "creative_fetch_source": "snapshot_parse"},
    )
    session.add(low)
    session.commit()

    result = queue_low_quality_reextractions(session, min_quality=40)
    session.commit()
    session.refresh(low)

    assert low.id in result["queued_ad_ids"]
    assert low.ad_metadata["needs_media_retry"] is True
    assert low.ad_metadata["preferred_extract_source_order"][0] == "api_render_ad"


def test_a47_build_meta_creative_extraction_report_summarizes_failures(session, monkeypatch, tmp_path):
    from app.services import meta_creative_extraction_ops as ops

    monkeypatch.setattr(ops, "_REPORTS_FILE", tmp_path / "meta_creative_extraction_reports.json")
    ok = _mk_ad("a47_ok", "広告", metadata={"extract_quality_score": 80})
    ok.image_url = "https://example.com/image.jpg"
    ok.description = "本文あり"
    bad = _mk_ad(
        "a47_bad",
        "広告",
        metadata={
            "extract_quality_score": 0,
            "creative_fetch_reason": "download_failed",
            "creative_fetch_source": "snapshot_parse",
        },
    )
    session.add_all([ok, bad])
    session.commit()

    report = build_meta_creative_extraction_report(session, persist=True, top_n=10)
    assert report["summary"]["total_ads"] == 2
    assert report["summary"]["needs_reextract_count"] >= 1
    assert report["failure_reason_ranking"][0]["reason"] in {"download_failed", "text_missing", "incomplete_creative"}
