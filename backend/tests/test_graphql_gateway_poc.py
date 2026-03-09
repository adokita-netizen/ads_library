from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.graphql.router import router

try:
    import strawberry  # noqa: F401

    _HAS_STRAWBERRY = True
except Exception:
    _HAS_STRAWBERRY = False


def test_graphql_router_available_or_fallback_contract():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    res = client.get("/api/v1/graphql")
    assert res.status_code in (200, 405, 503)


if _HAS_STRAWBERRY:
    from app.api.graphql.schema import schema
    from app.core.database import sync_session_scope
    from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
    from app.models.ad_metrics import ProductRanking

    def test_graphql_health_query():
        result = schema.execute_sync("query { health }")
        assert result.errors is None
        assert result.data == {"health": "ok"}

    def test_graphql_viewer_context_mapping():
        result = schema.execute_sync(
            "query { viewer { userId email } }",
            context_value={"current_user": {"user_id": 42, "email": "demo@example.com"}},
        )
        assert result.errors is None
        assert result.data == {
            "viewer": {
                "userId": 42,
                "email": "demo@example.com",
            }
        }

    def test_graphql_top_hit_ads_minimal_fields_overfetch_reduction():
        with sync_session_scope() as session:
            ad = Ad(
                external_id="graphql_poc_ad_001",
                title="GraphQL PoC Ad",
                advertiser_name="GraphQL Demo",
                platform=AdPlatformEnum.FACEBOOK,
                status=AdStatusEnum.ANALYZED,
            )
            session.add(ad)
            session.flush()

            ranking = ProductRanking(
                period="daily",
                period_start=date(2026, 3, 5),
                period_end=date(2026, 3, 5),
                ad_id=ad.id,
                advertiser_name="GraphQL Demo",
                genre="beauty",
                platform="facebook",
                rank_position=1,
                total_view_increase=100,
                total_spend_increase=10.0,
                cumulative_views=1000,
                cumulative_spend=50.0,
                is_hit=True,
                hit_score=88.0,
            )
            session.add(ranking)

        # Ask only `adId` to verify GraphQL overfetch reduction behavior.
        result = schema.execute_sync("query { topHitAds(limit: 5) { adId } }")
        assert result.errors is None
        items = result.data["topHitAds"]
        assert isinstance(items, list)
        assert len(items) >= 1
        assert set(items[0].keys()) == {"adId"}
