"""
growth/content_prioritizer.py
Content Prioritization Engine — decides what to create more of.

Analyzes performance data, platform weights, and content patterns
to produce ranked recommendations that feed back into the pipeline.

Reads from: performance_optimizer, analytics_tracker
Feeds into: content_pipeline (via optimization signals)
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default content type weights (used when no performance data exists)
DEFAULT_TYPE_WEIGHTS = {
    "thread": 0.25,
    "short_post": 0.20,
    "hook_question": 0.20,
    "how_to": 0.20,
    "long_post": 0.15,
}

DEFAULT_PLATFORM_WEIGHTS = {
    "x": 0.40,
    "linkedin": 0.35,
    "email_snippet": 0.15,
    "tiktok_script": 0.10,
}


def rank_content_types() -> dict:
    """Rank content types by performance score.

    Returns ordered list of content types with their avg scores
    and recommended production weights.
    """
    try:
        from growth.performance_optimizer import analyze_content_patterns
        result = analyze_content_patterns()
        if not result.get("success") or not result.get("patterns"):
            return {
                "success": True,
                "rankings": DEFAULT_TYPE_WEIGHTS,
                "source": "defaults",
                "message": "No performance data — using defaults",
            }
    except Exception:
        return {"success": True, "rankings": DEFAULT_TYPE_WEIGHTS, "source": "defaults"}

    patterns = result["patterns"]

    # Calculate weights from avg scores
    total_score = sum(p.get("avg_score", 0) for p in patterns.values())
    if total_score == 0:
        return {"success": True, "rankings": DEFAULT_TYPE_WEIGHTS, "source": "defaults"}

    rankings = {}
    for ct, data in patterns.items():
        weight = round(data.get("avg_score", 0) / total_score, 3)
        rankings[ct] = {
            "weight": weight,
            "avg_score": data.get("avg_score", 0),
            "count": data.get("count", 0),
            "best_score": data.get("best_score", 0),
        }

    # Sort by weight descending
    sorted_rankings = dict(sorted(rankings.items(), key=lambda x: x[1]["weight"], reverse=True))

    return {"success": True, "rankings": sorted_rankings, "source": "performance_data"}


def adjust_platform_weights() -> dict:
    """Adjust platform allocation based on performance data.

    Returns recommended platform weights for the content pipeline.
    """
    try:
        from growth.performance_optimizer import analyze_platform_performance
        result = analyze_platform_performance()
        if not result.get("success") or not result.get("platforms"):
            return {"success": True, "weights": DEFAULT_PLATFORM_WEIGHTS, "source": "defaults"}
    except Exception:
        return {"success": True, "weights": DEFAULT_PLATFORM_WEIGHTS, "source": "defaults"}

    platforms = result["platforms"]
    total_score = sum(p.get("avg_score", 0) for p in platforms.values())

    if total_score == 0:
        return {"success": True, "weights": DEFAULT_PLATFORM_WEIGHTS, "source": "defaults"}

    weights = {}
    for plat, data in platforms.items():
        weights[plat] = round(data.get("avg_score", 0) / total_score, 3)

    return {
        "success": True,
        "weights": weights,
        "best_platform": result.get("best_platform"),
        "source": "performance_data",
    }


def recommend_next_content(count: int = 5) -> dict:
    """Recommend what content to create next.

    Combines content type rankings, platform weights, and trending
    topics to produce actionable recommendations.
    """
    type_rankings = rank_content_types()
    platform_weights = adjust_platform_weights()

    recommendations = []

    # Get top content types
    rankings = type_rankings.get("rankings", DEFAULT_TYPE_WEIGHTS)
    if isinstance(rankings, dict) and rankings:
        first_key = next(iter(rankings))
        if isinstance(rankings[first_key], dict):
            sorted_types = sorted(rankings.items(), key=lambda x: x[1].get("weight", 0), reverse=True)
        else:
            sorted_types = sorted(rankings.items(), key=lambda x: x[1], reverse=True)
    else:
        sorted_types = list(DEFAULT_TYPE_WEIGHTS.items())

    # Get top platforms
    weights = platform_weights.get("weights", DEFAULT_PLATFORM_WEIGHTS)
    sorted_platforms = sorted(weights.items(), key=lambda x: x[1], reverse=True)

    # Generate recommendations
    for i, (content_type, _) in enumerate(sorted_types[:count]):
        platform = sorted_platforms[i % len(sorted_platforms)][0] if sorted_platforms else "x"
        recommendations.append({
            "rank": i + 1,
            "content_type": content_type,
            "platform": platform,
            "reason": f"Top-performing format on {platform}",
        })

    # Add trending topic recommendation
    try:
        from growth.content_discovery import fetch_trending_topics
        trends = fetch_trending_topics()
        if trends:
            recommendations.append({
                "rank": len(recommendations) + 1,
                "content_type": "trending",
                "platform": "x",
                "reason": f"Trending: {trends[0].get('title', 'AI SEO topic')[:80]}",
            })
    except Exception:
        pass

    return {
        "success": True,
        "recommendations": recommendations[:count],
        "content_type_rankings": type_rankings.get("rankings"),
        "platform_weights": platform_weights.get("weights"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
