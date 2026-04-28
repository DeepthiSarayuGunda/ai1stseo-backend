"""
Content Decay Detector Tool
Compares current SEO scores against historical baselines.
Flags pages with declining scores that need content refreshes.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import TypedDict
from collections import defaultdict


class DecayResult(TypedDict):
    url: str
    decaying: list
    stable: list
    improving: list
    total_tracked: int
    timestamp: str


def detect_decay(
    url: str,
    history_path: str = "data/history.json",
    threshold: int = 5
) -> DecayResult:
    """
    Compare current and historical SEO scores to detect content decay.

    Args:
        url: The site URL to check (matches against history)
        history_path: Path to scan history JSON
        threshold: Score drop that triggers a decay flag

    Returns:
        DecayResult with decaying/stable/improving pages
    """
    history_file = Path(history_path)
    if not history_file.exists():
        return DecayResult(
            url=url, decaying=[], stable=[], improving=[],
            total_tracked=0, timestamp=datetime.now().isoformat()
        )

    with open(history_file) as f:
        history = json.load(f)

    scans = history.get("scans", [])
    if not scans:
        return DecayResult(
            url=url, decaying=[], stable=[], improving=[],
            total_tracked=0, timestamp=datetime.now().isoformat()
        )

    # Group scans by URL
    by_url = defaultdict(list)
    for scan in scans:
        scan_url = scan.get("url", "")
        score = scan.get("score")
        ts = scan.get("timestamp", "")
        if scan_url and score is not None:
            by_url[scan_url].append({"score": score, "timestamp": ts})

    decaying = []
    stable = []
    improving = []

    for scan_url, url_scans in by_url.items():
        if len(url_scans) < 2:
            continue

        url_scans.sort(key=lambda x: x["timestamp"])
        latest = url_scans[-1]
        previous = url_scans[-2]
        change = latest["score"] - previous["score"]

        # Calculate historical average
        all_scores = [s["score"] for s in url_scans]
        avg = sum(all_scores) / len(all_scores)

        entry = {
            "url": scan_url,
            "latest_score": latest["score"],
            "previous_score": previous["score"],
            "change": round(change, 1),
            "historical_avg": round(avg, 1),
            "scan_count": len(url_scans),
            "latest_date": latest["timestamp"],
        }

        if change <= -threshold:
            entry["severity"] = "critical" if change <= -15 else "warning"
            decaying.append(entry)
        elif change >= threshold:
            improving.append(entry)
        else:
            stable.append(entry)

    return DecayResult(
        url=url,
        decaying=decaying,
        stable=stable,
        improving=improving,
        total_tracked=len(by_url),
        timestamp=datetime.now().isoformat(),
    )


TOOL_SCHEMA = {
    "name": "decay_detector",
    "description": "Detect content decay by comparing current SEO scores against historical baselines",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Site URL to check decay for"},
            "history_path": {"type": "string", "default": "data/history.json"},
            "threshold": {"type": "integer", "default": 5, "description": "Score drop threshold"},
        },
        "required": ["url"],
    },
}
