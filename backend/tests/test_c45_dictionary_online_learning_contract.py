from contextlib import contextmanager

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum


def _import_rankings_module():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints import rankings
    return rankings


@contextmanager
def _session_scope(session):
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


def _mk_ad(external_id: str, title: str, metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_dictionary_suggest_returns_candidates(session, monkeypatch, tmp_path):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))
    monkeypatch.setattr(rankings, "_DICTIONARY_REVIEWS_FILE", tmp_path / "reviews.json")
    monkeypatch.setattr(rankings, "_KNOWLEDGE_SNAPSHOTS_FILE", tmp_path / "snapshots.json")

    ad = _mk_ad(
        "c45_suggest_1",
        "GLP-1 モニター募集",
        metadata={"topic_label": "medical_diet", "topic_evidence": ["脂肪凍結"]},
    )
    session.add(ad)
    session.commit()

    body = rankings._DictionarySuggestBody(topic_labels=["medical_diet"], limit=10)
    res = rankings.suggest_dictionary_terms(body)
    assert "candidate_terms" in res
    assert any(
        c["topic_label"] == "medical_diet" and c["term"] == "脂肪凍結"
        for c in res["candidate_terms"]
    )


def test_dictionary_review_adopt_persists_and_affects_reclassification(monkeypatch, tmp_path):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "_DICTIONARY_REVIEWS_FILE", tmp_path / "reviews.json")
    monkeypatch.setattr(rankings, "_KNOWLEDGE_SNAPSHOTS_FILE", tmp_path / "snapshots.json")

    adopted_term = "脂肪凍結"
    topic = "medical_diet"
    words = rankings._TOPIC_KEYWORDS.setdefault(topic, [])
    already_present = adopted_term in words
    if already_present:
        words.remove(adopted_term)

    try:
        review_body = rankings._DictionaryReviewBody(
            reviewer="tester",
            items=[
                rankings._DictionaryReviewItem(
                    topic_label=topic,
                    term=adopted_term,
                    decision="adopt",
                    confidence=0.88,
                    reason="observed_in_topic_evidence",
                )
            ],
        )
        review_res = rankings.review_dictionary_terms(review_body)
        assert review_res["saved"] == 1
        assert review_res["summary"]["adopt"] == 1
        assert review_res["summary"]["applied_terms"] >= 1

        classify_res = rankings.classify_topic(
            rankings._TopicClassifyBody(text="脂肪凍結 モニター募集")
        )
        assert "medical_diet" in classify_res["topic_tags"]
    finally:
        # Keep test side effects isolated.
        if adopted_term in rankings._TOPIC_KEYWORDS.get(topic, []):
            rankings._TOPIC_KEYWORDS[topic].remove(adopted_term)


def test_knowledge_rebuild_creates_versioned_snapshot(session, monkeypatch, tmp_path):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))
    monkeypatch.setattr(rankings, "_DICTIONARY_REVIEWS_FILE", tmp_path / "reviews.json")
    monkeypatch.setattr(rankings, "_KNOWLEDGE_SNAPSHOTS_FILE", tmp_path / "snapshots.json")

    ad = _mk_ad(
        "c45_rebuild_1",
        "新NISAで資産運用",
        metadata={"topic_label": "finance", "topic_confidence": 0.84},
    )
    session.add(ad)
    session.commit()

    review_body = rankings._DictionaryReviewBody(
        reviewer="tester",
        items=[
            rankings._DictionaryReviewItem(
                topic_label="finance",
                term="積立nisa",
                decision="adopt",
                confidence=0.82,
                reason="manual_curate",
            )
        ],
    )
    rankings.review_dictionary_terms(review_body)

    rebuild_body = rankings._KnowledgeRebuildBody(
        source="post_crawl",
        trigger_job_id="job-c45-001",
        include_recent_days=90,
        max_ads=200,
    )
    res = rankings.rebuild_topic_knowledge(rebuild_body)
    assert res["ok"] is True
    assert res["snapshot"]["version"].startswith("topic-knowledge-")
    assert res["snapshot"]["source"] == "post_crawl"
    assert res["snapshot"]["classification"]["topic_counts"]["finance"] >= 1
    assert res["total_snapshots"] >= 1

