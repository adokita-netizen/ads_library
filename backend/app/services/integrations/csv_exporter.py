"""Scheduled export config helper."""

from datetime import datetime, timezone


class CSVExporter:
    """Builds normalized scheduled export config payloads."""

    VALID_SCHEDULES = {"daily", "weekly", "monthly"}
    VALID_FORMATS = {"csv", "json"}
    VALID_DELIVERY_TYPES = {"slack", "webhook", "email"}

    def build_config(
        self,
        *,
        name: str,
        schedule: str,
        export_format: str,
        filters: dict | None,
        delivery: dict,
    ) -> dict:
        schedule_l = (schedule or "").lower()
        format_l = (export_format or "").lower()
        delivery_type = str((delivery or {}).get("type", "")).lower()
        target = str((delivery or {}).get("target", "")).strip()

        if schedule_l not in self.VALID_SCHEDULES:
            raise ValueError("schedule must be one of: daily, weekly, monthly")
        if format_l not in self.VALID_FORMATS:
            raise ValueError("format must be one of: csv, json")
        if delivery_type not in self.VALID_DELIVERY_TYPES:
            raise ValueError("delivery.type must be one of: slack, webhook, email")
        if not target:
            raise ValueError("delivery.target is required")

        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "name": name.strip(),
            "schedule": schedule_l,
            "format": format_l,
            "filters": filters or {},
            "delivery": {"type": delivery_type, "target": target},
            "is_active": True,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

