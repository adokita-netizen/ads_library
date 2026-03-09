from datetime import date

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, MediaExtractionStatus
from app.services import full_cycle_data_taskpack as taskpack


def _mk_ad(
    external_id: str,
    title: str,
    *,
    advertiser_name: str = "広告主",
    metadata: dict | None = None,
    media_status: MediaExtractionStatus | None = None,
) -> Ad:
    ad = Ad(
        external_id=external_id,
        title=title,
        advertiser_name=advertiser_name,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )
    if media_status is not None:
        ad.media_extraction_status = media_status
    return ad


def test_a45_should_trigger_auto_recrawl():
    report = {
        "target_min_ads_per_day": 100,
        "summary": {"target_met_previous_day": False, "previous_day_new_ads": 12},
    }
    assert taskpack.should_trigger_auto_recrawl(report) is True


def test_a45_process_failed_record_queue_marks_retry_and_quarantine(session):
    retry_ad = _mk_ad(
        "a45_retry",
        "GLP-1",
        metadata={"media_retry_count": 1},
        media_status=MediaExtractionStatus.FAILED,
    )
    quarantine_ad = _mk_ad(
        "a45_quarantine",
        "",
        metadata={"media_retry_count": 3, "is_incomplete_record": True, "incomplete_reason": ["missing_title", "missing_destination_url"]},
        media_status=MediaExtractionStatus.FAILED,
    )
    session.add_all([retry_ad, quarantine_ad])
    session.commit()

    result = taskpack.process_failed_record_queue(session)
    session.commit()
    session.refresh(retry_ad)
    session.refresh(quarantine_ad)

    assert retry_ad.id in result["replay_queue_ad_ids"]
    assert retry_ad.ad_metadata["needs_media_retry"] is True
    assert quarantine_ad.id in result["quarantined_ad_ids"]
    assert quarantine_ad.ad_metadata["quarantine_reason"] in {"media_retry_exhausted", "missing_fields_unrecoverable"}


def test_a45_run_full_cycle_taskpack_combines_recovery_dictionary_and_reclassification(session, monkeypatch):
    glp = _mk_ad(
        "a45_glp",
        "GLP-1 医療ダイエット",
        advertiser_name="Clinic A",
        metadata={
            "topic_label": "medical_diet",
            "topic_evidence": ["glp-1", "自由診療"],
            "topic_dictionary_suggestions": [{"date": "2026-03-08", "topic_label": "medical_diet", "terms": ["脂肪凍結", "glp-1"]}],
        },
    )
    aga = _mk_ad(
        "a45_aga",
        "AGA オンライン診療",
        advertiser_name="Clinic B",
        metadata={
            "topic_label": "aga",
            "topic_evidence": ["aga", "ミノキシジル"],
            "topic_dictionary_suggestions": [{"date": "2026-03-08", "topic_label": "aga", "terms": ["ミノキシジル"]}],
        },
    )
    session.add_all([glp, aga])
    session.commit()

    monkeypatch.setattr(
        taskpack,
        "build_ads_volume_health_report",
        lambda session, days, min_ads, target_min_ads_per_day: {
            "target_min_ads_per_day": target_min_ads_per_day,
            "summary": {"target_met_previous_day": False, "previous_day_new_ads": 10},
        },
    )
    monkeypatch.setattr(
        taskpack,
        "build_false_negative_hunt_report",
        lambda session, target_date, false_negative_limit, queue_recrawls: {
            "summary": {"candidate_count": 2},
            "daily_candidates": [{"ad_id": glp.id, "expected_topic": "medical_diet"}],
            "queue_result": {"queued_count": 0},
        },
    )
    monkeypatch.setattr(
        taskpack,
        "build_daily_recovery_plan",
        lambda previous_day_new_ads, target_min_ads_per_day, focus_keywords, execute_recovery, api_base, recovery_limit, timeout_sec: {
            "should_trigger": True,
            "planned_queries": focus_keywords,
        },
    )

    result = taskpack.run_full_cycle_data_taskpack(
        session,
        target_date=date(2026, 3, 8),
        focus_keywords=["GLP-1", "AGA"],
        target_min_ads_per_day=100,
        queue_recrawls=False,
    )

    assert result["auto_recrawl"]["should_trigger"] is True
    assert result["dictionary_update"]["summary"]["candidate_count"] >= 2
    terms = {row["term"] for row in result["dictionary_update"]["candidate_terms"]}
    assert "glp-1" in terms or "脂肪凍結" in terms
    assert result["false_negative_hunt"]["summary"]["candidate_count"] == 2
