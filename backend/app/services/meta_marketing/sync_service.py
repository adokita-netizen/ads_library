"""Meta Marketing data synchronization — campaigns, ad sets, ads, and insights."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_ad_account import MetaAdAccount
from app.models.meta_campaign import MetaAd, MetaAdSet, MetaCampaign, MetaInsight
from app.services.meta_marketing.client import MetaMarketingClient

logger = structlog.get_logger()

CAMPAIGN_FIELDS = (
    "id,name,status,effective_status,objective,daily_budget,lifetime_budget,"
    "budget_remaining,start_time,stop_time,buying_type,special_ad_categories"
)

ADSET_FIELDS = (
    "id,name,status,effective_status,daily_budget,lifetime_budget,"
    "bid_strategy,bid_amount,billing_event,optimization_goal,targeting,"
    "start_time,end_time"
)

AD_FIELDS = (
    "id,name,status,effective_status,"
    "creative{id,body,title,image_url,effective_image_url,"
    "link_url,object_type,video_id,thumbnail_url},"
    "adset_id"
)

INSIGHT_FIELDS = (
    "impressions,reach,clicks,spend,ctr,cpc,cpm,cpp,frequency,"
    "actions,conversions,conversion_values,cost_per_conversion,"
    "video_thruplay_watched_actions,video_p25_watched_actions,"
    "video_p50_watched_actions,video_p75_watched_actions,"
    "video_p95_watched_actions,video_p100_watched_actions,"
    "inline_link_clicks,social_spend"
)


class MetaSyncService:
    """Synchronize Meta ad account data to local database."""

    def __init__(self, client: MetaMarketingClient, db: AsyncSession):
        self.client = client
        self.db = db

    async def sync_campaigns(self, account_id: str) -> int:
        """Sync campaigns from Meta API to local DB. Returns count of upserted campaigns."""
        raw_campaigns = await self.client.get_paginated(
            f"/act_{account_id}/campaigns",
            params={"fields": CAMPAIGN_FIELDS, "limit": 200},
        )

        count = 0
        for raw in raw_campaigns:
            meta_id = raw.get("id")
            if not meta_id:
                continue

            result = await self.db.execute(
                select(MetaCampaign).where(MetaCampaign.meta_id == meta_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.name = raw.get("name", existing.name)
                existing.status = raw.get("status", existing.status)
                existing.effective_status = raw.get("effective_status", existing.effective_status)
                existing.objective = raw.get("objective")
                existing.daily_budget = raw.get("daily_budget")
                existing.lifetime_budget = raw.get("lifetime_budget")
                existing.budget_remaining = raw.get("budget_remaining")
                existing.start_time = _parse_datetime(raw.get("start_time"))
                existing.stop_time = _parse_datetime(raw.get("stop_time"))
                existing.buying_type = raw.get("buying_type")
                existing.special_ad_categories = raw.get("special_ad_categories")
            else:
                campaign = MetaCampaign(
                    meta_id=meta_id,
                    account_id=account_id,
                    name=raw.get("name", ""),
                    status=raw.get("status", "UNKNOWN"),
                    effective_status=raw.get("effective_status", "UNKNOWN"),
                    objective=raw.get("objective"),
                    daily_budget=raw.get("daily_budget"),
                    lifetime_budget=raw.get("lifetime_budget"),
                    budget_remaining=raw.get("budget_remaining"),
                    start_time=_parse_datetime(raw.get("start_time")),
                    stop_time=_parse_datetime(raw.get("stop_time")),
                    buying_type=raw.get("buying_type"),
                    special_ad_categories=raw.get("special_ad_categories"),
                )
                self.db.add(campaign)
            count += 1

        await self.db.flush()
        logger.info("meta_sync_campaigns", account_id=account_id, count=count)
        return count

    async def sync_ad_sets(self, account_id: str, japan_only: bool = True) -> int:
        """Sync ad sets from Meta API to local DB.

        Args:
            japan_only: If True, skip ad sets not targeting Japan.
        """
        raw_adsets = await self.client.get_paginated(
            f"/act_{account_id}/adsets",
            params={"fields": ADSET_FIELDS, "limit": 200},
        )

        count = 0
        for raw in raw_adsets:
            meta_id = raw.get("id")
            if not meta_id:
                continue

            # Japan-only filter: check targeting.geo_locations.countries
            if japan_only:
                targeting = raw.get("targeting", {})
                if targeting:
                    geo = targeting.get("geo_locations", {})
                    countries = geo.get("countries", [])
                    # If countries are specified and JP is not among them, skip
                    if countries and "JP" not in countries:
                        logger.debug("meta_sync_skip_non_japan_adset", meta_id=meta_id,
                                     countries=countries)
                        continue

            result = await self.db.execute(
                select(MetaAdSet).where(MetaAdSet.meta_id == meta_id)
            )
            existing = result.scalar_one_or_none()

            campaign_id = raw.get("campaign_id", raw.get("campaign", {}).get("id", ""))

            if existing:
                existing.name = raw.get("name", existing.name)
                existing.status = raw.get("status", existing.status)
                existing.effective_status = raw.get("effective_status", existing.effective_status)
                existing.daily_budget = raw.get("daily_budget")
                existing.lifetime_budget = raw.get("lifetime_budget")
                existing.bid_strategy = raw.get("bid_strategy")
                existing.bid_amount = raw.get("bid_amount")
                existing.billing_event = raw.get("billing_event")
                existing.optimization_goal = raw.get("optimization_goal")
                existing.targeting = raw.get("targeting")
                existing.start_time = _parse_datetime(raw.get("start_time"))
                existing.end_time = _parse_datetime(raw.get("end_time"))
            else:
                ad_set = MetaAdSet(
                    meta_id=meta_id,
                    campaign_meta_id=campaign_id,
                    account_id=account_id,
                    name=raw.get("name", ""),
                    status=raw.get("status", "UNKNOWN"),
                    effective_status=raw.get("effective_status", "UNKNOWN"),
                    daily_budget=raw.get("daily_budget"),
                    lifetime_budget=raw.get("lifetime_budget"),
                    bid_strategy=raw.get("bid_strategy"),
                    bid_amount=raw.get("bid_amount"),
                    billing_event=raw.get("billing_event"),
                    optimization_goal=raw.get("optimization_goal"),
                    targeting=raw.get("targeting"),
                    start_time=_parse_datetime(raw.get("start_time")),
                    end_time=_parse_datetime(raw.get("end_time")),
                )
                self.db.add(ad_set)
            count += 1

        await self.db.flush()
        logger.info("meta_sync_ad_sets", account_id=account_id, count=count)
        return count

    async def sync_ads(self, account_id: str) -> int:
        """Sync ads (with creative details) from Meta API to local DB."""
        raw_ads = await self.client.get_paginated(
            f"/act_{account_id}/ads",
            params={"fields": AD_FIELDS, "limit": 200},
        )

        count = 0
        for raw in raw_ads:
            meta_id = raw.get("id")
            if not meta_id:
                continue

            result = await self.db.execute(
                select(MetaAd).where(MetaAd.meta_id == meta_id)
            )
            existing = result.scalar_one_or_none()

            creative = raw.get("creative", {})
            adset_id = raw.get("adset_id", "")

            creative_type = creative.get("object_type", "")
            # Thumbnail: prefer effective_image_url > thumbnail_url > image_url
            thumbnail = (
                creative.get("effective_image_url")
                or creative.get("thumbnail_url")
                or creative.get("image_url")
            )
            image_url = creative.get("image_url") or creative.get("effective_image_url")
            link_url = creative.get("link_url")
            # Build video URL from video_id if available
            video_id = creative.get("video_id")
            video_url = f"https://www.facebook.com/ads/videos/{video_id}/" if video_id else None

            if existing:
                existing.name = raw.get("name", existing.name)
                existing.status = raw.get("status", existing.status)
                existing.effective_status = raw.get("effective_status", existing.effective_status)
                existing.creative_id = creative.get("id")
                existing.creative_thumbnail_url = thumbnail
                existing.creative_body = creative.get("body")
                existing.creative_title = creative.get("title")
                existing.creative_image_url = image_url
                existing.creative_link_url = link_url
                existing.creative_video_url = video_url
                existing.creative_type = creative_type
            else:
                ad = MetaAd(
                    meta_id=meta_id,
                    ad_set_meta_id=adset_id,
                    account_id=account_id,
                    name=raw.get("name", ""),
                    status=raw.get("status", "UNKNOWN"),
                    effective_status=raw.get("effective_status", "UNKNOWN"),
                    creative_id=creative.get("id"),
                    creative_thumbnail_url=thumbnail,
                    creative_body=creative.get("body"),
                    creative_title=creative.get("title"),
                    creative_image_url=image_url,
                    creative_link_url=link_url,
                    creative_video_url=video_url,
                    creative_type=creative_type,
                )
                self.db.add(ad)
            count += 1

        await self.db.flush()

        # Fallback: fetch thumbnails for ads that still have no thumbnail
        result = await self.db.execute(
            select(MetaAd).where(
                MetaAd.account_id == account_id,
                MetaAd.creative_thumbnail_url.is_(None),
                MetaAd.creative_id.isnot(None),
            )
        )
        missing_thumb_ads = result.scalars().all()
        for ad_obj in missing_thumb_ads[:20]:  # Limit to 20 to avoid rate limits
            thumb_url = await self.client.get_creative_thumbnail(ad_obj.creative_id)
            if thumb_url:
                ad_obj.creative_thumbnail_url = thumb_url
        if missing_thumb_ads:
            await self.db.flush()
            logger.info("meta_sync_thumbnails_fallback", account_id=account_id,
                         fetched=min(len(missing_thumb_ads), 20))

        logger.info("meta_sync_ads", account_id=account_id, count=count)
        return count

    async def sync_insights(
        self,
        account_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        level: str = "ad",
    ) -> int:
        """Sync daily performance insights from Meta API.

        Args:
            account_id: Meta ad account ID
            date_from: Start date (YYYY-MM-DD). Defaults to 30 days ago.
            date_to: End date (YYYY-MM-DD). Defaults to yesterday.
            level: Granularity — 'campaign', 'adset', or 'ad'.
        """
        if not date_from:
            date_from = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        raw_insights = await self.client.get_paginated(
            f"/act_{account_id}/insights",
            params={
                "fields": INSIGHT_FIELDS,
                "time_range": f'{{"since":"{date_from}","until":"{date_to}"}}',
                "time_increment": "1",
                "level": level,
                "limit": 500,
            },
        )

        count = 0
        for raw in raw_insights:
            entity_id = raw.get("campaign_id") or raw.get("adset_id") or raw.get("ad_id") or ""
            entity_type = level
            date_start = raw.get("date_start", "")
            date_stop = raw.get("date_stop", "")

            if not entity_id or not date_start:
                continue

            # Upsert
            result = await self.db.execute(
                select(MetaInsight).where(
                    MetaInsight.entity_type == entity_type,
                    MetaInsight.entity_id == entity_id,
                    MetaInsight.date_start == date_start,
                )
            )
            existing = result.scalar_one_or_none()

            # Extract video metrics from action lists
            video_metrics = _extract_video_metrics(raw)

            if existing:
                existing.impressions = _int(raw.get("impressions"))
                existing.reach = _int(raw.get("reach"))
                existing.clicks = _int(raw.get("clicks"))
                existing.spend = _float(raw.get("spend"))
                existing.ctr = _float(raw.get("ctr"))
                existing.cpc = _float(raw.get("cpc"))
                existing.cpm = _float(raw.get("cpm"))
                existing.cpp = _float(raw.get("cpp"))
                existing.frequency = _float(raw.get("frequency"))
                existing.conversions = _int(raw.get("conversions"))
                existing.conversion_values = _float(raw.get("conversion_values"))
                existing.cost_per_conversion = _float(raw.get("cost_per_conversion"))
                existing.inline_link_clicks = _int(raw.get("inline_link_clicks"))
                existing.social_spend = _float(raw.get("social_spend"))
                existing.actions = raw.get("actions")
                existing.video_thruplay = video_metrics.get("thruplay")
                existing.video_p25_watched = video_metrics.get("p25")
                existing.video_p50_watched = video_metrics.get("p50")
                existing.video_p75_watched = video_metrics.get("p75")
                existing.video_p95_watched = video_metrics.get("p95")
                existing.video_p100_watched = video_metrics.get("p100")
            else:
                insight = MetaInsight(
                    account_id=account_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    date_start=date_start,
                    date_stop=date_stop,
                    impressions=_int(raw.get("impressions")),
                    reach=_int(raw.get("reach")),
                    clicks=_int(raw.get("clicks")),
                    spend=_float(raw.get("spend")),
                    ctr=_float(raw.get("ctr")),
                    cpc=_float(raw.get("cpc")),
                    cpm=_float(raw.get("cpm")),
                    cpp=_float(raw.get("cpp")),
                    frequency=_float(raw.get("frequency")),
                    conversions=_int(raw.get("conversions")),
                    conversion_values=_float(raw.get("conversion_values")),
                    cost_per_conversion=_float(raw.get("cost_per_conversion")),
                    inline_link_clicks=_int(raw.get("inline_link_clicks")),
                    social_spend=_float(raw.get("social_spend")),
                    actions=raw.get("actions"),
                    video_thruplay=video_metrics.get("thruplay"),
                    video_p25_watched=video_metrics.get("p25"),
                    video_p50_watched=video_metrics.get("p50"),
                    video_p75_watched=video_metrics.get("p75"),
                    video_p95_watched=video_metrics.get("p95"),
                    video_p100_watched=video_metrics.get("p100"),
                )
                self.db.add(insight)
            count += 1

        await self.db.flush()
        logger.info("meta_sync_insights", account_id=account_id, level=level, count=count)
        return count

    async def full_sync(self, account_id: str, insights_days: int = 30) -> dict:
        """Run a full sync for an account: campaigns → ad sets → ads → insights."""
        # Update account sync status
        result = await self.db.execute(
            select(MetaAdAccount).where(MetaAdAccount.account_id == account_id)
        )
        account = result.scalar_one_or_none()
        if account:
            account.sync_status = "syncing"
            account.sync_error = None
            await self.db.flush()

        try:
            campaigns = await self.sync_campaigns(account_id)
            ad_sets = await self.sync_ad_sets(account_id)
            ads = await self.sync_ads(account_id)

            date_from = (datetime.now(timezone.utc) - timedelta(days=insights_days)).strftime("%Y-%m-%d")
            # Sync insights at all levels for comprehensive data
            insights_ad = await self.sync_insights(account_id, date_from=date_from, level="ad")
            insights_adset = await self.sync_insights(account_id, date_from=date_from, level="adset")
            insights_campaign = await self.sync_insights(account_id, date_from=date_from, level="campaign")
            insights = insights_ad + insights_adset + insights_campaign

            if account:
                account.sync_status = "completed"
                account.last_synced_at = datetime.now(timezone.utc)
                await self.db.flush()

            summary = {
                "campaigns": campaigns,
                "ad_sets": ad_sets,
                "ads": ads,
                "insights": insights,
            }
            logger.info("meta_full_sync_completed", account_id=account_id, summary=summary)
            return summary

        except Exception as e:
            if account:
                account.sync_status = "failed"
                account.sync_error = str(e)
                await self.db.flush()
            logger.error("meta_full_sync_failed", account_id=account_id, error=str(e))
            raise


# ── Helpers ──────────────────────────────────────────────────────

def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string from Meta API."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _int(value) -> int:
    try:
        return int(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0


def _float(value) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def _extract_video_metrics(raw: dict) -> dict:
    """Extract video view percentile metrics from Meta action lists."""
    result = {}
    action_map = {
        "video_thruplay_watched_actions": "thruplay",
        "video_p25_watched_actions": "p25",
        "video_p50_watched_actions": "p50",
        "video_p75_watched_actions": "p75",
        "video_p95_watched_actions": "p95",
        "video_p100_watched_actions": "p100",
    }
    for field, key in action_map.items():
        actions = raw.get(field, [])
        if isinstance(actions, list) and actions:
            # Sum all action types (usually just "video_view")
            total = sum(_int(a.get("value", 0)) for a in actions)
            result[key] = total
    return result
