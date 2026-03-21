"""
Competitor Monitoring Tool
Track competitor SEO scores and benchmark against your sites
"""

import json
from pathlib import Path
from datetime import datetime
from typing import TypedDict, Optional

from .seo_scanner import scan_site


def _save_competitor_history(your_url, your_data, your_rank, competitor_data, history_path):
    """Save competitor comparison to RDS, fall back to JSON file."""
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot = {
        "your_score": your_data["score"],
        "your_rank": your_rank,
        "competitor_scores": {c["url"]: c["score"] for c in competitor_data},
    }
    # Try RDS first
    try:
        from db import execute
        execute(
            "INSERT INTO reports (project_id, report_type, title, data) "
            "VALUES (%s, 'competitor', %s, %s)",
            (
                "24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2",
                "Competitor comparison {}".format(today),
                json.dumps({"url": your_url, **snapshot}, default=str),
            ),
        )
        return
    except Exception:
        pass
    # Fallback: JSON file (EC2 only, Lambda has no writable FS)
    try:
        history_file = Path(history_path)
        history = {}
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)
        if today not in history:
            history[today] = {}
        history[today][your_url] = snapshot
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


class CompetitorComparison(TypedDict):
    your_site: dict
    competitors: list[dict]
    your_rank: int
    insights: list[str]
    ai_analysis: Optional[str]
    timestamp: str


def monitor_competitors(
    your_url: str,
    competitor_urls: list[str],
    history_path: str = "data/competitor_history.json"
) -> CompetitorComparison:
    """
    OpenClaw Tool: Monitor competitors and benchmark SEO performance
    
    Args:
        your_url: Your website URL
        competitor_urls: List of competitor URLs to track
        history_path: Path to store comparison history
    
    Returns:
        CompetitorComparison with rankings and insights
    """
    # Scan your site
    your_result = scan_site(your_url)
    your_data = {
        "url": your_url,
        "score": your_result["score"],
        "critical_issues": len(your_result["critical_issues"]),
        "warnings": len(your_result["warnings"]),
        "load_time": your_result["load_time"]
    }
    
    # Scan competitors
    competitor_data = []
    for comp_url in competitor_urls:
        result = scan_site(comp_url)
        competitor_data.append({
            "url": comp_url,
            "score": result["score"],
            "critical_issues": len(result["critical_issues"]),
            "warnings": len(result["warnings"]),
            "load_time": result["load_time"]
        })
    
    # Rank all sites
    all_sites = [your_data] + competitor_data
    all_sites.sort(key=lambda x: x["score"], reverse=True)
    your_rank = next(i for i, s in enumerate(all_sites, 1) if s["url"] == your_url)
    
    # Generate insights
    insights = []
    
    if your_rank == 1:
        insights.append("You're leading the pack. Maintain your advantage.")
    else:
        leader = all_sites[0]
        gap = leader["score"] - your_data["score"]
        insights.append(f"You're ranked #{your_rank}. Gap to leader: {gap} points")
    
    # Compare specific metrics
    avg_competitor_score = sum(c["score"] for c in competitor_data) / len(competitor_data) if competitor_data else 0
    if your_data["score"] > avg_competitor_score:
        insights.append(f"Your score ({your_data['score']}) beats competitor average ({avg_competitor_score:.0f})")
    else:
        insights.append(f"Your score ({your_data['score']}) is below competitor average ({avg_competitor_score:.0f})")
    
    # Load time comparison
    avg_load = sum(c["load_time"] for c in competitor_data) / len(competitor_data) if competitor_data else 0
    if your_data["load_time"] < avg_load:
        insights.append(f"Your site is faster ({your_data['load_time']}s) than competitors ({avg_load:.1f}s avg)")
    else:
        insights.append(f"Your site is slower ({your_data['load_time']}s) than competitors ({avg_load:.1f}s avg)")
    
    # Check for competitors with fewer issues
    better_competitors = [c for c in competitor_data if c["critical_issues"] < your_data["critical_issues"]]
    if better_competitors:
        insights.append(f"{len(better_competitors)} competitor(s) have fewer critical issues than you")
    
    # AI-powered competitive analysis (if available)
    ai_analysis = None
    try:
        from .ai_analyzer import get_analyzer
        analyzer = get_analyzer()
        ai_analysis = analyzer.analyze_competitor_gap(your_data, competitor_data)
    except Exception:
        pass  # AI analysis optional
    
    # Save history to RDS (Lambda-compatible), fall back to JSON file
    _save_competitor_history(your_url, your_data, your_rank, competitor_data, history_path)
    
    return CompetitorComparison(
        your_site=your_data,
        competitors=competitor_data,
        your_rank=your_rank,
        insights=insights,
        ai_analysis=ai_analysis,
        timestamp=datetime.now().isoformat()
    )


TOOL_SCHEMA = {
    "name": "competitor_monitor",
    "description": "Monitor competitor SEO scores and benchmark against your sites",
    "input_schema": {
        "type": "object",
        "properties": {
            "your_url": {"type": "string", "description": "Your website URL"},
            "competitor_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of competitor URLs"
            }
        },
        "required": ["your_url", "competitor_urls"]
    }
}
