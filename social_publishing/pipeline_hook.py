"""
social_publishing/pipeline_hook.py
Pipeline integration hooks — connects the content generation system
to automatic publishing.

Wraps existing pipeline functions to automatically enqueue content
for publishing after generation. Drop-in replacement for the current
manual flow.

Usage:
    # Instead of:
    from growth.content_pipeline import run_content_pipeline
    result = run_content_pipeline(limit=5)
    # ... then manually trigger publish runner

    # Use:
    from social_publishing.pipeline_hook import run_pipeline_with_auto_publish
    result = run_pipeline_with_auto_publish(limit=5)
    # Content is automatically queued for publishing

Environment variables:
    AUTO_PUBLISH_ENABLED  — "1" to enable auto-publish after pipeline (default: "0")
    AUTO_PUBLISH_MODE     — "queue" (default) or "immediate"
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AUTO_PUBLISH_ENABLED = os.environ.get("AUTO_PUBLISH_ENABLED", "0") == "1"
AUTO_PUBLISH_MODE = os.environ.get("AUTO_PUBLISH_MODE", "queue").strip().lower()


def run_pipeline_with_auto_publish(
    limit: int = 5,
    dry_run: bool = False,
    auto_publish: bool = None,
) -> dict:
    """Run the content pipeline and automatically publish generated content.

    Wraps growth.content_pipeline.run_content_pipeline() and adds
    automatic publishing of generated social posts.

    Args:
        limit: Max content items to process.
        dry_run: If True, generate but don't schedule or publish.
        auto_publish: Override AUTO_PUBLISH_ENABLED. None = use env var.

    Returns:
        Pipeline result + auto_publish results.
    """
    from growth.content_pipeline import run_content_pipeline

    # Run the content pipeline (fetch → repurpose → schedule)
    pipeline_result = run_content_pipeline(limit=limit, dry_run=dry_run)

    if not pipeline_result.get("success"):
        return pipeline_result

    should_publish = auto_publish if auto_publish is not None else AUTO_PUBLISH_ENABLED

    if dry_run or not should_publish:
        pipeline_result["auto_publish"] = {"enabled": False, "reason": "dry_run" if dry_run else "disabled"}
        return pipeline_result

    # Auto-publish: collect scheduled posts and enqueue them
    publish_result = _auto_publish_scheduled_posts(pipeline_result)
    pipeline_result["auto_publish"] = publish_result

    return pipeline_result


def _auto_publish_scheduled_posts(pipeline_result: dict) -> dict:
    """Enqueue newly scheduled posts for immediate publishing.

    Reads the scheduled post IDs from the pipeline result and
    enqueues them through the publish queue.
    """
    from social_publishing.queue import enqueue

    scheduled_ids = []
    for item_result in pipeline_result.get("results", []):
        scheduled_ids.extend(item_result.get("scheduled_post_ids", []))

    if not scheduled_ids:
        return {"enabled": True, "queued": 0, "message": "No posts to auto-publish"}

    # Fetch the actual post content from the scheduler
    queued = 0
    errors = []

    try:
        from growth.social_scheduler_dynamo import get_posts
        all_posts = get_posts()
        if not all_posts.get("success"):
            return {"enabled": True, "queued": 0, "error": "Failed to fetch scheduled posts"}

        posts_by_id = {p["post_id"]: p for p in all_posts.get("posts", []) if "post_id" in p}

        for post_id in scheduled_ids:
            post = posts_by_id.get(post_id)
            if not post:
                errors.append(f"Post {post_id} not found")
                continue

            platforms = [p.strip().lower() for p in post.get("platforms", "").split(",") if p.strip()]
            content = {
                "text": post.get("content", ""),
                "platforms": platforms,
                "image_url": post.get("image_path") or None,
            }

            # If the post has a future scheduled_datetime, keep it scheduled
            sdt = post.get("scheduled_datetime", "")
            if sdt:
                try:
                    scheduled = datetime.strptime(sdt, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                    if scheduled > datetime.now(timezone.utc):
                        content["scheduled_at"] = sdt
                except (ValueError, TypeError):
                    pass

            result = enqueue(content, priority=3, source="auto_pipeline")
            if result.get("success"):
                queued += 1
            else:
                errors.append(f"Enqueue failed for {post_id}")

    except Exception as e:
        logger.error("Auto-publish failed: %s", e)
        return {"enabled": True, "queued": queued, "error": str(e)}

    return {
        "enabled": True,
        "queued": queued,
        "total_scheduled": len(scheduled_ids),
        "errors": errors if errors else None,
    }


def run_full_cycle_with_auto_publish(
    content_limit: int = 5,
    publish_dry_run: bool = False,
    auto_publish: bool = None,
    **kwargs,
) -> dict:
    """Run the full growth cycle with automatic publishing via the queue.

    Wraps growth.auto_pipeline_runner.run_full_cycle() and adds
    queue-based publishing instead of the existing publish runner.

    When auto_publish is enabled, the publish step uses the queue
    system instead of the synchronous publish runner, allowing
    rate-limited, retried publishing.
    """
    should_publish = auto_publish if auto_publish is not None else AUTO_PUBLISH_ENABLED

    if not should_publish:
        # Fall back to existing behavior
        from growth.auto_pipeline_runner import run_full_cycle
        return run_full_cycle(
            content_limit=content_limit,
            publish_dry_run=publish_dry_run,
            **kwargs,
        )

    # Run content pipeline with auto-publish
    from growth.content_pipeline import run_content_pipeline
    from social_publishing.queue import enqueue, get_queue_status, flush_queue

    started_at = datetime.now(timezone.utc).isoformat()

    # Step 1: Content pipeline
    pipeline_result = None
    try:
        pipeline_result = run_content_pipeline(limit=content_limit)
        logger.info("Pipeline: processed=%s scheduled=%s",
                     pipeline_result.get("processed", 0),
                     pipeline_result.get("posts_scheduled", 0))
    except Exception as e:
        logger.error("Content pipeline failed: %s", e)
        pipeline_result = {"success": False, "error": str(e)}

    # Step 2: Auto-publish via queue
    publish_result = None
    if pipeline_result and pipeline_result.get("success"):
        publish_result = _auto_publish_scheduled_posts(pipeline_result)

    # Step 3: Also publish any overdue scheduled posts via queue
    overdue_result = _enqueue_overdue_posts()

    # Step 4: Process queue (synchronous flush for API-triggered runs)
    if AUTO_PUBLISH_MODE == "immediate":
        queue_result = flush_queue()
    else:
        from social_publishing.queue import start_worker
        start_worker()
        queue_result = get_queue_status()

    # Step 5: Performance ingestor (optional, non-blocking)
    ingest_result = None
    try:
        from growth.performance_ingestor import ingest_performance
        ingest_result = ingest_performance(mode="auto")
    except Exception as e:
        logger.error("Performance ingestor failed: %s", e)
        ingest_result = {"success": False, "error": str(e)}

    # Track analytics
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="auto_pipeline_run",
            event_data={
                "auto_publish": True,
                "content_processed": (pipeline_result or {}).get("processed", 0),
                "posts_scheduled": (pipeline_result or {}).get("posts_scheduled", 0),
                "auto_queued": (publish_result or {}).get("queued", 0),
                "overdue_queued": (overdue_result or {}).get("queued", 0),
            },
        )
    except Exception:
        pass

    return {
        "success": True,
        "auto_publish": True,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": _safe_summary(pipeline_result),
        "auto_publish_result": publish_result,
        "overdue_result": overdue_result,
        "queue": queue_result,
        "ingestor": _safe_summary(ingest_result),
    }


def _enqueue_overdue_posts() -> dict:
    """Find overdue scheduled posts and enqueue them for publishing."""
    from social_publishing.queue import enqueue

    try:
        from growth.publish_runner import _get_due_posts
        due_posts, skipped = _get_due_posts()
    except Exception as e:
        return {"success": False, "error": str(e), "queued": 0}

    queued = 0
    for post in due_posts:
        platforms = [p.strip().lower() for p in post.get("platforms", "").split(",") if p.strip()]
        content = {
            "text": post.get("content", ""),
            "platforms": platforms,
            "image_url": post.get("image_path") or None,
        }
        result = enqueue(content, priority=2, source="overdue_scheduled")
        if result.get("success"):
            queued += 1

    return {"success": True, "queued": queued, "total_due": len(due_posts), "skipped": len(skipped)}


def _safe_summary(result: dict | None) -> dict:
    """Extract a safe summary from a step result."""
    if not result:
        return {"success": False, "error": "Step did not run"}
    summary = {"success": result.get("success", False)}
    for key in ("processed", "posts_generated", "posts_scheduled", "error",
                "scored", "queued", "message", "dry_run"):
        if key in result:
            summary[key] = result[key]
    return summary
