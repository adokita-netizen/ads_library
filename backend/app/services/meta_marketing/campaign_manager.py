"""Meta campaign management — CRUD operations via the Marketing API.

All creation operations default to PAUSED status for safety.
Budget values are in cents (e.g., 100000 = 1000 JPY).
"""

from typing import Any, Optional

import structlog

from app.services.meta_marketing.client import MetaMarketingClient

logger = structlog.get_logger()


class MetaCampaignManager:
    """Create, update, and manage Meta campaigns, ad sets, ads, and creatives."""

    def __init__(self, client: MetaMarketingClient):
        self.client = client

    # ── Campaigns ────────────────────────────────────────────────

    async def create_campaign(
        self,
        account_id: str,
        name: str,
        objective: str,
        daily_budget: Optional[int] = None,
        lifetime_budget: Optional[int] = None,
        status: str = "PAUSED",
        special_ad_categories: Optional[list[str]] = None,
    ) -> dict:
        """Create a new campaign. Always created as PAUSED for safety."""
        data: dict[str, Any] = {
            "name": name,
            "objective": objective,
            "status": "PAUSED",  # Force PAUSED regardless of input
            "special_ad_categories": special_ad_categories or [],
        }
        if daily_budget is not None:
            data["daily_budget"] = str(daily_budget)
        if lifetime_budget is not None:
            data["lifetime_budget"] = str(lifetime_budget)

        result = await self.client.post(f"/act_{account_id}/campaigns", data=data)
        logger.info("meta_campaign_created", account_id=account_id, campaign_id=result.get("id"))
        return result

    async def update_campaign(self, campaign_id: str, **updates: Any) -> dict:
        """Update campaign fields (name, daily_budget, etc.)."""
        result = await self.client.post(f"/{campaign_id}", data=updates)
        logger.info("meta_campaign_updated", campaign_id=campaign_id, updates=list(updates.keys()))
        return result

    async def update_campaign_status(self, campaign_id: str, status: str) -> dict:
        """Update campaign status (ACTIVE, PAUSED, DELETED)."""
        if status not in ("ACTIVE", "PAUSED", "DELETED", "ARCHIVED"):
            raise ValueError(f"Invalid campaign status: {status}")
        result = await self.client.post(f"/{campaign_id}", data={"status": status})
        logger.info("meta_campaign_status_updated", campaign_id=campaign_id, status=status)
        return result

    # ── Ad Sets ──────────────────────────────────────────────────

    async def create_ad_set(
        self,
        account_id: str,
        campaign_id: str,
        name: str,
        daily_budget: Optional[int] = None,
        lifetime_budget: Optional[int] = None,
        optimization_goal: str = "LINK_CLICKS",
        billing_event: str = "IMPRESSIONS",
        bid_strategy: Optional[str] = None,
        bid_amount: Optional[int] = None,
        targeting: Optional[dict] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        status: str = "PAUSED",
    ) -> dict:
        """Create a new ad set. Always created as PAUSED for safety."""
        data: dict[str, Any] = {
            "campaign_id": campaign_id,
            "name": name,
            "optimization_goal": optimization_goal,
            "billing_event": billing_event,
            "status": "PAUSED",  # Force PAUSED
        }
        if daily_budget is not None:
            data["daily_budget"] = str(daily_budget)
        if lifetime_budget is not None:
            data["lifetime_budget"] = str(lifetime_budget)
        if bid_strategy:
            data["bid_strategy"] = bid_strategy
        if bid_amount is not None:
            data["bid_amount"] = str(bid_amount)
        if targeting:
            data["targeting"] = targeting
        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time

        result = await self.client.post(f"/act_{account_id}/adsets", data=data)
        logger.info("meta_adset_created", account_id=account_id, adset_id=result.get("id"))
        return result

    async def update_ad_set(self, ad_set_id: str, **updates: Any) -> dict:
        """Update ad set fields."""
        result = await self.client.post(f"/{ad_set_id}", data=updates)
        logger.info("meta_adset_updated", adset_id=ad_set_id, updates=list(updates.keys()))
        return result

    async def update_ad_set_status(self, ad_set_id: str, status: str) -> dict:
        """Update ad set status."""
        if status not in ("ACTIVE", "PAUSED", "DELETED", "ARCHIVED"):
            raise ValueError(f"Invalid ad set status: {status}")
        result = await self.client.post(f"/{ad_set_id}", data={"status": status})
        logger.info("meta_adset_status_updated", adset_id=ad_set_id, status=status)
        return result

    # ── Ads ──────────────────────────────────────────────────────

    async def create_ad(
        self,
        account_id: str,
        ad_set_id: str,
        name: str,
        creative_id: str,
        status: str = "PAUSED",
    ) -> dict:
        """Create a new ad. Always created as PAUSED for safety."""
        data = {
            "adset_id": ad_set_id,
            "name": name,
            "creative": {"creative_id": creative_id},
            "status": "PAUSED",  # Force PAUSED
        }
        result = await self.client.post(f"/act_{account_id}/ads", data=data)
        logger.info("meta_ad_created", account_id=account_id, ad_id=result.get("id"))
        return result

    async def update_ad_status(self, ad_id: str, status: str) -> dict:
        """Update ad status."""
        if status not in ("ACTIVE", "PAUSED", "DELETED", "ARCHIVED"):
            raise ValueError(f"Invalid ad status: {status}")
        result = await self.client.post(f"/{ad_id}", data={"status": status})
        logger.info("meta_ad_status_updated", ad_id=ad_id, status=status)
        return result

    # ── Creatives ────────────────────────────────────────────────

    async def create_creative(
        self,
        account_id: str,
        name: str,
        object_story_spec: dict,
    ) -> dict:
        """Create a new ad creative."""
        data = {
            "name": name,
            "object_story_spec": object_story_spec,
        }
        result = await self.client.post(f"/act_{account_id}/adcreatives", data=data)
        logger.info("meta_creative_created", account_id=account_id, creative_id=result.get("id"))
        return result

    async def upload_image(self, account_id: str, image_bytes: bytes, filename: str = "image.jpg") -> dict:
        """Upload an image to the ad account."""
        result = await self.client.post(
            f"/act_{account_id}/adimages",
            files={"filename": (filename, image_bytes, "image/jpeg")},
        )
        logger.info("meta_image_uploaded", account_id=account_id)
        return result

    async def upload_video(self, account_id: str, video_bytes: bytes, filename: str = "video.mp4") -> dict:
        """Upload a video to the ad account."""
        result = await self.client.post(
            f"/act_{account_id}/advideos",
            files={"source": (filename, video_bytes, "video/mp4")},
        )
        logger.info("meta_video_uploaded", account_id=account_id)
        return result
