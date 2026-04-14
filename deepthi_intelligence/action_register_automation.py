#!/usr/bin/env python3
"""
action_register_automation.py
Automated Action Register — closes the loop on GEO improvement tracking.

After every automated probe cycle:
  1. Logs before/after geo_score automatically
  2. Tracks what changed and why
  3. Builds a history of what actions improved AI visibility
  4. Correlates content changes with score movements

Does NOT modify GEOActionRegister or any existing Month 3 classes.
Reads from existing tables via data_hooks (read-only) and writes
to its own Deepthi-specific table.
"""

import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
AUTO_ACTION_TABLE = f'{TABLE_PREFIX}deepthi-auto-actions'

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


class AutoActionRegister:
    """
    Automated action tracking that logs before/after GEO scores
    around every probe cycle and content change.

    Table: deepthi-auto-actions
    PK: action_id
    """

    def __init__(self):
        try:
            self._table = _get_ddb().Table(AUTO_ACTION_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def log_probe_cycle(self, brand: str, before_score: float,
                        after_score: float, details: Dict = None) -> str:
        """Log a complete probe cycle with before/after scores."""
        action_id = str(uuid.uuid4())[:12]
        impact = round(after_score - before_score, 4)
        item = {
            'action_id': action_id,
            'brand': brand,
            'action_type': 'probe_cycle',
            'geo_score_before': _dec(before_score),
            'geo_score_after': _dec(after_score),
            'measured_impact': _dec(impact),
            'impact_direction': 'up' if impact > 0.01 else 'down' if impact < -0.01 else 'stable',
            'week': _week(),
            'details': json.dumps(details or {}, default=str),
            'created_at': _now(),
        }
        if self._available:
            self._table.put_item(Item=item)
        logger.info("Auto-action logged: %s brand=%s impact=%.4f (%s)",
                     action_id, brand, impact, item['impact_direction'])
        return action_id

    def log_content_change(self, brand: str, url: str,
                           change_type: str, before_score: float,
                           after_score: float = None) -> str:
        """Log a content change event for later impact measurement."""
        action_id = str(uuid.uuid4())[:12]
        item = {
            'action_id': action_id,
            'brand': brand,
            'action_type': 'content_change',
            'change_type': change_type,
            'url': url,
            'geo_score_before': _dec(before_score),
            'geo_score_after': _dec(after_score) if after_score is not None else _dec(0),
            'measured_impact': _dec(0),
            'impact_direction': 'pending',
            'week': _week(),
            'details': json.dumps({'url': url, 'change_type': change_type}),
            'created_at': _now(),
        }
        if self._available:
            self._table.put_item(Item=item)
        return action_id

    def measure_pending_impacts(self, brand: str) -> Dict:
        """
        Find all pending content_change actions and measure their impact
        by comparing current GEO score to the before_score.
        """
        if not self._available:
            return {'status': 'unavailable'}

        # Get current GEO score
        current_score = 0
        try:
            from deepthi_intelligence.data_hooks import get_m3_geo_score
            m3 = get_m3_geo_score(brand)
            if m3:
                current_score = float(m3.get('geo_score', 0))
        except Exception:
            pass

        # Find pending actions
        resp = self._table.scan(
            FilterExpression=(
                Attr('brand').eq(brand) &
                Attr('impact_direction').eq('pending')
            ),
            Limit=100)
        pending = [_deserialize(i) for i in resp.get('Items', [])]

        measured = 0
        for action in pending:
            before = float(action.get('geo_score_before', 0))
            impact = round(current_score - before, 4)
            direction = 'up' if impact > 0.01 else 'down' if impact < -0.01 else 'stable'

            self._table.update_item(
                Key={'action_id': action['action_id']},
                UpdateExpression='SET geo_score_after = :a, measured_impact = :i, '
                                 'impact_direction = :d, measured_at = :t',
                ExpressionAttributeValues={
                    ':a': _dec(current_score),
                    ':i': _dec(impact),
                    ':d': direction,
                    ':t': _now(),
                })
            measured += 1

        return {
            'brand': brand,
            'current_score': current_score,
            'pending_measured': measured,
            'timestamp': _now(),
        }

    def get_action_history(self, brand: str = None, action_type: str = None,
                           limit: int = 50) -> List[Dict]:
        """Get action history with optional brand/type filters."""
        if not self._available:
            return []

        filter_parts = []
        expr_values = {}
        if brand:
            filter_parts.append('brand = :b')
            expr_values[':b'] = brand
        if action_type:
            filter_parts.append('action_type = :at')
            expr_values[':at'] = action_type

        kwargs = {'Limit': limit}
        if filter_parts:
            kwargs['FilterExpression'] = Attr('brand').eq(brand) if brand else None
            # Build combined filter
            if brand and action_type:
                kwargs['FilterExpression'] = (
                    Attr('brand').eq(brand) & Attr('action_type').eq(action_type))
            elif brand:
                kwargs['FilterExpression'] = Attr('brand').eq(brand)
            elif action_type:
                kwargs['FilterExpression'] = Attr('action_type').eq(action_type)

        resp = self._table.scan(**kwargs)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('details'), str):
                try:
                    i['details'] = json.loads(i['details'])
                except Exception:
                    pass
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return items[:limit]

    def get_impact_summary(self, brand: str) -> Dict:
        """Get a summary of all measured impacts for a brand."""
        actions = self.get_action_history(brand=brand, limit=200)
        if not actions:
            return {'brand': brand, 'status': 'no_data'}

        measured = [a for a in actions if a.get('impact_direction') != 'pending']
        positive = [a for a in measured if a.get('measured_impact', 0) > 0.01]
        negative = [a for a in measured if a.get('measured_impact', 0) < -0.01]
        stable = [a for a in measured if abs(a.get('measured_impact', 0)) <= 0.01]

        avg_impact = (sum(a.get('measured_impact', 0) for a in measured) / len(measured)
                      if measured else 0)

        # Best and worst actions
        best = max(measured, key=lambda x: x.get('measured_impact', 0)) if measured else None
        worst = min(measured, key=lambda x: x.get('measured_impact', 0)) if measured else None

        return {
            'brand': brand,
            'total_actions': len(actions),
            'measured': len(measured),
            'pending': len(actions) - len(measured),
            'positive_impact': len(positive),
            'negative_impact': len(negative),
            'stable': len(stable),
            'avg_impact': round(avg_impact, 4),
            'best_action': {
                'action_id': best.get('action_id'),
                'impact': best.get('measured_impact'),
                'type': best.get('action_type'),
            } if best else None,
            'worst_action': {
                'action_id': worst.get('action_id'),
                'impact': worst.get('measured_impact'),
                'type': worst.get('action_type'),
            } if worst else None,
            'timestamp': _now(),
        }


def auto_track_probe_cycle(brand: str) -> str:
    """
    Convenience function: capture before score, to be called BEFORE a probe cycle.
    Returns action_id to be completed after the cycle.
    """
    before_score = 0
    try:
        from deepthi_intelligence.data_hooks import get_m3_geo_score
        m3 = get_m3_geo_score(brand)
        if m3:
            before_score = float(m3.get('geo_score', 0))
    except Exception:
        pass

    register = AutoActionRegister()
    return register.log_probe_cycle(brand, before_score, before_score,
                                    {'status': 'pre_cycle', 'note': 'before score captured'})


def auto_complete_probe_cycle(brand: str, action_id: str) -> Dict:
    """
    Convenience function: capture after score and update the action.
    Called AFTER a probe cycle completes.
    """
    after_score = 0
    try:
        from deepthi_intelligence.data_hooks import get_m3_geo_score
        m3 = get_m3_geo_score(brand)
        if m3:
            after_score = float(m3.get('geo_score', 0))
    except Exception:
        pass

    register = AutoActionRegister()
    if register._available:
        resp = register._table.get_item(Key={'action_id': action_id})
        item = _deserialize(resp.get('Item'))
        if item:
            before = float(item.get('geo_score_before', 0))
            impact = round(after_score - before, 4)
            direction = 'up' if impact > 0.01 else 'down' if impact < -0.01 else 'stable'
            register._table.update_item(
                Key={'action_id': action_id},
                UpdateExpression='SET geo_score_after = :a, measured_impact = :i, '
                                 'impact_direction = :d, details = :det',
                ExpressionAttributeValues={
                    ':a': _dec(after_score),
                    ':i': _dec(impact),
                    ':d': direction,
                    ':det': json.dumps({'status': 'post_cycle', 'before': before,
                                        'after': after_score, 'impact': impact}),
                })

    return {'action_id': action_id, 'brand': brand, 'after_score': after_score}
