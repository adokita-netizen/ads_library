from datetime import date

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.analysis import AdAnalysis, TextDetection
from app.tasks.metrics_tasks import build_topic_gap_report, enrich_topic_metadata_for_ads


def _mk_ad(external_id: str, title: str, description: str = "", metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        description=description,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        advertiser_name="テスト広告主",
        ad_metadata=metadata or {},
    )


def test_a48_enrich_topic_metadata_uses_copy_ocr_and_lp_sources(session):
    ad = _mk_ad(
        "a48_topic_1",
        "GLP-1で始める医療ダイエット",
        description="オンライン診療で継続しやすい",
        metadata={"lp_keywords": ["肥満外来", "リベルサス"]},
    )
    analysis = AdAnalysis(ad=ad)
    detection = TextDetection(
        analysis=analysis,
        frame_number=1,
        timestamp_seconds=0.5,
        text="肥満外来で相談受付中",
        confidence=0.93,
        language="ja",
        bbox_x=0.1,
        bbox_y=0.1,
        bbox_width=0.3,
        bbox_height=0.1,
    )
    session.add_all([ad, analysis, detection])
    session.commit()

    updated = enrich_topic_metadata_for_ads(session, target_date=date(2026, 3, 7))
    session.commit()
    session.refresh(ad)
    meta = ad.ad_metadata or {}

    assert updated >= 1
    assert meta["topic_label"] == "medical_diet"
    assert meta["topic_tags"][0] == "medical_diet"
    assert meta["topic_confidence"] >= 0.6
    assert meta["needs_topic_review"] is False
    assert "glp-1" in [term.lower() for term in meta["matched_terms"]]
    assert "glp-1" in [term.lower() for term in meta["topic_evidence"]]
    assert "appeal_medical_authority" in meta["hit_drivers"]
    assert "visual_text_overlay" in meta["hit_drivers"]
    assert isinstance(meta["topic_candidates"], list) and meta["topic_candidates"]

    suggestion_rows = meta["topic_dictionary_suggestions"]
    assert suggestion_rows[0]["date"] == "2026-03-07"
    assert suggestion_rows[0]["topic_label"] == "medical_diet"
    assert "肥満外来" in suggestion_rows[0]["terms"]


def test_a48_topic_gap_report_flags_missing_classifications(session):
    finance_miss = _mk_ad(
        "a48_gap_1",
        "新NISAで資産運用を始める",
        metadata={"topic_label": "education"},
    )
    education_ok = _mk_ad(
        "a48_gap_2",
        "英語スクールの無料講座",
        metadata={"topic_label": "education"},
    )
    session.add_all([finance_miss, education_ok])
    session.commit()

    report = build_topic_gap_report(session, target_date=date(2026, 3, 7), false_negative_limit=10)

    finance = next(item for item in report["categories"] if item["topic_label"] == "finance")
    assert report["date"] == "2026-03-07"
    assert finance["expected_volume"] >= 1
    assert finance["classified_volume"] == 0
    assert finance["gap"] >= 1
    assert any(candidate["ad_id"] == finance_miss.id for candidate in finance["false_negative_candidates"])
    assert report["false_negative_report"]["total_candidates"] >= 1
    top_candidate = report["false_negative_report"]["top_candidates"][0]
    assert top_candidate["expected_topic"] == "finance"
    assert "detected_topics" in top_candidate
    assert "hit_drivers" in top_candidate
    assert any(alert["topic_label"] == "finance" for alert in report["alerts"])
