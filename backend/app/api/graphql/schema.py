"""GraphQL schema for core dashboard and ads queries."""

from __future__ import annotations

from typing import Optional

import strawberry
from sqlalchemy import func

from app.core.database import sync_session_scope
from app.models.ad import Ad
from app.models.ad_metrics import ProductRanking


@strawberry.type
class Viewer:
    user_id: int
    email: str


@strawberry.type
class DashboardStats:
    total_ads: int
    hit_count: int
    hit_rate: float
    avg_hit_score: float


@strawberry.type
class AdSummary:
    ad_id: int
    title: str
    advertiser_name: Optional[str]
    genre: Optional[str]
    hit_score: float
    is_hit: bool


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> str:
        return "ok"

    @strawberry.field
    def viewer(self, info: strawberry.Info) -> Viewer:
        user = info.context.get("current_user") or {}
        return Viewer(
            user_id=int(user.get("user_id", 0)),
            email=str(user.get("email", "")),
        )

    @strawberry.field
    def dashboard_stats(self) -> DashboardStats:
        with sync_session_scope() as session:
            total_ads = int(session.query(func.count(Ad.id)).scalar() or 0)
            hit_count = int(
                session.query(func.count(func.distinct(ProductRanking.ad_id)))
                .filter(ProductRanking.is_hit.is_(True))
                .scalar()
                or 0
            )
            avg_score = float(session.query(func.avg(ProductRanking.hit_score)).scalar() or 0.0)
            hit_rate = round((hit_count / max(total_ads, 1)) * 100.0, 1)
            return DashboardStats(
                total_ads=total_ads,
                hit_count=hit_count,
                hit_rate=hit_rate,
                avg_hit_score=round(avg_score, 1),
            )

    @strawberry.field
    def top_hit_ads(
        self,
        limit: int = 10,
        genre: Optional[str] = None,
    ) -> list[AdSummary]:
        safe_limit = max(1, min(int(limit), 100))
        with sync_session_scope() as session:
            query = (
                session.query(ProductRanking, Ad)
                .outerjoin(Ad, Ad.id == ProductRanking.ad_id)
                .filter(ProductRanking.is_hit.is_(True))
            )
            if genre:
                query = query.filter(ProductRanking.genre == genre)
            rows = query.order_by(ProductRanking.hit_score.desc()).limit(safe_limit).all()

            return [
                AdSummary(
                    ad_id=int(r.ad_id),
                    title=((ad.title if ad else None) or "(untitled)"),
                    advertiser_name=(r.advertiser_name if r.advertiser_name else (ad.advertiser_name if ad else None)),
                    genre=r.genre,
                    hit_score=round(float(r.hit_score or 0.0), 1),
                    is_hit=bool(r.is_hit),
                )
                for r, ad in rows
            ]


schema = strawberry.Schema(query=Query)
