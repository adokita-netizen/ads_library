from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.services import crawl_knowledge_pipeline as knowledge_mod
from app.tasks import crawl_tasks


def _mk_ad(external_id: str, title: str, metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_a43_persist_crawl_knowledge_snapshot_writes_topic_rows(tmp_path):
    knowledge_mod.KNOWLEDGE_BASE_FILE = tmp_path / "topic_knowledge_base.json"
    knowledge_mod.KNOWLEDGE_RUNS_FILE = tmp_path / "crawl_knowledge_runs.json"

    ads = [
        _mk_ad(
            "a43_1",
            "GLP-1",
            metadata={
                "topic_tags": ["medical_diet"],
                "topic_evidence": ["GLP-1", "自由診療"],
                "hit_drivers": ["appeal_medical_authority", "offer_trial"],
            },
        ),
        _mk_ad(
            "a43_2",
            "NISA",
            metadata={
                "topic_tags": ["finance"],
                "topic_evidence": ["新NISA", "資産運用"],
                "hit_drivers": ["appeal_price"],
            },
        ),
    ]
    ads[0].id = 101
    ads[1].id = 102

    snapshot = knowledge_mod.persist_crawl_knowledge_snapshot(
        ads,
        source="scheduled",
        trigger_job_id="job-a43-1",
        query="glp-1",
        schedule_window="morning",
        priority="high",
    )

    assert snapshot["source"] == "scheduled"
    assert snapshot["schedule_window"] == "morning"
    assert snapshot["scanned_ads"] == 2
    assert any(row["topic"] == "medical_diet" for row in snapshot["knowledge_rows"])
    assert any(item["driver"] == "appeal_medical_authority" for item in snapshot["dictionary_candidate_summary"]["strong_hit_drivers"])
    assert knowledge_mod.KNOWLEDGE_BASE_FILE.exists()
    assert knowledge_mod.KNOWLEDGE_RUNS_FILE.exists()


def test_a43_live_ingestion_wave_queues_scheduled_priority(monkeypatch):
    class _DummySession:
        def close(self):
            return None

    queued = []
    monkeypatch.setattr(crawl_tasks, "SyncSessionLocal", lambda: _DummySession())
    monkeypatch.setattr(crawl_tasks, "get_connected_platforms", lambda: ["facebook", "instagram"])
    monkeypatch.setattr(crawl_tasks, "get_today_keywords", lambda prioritize_stale, session, limit: ["glp-1", "nisa"])
    monkeypatch.setattr(crawl_tasks, "is_duplicate_crawl", lambda session, keyword, hours=6: False)
    monkeypatch.setattr(crawl_tasks, "queue_incomplete_fresh_ads", lambda session, limit: {"queued": 0, "ad_ids": [], "reason_counts": {}})
    monkeypatch.setattr(crawl_tasks, "_collect_recent_query_stats", lambda session, hours=72: {})
    monkeypatch.setattr(
        crawl_tasks.crawl_ads_task,
        "apply_async",
        lambda kwargs: queued.append(kwargs),
    )

    res = crawl_tasks.run_live_ingestion_wave_task(
        None,
        platforms=["facebook"],
        keyword_limit=2,
        limit_per_platform=10,
        country="JP",
        queue_backfill=True,
    )

    assert res["status"] == "queued"
    assert len(queued) == 2
    assert all(item["trigger_source"] == "scheduled" for item in queued)
    assert all(item["priority"] == "high" for item in queued)
    assert all(item["schedule_window"] in {"morning", "noon", "night"} for item in queued)


def test_a43_inventory_seed_keywords_prefers_japanese_real_inventory():
    ads = [
        _mk_ad(
            "a43_kw_1",
            "脂肪冷却 まずは無料カウンセリング",
            metadata={"product_name": "脂肪冷却", "topic_label": "医療ダイエット"},
        ),
        _mk_ad(
            "a43_kw_2",
            "英語 only creative",
            metadata={"product_name": "English product"},
        ),
    ]
    ads[0].advertiser_name = "渋谷メディカルダイエット"
    ads[0].brand_name = "メディカルダイエット"
    ads[1].advertiser_name = "English advertiser"

    class _FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return ads

    class _FakeSession:
        def query(self, *_args, **_kwargs):
            return _FakeQuery()

    keywords = crawl_tasks.get_inventory_seed_keywords(_FakeSession(), limit=6)

    assert "脂肪冷却" in keywords
    assert "メディカルダイエット" in keywords
    assert "English product" not in keywords
