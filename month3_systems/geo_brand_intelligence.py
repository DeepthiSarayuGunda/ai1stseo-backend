#!/usr/bin/env python3
"""
3.2 GEO Brand Intelligence System

Five components:
  1. GEO Score Tracker — weekly time-series
  2. Keyword Performance Register — per-keyword weekly tracking
  3. Competitor Visibility Matrix — weekly competitor scores
  4. GEO Improvement Action Register — cause-effect evidence
  5. Provider Sensitivity Map — provider response patterns

All backed by DynamoDB.
"""

import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

GEO_TRACKER_TABLE = f'{TABLE_PREFIX}geo-score-tracker'
KW_PERF_TABLE = f'{TABLE_PREFIX}geo-keyword-performance'
COMP_MATRIX_TABLE = f'{TABLE_PREFIX}geo-competitor-matrix'
ACTION_REG_TABLE = f'{TABLE_PREFIX}geo-action-register'
PROVIDER_MAP_TABLE = f'{TABLE_PREFIX}geo-provider-sensitivity'

_ddb = None

def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb

def _now():
    return datetime.now(timezone.utc).isoformat()

def _week():
    return datetime.now(timezone.utc).strftime('%Y-W%W')

def _dec(v):
    if v is None: return Decimal('0')
    return Decimal(str(v))

def _deserialize(item):
    if not item: return None
    d = dict(item)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v) if '.' in str(v) else int(v)
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GEO SCORE TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

class GEOScoreTracker:
    """Weekly time-series of overall GEO and visibility scores."""

    def __init__(self):
        self._table = _get_ddb().Table(GEO_TRACKER_TABLE)

    def record_week(self, brand: str, data: Dict) -> str:
        week = data.get('week', _week())
        item = {
            'brand': brand,
            'week': week,
            'geo_score': _dec(data.get('geo_score', 0)),
            'visibility_score': _dec(data.get('visibility_score', 0)),
            'keywords_probed': data.get('keywords_probed', 0),
            'keywords_cited': data.get('keywords_cited', 0),
            'provider_scores': json.dumps(data.get('provider_scores', {})),
            'recorded_at': _now(),
        }
        self._table.put_item(Item=item)
        return week

    def get_trend(self, brand: str, limit: int = 12) -> List[Dict]:
        resp = self._table.query(
            KeyConditionExpression=Key('brand').eq(brand),
            ScanIndexForward=False, Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('provider_scores'), str):
                try: i['provider_scores'] = json.loads(i['provider_scores'])
                except: pass
        return items

    def get_latest(self, brand: str) -> Optional[Dict]:
        trend = self.get_trend(brand, limit=1)
        return trend[0] if trend else None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. KEYWORD PERFORMANCE REGISTER
# ═══════════════════════════════════════════════════════════════════════════════

class KeywordPerformanceRegister:
    """Per-keyword weekly tracking with trend direction."""

    def __init__(self):
        self._table = _get_ddb().Table(KW_PERF_TABLE)

    def record(self, keyword: str, week: str, data: Dict):
        item = {
            'keyword': keyword,
            'week': week,
            'geo_score': _dec(data.get('geo_score', 0)),
            'visibility_score': _dec(data.get('visibility_score', 0)),
            'confidence': _dec(data.get('confidence', 0)),
            'trend': data.get('trend', 'stable'),
            'priority_flag': data.get('priority_flag', False),
            'recorded_at': _now(),
        }
        self._table.put_item(Item=item)

    def get_keyword_history(self, keyword: str, limit: int = 12) -> List[Dict]:
        resp = self._table.query(
            KeyConditionExpression=Key('keyword').eq(keyword),
            ScanIndexForward=False, Limit=limit)
        return [_deserialize(i) for i in resp.get('Items', [])]

    def get_all_latest(self, week: str = None) -> List[Dict]:
        week = week or _week()
        resp = self._table.scan(
            FilterExpression=Attr('week').eq(week), Limit=500)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('geo_score', 0))
        return items

    def bulk_record(self, week: str, records: List[Dict]) -> int:
        count = 0
        for r in records:
            kw = r.get('keyword')
            if not kw: continue
            self.record(kw, week, r)
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# 3. COMPETITOR VISIBILITY MATRIX
# ═══════════════════════════════════════════════════════════════════════════════

class CompetitorVisibilityMatrix:
    """Weekly cross-model visibility scores per competitor."""

    def __init__(self):
        self._table = _get_ddb().Table(COMP_MATRIX_TABLE)

    def record(self, competitor: str, week: str, data: Dict):
        item = {
            'competitor': competitor,
            'week': week,
            'visibility_score': _dec(data.get('visibility_score', 0)),
            'keywords_cited': data.get('keywords_cited', 0),
            'total_keywords': data.get('total_keywords', 0),
            'provider_breakdown': json.dumps(data.get('provider_breakdown', {})),
            'top_keywords': json.dumps(data.get('top_keywords', [])),
            'recorded_at': _now(),
        }
        self._table.put_item(Item=item)

    def get_matrix(self, week: str = None) -> List[Dict]:
        week = week or _week()
        resp = self._table.scan(
            FilterExpression=Attr('week').eq(week), Limit=100)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            for f in ('provider_breakdown', 'top_keywords'):
                if isinstance(i.get(f), str):
                    try: i[f] = json.loads(i[f])
                    except: pass
        items.sort(key=lambda x: x.get('visibility_score', 0), reverse=True)
        return items

    def get_competitor_trend(self, competitor: str, limit: int = 12) -> List[Dict]:
        resp = self._table.query(
            KeyConditionExpression=Key('competitor').eq(competitor),
            ScanIndexForward=False, Limit=limit)
        return [_deserialize(i) for i in resp.get('Items', [])]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GEO IMPROVEMENT ACTION REGISTER
# ═══════════════════════════════════════════════════════════════════════════════

class GEOActionRegister:
    """Log every action taken to improve GEO visibility with cause-effect tracking."""

    def __init__(self):
        self._table = _get_ddb().Table(ACTION_REG_TABLE)

    def log_action(self, brand: str, data: Dict) -> str:
        action_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'action_id': action_id,
            'brand': brand,
            'action_type': data.get('action_type', 'content'),
            'description': data.get('description', ''),
            'target_keywords': json.dumps(data.get('target_keywords', [])),
            'geo_score_before': _dec(data.get('geo_score_before', 0)),
            'geo_score_after': _dec(data.get('geo_score_after', 0)),
            'measured_impact': _dec(data.get('measured_impact', 0)),
            'status': data.get('status', 'pending'),
            'created_at': now,
            'updated_at': now,
        }
        self._table.put_item(Item=item)
        return action_id

    def update_impact(self, action_id: str, geo_score_after: float):
        resp = self._table.get_item(Key={'action_id': action_id})
        item = resp.get('Item')
        if not item: return
        before = float(item.get('geo_score_before', 0))
        impact = geo_score_after - before
        self._table.update_item(
            Key={'action_id': action_id},
            UpdateExpression='SET geo_score_after = :a, measured_impact = :i, #s = :s, updated_at = :t',
            ExpressionAttributeValues={
                ':a': _dec(geo_score_after), ':i': _dec(impact),
                ':s': 'measured', ':t': _now()},
            ExpressionAttributeNames={'#s': 'status'})

    def get_all(self, brand: str = None, limit: int = 50) -> List[Dict]:
        if brand:
            resp = self._table.scan(
                FilterExpression=Attr('brand').eq(brand), Limit=limit)
        else:
            resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('target_keywords'), str):
                try: i['target_keywords'] = json.loads(i['target_keywords'])
                except: pass
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return items


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PROVIDER SENSITIVITY MAP
# ═══════════════════════════════════════════════════════════════════════════════

class ProviderSensitivityMap:
    """Track which providers respond fastest/slowest to content changes."""

    def __init__(self):
        self._table = _get_ddb().Table(PROVIDER_MAP_TABLE)

    def update_provider(self, provider: str, data: Dict):
        now = _now()
        item = {
            'provider': provider,
            'response_speed': data.get('response_speed', 'medium'),
            'volatility': data.get('volatility', 'low'),
            'avg_days_to_reflect': _dec(data.get('avg_days_to_reflect', 14)),
            'citation_rate': _dec(data.get('citation_rate', 0)),
            'best_for': data.get('best_for', 'monitoring'),
            'notes': data.get('notes', ''),
            'updated_at': now,
        }
        self._table.put_item(Item=item)

    def get_map(self) -> List[Dict]:
        resp = self._table.scan()
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('citation_rate', 0), reverse=True)
        return items

    def seed_defaults(self) -> int:
        defaults = [
            {'provider': 'nova', 'response_speed': 'fast', 'volatility': 'low',
             'avg_days_to_reflect': 7, 'citation_rate': 0.35, 'best_for': 'monitoring'},
            {'provider': 'claude', 'response_speed': 'medium', 'volatility': 'medium',
             'avg_days_to_reflect': 14, 'citation_rate': 0.42, 'best_for': 'experimentation'},
            {'provider': 'openai', 'response_speed': 'slow', 'volatility': 'low',
             'avg_days_to_reflect': 21, 'citation_rate': 0.38, 'best_for': 'baseline'},
            {'provider': 'gemini', 'response_speed': 'medium', 'volatility': 'high',
             'avg_days_to_reflect': 10, 'citation_rate': 0.30, 'best_for': 'experimentation'},
            {'provider': 'perplexity', 'response_speed': 'fast', 'volatility': 'high',
             'avg_days_to_reflect': 3, 'citation_rate': 0.55, 'best_for': 'monitoring'},
            {'provider': 'groq', 'response_speed': 'fast', 'volatility': 'medium',
             'avg_days_to_reflect': 7, 'citation_rate': 0.25, 'best_for': 'monitoring'},
            {'provider': 'ollama', 'response_speed': 'medium', 'volatility': 'low',
             'avg_days_to_reflect': 14, 'citation_rate': 0.20, 'best_for': 'baseline'},
        ]
        for d in defaults:
            p = d.pop('provider')
            self.update_provider(p, d)
        return len(defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# WEEKLY CADENCE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_geo_weekly_cadence(brand: str, competitors: List[str] = None) -> Dict:
    """Execute the GEO System weekly cadence."""
    results = {}
    week = _week()

    tracker = GEOScoreTracker()
    latest = tracker.get_latest(brand)
    results['latest_geo_score'] = latest.get('geo_score', 0) if latest else 0
    results['week'] = week

    kpr = KeywordPerformanceRegister()
    kw_data = kpr.get_all_latest(week)
    results['keywords_tracked'] = len(kw_data)

    if competitors:
        matrix = CompetitorVisibilityMatrix()
        comp_data = matrix.get_matrix(week)
        results['competitors_tracked'] = len(comp_data)

    results['status'] = 'complete'
    results['timestamp'] = _now()
    return results
