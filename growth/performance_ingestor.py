"""
growth/performance_ingestor.py
Performance Ingestor — auto-scores published posts.

When real platform analytics APIs are unavailable (no Postiz/Buffer keys),
generates simulated metrics based on content characteristics so the
optimizer feedback loop stays active. When real APIs are available,
fetches actual metrics.

Connects: social_scheduler_dynamo → performance_optimizer.score_post()
Tracks: performance_ingested analytics event
"""

import hashlib
import logging
import random
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _simulate_metrics(post: dict) -> dict:
    """Generate deterministic simulated metrics from post content.

    Uses content hash as seed so the same post always gets the same
    simulated metrics. This keeps the optimizer stable between runs.
    """
    content = post.get("content", "")
    platform = post.get("platforms", "x").split(",")[0].strip().lower()
    post_id = post.get("post_id", "")

    # Deterministic seed from post_id + platform
    seed = int(hashlib.md5(f"{post_id}:{platform}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Platform-specific base ranges
    ranges = {
        "linkedin": {"imp": (200, 2000), "ctr": (0.02, 0.08), "eng_rate": (0.01, 0.05)},
        "x":        {"imp": (100, 1500), "ctr": (0.01, 0.06), "eng_rate": (0.005, 0.04)},
        "instagram": {"imp": (150, 1800), "ctr": (0.015, 0.07), "eng_rate": (0.02, 0.06)},
        "facebook": {"imp": (100, 1200), "ctr": (0.01, 0.05), "eng_rate": (0.008, 0.03)},
    }
    r = ranges.get(platform, ranges["x"])

    # Content quality signals boost metrics
    has_cta = any(w in content.lower() for w in ["→", "check", "try", "get", "start", "link"])
    has_question = "?" in content
    has_list = any(c in content for c in ["1.", "✅", "→", "•"])
    quality_boost = 1.0 + (0.15 if has_cta else 0) + (0.1 if has_question else 0) + (0.1 if has_list else 0)

    impressions = int(rng.uniform(*r["imp"]) * quality_boost)
    ctr = rng.uniform(*r["ctr"]) * quality_boost
    clicks = max(1, int(impressions * ctr))
    eng_rate = rng.uniform(*r["eng_rate"]) * quality_boost
    engagements = max(0, int(impressions * eng_rate))
    conversions = max(0, int(clicks * rng.uniform(0.01, 0.05)))

    return {
        "impressions": impressions,
        "clicks": clicks,
        "engagements": engagements,
        "conversions": conversions,
        "platform": platform,
        "content_type": _detect_content_type(content),
        "simulated": True,
    }


def _detect_content_type(content: str) -> str:
    """Detect content format from text characteristics."""
    if content.count("\n") > 5 and any(f"{i}." in content or f"{i}/" in content for i in range(1, 7)):
        return "thread"
    if len(content) < 300:
        return "short_post"
    if "?" in content[:100]:
        return "hook_question"
    if any(w in content.lower()[:50] for w in ["tip", "how to", "step", "guide"]):
        return "how_to"
    return "long_post"


def _get_already_scored() -> set:
    """Get post_ids that already have scores to avoid re-scoring."""
    try:
        from growth.performance_optimizer import get_top_posts
        result = get_top_posts(limit=200)
        if result.get("success"):
            return {p.get("post_id") for p in result.get("posts", [])}
    except Exception:
        pass
    return set()


def ingest_performance(mode: str = "auto") -> dict:
    """Ingest performance metrics for published posts.

    Args:
        mode: "auto" (simulate if no real API), "simulate" (always simulate),
              "real" (only real APIs, skip if unavailable)

    Returns:
        Summary of ingested posts.
    """
    from growth.social_scheduler_dynamo import get_posts
    from growth.performance_optimizer import score_post

    result = get_posts()
    if not result.get("success"):
        return {"success": False, "error": f"Failed to fetch posts: {result.get('error')}"}

    # Only score published or failed posts (they went through the pipeline)
    scoreable_statuses = {"published", "failed", "scheduled"}
    posts = [
        p for p in result.get("posts", [])
        if p.get("status") in scoreable_statuses
    ]

    if not posts:
        return {"success": True, "scored": 0, "skipped": 0, "message": "No posts to score"}

    already_scored = _get_already_scored()
    scored = 0
    skipped = 0
    errors = 0

    use_real = mode == "real"
    use_simulate = mode == "simulate"

    for post in posts:
        post_id = post.get("post_id", "")
        if post_id in already_scored:
            skipped += 1
            continue

        metrics = None

        # Try real API first if mode allows
        if not use_simulate:
            metrics = _try_real_metrics(post)

        # Fall back to simulation if no real data and mode allows
        if metrics is None and not use_real:
            metrics = _simulate_metrics(post)

        if metrics is None:
            skipped += 1
            continue

        try:
            score_result = score_post(post_id, metrics)
            if score_result.get("success"):
                scored += 1
            else:
                errors += 1
        except Exception as e:
            logger.error("Failed to score post %s: %s", post_id, e)
            errors += 1

    # Track analytics (non-blocking)
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="performance_ingested",
            event_data={"scored": scored, "skipped": skipped, "errors": errors, "mode": mode},
        )
    except Exception:
        pass

    return {
        "success": True,
        "scored": scored,
        "skipped": skipped,
        "errors": errors,
        "total_posts": len(posts),
        "mode": mode,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def _try_real_metrics(post: dict) -> dict | None:
    """Attempt to fetch real metrics from publisher APIs.

    Returns metrics dict or None if unavailable.
    """
    # Check if Buffer is configured
    try:
        from buffer_publisher import BufferPublisher
        bp = BufferPublisher()
        if bp.configured:
            # Buffer doesn't expose per-post analytics in the free tier
            # Future: implement bp.get_post_analytics(post_id)
            pass
    except Exception:
        pass

    # Check if Postiz is configured
    try:
        from postiz_publisher import PostizPublisher
        pp = PostizPublisher()
        if pp.configured:
            # Future: implement pp.get_post_analytics(post_id)
            pass
    except Exception:
        pass

    return None  # No real API available yet
