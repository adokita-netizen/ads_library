"""Notification service - send alerts via Slack/Chatwork/Email."""

import json
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


class NotificationService:
    """Send notifications to configured channels."""

    async def send_slack(self, webhook_url: str, message: str, blocks: Optional[list] = None) -> bool:
        """Send notification to Slack via webhook."""
        payload = {"text": message}
        if blocks:
            payload["blocks"] = blocks

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code == 200:
                    logger.info("slack_notification_sent", status=resp.status_code)
                    return True
                else:
                    logger.warning("slack_notification_failed", status=resp.status_code, body=resp.text)
                    return False
        except Exception as e:
            logger.error("slack_notification_error", error=str(e))
            return False

    async def send_chatwork(self, api_token: str, room_id: str, message: str) -> bool:
        """Send notification to Chatwork."""
        url = f"https://api.chatwork.com/v2/rooms/{room_id}/messages"
        headers = {"X-ChatWorkToken": api_token}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=headers, data={"body": message})
                if resp.status_code in (200, 201):
                    logger.info("chatwork_notification_sent", room_id=room_id)
                    return True
                else:
                    logger.warning("chatwork_notification_failed", status=resp.status_code)
                    return False
        except Exception as e:
            logger.error("chatwork_notification_error", error=str(e))
            return False

    async def notify_hit_ads(self, config, hit_ads: list) -> bool:
        """Send hit ad notification."""
        if not hit_ads:
            return True

        message = "🔥 *新しいヒット広告を検出*\n\n"
        for ad in hit_ads[:5]:
            message += (
                f"• *{ad.get('product_name', 'N/A')}* ({ad.get('genre', '')})\n"
                f"  再生増加: {ad.get('view_increase', 0):,} | "
                f"予想消化額: ¥{ad.get('spend_increase', 0):,.0f}\n"
            )

        if config.channel_type == "slack" and config.webhook_url:
            return await self.send_slack(config.webhook_url, message)
        elif config.channel_type == "chatwork" and config.api_token and config.room_id:
            chatwork_msg = message.replace("*", "").replace("🔥", "[info]").replace("\n\n", "\n")
            return await self.send_chatwork(config.api_token, config.room_id, chatwork_msg)

        return False

    async def notify_competitor_activity(self, config, activity: dict) -> bool:
        """Send competitor activity notification."""
        advertiser = activity.get("advertiser_name", "不明")
        new_ads = activity.get("new_ads_count", 0)

        message = (
            f"📊 *競合アクティビティ検出*\n\n"
            f"*{advertiser}* が新しい広告を {new_ads}件 出稿しました。\n"
        )

        if activity.get("genres"):
            message += f"ジャンル: {', '.join(activity['genres'])}\n"

        if config.channel_type == "slack" and config.webhook_url:
            return await self.send_slack(config.webhook_url, message)
        elif config.channel_type == "chatwork" and config.api_token and config.room_id:
            chatwork_msg = message.replace("*", "").replace("📊", "[info]")
            return await self.send_chatwork(config.api_token, config.room_id, chatwork_msg)

        return False

    async def notify_ranking_change(self, config, changes: list) -> bool:
        """Send ranking change notification."""
        if not changes:
            return True

        message = "📈 *ランキング変動通知*\n\n"
        for change in changes[:5]:
            direction = "⬆️" if change.get("rank_change", 0) > 0 else "⬇️"
            message += (
                f"• *{change.get('product_name', 'N/A')}*: "
                f"{direction} {abs(change.get('rank_change', 0))}位 → 現在{change.get('rank', 0)}位\n"
            )

        if config.channel_type == "slack" and config.webhook_url:
            return await self.send_slack(config.webhook_url, message)
        elif config.channel_type == "chatwork" and config.api_token and config.room_id:
            chatwork_msg = message.replace("*", "")
            return await self.send_chatwork(config.api_token, config.room_id, chatwork_msg)

        return False
