#!/usr/bin/env python3
"""
3.3 SEO Foundation System

Four components:
  1. Technical Debt Register (live)
  2. E-E-A-T Improvement Pipeline
  3. Content Optimisation Queue
  4. Topical Authority Map

All backed by DynamoDB.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

TECH_DEBT_TABLE = f'{TABLE_PREFIX}seo-technical-debt'
EEAT_TABLE = f'{TABLE_PREFIX}seo-eeat-pipeline'
CONTENT_QUEUE_TABLE = f'{TABLE_PREFIX}seo-content-queue'
AUTHORITY_MAP_TABLE = f'{TABLE_PREFIX}seo-authority-map'

_ddb = None

def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb

def _now():
    return datetime.now(timezone.utc).isoformat()

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
# 1. TECHNICAL DEBT REGISTER
# ═══════════════════════════════════════════════════════════════════════════════

class TechnicalDebtRegister:
    """Live register from Month 1 audit, actively managed."""

    def __init__(self):
        self._table = _get_ddb().Table(TECH_DEBT_TABLE)

    def add_issue(self, data: Dict) -> str:
        issue_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'issue_id': issue_id,
            'description': data.get('description', ''),
            'source_check': data.get('source_check', ''),
            'category': data.get('category', 'technical'),
            'ai_visibility_impact': data.get('ai_visibility_impact', 'medium'),
            'fix_status': data.get('fix_status', 'open'),
            'assigned_date': data.get('assigned_date', now),
            'resolved_date': '',
            'url': data.get('url', ''),
            'priority': _dec(data.get('priority', 5)),
            'created_at': now,
            'updated_at': now,
        }
        self._table.put_item(Item=item)
        return issue_id

    def resolve_issue(self, issue_id: str):
        self._table.update_item(
            Key={'issue_id': issue_id},
            UpdateExpression='SET fix_status = :s, resolved_date = :r, updated_at = :t',
            ExpressionAttributeValues={':s': 'resolved', ':r': _now(), ':t': _now()})

    def get_all(self, status: str = None, limit: int = 100) -> List[Dict]:
        if status:
            resp = self._table.scan(
                FilterExpression=Attr('fix_status').eq(status), Limit=limit)
        else:
            resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('priority', 0), reverse=True)
        return items

    def get_stats(self) -> Dict:
        all_items = self.get_all()
        open_items = [i for i in all_items if i.get('fix_status') == 'open']
        resolved = [i for i in all_items if i.get('fix_status') == 'resolved']
        high = [i for i in open_items if i.get('ai_visibility_impact') == 'high']
        return {
            'total': len(all_items), 'open': len(open_items),
            'resolved': len(resolved), 'high_impact_open': len(high),
        }

    def seed_from_audit(self, audit_results: List[Dict]) -> int:
        count = 0
        for check in audit_results:
            if check.get('status') == 'fail':
                self.add_issue({
                    'description': check.get('name', ''),
                    'source_check': check.get('check_id', ''),
                    'category': check.get('category', 'technical'),
                    'ai_visibility_impact': check.get('impact', 'medium'),
                    'url': check.get('url', ''),
                    'priority': check.get('priority', 5),
                })
                count += 1
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# 2. E-E-A-T IMPROVEMENT PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class EEATPipeline:
    """E-E-A-T Gap Register in active remediation."""

    def __init__(self):
        self._table = _get_ddb().Table(EEAT_TABLE)

    def add_gap(self, data: Dict) -> str:
        gap_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'gap_id': gap_id,
            'gap_type': data.get('gap_type', 'authority'),
            'description': data.get('description', ''),
            'url': data.get('url', ''),
            'proposed_fix': data.get('proposed_fix', ''),
            'owner': data.get('owner', 'unassigned'),
            'target_date': data.get('target_date', ''),
            'status': data.get('status', 'identified'),
            'verification_result': '',
            'created_at': now,
            'updated_at': now,
        }
        self._table.put_item(Item=item)
        return gap_id

    def update_status(self, gap_id: str, status: str, verification: str = ''):
        update = 'SET #s = :s, updated_at = :t'
        vals = {':s': status, ':t': _now()}
        names = {'#s': 'status'}
        if verification:
            update += ', verification_result = :v'
            vals[':v'] = verification
        self._table.update_item(
            Key={'gap_id': gap_id},
            UpdateExpression=update,
            ExpressionAttributeValues=vals,
            ExpressionAttributeNames=names)

    def get_all(self, status: str = None, limit: int = 100) -> List[Dict]:
        if status:
            resp = self._table.scan(
                FilterExpression=Attr('status').eq(status), Limit=limit)
        else:
            resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('created_at', ''))
        return items


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CONTENT OPTIMISATION QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

class ContentOptimisationQueue:
    """Existing pages ranked by AI citation opportunity."""

    def __init__(self):
        self._table = _get_ddb().Table(CONTENT_QUEUE_TABLE)

    def add_page(self, url: str, data: Dict) -> str:
        page_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'page_id': page_id,
            'url': url,
            'geo_score_gap': _dec(data.get('geo_score_gap', 0)),
            'estimated_traffic': _dec(data.get('estimated_traffic', 0)),
            'opportunity_score': _dec(data.get('opportunity_score', 0)),
            'current_aeo_score': _dec(data.get('current_aeo_score', 0)),
            'status': data.get('status', 'queued'),
            'audit_date': '',
            'created_at': now,
            'updated_at': now,
        }
        self._table.put_item(Item=item)
        return page_id

    def mark_audited(self, page_id: str, aeo_score: float):
        self._table.update_item(
            Key={'page_id': page_id},
            UpdateExpression='SET #s = :s, current_aeo_score = :a, audit_date = :d, updated_at = :t',
            ExpressionAttributeValues={
                ':s': 'audited', ':a': _dec(aeo_score), ':d': _now(), ':t': _now()},
            ExpressionAttributeNames={'#s': 'status'})

    def get_queue(self, status: str = None, limit: int = 50) -> List[Dict]:
        if status:
            resp = self._table.scan(
                FilterExpression=Attr('status').eq(status), Limit=limit)
        else:
            resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('opportunity_score', 0), reverse=True)
        return items


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TOPICAL AUTHORITY MAP
# ═══════════════════════════════════════════════════════════════════════════════

class TopicalAuthorityMap:
    """Topic cluster map showing coverage and gaps."""

    def __init__(self):
        self._table = _get_ddb().Table(AUTHORITY_MAP_TABLE)

    def add_topic(self, pillar: str, data: Dict) -> str:
        topic_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'topic_id': topic_id,
            'pillar': pillar,
            'subtopic': data.get('subtopic', ''),
            'coverage_status': data.get('coverage_status', 'missing'),
            'page_url': data.get('page_url', ''),
            'geo_opportunity': _dec(data.get('geo_opportunity', 0)),
            'target_keywords': json.dumps(data.get('target_keywords', [])),
            'created_at': now,
            'updated_at': now,
        }
        self._table.put_item(Item=item)
        return topic_id

    def update_coverage(self, topic_id: str, status: str, page_url: str = ''):
        update = 'SET coverage_status = :s, updated_at = :t'
        vals = {':s': status, ':t': _now()}
        if page_url:
            update += ', page_url = :u'
            vals[':u'] = page_url
        self._table.update_item(
            Key={'topic_id': topic_id},
            UpdateExpression=update,
            ExpressionAttributeValues=vals)

    def get_map(self, pillar: str = None) -> List[Dict]:
        if pillar:
            resp = self._table.scan(
                FilterExpression=Attr('pillar').eq(pillar), Limit=200)
        else:
            resp = self._table.scan(Limit=200)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('target_keywords'), str):
                try: i['target_keywords'] = json.loads(i['target_keywords'])
                except: pass
        items.sort(key=lambda x: x.get('geo_opportunity', 0), reverse=True)
        return items

    def get_gaps(self) -> List[Dict]:
        return [t for t in self.get_map() if t.get('coverage_status') == 'missing']


# ═══════════════════════════════════════════════════════════════════════════════
# WEEKLY CADENCE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_seo_weekly_cadence() -> Dict:
    """Execute the SEO Foundation weekly cadence."""
    results = {}

    debt = TechnicalDebtRegister()
    stats = debt.get_stats()
    results['tech_debt'] = stats

    queue = ContentOptimisationQueue()
    top3 = queue.get_queue(status='queued')[:3]
    results['content_queue_top3'] = [q.get('url', '') for q in top3]

    eeat = EEATPipeline()
    open_gaps = eeat.get_all(status='identified')
    results['eeat_open_gaps'] = len(open_gaps)

    results['status'] = 'complete'
    results['timestamp'] = _now()
    return results
