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
