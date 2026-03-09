from contextlib import contextmanager

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.ad_metrics import ProductRanking


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
    yield session


def test_refresh_trends_persists_score_delta_to_ranking_and_metadata(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "_db_session_scope", lambda: _session_scope(session))
    monkeypatch.setattr(rankings, "compute_genre_stats", lambda _session: {})
    monkeypatch.setattr(
        rankings,
        "compute_hit_score_with_details",
        lambda *_args, **_kwargs: {"hit_score": 82.4, "trend_score": 11.2},
    )

    ad = Ad(
        external_id="refresh_delta_1",
        title="差分検証広告",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={"latest_hit_score": 70.0},
    )
    session.add(ad)
    session.flush()

    ranking = ProductRanking(
        ad_id=ad.id,
        period="weekly",
        period_start=rankings._today_jst(),
        period_end=rankings._today_jst(),
        rank_position=1,
        hit_score=70.0,
        trend_score=4.0,
        is_hit=True,
    )
    session.add(ranking)
    session.commit()

    result = rankings.refresh_trends()
    session.refresh(ad)
    session.refresh(ranking)

    assert result["updated_count"] == 1
    assert ranking.hit_score == 82.4
    assert ranking.trend_score == 11.2
    assert ranking.score_delta == 12.4
    assert ranking.extra_metadata["previous_hit_score"] == 70.0
    assert ranking.extra_metadata["score_delta"] == 12.4

    meta = ad.ad_metadata or {}
    assert meta["previous_hit_score"] == 70.0
    assert meta["latest_hit_score"] == 82.4
    assert meta["hit_score_diff"] == 12.4
    assert meta["score_delta"] == 12.4
    assert "score_updated_at" in meta
