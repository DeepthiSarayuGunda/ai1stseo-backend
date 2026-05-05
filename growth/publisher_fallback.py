"""
growth/publisher_fallback.py
Publisher Fallback System — ensures the pipeline never blocks.

When no real publisher API keys are configured (Buffer/Postiz),
this module provides simulated publishing that:
    - Updates post status to "simulated" (not "published")
    - Logs analytics events so the tracking pipeline stays active
    - Returns structured results matching the orchestrator format

The social_orchestrator already returns "No publisher configured"
when keys are missing. This module wraps that behavior to keep
posts moving through the system instead of staying stuck as "failed".

Does NOT modify social_orchestrator.py. Sits alongside it.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def publish_with_fallback(payload: dict) -> dict:
    """Attempt real publish, fall back to simulation if no provider.

    Args:
        payload: {"post_id": str, "content": str, "platform": str, "scheduled_at": str}

    Returns:
        Orchestrator-compatible result dict.
    """
    # Try real publish first
    try:
        from growth.social_orchestrator import publish_post
        result = publish_post(payload)

        # If it succeeded or failed for a real reason, return as-is
        if result.get("status") != "provider_unavailable":
            return result
    except Exception as e:
        logger.warning("Orchestrator raised: %s — falling back to simulation", e)

    # No provider available — simulate
    return _simulate_publish(payload)


def _simulate_publish(payload: dict) -> dict:
    """Simulate a publish and update post status."""
    post_id = payload.get("post_id")
    platform = payload.get("platform", "unknown")
    content = payload.get("content", "")

    logger.info("Simulated publish: post=%s platform=%s chars=%d",
               post_id, platform, len(content))

    # Update post status to "simulated" so it's distinguishable
    if post_id:
        try:
            from growth.social_scheduler_dynamo import update_post
            update_post(post_id, {"status": "simulated"})
        except Exception as e:
            logger.warning("Failed to update simulated status: %s", e)

    # Track simulated publish event
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="publish_simulated",
            event_data={
                "platform": platform,
                "post_id": post_id,
                "content_length": len(content),
            },
        )
    except Exception:
        pass

    return {
        "success": True,
        "provider": "simulation",
        "result": {"simulated": True, "platform": platform},
        "error": None,
        "status": "simulated",
    }


def run_scheduled_with_fallback(dry_run: bool = False) -> dict:
    """Run the scheduled post runner with fallback publishing.

    Replaces the orchestrator's publish_post with publish_with_fallback
    for posts that would otherwise fail due to missing credentials.
    """
    from growth.social_scheduler_dynamo import get_posts
    from growth.publish_runner import _get_due_posts, _split_platforms, _build_payload

    due_posts, skipped_entries = _get_due_posts()
    total_due = len(due_posts)

    if not due_posts and not skipped_entries:
        return {
            "success": True,
            "total_due": 0,
            "succeeded": 0,
            "failed": 0,
            "simulated": 0,
            "skipped": 0,
            "results": [],
        }

    results = list(skipped_entries)
    succeeded = 0
    failed = 0
    simulated = 0

    for post in due_posts:
        platforms = _split_platforms(post)
        for platform in platforms:
            if dry_run:
                results.append({
                    "post_id": post.get("post_id"),
                    "platform": platform,
                    "success": None,
                    "error": None,
                })
                continue

            payload = _build_payload(post, platform)
            pub_result = publish_with_fallback(payload)

            if pub_result.get("status") == "simulated":
                simulated += 1
                results.append({
                    "post_id": post.get("post_id"),
                    "platform": platform,
                    "success": True,
                    "error": None,
                    "simulated": True,
                })
            elif pub_result.get("success"):
                succeeded += 1
                results.append({
                    "post_id": post.get("post_id"),
                    "platform": platform,
                    "success": True,
                    "error": None,
                })
            else:
                failed += 1
                results.append({
                    "post_id": post.get("post_id"),
                    "platform": platform,
                    "success": False,
                    "error": pub_result.get("error", "Unknown"),
                })

    return {
        "success": True,
        "dry_run": dry_run,
        "total_due": total_due,
        "succeeded": succeeded,
        "failed": failed,
        "simulated": simulated,
        "skipped": len(skipped_entries),
        "results": results,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
