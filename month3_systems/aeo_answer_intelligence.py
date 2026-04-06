#!/usr/bin/env python3
"""
3.1 AEO Answer Intelligence System

Five components:
  1. Question Intelligence Database
  2. Answer Template Library
  3. AEO Content Calendar
  4. Citation Monitoring Register
  5. AEO Learning Log

All backed by DynamoDB. Uses existing platform tools as the operational engine.
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

# Table names
QUESTION_DB_TABLE = f'{TABLE_PREFIX}aeo-question-intelligence'
TEMPLATE_TABLE = f'{TABLE_PREFIX}aeo-answer-templates'
CALENDAR_TABLE = f'{TABLE_PREFIX}aeo-content-calendar'
CITATION_REG_TABLE = f'{TABLE_PREFIX}aeo-citation-register'
LEARNING_LOG_TABLE = f'{TABLE_PREFIX}aeo-learning-log'

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
# 1. QUESTION INTELLIGENCE DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionIntelligenceDB:
    """Structured register of all queries from Master Keyword Universe."""

    def __init__(self):
        self._table = _get_ddb().Table(QUESTION_DB_TABLE)

    def upsert_query(self, keyword: str, data: Dict) -> str:
        now = _now()
        item = {
            'keyword': keyword,
            'updated_at': now,
            'geo_score': _dec(data.get('geo_score', 0)),
            'visibility_score': _dec(data.get('visibility_score', 0)),
            'top_cited_brand': data.get('top_cited_brand', ''),
            'answer_format': data.get('answer_format', 'paragraph'),
            'aeo_findings': json.dumps(data.get('aeo_findings', {})),
            'priority_score': _dec(data.get('priority_score', 0)),
            'category': data.get('category', 'general'),
            'trend': data.get('trend', 'stable'),
            'last_probed': data.get('last_probed', now),
        }
        self._table.put_item(Item=item)
        return keyword

    def get_query(self, keyword: str) -> Optional[Dict]:
        resp = self._table.get_item(Key={'keyword': keyword})
        return _deserialize(resp.get('Item'))

    def get_priority_gaps(self, limit: int = 10) -> List[Dict]:
        resp = self._table.scan(Limit=200)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        return items[:limit]

    def get_all(self, limit: int = 200) -> List[Dict]:
        resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('geo_score', 0))
        return items

    def bulk_enrich(self, enrichments: List[Dict]) -> int:
        count = 0
        for e in enrichments:
            kw = e.get('keyword')
            if not kw: continue
            self.upsert_query(kw, e)
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ANSWER TEMPLATE LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════

class AnswerTemplateLibrary:
    """Templates derived from Answer Format Taxonomy with JSON-LD schema."""

    def __init__(self):
        self._table = _get_ddb().Table(TEMPLATE_TABLE)

    def save_template(self, format_type: str, data: Dict) -> str:
        now = _now()
        item = {
            'format_type': format_type,
            'updated_at': now,
            'template_name': data.get('template_name', format_type),
            'description': data.get('description', ''),
            'html_structure': data.get('html_structure', ''),
            'json_ld_schema': json.dumps(data.get('json_ld_schema', {})),
            'example_content': data.get('example_content', ''),
            'citation_success_rate': _dec(data.get('citation_success_rate', 0)),
            'usage_count': data.get('usage_count', 0),
        }
        self._table.put_item(Item=item)
        return format_type

    def get_template(self, format_type: str) -> Optional[Dict]:
        resp = self._table.get_item(Key={'format_type': format_type})
        item = _deserialize(resp.get('Item'))
        if item and isinstance(item.get('json_ld_schema'), str):
            try: item['json_ld_schema'] = json.loads(item['json_ld_schema'])
            except: pass
        return item

    def get_all(self) -> List[Dict]:
        resp = self._table.scan()
        return [_deserialize(i) for i in resp.get('Items', [])]

    def seed_defaults(self) -> int:
        defaults = [
            {'format_type': 'faq', 'template_name': 'FAQ Page',
             'description': 'Question-answer pairs with FAQPage schema',
             'json_ld_schema': {'@type': 'FAQPage', 'mainEntity': []}},
            {'format_type': 'howto', 'template_name': 'How-To Guide',
             'description': 'Step-by-step instructions with HowTo schema',
             'json_ld_schema': {'@type': 'HowTo', 'step': []}},
            {'format_type': 'comparison', 'template_name': 'Comparison Table',
             'description': 'Side-by-side product/service comparison',
             'json_ld_schema': {'@type': 'ItemList', 'itemListElement': []}},
            {'format_type': 'listicle', 'template_name': 'Top-N List',
             'description': 'Ranked list with brief descriptions',
             'json_ld_schema': {'@type': 'ItemList', 'itemListElement': []}},
            {'format_type': 'definition', 'template_name': 'Definition Block',
             'description': 'Concise definition with DefinedTerm schema',
             'json_ld_schema': {'@type': 'DefinedTerm'}},
            {'format_type': 'review', 'template_name': 'Product Review',
             'description': 'Structured review with Review schema',
             'json_ld_schema': {'@type': 'Review', 'reviewRating': {'@type': 'Rating'}}},
        ]
        for d in defaults:
            ft = d.pop('format_type')
            self.save_template(ft, d)
        return len(defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. AEO CONTENT CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════

class AEOContentCalendar:
    """Tracks content from brief → production → published → monitoring."""

    STATUSES = ['brief', 'in_production', 'published', 'monitoring', 'complete']

    def __init__(self):
        self._table = _get_ddb().Table(CALENDAR_TABLE)

    def add_entry(self, keyword: str, data: Dict = None) -> str:
        data = data or {}
        entry_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'entry_id': entry_id,
            'keyword': keyword,
            'status': data.get('status', 'brief'),
            'assigned_week': data.get('assigned_week', datetime.now(timezone.utc).strftime('%Y-W%W')),
            'content_type': data.get('content_type', 'faq'),
            'target_url': data.get('target_url', ''),
            'priority_score': _dec(data.get('priority_score', 0)),
            'created_at': now,
            'updated_at': now,
            'published_at': '',
            'notes': data.get('notes', ''),
        }
        self._table.put_item(Item=item)
        return entry_id

    def update_status(self, entry_id: str, status: str, **kwargs):
        update_expr = 'SET #s = :s, updated_at = :t'
        expr_vals = {':s': status, ':t': _now()}
        expr_names = {'#s': 'status'}
        if status == 'published' and kwargs.get('target_url'):
            update_expr += ', target_url = :u, published_at = :p'
            expr_vals[':u'] = kwargs['target_url']
            expr_vals[':p'] = _now()
        self._table.update_item(
            Key={'entry_id': entry_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_vals,
            ExpressionAttributeNames=expr_names,
        )

    def get_calendar(self, status: str = None, limit: int = 50) -> List[Dict]:
        if status:
            resp = self._table.scan(
                FilterExpression=Attr('status').eq(status), Limit=limit)
        else:
            resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        return items

    def populate_from_gaps(self, question_db: QuestionIntelligenceDB, count: int = 10) -> int:
        gaps = question_db.get_priority_gaps(limit=count)
        added = 0
        for g in gaps:
            existing = self._table.scan(
                FilterExpression=Attr('keyword').eq(g['keyword']) & Attr('status').ne('complete'),
                Limit=1)
            if not existing.get('Items'):
                self.add_entry(g['keyword'], {
                    'priority_score': g.get('priority_score', 0),
                    'content_type': g.get('answer_format', 'faq'),
                })
                added += 1
        return added


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CITATION MONITORING REGISTER
# ═══════════════════════════════════════════════════════════════════════════════

class CitationMonitoringRegister:
    """Tracks citation status for every optimised page."""

    def __init__(self):
        self._table = _get_ddb().Table(CITATION_REG_TABLE)

    def register_page(self, url: str, data: Dict) -> str:
        page_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'page_id': page_id,
            'url': url,
            'target_query': data.get('target_query', ''),
            'publication_date': data.get('publication_date', now),
            'pre_citation_status': json.dumps(data.get('pre_citation_status', {})),
            'weekly_checks': json.dumps([]),
            'current_cited': False,
            'weeks_monitored': 0,
            'created_at': now,
            'updated_at': now,
        }
        self._table.put_item(Item=item)
        return page_id

    def record_weekly_check(self, page_id: str, check_result: Dict):
        resp = self._table.get_item(Key={'page_id': page_id})
        item = resp.get('Item')
        if not item: return
        checks = json.loads(item.get('weekly_checks', '[]'))
        checks.append({
            'date': _now(),
            'cited': check_result.get('cited', False),
            'providers': check_result.get('providers', {}),
        })
        self._table.update_item(
            Key={'page_id': page_id},
            UpdateExpression='SET weekly_checks = :w, current_cited = :c, weeks_monitored = :wm, updated_at = :t',
            ExpressionAttributeValues={
                ':w': json.dumps(checks),
                ':c': check_result.get('cited', False),
                ':wm': len(checks),
                ':t': _now(),
            })

    def get_all(self, limit: int = 100) -> List[Dict]:
        resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            for field in ('pre_citation_status', 'weekly_checks'):
                if isinstance(i.get(field), str):
                    try: i[field] = json.loads(i[field])
                    except: pass
        return items

    def get_pages_needing_check(self, max_weeks: int = 8) -> List[Dict]:
        all_pages = self.get_all()
        return [p for p in all_pages if p.get('weeks_monitored', 0) < max_weeks]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AEO LEARNING LOG
# ═══════════════════════════════════════════════════════════════════════════════

class AEOLearningLog:
    """Bi-weekly log of what content formats generate citations."""

    def __init__(self):
        self._table = _get_ddb().Table(LEARNING_LOG_TABLE)

    def add_entry(self, data: Dict) -> str:
        entry_id = str(uuid.uuid4())[:8]
        now = _now()
        item = {
            'entry_id': entry_id,
            'period': data.get('period', datetime.now(timezone.utc).strftime('%Y-W%W')),
            'formats_generating_citations': json.dumps(data.get('formats_generating_citations', [])),
            'formats_not_generating': json.dumps(data.get('formats_not_generating', [])),
            'schema_correlation': json.dumps(data.get('schema_correlation', {})),
            'provider_responsiveness': json.dumps(data.get('provider_responsiveness', {})),
            'key_insights': data.get('key_insights', ''),
            'actions_taken': data.get('actions_taken', ''),
            'created_at': now,
        }
        self._table.put_item(Item=item)
        return entry_id

    def get_log(self, limit: int = 20) -> List[Dict]:
        resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            for field in ('formats_generating_citations', 'formats_not_generating',
                          'schema_correlation', 'provider_responsiveness'):
                if isinstance(i.get(field), str):
                    try: i[field] = json.loads(i[field])
                    except: pass
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return items


# ═══════════════════════════════════════════════════════════════════════════════
# WEEKLY CADENCE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_aeo_weekly_cadence(brand: str) -> Dict:
    """Execute the AEO System weekly cadence."""
    results = {}

    # 1. Populate calendar from top 10 priority gaps
    qdb = QuestionIntelligenceDB()
    cal = AEOContentCalendar()
    added = cal.populate_from_gaps(qdb, count=10)
    results['calendar_entries_added'] = added

    # 2. Get top 3 for content generation this week
    briefs = cal.get_calendar(status='brief')[:3]
    results['briefs_for_generation'] = [b['keyword'] for b in briefs]

    # 3. Run citation checks on published pages < 8 weeks
    reg = CitationMonitoringRegister()
    pages = reg.get_pages_needing_check(max_weeks=8)
    results['pages_needing_citation_check'] = len(pages)

    results['status'] = 'complete'
    results['timestamp'] = _now()
    return results
