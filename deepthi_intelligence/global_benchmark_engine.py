#!/usr/bin/env python3
"""
global_benchmark_engine.py
Global Benchmark Intelligence for Deepthi Intelligence Layer.

Provides:
  1. Industry category tracking — top brands per industry, not just SEO tools
  2. Auto-detection of new competitors entering AI visibility space
  3. Weekly benchmark reports generated automatically

Does NOT modify any existing files. Reads from existing probe/score tables.
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
INDUSTRY_TABLE = f'{TABLE_PREFIX}deepthi-industry-benchmarks'
WEEKLY_REPORT_TABLE = f'{TABLE_PREFIX}deepthi-weekly-reports'

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


# Default industry categories with representative keywords
INDUSTRY_CATEGORIES = {
    'seo_tools': {
        'name': 'SEO Tools',
        'keywords': ['best seo tool', 'keyword research tool', 'backlink analysis',
                     'rank tracking software', 'site audit tool'],
        'known_brands': ['Ahrefs', 'SEMrush', 'Moz', 'Surfer SEO', 'SE Ranking'],
    },
    'ai_writing': {
        'name': 'AI Writing Tools',
        'keywords': ['best ai writing tool', 'ai content generator', 'ai copywriting',
                     'automated blog writing', 'ai article writer'],
        'known_brands': ['Jasper', 'Copy.ai', 'Writesonic', 'Rytr', 'Frase'],
    },
    'ecommerce': {
        'name': 'E-Commerce Platforms',
        'keywords': ['best ecommerce platform', 'online store builder',
                     'ecommerce website builder', 'sell online platform'],
        'known_brands': ['Shopify', 'WooCommerce', 'BigCommerce', 'Wix', 'Squarespace'],
    },
    'email_marketing': {
        'name': 'Email Marketing',
        'keywords': ['best email marketing tool', 'email automation platform',
                     'newsletter software', 'email campaign tool'],
        'known_brands': ['Mailchimp', 'ConvertKit', 'ActiveCampaign', 'Brevo', 'Klaviyo'],
    },
    'analytics': {
        'name': 'Web Analytics',
        'keywords': ['best web analytics tool', 'website traffic analysis',
                     'user behavior analytics', 'conversion tracking tool'],
        'known_brands': ['Google Analytics', 'Mixpanel', 'Amplitude', 'Hotjar', 'Plausible'],
    },
}


class IndustryBenchmarkTracker:
    """
    Tracks top brands per industry category with AI visibility scores.
    Table: deepthi-industry-benchmarks
    PK: category_id, SK: week
    """

    def __init__(self):
        try:
            self._table = _get_ddb().Table(INDUSTRY_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def record_industry_snapshot(self, category_id: str, week: str,
                                 brand_scores: Dict) -> str:
        """Record weekly industry benchmark snapshot."""
        item = {
            'category_id': category_id,
            'week': week,
            'category_name': INDUSTRY_CATEGORIES.get(category_id, {}).get('name', category_id),
            'brand_scores': json.dumps(brand_scores, default=str),
            'top_brand': max(brand_scores, key=lambda b: brand_scores[b].get('geo_score', 0))
                         if brand_scores else '',
            'brands_tracked': len(brand_scores),
            'recorded_at': _now(),
        }
        if self._available:
            self._table.put_item(Item=item)
        return week

    def get_industry_trend(self, category_id: str, limit: int = 12) -> List[Dict]:
        if not self._available:
            return []
        resp = self._table.query(
            KeyConditionExpression=Key('category_id').eq(category_id),
            ScanIndexForward=False, Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('brand_scores'), str):
                try:
                    i['brand_scores'] = json.loads(i['brand_scores'])
                except Exception:
                    pass
        return items

    def get_latest_snapshot(self, category_id: str) -> Optional[Dict]:
        trend = self.get_industry_trend(category_id, limit=1)
        return trend[0] if trend else None

    def list_categories(self) -> List[Dict]:
        return [
            {'id': k, 'name': v['name'], 'keywords': len(v['keywords']),
             'known_brands': len(v['known_brands'])}
            for k, v in INDUSTRY_CATEGORIES.items()
        ]


class CompetitorDetector:
    """
    Auto-detects new competitors entering the AI visibility space.
    Analyzes probe responses to find brands mentioned alongside tracked brands.
    """

    def detect_new_competitors(self, category_id: str = None,
                               limit: int = 200) -> Dict:
        """
        Scan recent probe responses for brand mentions not in our tracked list.
        Returns newly detected brands with mention counts.
        """
        import re
        from deepthi_intelligence.data_hooks import get_raw_probes

        probes = get_raw_probes(limit=limit)
        if not probes:
            return {'detected': [], 'probes_scanned': 0}

        # Get all known brands
        known = set()
        for cat in INDUSTRY_CATEGORIES.values():
            known.update(b.lower() for b in cat['known_brands'])

        # Extract brand-like mentions from probe responses
        mention_counts = defaultdict(int)
        for probe in probes:
            snippet = probe.get('response_snippet', '') or probe.get('citation_context', '')
            if not snippet:
                continue
            # Look for capitalized multi-word names (brand-like patterns)
            candidates = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\.[a-z]+)?)\b', snippet)
            for c in candidates:
                c_lower = c.lower()
                if c_lower not in known and len(c) > 3:
                    mention_counts[c] += 1

        # Filter to significant mentions (3+ occurrences)
        detected = [
            {'brand': brand, 'mentions': count}
            for brand, count in sorted(mention_counts.items(),
                                       key=lambda x: x[1], reverse=True)
            if count >= 3
        ][:20]

        return {
            'detected': detected,
            'probes_scanned': len(probes),
            'known_brands': len(known),
            'timestamp': _now(),
        }


class WeeklyReportGenerator:
    """
    Generates weekly benchmark reports automatically.
    Table: deepthi-weekly-reports
    PK: report_id
    """

    def __init__(self):
        try:
            self._table = _get_ddb().Table(WEEKLY_REPORT_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def generate_report(self, project_id: str = None) -> Dict:
        """Generate a comprehensive weekly benchmark report."""
        report_id = str(uuid.uuid4())[:12]
        week = _week()

        report = {
            'report_id': report_id,
            'week': week,
            'generated_at': _now(),
            'project_id': project_id or '',
            'sections': {},
        }

        # Section 1: Brand scores overview
        try:
            from deepthi_intelligence.benchmark_brands import MultiBrandGeoScores
            scorer = MultiBrandGeoScores()
            comparison = scorer.get_latest_comparison()
            report['sections']['brand_overview'] = {
                'brands': comparison,
                'total_brands': len(comparison),
            }
        except Exception as e:
            report['sections']['brand_overview'] = {'error': str(e)}

        # Section 2: Industry benchmarks
        try:
            tracker = IndustryBenchmarkTracker()
            industries = {}
            for cat_id in INDUSTRY_CATEGORIES:
                latest = tracker.get_latest_snapshot(cat_id)
                if latest:
                    industries[cat_id] = latest
            report['sections']['industry_benchmarks'] = industries
        except Exception as e:
            report['sections']['industry_benchmarks'] = {'error': str(e)}

        # Section 3: New competitor detection
        try:
            detector = CompetitorDetector()
            detected = detector.detect_new_competitors()
            report['sections']['new_competitors'] = detected
        except Exception as e:
            report['sections']['new_competitors'] = {'error': str(e)}

        # Section 4: Freshness summary
        try:
            from deepthi_intelligence.freshness_integration import FreshnessDigest
            from deepthi_intelligence.benchmark_brands import BenchmarkBrandRegistry
            digest = FreshnessDigest()
            brands = BenchmarkBrandRegistry().get_brand_names()
            freshness = {}
            for brand in brands:
                latest = digest.get_latest_digest(brand)
                if latest:
                    freshness[brand] = latest
            report['sections']['freshness'] = freshness
        except Exception as e:
            report['sections']['freshness'] = {'error': str(e)}

        # Persist report
        if self._available:
            self._table.put_item(Item={
                'report_id': report_id,
                'week': week,
                'generated_at': report['generated_at'],
                'project_id': report.get('project_id', ''),
                'sections': json.dumps(report['sections'], default=str),
            })

        return report

    def get_report(self, report_id: str) -> Optional[Dict]:
        if not self._available:
            return None
        resp = self._table.get_item(Key={'report_id': report_id})
        item = _deserialize(resp.get('Item'))
        if item and isinstance(item.get('sections'), str):
            try:
                item['sections'] = json.loads(item['sections'])
            except Exception:
                pass
        return item

    def list_reports(self, limit: int = 20) -> List[Dict]:
        if not self._available:
            return []
        resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('sections'), str):
                try:
                    i['sections'] = json.loads(i['sections'])
                except Exception:
                    pass
        items.sort(key=lambda x: x.get('generated_at', ''), reverse=True)
        return items[:limit]
