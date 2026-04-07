"""
db_dynamo.py
DynamoDB replacement for db.py (PostgreSQL).
Provides the same function signatures so app.py routes work unchanged.
Uses Troy's dynamodb_helper.py pattern.

Tables:
  ai1stseo-content-briefs  (PK: id)
  ai1stseo-geo-probes      (PK: id, GSI: keyword-index)
"""

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

_dynamodb = None

CONTENT_BRIEFS_TABLE = 'ai1stseo-content-briefs'
GEO_PROBES_TABLE = 'ai1stseo-geo-probes'


def _get_table(table_name):
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    return _dynamodb.Table(table_name)


def _serialize(item):
    cleaned = {}
    for k, v in item.items():
        if v is None:
            continue
        if isinstance(v, float):
            cleaned[k] = Decimal(str(v))
        elif isinstance(v, (dict, list)):
            cleaned[k] = json.loads(json.dumps(v, default=str))
        elif isinstance(v, datetime):
            cleaned[k] = v.isoformat()
        else:
            cleaned[k] = v
    return cleaned


def _deserialize(item):
    if item is None:
        return None
    cleaned = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            cleaned[k] = int(v) if v == int(v) else float(v)
        else:
            cleaned[k] = v
    return cleaned


def init_db():
    """No-op for DynamoDB — tables are pre-created."""
    logger.info("DynamoDB mode — tables are pre-provisioned")


# ── content_briefs CRUD ───────────────────────────────────────────────────────

def save_content_brief(keyword, content_type, brief_json,
                       serp_competitors=None, keywords=None,
                       target_word_count=None, ai_generated=True,
                       project_id=None):
    """Save a content brief to DynamoDB. Returns brief ID."""
    table = _get_table(CONTENT_BRIEFS_TABLE)
    brief_id = str(uuid.uuid4())
    item = {
        'id': brief_id,
        'keyword': keyword,
        'content_type': content_type,
        'target_word_count': target_word_count or brief_json.get('target_word_count', 0),
        'brief_json': brief_json,
        'status': 'generated' if ai_generated else 'draft',
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    }
    if serp_competitors:
        item['competitors'] = serp_competitors
    if keywords:
        item['keywords'] = keywords
    table.put_item(Item=_serialize(item))
    logger.info("Saved content brief %s for keyword '%s'", brief_id, keyword)
    return brief_id


def get_content_briefs(limit=20, project_id=None, keyword_filter=''):
    """Retrieve past content briefs, optionally filtered by keyword."""
    table = _get_table(CONTENT_BRIEFS_TABLE)
    if keyword_filter:
        resp = table.scan(
            FilterExpression=Attr('keyword').contains(keyword_filter),
            Limit=limit
        )
    else:
        resp = table.scan(Limit=limit)
    rows = [_deserialize(i) for i in resp.get('Items', [])]
    rows.sort(key=lambda r: r.get('created_at', ''), reverse=True)
    return rows[:limit]


def get_content_brief_by_id(brief_id, project_id=None):
    """Retrieve a single brief by ID."""
    table = _get_table(CONTENT_BRIEFS_TABLE)
    resp = table.get_item(Key={'id': brief_id})
    item = resp.get('Item')
    if not item:
        return None
    return _deserialize(item)


# ── geo_probes CRUD ───────────────────────────────────────────────────────────

def insert_probe(keyword, brand, ai_model, cited,
                 citation_context=None, confidence=0.0,
                 site_url=None, response_snippet=None,
                 sentiment=None, query_text=None,
                 project_id=None):
    """Insert a probe result. Returns the new row ID."""
    table = _get_table(GEO_PROBES_TABLE)
    row_id = str(uuid.uuid4())
    item = {
        'id': row_id,
        'keyword': keyword,
        'brand_name': brand,
        'ai_model': ai_model,
        'cited': cited,
        'citation_context': citation_context or '',
        'confidence': confidence,
        'url': site_url or '',
        'response_snippet': response_snippet or '',
        'sentiment': sentiment or '',
        'ai_platform': ai_model,
        'query_text': query_text or '',
        'probe_timestamp': datetime.utcnow().isoformat(),
    }
    table.put_item(Item=_serialize(item))
    return row_id


def insert_visibility_batch(brand, ai_model, keyword,
                            geo_score, cited_count,
                            total_prompts, batch_results=None,
                            project_id=None):
    """Insert a batch visibility result. Returns row ID."""
    table = _get_table(GEO_PROBES_TABLE)
    row_id = str(uuid.uuid4())
    item = {
        'id': row_id,
        'keyword': keyword,
        'brand_name': brand,
        'ai_model': ai_model,
        'cited': cited_count > 0,
        'confidence': geo_score,
        'probe_timestamp': datetime.utcnow().isoformat(),
        'batch_results': batch_results or {},
    }
    table.put_item(Item=_serialize(item))
    return row_id


# ── geo_probes READ functions (match db.py signatures) ────────────────────────

def get_probes(limit: int = 50, brand: str = None, ai_model: str = None,
               project_id: str = None) -> list:
    """Retrieve probe results, optionally filtered by brand/model."""
    table = _get_table(GEO_PROBES_TABLE)
    filter_parts = []
    expr_vals = {}

    if brand:
        filter_parts.append(Attr('brand_name').eq(brand))
    if ai_model:
        filter_parts.append(Attr('ai_model').eq(ai_model))

    scan_kwargs = {'Limit': min(limit * 3, 200)}  # over-fetch then sort/trim
    if filter_parts:
        combined = filter_parts[0]
        for fp in filter_parts[1:]:
            combined = combined & fp
        scan_kwargs['FilterExpression'] = combined

    resp = table.scan(**scan_kwargs)
    rows = [_deserialize(i) for i in resp.get('Items', [])]
    rows.sort(key=lambda r: r.get('probe_timestamp', ''), reverse=True)
    return rows[:limit]


def get_visibility_history(limit: int = 20, brand: str = None,
                           project_id: str = None) -> list:
    """Retrieve visibility batch results (rows that have batch_results)."""
    table = _get_table(GEO_PROBES_TABLE)
    scan_kwargs = {'Limit': min(limit * 3, 200)}

    filter_expr = Attr('batch_results').exists()
    if brand:
        filter_expr = filter_expr & Attr('brand_name').eq(brand)
    scan_kwargs['FilterExpression'] = filter_expr

    resp = table.scan(**scan_kwargs)
    rows = [_deserialize(i) for i in resp.get('Items', [])]
    rows.sort(key=lambda r: r.get('probe_timestamp', ''), reverse=True)
    return rows[:limit]


def get_probe_trend(brand: str, limit: int = 30, project_id: str = None) -> list:
    """Get daily probe trend for a brand (aggregated by date).

    Returns list of dicts: [{date, total, cited, geo_score}, ...]
    """
    table = _get_table(GEO_PROBES_TABLE)
    scan_kwargs = {
        'FilterExpression': Attr('brand_name').eq(brand),
        'Limit': 500,
    }
    resp = table.scan(**scan_kwargs)
    rows = [_deserialize(i) for i in resp.get('Items', [])]

    # Aggregate by date
    from collections import defaultdict
    daily = defaultdict(lambda: {'total': 0, 'cited': 0})
    for r in rows:
        ts = r.get('probe_timestamp', '')
        date_str = ts[:10] if len(ts) >= 10 else 'unknown'
        daily[date_str]['total'] += 1
        if r.get('cited'):
            daily[date_str]['cited'] += 1

    trend = []
    for date_str in sorted(daily.keys(), reverse=True)[:limit]:
        d = daily[date_str]
        geo_score = round(d['cited'] / d['total'], 2) if d['total'] else 0
        trend.append({
            'date': date_str,
            'total': d['total'],
            'cited': d['cited'],
            'geo_score': geo_score,
        })

    return trend
