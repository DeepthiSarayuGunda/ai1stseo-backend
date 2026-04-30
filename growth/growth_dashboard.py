"""
growth/growth_dashboard.py
Growth KPI Dashboard Aggregator.

Collects metrics from analytics_tracker and email_subscriber into
a single KPI summary. No new tables, no new dependencies.

Integration points:
  - growth/analytics_tracker.get_summary(days)
  - growth/email_subscriber.list_subscribers(page, per_page)
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def get_dashboard_kpis(days: int = 7) -> dict:
    """Aggregate growth KPIs from analytics and subscriber data sources.

    Args:
        days: Lookback window in days. Clamped to [1, 90].

    Returns:
        dict with success, all KPI fields, and availability flags.
    """
    try:
        days = max(1, min(int(days), 90))
    except (ValueError, TypeError):
        days = 7

    analytics_available = True
    subscribers_available = True

    # Defaults
    by_type = {}
    by_utm_source = {}
    by_utm_campaign = {}
    total_subscribers = 0
    new_subscribers = 0

    # Fetch analytics
    try:
        from growth.analytics_tracker import get_summary
        summary = get_summary(days=days)
        if summary.get("success"):
            by_type = summary.get("by_type", {})
            by_utm_source = summary.get("by_utm_source", {})
            by_utm_campaign = summary.get("by_utm_campaign", {})
        else:
            analytics_available = False
            logger.warning("Analytics source returned failure: %s", summary.get("error"))
    except Exception as e:
        analytics_available = False
        logger.warning("Analytics source unavailable: %s", e)

    # Fetch subscribers
    try:
        from growth.email_subscriber import list_subscribers
        sub_result = list_subscribers(page=1, per_page=10000)
        if sub_result.get("success"):
            total_subscribers = sub_result.get("total", 0)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            subs = sub_result.get("subscribers", [])
            new_subscribers = sum(
                1 for s in subs
                if s.get("subscribed_at", "") >= cutoff
            )
        else:
            subscribers_available = False
            logger.warning("Subscriber source returned failure: %s", sub_result.get("error"))
    except Exception as e:
        subscribers_available = False
        logger.warning("Subscriber source unavailable: %s", e)

    return {
        "success": True,
        "days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics_available": analytics_available,
        "subscribers_available": subscribers_available,
        "total_subscribers": total_subscribers,
        "new_subscribers": new_subscribers,
        "lead_magnet_downloads": by_type.get("lead_magnet_downloaded", 0),
        "welcome_email_attempted": by_type.get("welcome_email_attempted", 0),
        "welcome_email_sent": by_type.get("welcome_email_sent", 0),
        "welcome_email_failed": by_type.get("welcome_email_failed", 0),
        "content_repurposed": by_type.get("content_repurposed", 0),
        "publish_attempted": by_type.get("publish_attempted", 0),
        "publish_succeeded": by_type.get("publish_succeeded", 0),
        "publish_failed": by_type.get("publish_failed", 0),
        "pipeline": _get_pipeline_stats(),
        "top_event_types": by_type,
        "top_utm_sources": by_utm_source,
        "top_utm_campaigns": by_utm_campaign,
    }


def _get_pipeline_stats() -> dict:
    """Get content pipeline stats (non-blocking)."""
    try:
        from growth.content_source_manager import list_content
        all_content = list_content(limit=200)
        if not all_content.get("success"):
            return {"available": False}
        items = all_content.get("items", [])
        return {
            "available": True,
            "total_content": len(items),
            "new": sum(1 for i in items if i.get("status") == "new"),
            "processed": sum(1 for i in items if i.get("status") == "processed"),
            "failed": sum(1 for i in items if i.get("status") == "failed"),
            "processing": sum(1 for i in items if i.get("status") == "processing"),
        }
    except Exception:
        return {"available": False}
