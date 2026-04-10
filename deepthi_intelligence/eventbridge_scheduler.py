#!/usr/bin/env python3
"""
eventbridge_scheduler.py
EventBridge Automation for production-ready GEO Scanner Agent.

Scheduled cadences:
  - Every 6 hours:  directory freshness check
  - Every 24 hours: AEO learning log update
  - Every 7 days:   full GEO scoring across all brands
  - Every 7 days:   competitor visibility matrix update

Designed to be invoked by AWS EventBridge rules targeting Lambda or
called directly via the /api/m3/deepthi/scheduler/* endpoints.

Does NOT modify scheduler.py or any existing scheduling logic.
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
SCHEDULE_LOG_TABLE = f'{TABLE_PREFIX}deepthi-schedule-log'

_ddb = None


def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb


def _now():
    return datetime.now(timezone.utc).isoformat()


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


class ScheduleLog:
    """Logs every scheduled execution for audit and debugging."""

    def __init__(self):
        try:
            self._table = _get_ddb().Table(SCHEDULE_LOG_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def log_run(self, task_type: str, result: Dict) -> str:
        run_id = str(uuid.uuid4())[:12]
        entry = {
            'run_id': run_id,
            'task_type': task_type,
            'status': result.get('status', 'complete'),
            'summary': json.dumps(result, default=str),
            'started_at': result.get('started_at', _now()),
            'completed_at': _now(),
        }
        if self._available:
            self._table.put_item(Item=entry)
        logger.info("Schedule log: %s [%s] -> %s", task_type, run_id, result.get('status'))
        return run_id

    def get_history(self, task_type: str = None, limit: int = 50) -> List[Dict]:
        if not self._available:
            return []
        if task_type:
            resp = self._table.scan(
                FilterExpression=Attr('task_type').eq(task_type),
                Limit=limit)
        else:
            resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('summary'), str):
                try:
                    i['summary'] = json.loads(i['summary'])
                except Exception:
                    pass
        items.sort(key=lambda x: x.get('completed_at', ''), reverse=True)
        return items[:limit]


# -- Scheduled task: directory freshness (every 6 hours) --

def run_directory_freshness(project_id: str = None) -> Dict:
    """Check freshness of all tracked content pages."""
    started = _now()
    result = {'task': 'directory_freshness', 'started_at': started}
    try:
        from deepthi_intelligence.freshness_integration import FreshnessDigest
        from deepthi_intelligence.benchmark_brands import BenchmarkBrandRegistry

        digest = FreshnessDigest()
        brands = BenchmarkBrandRegistry().get_brand_names()
        brand_results = {}
        for brand in brands:
            d = digest.compute_digest_from_freshness(brand)
            brand_results[brand] = {
                'avg_freshness': d.get('avg_freshness_score', 0),
                'pages_checked': d.get('pages_checked', 0),
                'pages_stale': d.get('pages_stale', 0),
            }
        result['brands'] = brand_results
        result['status'] = 'complete'
    except Exception as e:
        logger.error("Directory freshness failed: %s", e)
        result['status'] = 'error'
        result['error'] = str(e)

    ScheduleLog().log_run('directory_freshness', result)
    return result


# -- Scheduled task: AEO learning log (every 24 hours) --

def run_aeo_learning_update(project_id: str = None) -> Dict:
    """Update AEO learning log from latest probe data."""
    started = _now()
    result = {'task': 'aeo_learning_update', 'started_at': started}
    try:
        from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
        engine = CitationLearningEngine()
        learn_result = engine.learn_from_recent_probes(limit=200)
        result.update(learn_result)
        result['status'] = 'complete'
    except Exception as e:
        logger.error("AEO learning update failed: %s", e)
        result['status'] = 'error'
        result['error'] = str(e)

    ScheduleLog().log_run('aeo_learning_update', result)
    return result


# -- Scheduled task: full GEO scoring (every 7 days) --

def run_full_geo_scoring(project_id: str = None) -> Dict:
    """Run full GEO scoring across all registered brands."""
    started = _now()
    result = {'task': 'full_geo_scoring', 'started_at': started}
    try:
        from deepthi_intelligence.benchmark_brands import BenchmarkBrandRegistry
        from probe_to_intelligence import transform_probes_to_intelligence

        brands = BenchmarkBrandRegistry().get_brand_names()
        brand_results = {}
        for brand in brands:
            try:
                tr = transform_probes_to_intelligence(brand)
                brand_results[brand] = {
                    'status': tr.get('status', 'unknown'),
                    'probes_processed': tr.get('total_probes_processed', 0),
                    'keywords_written': tr.get('keywords_written', 0),
                }
            except Exception as e:
                brand_results[brand] = {'status': 'error', 'error': str(e)}

        result['brands'] = brand_results
        result['total_brands'] = len(brands)
        result['status'] = 'complete'
    except Exception as e:
        logger.error("Full GEO scoring failed: %s", e)
        result['status'] = 'error'
        result['error'] = str(e)

    ScheduleLog().log_run('full_geo_scoring', result)
    return result


# -- Scheduled task: competitor visibility matrix (every 7 days) --

def run_competitor_matrix_update(project_id: str = None) -> Dict:
    """Update competitor visibility matrix for all brands."""
    started = _now()
    result = {'task': 'competitor_matrix_update', 'started_at': started}
    try:
        from deepthi_intelligence.benchmark_brands import BenchmarkBrandRegistry
        from probe_to_intelligence import _load_raw_probes, _aggregate_keyword_metrics
        from month3_systems.geo_brand_intelligence import CompetitorVisibilityMatrix
        from collections import defaultdict

        brands = BenchmarkBrandRegistry().get_brand_names()
        matrix = CompetitorVisibilityMatrix()
        week = datetime.now(timezone.utc).strftime('%Y-W%W')
        updated = 0

        for brand in brands:
            probes = _load_raw_probes(brand=brand, limit=200)
            if not probes:
                continue
            kw_metrics = _aggregate_keyword_metrics(probes)
            total_cited = sum(1 for p in probes if p.get('cited'))
            total = len(probes)
            vis = round(total_cited / total * 100) if total else 0

            prov_stats = defaultdict(lambda: {'cited': 0, 'total': 0})
            for p in probes:
                prov = p.get('ai_model', 'unknown')
                prov_stats[prov]['total'] += 1
                if p.get('cited'):
                    prov_stats[prov]['cited'] += 1

            top_kws = sorted(kw_metrics.values(),
                             key=lambda x: x['geo_score'], reverse=True)[:5]

            matrix.record(brand, week, {
                'visibility_score': vis,
                'keywords_cited': sum(1 for m in kw_metrics.values() if m['geo_score'] > 0),
                'total_keywords': len(kw_metrics),
                'provider_breakdown': {
                    prov: round(d['cited'] / d['total'], 2) if d['total'] else 0
                    for prov, d in prov_stats.items()
                },
                'top_keywords': [k['keyword'] for k in top_kws],
            })
            updated += 1

        result['brands_updated'] = updated
        result['week'] = week
        result['status'] = 'complete'
    except Exception as e:
        logger.error("Competitor matrix update failed: %s", e)
        result['status'] = 'error'
        result['error'] = str(e)

    ScheduleLog().log_run('competitor_matrix_update', result)
    return result


# -- EventBridge CloudFormation template generator --

def generate_eventbridge_rules() -> Dict:
    """
    Generate EventBridge rule definitions for CloudFormation / Terraform.
    Returns JSON-serializable config for all 4 scheduled tasks.
    """
    api_base = os.environ.get('API_BASE_URL', 'https://your-app.us-east-1.awsapprunner.com')
    return {
        'rules': [
            {
                'name': 'deepthi-directory-freshness-6h',
                'description': 'Directory freshness check every 6 hours',
                'schedule_expression': 'rate(6 hours)',
                'target_endpoint': f'{api_base}/api/m3/deepthi/scheduler/run/directory_freshness',
                'method': 'POST',
            },
            {
                'name': 'deepthi-aeo-learning-24h',
                'description': 'AEO learning log update every 24 hours',
                'schedule_expression': 'rate(24 hours)',
                'target_endpoint': f'{api_base}/api/m3/deepthi/scheduler/run/aeo_learning_update',
                'method': 'POST',
            },
            {
                'name': 'deepthi-geo-scoring-7d',
                'description': 'Full GEO scoring across all brands every 7 days',
                'schedule_expression': 'rate(7 days)',
                'target_endpoint': f'{api_base}/api/m3/deepthi/scheduler/run/full_geo_scoring',
                'method': 'POST',
            },
            {
                'name': 'deepthi-competitor-matrix-7d',
                'description': 'Competitor visibility matrix update every 7 days',
                'schedule_expression': 'rate(7 days)',
                'target_endpoint': f'{api_base}/api/m3/deepthi/scheduler/run/competitor_matrix_update',
                'method': 'POST',
            },
        ],
    }


# -- Lambda handler for EventBridge invocation --

def lambda_handler(event, context):
    """
    AWS Lambda entry point for EventBridge scheduled invocations.
    Event should contain: {"task": "directory_freshness|aeo_learning_update|..."}
    """
    task = event.get('task', '')
    project_id = event.get('project_id')

    task_map = {
        'directory_freshness': run_directory_freshness,
        'aeo_learning_update': run_aeo_learning_update,
        'full_geo_scoring': run_full_geo_scoring,
        'competitor_matrix_update': run_competitor_matrix_update,
    }

    handler = task_map.get(task)
    if not handler:
        return {'status': 'error', 'error': f'Unknown task: {task}'}

    return handler(project_id=project_id)
