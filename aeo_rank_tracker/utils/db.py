"""
DynamoDB storage for AEO Rank Tracker results.
Uses the project's existing DynamoDB patterns.
"""

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

TABLE_NAME = "ai1stseo-aeo-rank-tracker"

_dynamodb = None


def _get_table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    return _dynamodb.Table(TABLE_NAME)


def _serialize(item: dict) -> dict:
    """Convert Python types to DynamoDB-safe types."""
    cleaned = {}
    for k, v in item.items():
        if v is None:
            continue
        if isinstance(v, float):
            cleaned[k] = Decimal(str(round(v, 6)))
        elif isinstance(v, bool):
            cleaned[k] = v
        elif isinstance(v, (dict, list)):
            cleaned[k] = json.loads(json.dumps(v, default=str))
        elif isinstance(v, datetime):
            cleaned[k] = v.isoformat()
        else:
            cleaned[k] = v
    return cleaned


def _deserialize(item: dict) -> dict:
    """Convert DynamoDB types back to Python types."""
    if not item:
        return {}
    cleaned = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            cleaned[k] = int(v) if v == int(v) else float(v)
        else:
            cleaned[k] = v
    return cleaned


def save_results(results: list[dict]) -> list[str]:
    """Save a batch of scan results. Returns list of IDs."""
    table = _get_table()
    ids = []
    with table.batch_writer() as batch:
        for r in results:
            row_id = str(uuid.uuid4())
            item = {
                "id": row_id,
                "query": r.get("query", ""),
                "llm": r.get("llm", ""),
                "citation_found": r.get("citation_found", False),
                "match_type": r.get("match_type"),
                "matches": r.get("matches", []),
                "response_snippet": r.get("response_snippet", "")[:500],
                "sources": r.get("sources", []),
                "brand_name": r.get("brand_name", ""),
                "target_domain": r.get("target_domain", ""),
                "timestamp": r.get("timestamp", datetime.utcnow().isoformat()),
                "scan_id": r.get("scan_id", ""),
            }
            batch.put_item(Item=_serialize(item))
            ids.append(row_id)
    logger.info("Saved %d AEO rank tracker results", len(ids))
    return ids


def get_history(query: str = None, llm: str = None, brand: str = None,
                limit: int = 50) -> list[dict]:
    """Retrieve scan history with optional filters."""
    table = _get_table()
    filters = []
    if query:
        filters.append(Attr("query").contains(query))
    if llm:
        filters.append(Attr("llm").eq(llm))
    if brand:
        filters.append(Attr("brand_name").eq(brand))

    scan_kwargs = {"Limit": min(limit * 3, 300)}
    if filters:
        combined = filters[0]
        for f in filters[1:]:
            combined = combined & f
        scan_kwargs["FilterExpression"] = combined

    resp = table.scan(**scan_kwargs)
    rows = [_deserialize(i) for i in resp.get("Items", [])]
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return rows[:limit]


def get_velocity_data(brand: str, limit: int = 500) -> dict:
    """Aggregate scan results into daily velocity metrics for a brand.

    Returns:
        {
            "daily": [{"date": "2026-05-01", "total": 6, "cited": 3, "rate": 50.0}, ...],
            "by_llm": {"gemini": [{"date": ..., "total": ..., "cited": ..., "rate": ...}], ...},
            "by_query": {"what is X": [{"date": ..., "total": ..., "cited": ..., "rate": ...}], ...},
            "totals": {"total": 20, "cited": 8, "rate": 40.0, "scans": 5, "first_scan": "...", "last_scan": "..."},
        }
    """
    table = _get_table()
    scan_kwargs = {"Limit": min(limit * 3, 1500)}
    if brand:
        scan_kwargs["FilterExpression"] = Attr("brand_name").eq(brand)

    resp = table.scan(**scan_kwargs)
    rows = [_deserialize(i) for i in resp.get("Items", [])]

    if not rows:
        return {"daily": [], "by_llm": {}, "by_query": {}, "totals": {"total": 0, "cited": 0, "rate": 0, "scans": 0}}

    # Sort by timestamp
    rows.sort(key=lambda r: r.get("timestamp", ""))

    # Aggregate by date
    from collections import defaultdict
    daily = defaultdict(lambda: {"total": 0, "cited": 0})
    by_llm = defaultdict(lambda: defaultdict(lambda: {"total": 0, "cited": 0}))
    by_query = defaultdict(lambda: defaultdict(lambda: {"total": 0, "cited": 0}))
    scan_ids = set()

    for r in rows:
        ts = r.get("timestamp", "")
        date_str = ts[:10] if len(ts) >= 10 else "unknown"
        llm = r.get("llm", "unknown")
        query = r.get("query", "unknown")
        cited = r.get("citation_found", False)

        daily[date_str]["total"] += 1
        if cited:
            daily[date_str]["cited"] += 1

        by_llm[llm][date_str]["total"] += 1
        if cited:
            by_llm[llm][date_str]["cited"] += 1

        by_query[query][date_str]["total"] += 1
        if cited:
            by_query[query][date_str]["cited"] += 1

        if r.get("scan_id"):
            scan_ids.add(r["scan_id"])

    # Format daily
    daily_list = []
    for date_str in sorted(daily.keys()):
        d = daily[date_str]
        rate = round((d["cited"] / d["total"]) * 100, 1) if d["total"] else 0
        daily_list.append({"date": date_str, "total": d["total"], "cited": d["cited"], "rate": rate})

    # Format by_llm
    llm_data = {}
    for llm, dates in by_llm.items():
        llm_data[llm] = []
        for date_str in sorted(dates.keys()):
            d = dates[date_str]
            rate = round((d["cited"] / d["total"]) * 100, 1) if d["total"] else 0
            llm_data[llm].append({"date": date_str, "total": d["total"], "cited": d["cited"], "rate": rate})

    # Format by_query
    query_data = {}
    for query, dates in by_query.items():
        query_data[query] = []
        for date_str in sorted(dates.keys()):
            d = dates[date_str]
            rate = round((d["cited"] / d["total"]) * 100, 1) if d["total"] else 0
            query_data[query].append({"date": date_str, "total": d["total"], "cited": d["cited"], "rate": rate})

    # Totals
    total = len(rows)
    cited = sum(1 for r in rows if r.get("citation_found"))
    rate = round((cited / total) * 100, 1) if total else 0
    timestamps = [r.get("timestamp", "") for r in rows if r.get("timestamp")]

    return {
        "daily": daily_list,
        "by_llm": llm_data,
        "by_query": query_data,
        "totals": {
            "total": total,
            "cited": cited,
            "rate": rate,
            "scans": len(scan_ids),
            "first_scan": min(timestamps) if timestamps else None,
            "last_scan": max(timestamps) if timestamps else None,
        },
    }


def get_tracked_brands(limit: int = 100) -> list[dict]:
    """Get all brands that have been scanned, with their latest stats."""
    table = _get_table()
    resp = table.scan(Limit=min(limit * 10, 1000))
    rows = [_deserialize(i) for i in resp.get("Items", [])]

    from collections import defaultdict
    brands = defaultdict(lambda: {"total": 0, "cited": 0, "last_scan": "", "domain": ""})

    for r in rows:
        b = r.get("brand_name", "")
        if not b:
            continue
        brands[b]["total"] += 1
        if r.get("citation_found"):
            brands[b]["cited"] += 1
        ts = r.get("timestamp", "")
        if ts > brands[b]["last_scan"]:
            brands[b]["last_scan"] = ts
        if r.get("target_domain"):
            brands[b]["domain"] = r["target_domain"]

    result = []
    for name, stats in brands.items():
        rate = round((stats["cited"] / stats["total"]) * 100, 1) if stats["total"] else 0
        result.append({
            "brand": name,
            "domain": stats["domain"],
            "total": stats["total"],
            "cited": stats["cited"],
            "rate": rate,
            "last_scan": stats["last_scan"],
        })

    result.sort(key=lambda x: x["last_scan"], reverse=True)
    return result[:limit]
