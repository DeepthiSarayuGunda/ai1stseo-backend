"""
growth/publish_runner.py
Scheduled Publishing Runner — batch-publishes overdue social posts.

Scans the DynamoDB social posts table for posts with status "scheduled"
whose scheduled_datetime has passed, splits multi-platform posts, and
routes each through social_orchestrator.publish_post().

No background workers — triggered manually via API endpoint.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _get_due_posts() -> tuple:
    """Fetch all posts, filter to due ones.

    Returns (due_posts, skipped_entries) where skipped_entries are
    posts with parse errors or missing platforms.
    """
    from growth.social_scheduler_dynamo import get_posts

    result = get_posts()
    if not result.get("success"):
        raise RuntimeError(f"Failed to fetch posts: {result.get('error', 'unknown')}")

    now = datetime.now(timezone.utc)
    due = []
    skipped = []

    for post in result.get("posts", []):
        post_id = post.get("post_id", "unknown")
        status = post.get("status", "")

        if status != "scheduled":
            continue

        # Parse scheduled_datetime ("YYYY-MM-DD HH:MM" as UTC)
        sdt = post.get("scheduled_datetime", "")
        try:
            scheduled = datetime.strptime(sdt, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            skipped.append({"post_id": post_id, "platform": "", "success": False,
                           "error": f"Unparseable scheduled_datetime: {sdt}"})
            continue

        if scheduled > now:
            continue

        # Check platforms
        platforms = post.get("platforms", "")
        if not platforms or not platforms.strip():
            skipped.append({"post_id": post_id, "platform": "", "success": False,
                           "error": "Missing or empty platforms field"})
            continue

        due.append(post)

    return due, skipped


def _split_platforms(post: dict) -> list:
    """Split comma-separated platforms string into lowercased, trimmed list."""
    raw = post.get("platforms", "")
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _build_payload(post: dict, platform: str) -> dict:
    """Construct payload for social_orchestrator.publish_post()."""
    return {
        "post_id": post.get("post_id"),
        "content": post.get("content", ""),
        "platform": platform,
        "scheduled_at": post.get("scheduled_datetime"),
    }


def run_scheduled_posts(dry_run: bool = False) -> dict:
    """Fetch due posts and publish them in batch.

    Args:
        dry_run: If True, identify due posts without publishing.

    Returns:
        BatchSummary dict with success, dry_run, counts, and per-platform results.
    """
    due_posts, skipped_entries = _get_due_posts()
    total_due = len(due_posts)

    # Track batch started (non-blocking)
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="runner_batch_started",
            event_data={"dry_run": dry_run, "total_due": total_due},
        )
    except Exception:
        logger.warning("Failed to track runner_batch_started")

    results = list(skipped_entries)
    succeeded = 0
    failed = 0
    total_attempts = 0

    for post in due_posts:
        platforms = _split_platforms(post)
        for platform in platforms:
            total_attempts += 1
            if dry_run:
                results.append({
                    "post_id": post.get("post_id"),
                    "platform": platform,
                    "success": None,
                    "error": None,
                })
                continue

            try:
                from growth.social_orchestrator import publish_post
                pub_result = publish_post(_build_payload(post, platform))
                if pub_result.get("success"):
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
                        "error": pub_result.get("error", "Unknown error"),
                    })
            except Exception as e:
                failed += 1
                results.append({
                    "post_id": post.get("post_id"),
                    "platform": platform,
                    "success": False,
                    "error": str(e),
                })
                logger.error("Publish failed for post %s platform %s: %s",
                           post.get("post_id"), platform, e)

    # Track batch completed (non-blocking)
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="runner_batch_completed",
            event_data={
                "dry_run": dry_run,
                "total_due": total_due,
                "succeeded": succeeded,
                "failed": failed,
                "skipped": len(skipped_entries),
            },
        )
    except Exception:
        logger.warning("Failed to track runner_batch_completed")

    return {
        "success": True,
        "dry_run": dry_run,
        "total_due": total_due,
        "total_publish_attempts": total_attempts,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": len(skipped_entries),
        "results": results,
    }
