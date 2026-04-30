"""
growth/performance_optimizer.py
Performance Feedback Loop — analyzes content performance and generates
optimization signals that feed back into the content pipeline.

Reads from:
    - analytics_tracker (publish events, page_view, email_signup)
    - social_scheduler_dynamo (post metadata + status)

Produces:
    - Post-level performance scores
    - Platform performance rankings
    - Content pattern analysis (best hooks, formats, categories)
    - Optimization signals for the repurposer

Does NOT modify any existing modules. Read-only analysis layer.

Environment variables:
    GROWTH_SCORES_TABLE  — DynamoDB table (default: ai1stseo-content-scores)
    AWS_REGION           — AWS region (default: us-east-1)
"""

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3

logger = logging.getLogger(__name__)

SCORES_TABLE = os.environ.get("GROWTH_SCORES_TABLE", "ai1stseo-content-scores")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(SCORES_TABLE)
    return _table


def init_scores_table() -> None:
    """Create the scores table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(SCORES_TABLE)
        table.load()
        logger.info("Scores table %s exists", SCORES_TABLE)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating scores table %s ...", SCORES_TABLE)
        dynamodb.create_table(
            TableName=SCORES_TABLE,
            KeySchema=[{"AttributeName": "post_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "post_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("Scores table %s created", SCORES_TABLE)
    except Exception as e:
        logger.warning("Scores table init: %s", e)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _decimal_to_float(obj):
    """Convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


def score_post(post_id: str, metrics: dict) -> dict:
    """Calculate and store a performance score for a post.

    Args:
        post_id: The scheduled post ID.
        metrics: {"clicks": int, "impressions": int, "engagements": int,
                  "conversions": int, "platform": str, "content_type": str}

    Score formula:
        base = engagements * 3 + clicks * 2 + conversions * 5
        ctr_bonus = (clicks / impressions * 10) if impressions > 0
        score = base + ctr_bonus

    Returns:
        {"success": bool, "post_id": str, "score": float}
    """
    clicks = int(metrics.get("clicks", 0))
    impressions = int(metrics.get("impressions", 0))
    engagements = int(metrics.get("engagements", 0))
    conversions = int(metrics.get("conversions", 0))

    base = engagements * 3 + clicks * 2 + conversions * 5
    ctr_bonus = (clicks / impressions * 10) if impressions > 0 else 0
    score = round(base + ctr_bonus, 2)

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "post_id": post_id,
        "score": Decimal(str(score)),
        "clicks": clicks,
        "impressions": impressions,
        "engagements": engagements,
        "conversions": conversions,
        "ctr": round(clicks / impressions, 4) if impressions > 0 else 0,
        "platform": metrics.get("platform", ""),
        "content_type": metrics.get("content_type", ""),
        "scored_at": now,
    }

    try:
        _get_table().put_item(Item=item)
        return {"success": True, "post_id": post_id, "score": score}
    except Exception as e:
        logger.error("score_post error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


def get_top_posts(limit: int = 10) -> dict:
    """Get top-performing posts by score."""
    limit = max(1, min(limit, 50))
    try:
        resp = _get_table().scan()
        items = resp.get("Items", [])
        items.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        top = _decimal_to_float(items[:limit])
        return {"success": True, "posts": top, "count": len(top)}
    except Exception as e:
        logger.error("get_top_posts error: %s", e)
        return {"success": False, "error": f"Database error: {e}", "posts": []}


# ---------------------------------------------------------------------------
# Platform & Pattern Analysis
# ---------------------------------------------------------------------------

def analyze_platform_performance() -> dict:
    """Analyze performance by platform.

    Returns engagement rate, avg score, and post count per platform.
    """
    try:
        resp = _get_table().scan()
        items = resp.get("Items", [])
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not items:
        return {"success": True, "platforms": {}, "message": "No scored posts yet"}

    platforms = defaultdict(lambda: {
        "count": 0, "total_score": 0, "total_clicks": 0,
        "total_impressions": 0, "total_engagements": 0, "total_conversions": 0,
    })

    for item in items:
        plat = item.get("platform", "unknown")
        p = platforms[plat]
        p["count"] += 1
        p["total_score"] += float(item.get("score", 0))
        p["total_clicks"] += int(item.get("clicks", 0))
        p["total_impressions"] += int(item.get("impressions", 0))
        p["total_engagements"] += int(item.get("engagements", 0))
        p["total_conversions"] += int(item.get("conversions", 0))

    result = {}
    for plat, p in platforms.items():
        result[plat] = {
            "post_count": p["count"],
            "avg_score": round(p["total_score"] / p["count"], 2) if p["count"] else 0,
            "total_clicks": p["total_clicks"],
            "total_engagements": p["total_engagements"],
            "total_conversions": p["total_conversions"],
            "ctr": round(p["total_clicks"] / p["total_impressions"], 4) if p["total_impressions"] > 0 else 0,
        }

    # Rank platforms by avg score
    ranked = sorted(result.items(), key=lambda x: x[1]["avg_score"], reverse=True)
    return {
        "success": True,
        "platforms": dict(ranked),
        "best_platform": ranked[0][0] if ranked else None,
    }


def analyze_content_patterns() -> dict:
    """Analyze which content types and patterns perform best.

    Groups by content_type and extracts winning patterns.
    """
    try:
        resp = _get_table().scan()
        items = resp.get("Items", [])
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not items:
        return {"success": True, "patterns": {}, "message": "No scored posts yet"}

    by_type = defaultdict(lambda: {"count": 0, "total_score": 0, "scores": []})

    for item in items:
        ct = item.get("content_type", "unknown")
        score = float(item.get("score", 0))
        by_type[ct]["count"] += 1
        by_type[ct]["total_score"] += score
        by_type[ct]["scores"].append(score)

    patterns = {}
    for ct, data in by_type.items():
        avg = round(data["total_score"] / data["count"], 2) if data["count"] else 0
        scores = sorted(data["scores"], reverse=True)
        patterns[ct] = {
            "count": data["count"],
            "avg_score": avg,
            "best_score": scores[0] if scores else 0,
            "worst_score": scores[-1] if scores else 0,
        }

    ranked = sorted(patterns.items(), key=lambda x: x[1]["avg_score"], reverse=True)
    return {
        "success": True,
        "patterns": dict(ranked),
        "best_content_type": ranked[0][0] if ranked else None,
    }


# ---------------------------------------------------------------------------
# Optimization Signals — feeds back into the repurposer
# ---------------------------------------------------------------------------

def generate_optimization_signals() -> dict:
    """Generate optimization signals based on all available performance data.

    Returns a structured set of recommendations that the pipeline
    can use to adjust content generation behavior.

    Signal structure:
        preferred_platforms: ordered list of platforms by performance
        preferred_formats: ordered list of content types by performance
        platform_weights: {"x": 0.4, "linkedin": 0.6} — allocation ratios
        generation_hints: list of text hints for the AI repurposer
    """
    platform_data = analyze_platform_performance()
    pattern_data = analyze_content_patterns()

    signals = {
        "success": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preferred_platforms": [],
        "preferred_formats": [],
        "platform_weights": {},
        "generation_hints": [],
        "has_data": False,
    }

    # Platform signals
    if platform_data.get("success") and platform_data.get("platforms"):
        signals["has_data"] = True
        platforms = platform_data["platforms"]
        ranked_plats = list(platforms.keys())
        signals["preferred_platforms"] = ranked_plats

        # Weight by relative avg_score
        total_avg = sum(p["avg_score"] for p in platforms.values())
        if total_avg > 0:
            signals["platform_weights"] = {
                k: round(v["avg_score"] / total_avg, 2)
                for k, v in platforms.items()
            }

        best = platform_data.get("best_platform")
        if best:
            signals["generation_hints"].append(
                f"Prioritize {best} — highest avg engagement score."
            )

        # Identify underperformers
        for plat, stats in platforms.items():
            if stats["avg_score"] == 0 and stats["post_count"] > 2:
                signals["generation_hints"].append(
                    f"Consider reducing {plat} frequency — zero engagement after {stats['post_count']} posts."
                )

    # Content type signals
    if pattern_data.get("success") and pattern_data.get("patterns"):
        signals["has_data"] = True
        patterns = pattern_data["patterns"]
        signals["preferred_formats"] = list(patterns.keys())

        best_type = pattern_data.get("best_content_type")
        if best_type:
            signals["generation_hints"].append(
                f"Best performing format: {best_type}. Generate more of this type."
            )

        # Find formats to avoid
        for ct, stats in patterns.items():
            if stats["avg_score"] == 0 and stats["count"] > 3:
                signals["generation_hints"].append(
                    f"Format '{ct}' has zero engagement — consider dropping or reworking."
                )

    # Default hints when no data yet
    if not signals["has_data"]:
        signals["generation_hints"] = [
            "No performance data yet. Using default strategy.",
            "Prioritize X threads and LinkedIn posts for initial reach.",
            "Use hooks: questions, stats, contrarian takes.",
            "Include clear CTAs with UTM-tagged links.",
        ]
        signals["preferred_platforms"] = ["x", "linkedin"]
        signals["preferred_formats"] = ["x_thread", "linkedin", "x"]
        signals["platform_weights"] = {"x": 0.5, "linkedin": 0.3, "email_snippet": 0.2}

    return signals


def get_performance_dashboard(days: int = 30) -> dict:
    """Extended performance dashboard with scoring, platform analysis, and patterns.

    Combines top posts, platform rankings, content patterns, and optimization signals
    into a single response for the admin dashboard.
    """
    top = get_top_posts(limit=10)
    platforms = analyze_platform_performance()
    patterns = analyze_content_patterns()
    signals = generate_optimization_signals()

    # Also pull publish event counts from analytics
    publish_stats = {"attempted": 0, "succeeded": 0, "failed": 0}
    try:
        from growth.analytics_tracker import get_summary
        summary = get_summary(days=days)
        if summary.get("success"):
            by_type = summary.get("by_type", {})
            publish_stats = {
                "attempted": by_type.get("publish_attempted", 0),
                "succeeded": by_type.get("publish_succeeded", 0),
                "failed": by_type.get("publish_failed", 0),
            }
    except Exception:
        pass

    # Scheduled post counts by status
    post_stats = {"total": 0, "scheduled": 0, "published": 0, "failed": 0, "draft": 0}
    try:
        from growth.social_scheduler_dynamo import get_posts
        result = get_posts()
        if result.get("success"):
            posts = result.get("posts", [])
            post_stats["total"] = len(posts)
            for p in posts:
                s = p.get("status", "")
                if s in post_stats:
                    post_stats[s] += 1
    except Exception:
        pass

    return {
        "success": True,
        "days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_posts": top.get("posts", []),
        "platform_performance": platforms.get("platforms", {}),
        "best_platform": platforms.get("best_platform"),
        "content_patterns": patterns.get("patterns", {}),
        "best_content_type": patterns.get("best_content_type"),
        "optimization_signals": signals,
        "publish_stats": publish_stats,
        "post_stats": post_stats,
    }
