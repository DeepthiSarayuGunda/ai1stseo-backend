#!/usr/bin/env python3
"""
freshness_integration.py
Isolated integration path for freshness / time-stamped updates.

Supports continuous daily content & Q&A refresh signals for AI visibility.
Consumes data from the existing FreshnessTracker and GEO Score Tracker
without modifying them.

Provides:
  1. Daily freshness digest — aggregated freshness signals per brand
  2. Freshness-to-GEO correlation pipeline — links content updates to score changes
  3. Q&A refresh signal tracking — monitors FAQ/schema freshness for AEO
"""

import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
FRESHNESS_DIGEST_TABLE = f'{TABLE_PREFIX}deepthi-freshness-digest'

_ddb = None


def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb


def _now():
    return datetime.now(timezone.utc).isoformat()


def _today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _dec(v):
    if v is None:
        return Decimal('0')
    return Decimal(str(round(float(v), 4)))


def _deserialize(item):
    if not item:
        return None
    d = dict(item)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v) if '.' in str(v) else int(v)
    return d


class FreshnessDigest:
    """
    Daily freshness digest — aggregates freshness signals per brand.
    Stores in its own table so the intelligence layer can query
    daily refresh patterns without scanning the full freshness-signals table.

    Table: deepthi-freshness-digest
    PK: brand, SK: date (YYYY-MM-DD)
    """

    def __init__(self):
        try:
            self._table = _get_ddb().Table(FRESHNESS_DIGEST_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def record_daily_digest(self, brand: str, data: Dict) -> str:
        """Record a daily freshness digest for a brand."""
        date = data.get('date', _today())
        item = {
            'brand': brand,
            'date': date,
            'avg_freshness_score': _dec(data.get('avg_freshness_score', 0)),
            'pages_checked': data.get('pages_checked', 0),
            'pages_stale': data.get('pages_stale', 0),
            'pages_fresh': data.get('pages_fresh', 0),
            'faq_count': data.get('faq_count', 0),
            'schema_updated_count': data.get('schema_updated_count', 0),
            'geo_score_at_check': _dec(data.get('geo_score_at_check', 0)),
            'recorded_at': _now(),
        }
        if self._available:
            self._table.put_item(Item=item)
        return date

    def get_digest_trend(self, brand: str, days: int = 30) -> List[Dict]:
        """Get daily freshness digest trend for a brand."""
        if not self._available:
            return []
        resp = self._table.query(
            KeyConditionExpression=Key('brand').eq(brand),
            ScanIndexForward=False,
            Limit=days,
        )
        return [_deserialize(i) for i in resp.get('Items', [])]

    def get_latest_digest(self, brand: str) -> Optional[Dict]:
        """Get the most recent daily digest for a brand."""
        trend = self.get_digest_trend(brand, days=1)
        return trend[0] if trend else None

    def compute_digest_from_freshness(self, brand: str) -> Dict:
        """
        Pull current freshness data from the existing FreshnessTracker
        and compute a daily digest. Read-only against existing tables.
        """
        try:
            from deepthi_intelligence.freshness_tracker import FreshnessTracker
            tracker = FreshnessTracker()
        except Exception as e:
            logger.warning("Cannot access FreshnessTracker: %s", e)
            return {'brand': brand, 'status': 'unavailable', 'error': str(e)}

        # Get stale content
        stale = tracker.get_stale_content(threshold_score=40, limit=200)
        all_items = tracker.get_stale_content(threshold_score=100, limit=200)

        pages_checked = len(all_items)
        pages_stale = len(stale)
        pages_fresh = pages_checked - pages_stale

        scores = [item.get('freshness_score', 0) for item in all_items]
        avg_score = sum(scores) / len(scores) if scores else 0

        faq_count = sum(item.get('faq_count', 0) for item in all_items)
        schema_updated = sum(1 for item in all_items if item.get('schema_date_modified'))

        # Get current GEO score for correlation
        geo_score = 0
        try:
            from deepthi_intelligence.data_hooks import get_m3_geo_score
            m3 = get_m3_geo_score(brand)
            if m3:
                geo_score = m3.get('geo_score', 0)
        except Exception:
            pass

        digest = {
            'brand': brand,
            'date': _today(),
            'avg_freshness_score': round(avg_score, 1),
            'pages_checked': pages_checked,
            'pages_stale': pages_stale,
            'pages_fresh': pages_fresh,
            'faq_count': faq_count,
            'schema_updated_count': schema_updated,
            'geo_score_at_check': geo_score,
        }

        # Store it
        self.record_daily_digest(brand, digest)
        digest['status'] = 'computed'
        return digest
