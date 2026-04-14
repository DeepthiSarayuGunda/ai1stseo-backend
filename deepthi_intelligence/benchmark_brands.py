#!/usr/bin/env python3
"""
benchmark_brands.py
Multi-Brand Benchmark Data Service for Deepthi Intelligence Layer.

Provides:
  1. Brand registry — manage benchmark brands alongside AI1stSEO
  2. Multi-brand GEO score queries across the existing geo-score-tracker table
  3. Multi-brand keyword performance queries across geo-keyword-performance table
  4. Seed data — realistic benchmark brand data for demo

SAFE ADDITIVE: Reads/writes to existing Month 3 DynamoDB tables using the
same schema. Does NOT modify any existing classes or modules.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

GEO_TRACKER_TABLE = f'{TABLE_PREFIX}geo-score-tracker'
KW_PERF_TABLE = f'{TABLE_PREFIX}geo-keyword-performance'
BRAND_REGISTRY_TABLE = f'{TABLE_PREFIX}deepthi-brand-registry'

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


def _week_str(dt: datetime = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime('%Y-W%W')


# ═══════════════════════════════════════════════════════════════════════════════
# BRAND REGISTRY — lightweight brand list stored in its own table
# ═══════════════════════════════════════════════════════════════════════════════

class BenchmarkBrandRegistry:
    """
    Manages the list of benchmark brands to track.
    Uses a small dedicated DynamoDB table so we don't pollute existing tables.
    Falls back to in-memory defaults if the table doesn't exist yet.
    """

    DEFAULT_BRANDS = [
        {'brand': 'AI1stSEO', 'category': 'primary', 'added_at': '2025-01-01T00:00:00Z'},
        {'brand': 'Ahrefs', 'category': 'benchmark', 'added_at': '2025-01-01T00:00:00Z'},
        {'brand': 'SEMrush', 'category': 'benchmark', 'added_at': '2025-01-01T00:00:00Z'},
        {'brand': 'Moz', 'category': 'benchmark', 'added_at': '2025-01-01T00:00:00Z'},
        {'brand': 'Surfer SEO', 'category': 'benchmark', 'added_at': '2025-01-01T00:00:00Z'},
    ]

    def __init__(self):
        try:
            self._table = _get_ddb().Table(BRAND_REGISTRY_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def list_brands(self) -> List[Dict]:
        if not self._available:
            return list(self.DEFAULT_BRANDS)
        resp = self._table.scan(Limit=50)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        return items if items else list(self.DEFAULT_BRANDS)

    def add_brand(self, brand: str, category: str = 'benchmark') -> Dict:
        entry = {
            'brand': brand,
            'category': category,
            'added_at': _now(),
        }
        if self._available:
            self._table.put_item(Item=entry)
        return entry

    def get_brand_names(self) -> List[str]:
        return [b['brand'] for b in self.list_brands()]


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-BRAND GEO SCORE QUERIES — reads from existing geo-score-tracker
# ═══════════════════════════════════════════════════════════════════════════════

class MultiBrandGeoScores:
    """
    Query geo-score-tracker for multiple brands.
    Uses the existing table schema: PK=brand, SK=week.
    Read-only against existing data; writes only when seeding.
    """

    def __init__(self):
        self._table = _get_ddb().Table(GEO_TRACKER_TABLE)

    def get_all_brands_scores(self, brands: List[str] = None,
                              limit_per_brand: int = 12) -> Dict:
        """
        Returns {brand: [weekly_scores]} for all requested brands.
        If brands is None, uses the registry.
        """
        if brands is None:
            brands = BenchmarkBrandRegistry().get_brand_names()

        result = {}
        for brand in brands:
            resp = self._table.query(
                KeyConditionExpression=Key('brand').eq(brand),
                ScanIndexForward=False,
                Limit=limit_per_brand,
            )
            items = [_deserialize(i) for i in resp.get('Items', [])]
            for i in items:
                if isinstance(i.get('provider_scores'), str):
                    try:
                        i['provider_scores'] = json.loads(i['provider_scores'])
                    except Exception:
                        pass
            result[brand] = items
        return result

    def get_latest_comparison(self, brands: List[str] = None) -> List[Dict]:
        """Get the most recent score for each brand, sorted by geo_score desc."""
        all_scores = self.get_all_brands_scores(brands, limit_per_brand=1)
        comparison = []
        for brand, scores in all_scores.items():
            if scores:
                entry = scores[0]
                entry['brand'] = brand
                comparison.append(entry)
            else:
                comparison.append({'brand': brand, 'geo_score': 0, 'visibility_score': 0})
        comparison.sort(key=lambda x: x.get('geo_score', 0), reverse=True)
        return comparison

    def seed_brand_score(self, brand: str, week: str, data: Dict):
        """Write a score entry for a brand (used for seeding demo data)."""
        item = {
            'brand': brand,
            'week': week,
            'geo_score': _dec(data.get('geo_score', 0)),
            'visibility_score': _dec(data.get('visibility_score', 0)),
            'keywords_probed': data.get('keywords_probed', 0),
            'keywords_cited': data.get('keywords_cited', 0),
            'provider_scores': json.dumps(data.get('provider_scores', {})),
            'recorded_at': data.get('recorded_at', _now()),
        }
        self._table.put_item(Item=item)


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-BRAND KEYWORD PERFORMANCE — reads from existing geo-keyword-performance
# ═══════════════════════════════════════════════════════════════════════════════

class MultiBrandKeywordPerformance:
    """
    Query keyword performance across multiple brands.

    The existing geo-keyword-performance table has PK=keyword, SK=week and
    does NOT have a brand dimension. To support multi-brand keyword comparison
    we use a composite key approach: store brand-specific entries with
    keyword = "brand#keyword" so existing single-brand entries are untouched.

    Read methods transparently handle both formats.
    """

    def __init__(self):
        self._table = _get_ddb().Table(KW_PERF_TABLE)

    def get_keyword_across_brands(self, keyword: str, brands: List[str] = None,
                                  limit: int = 12) -> Dict:
        """
        Get performance for a keyword across all benchmark brands.
        Returns {brand: [weekly_entries]}.
        """
        if brands is None:
            brands = BenchmarkBrandRegistry().get_brand_names()

        result = {}
        for brand in brands:
            composite_key = f'{brand}#{keyword}'
            resp = self._table.query(
                KeyConditionExpression=Key('keyword').eq(composite_key),
                ScanIndexForward=False,
                Limit=limit,
            )
            items = [_deserialize(i) for i in resp.get('Items', [])]
            # Strip the brand prefix from keyword field for clean output
            for i in items:
                i['brand'] = brand
                i['keyword'] = keyword
            result[brand] = items
        return result

    def get_all_keywords_for_brands(self, brands: List[str] = None,
                                    week: str = None,
                                    limit: int = 500) -> List[Dict]:
        """
        Get all keyword performance entries for the given week across brands.
        Returns flat list with brand field added.
        """
        if brands is None:
            brands = BenchmarkBrandRegistry().get_brand_names()
        week = week or _week_str()

        all_items = []
        for brand in brands:
            # Scan for entries with brand# prefix for this week
            resp = self._table.scan(
                FilterExpression=Attr('week').eq(week) & Attr('keyword').begins_with(f'{brand}#'),
                Limit=limit,
            )
            items = [_deserialize(i) for i in resp.get('Items', [])]
            for i in items:
                i['brand'] = brand
                # Extract actual keyword from composite key
                if '#' in str(i.get('keyword', '')):
                    i['keyword'] = i['keyword'].split('#', 1)[1]
            all_items.extend(items)

        all_items.sort(key=lambda x: x.get('geo_score', 0), reverse=True)
        return all_items

    def seed_keyword_performance(self, brand: str, keyword: str, week: str, data: Dict):
        """Write a brand-specific keyword performance entry (for seeding)."""
        composite_key = f'{brand}#{keyword}'
        item = {
            'keyword': composite_key,
            'week': week,
            'geo_score': _dec(data.get('geo_score', 0)),
            'visibility_score': _dec(data.get('visibility_score', 0)),
            'confidence': _dec(data.get('confidence', 0)),
            'trend': data.get('trend', 'stable'),
            'priority_flag': data.get('priority_flag', False),
            'recorded_at': data.get('recorded_at', _now()),
        }
        self._table.put_item(Item=item)


# ═══════════════════════════════════════════════════════════════════════════════
# SEED DATA — realistic benchmark brand data for demo
# ═══════════════════════════════════════════════════════════════════════════════

# SEO industry keywords used across all brands
BENCHMARK_KEYWORDS = [
    'best seo tool', 'ai seo optimization', 'keyword research tool',
    'backlink analysis', 'site audit tool', 'rank tracking software',
    'content optimization platform', 'seo competitor analysis',
    'technical seo checker', 'local seo tool',
]

# Realistic brand profiles — geo_score ranges reflect real-world AI visibility
BRAND_PROFILES = {
    'AI1stSEO': {
        'geo_base': 0.18, 'vis_base': 22, 'confidence_base': 0.35,
        'trend_direction': 'up', 'weekly_variance': 0.04,
        'provider_scores': {'nova': 0.20, 'ollama': 0.15, 'gpt4': 0.22},
    },
    'Ahrefs': {
        'geo_base': 0.72, 'vis_base': 78, 'confidence_base': 0.85,
        'trend_direction': 'stable', 'weekly_variance': 0.03,
        'provider_scores': {'nova': 0.70, 'ollama': 0.68, 'gpt4': 0.78},
    },
    'SEMrush': {
        'geo_base': 0.68, 'vis_base': 74, 'confidence_base': 0.82,
        'trend_direction': 'stable', 'weekly_variance': 0.03,
        'provider_scores': {'nova': 0.65, 'ollama': 0.64, 'gpt4': 0.75},
    },
    'Moz': {
        'geo_base': 0.55, 'vis_base': 60, 'confidence_base': 0.70,
        'trend_direction': 'down', 'weekly_variance': 0.04,
        'provider_scores': {'nova': 0.52, 'ollama': 0.50, 'gpt4': 0.62},
    },
    'Surfer SEO': {
        'geo_base': 0.45, 'vis_base': 50, 'confidence_base': 0.60,
        'trend_direction': 'up', 'weekly_variance': 0.05,
        'provider_scores': {'nova': 0.42, 'ollama': 0.40, 'gpt4': 0.52},
    },
}

# Per-keyword brand strengths (multiplier on base geo_score)
KEYWORD_BRAND_STRENGTHS = {
    'best seo tool':                {'AI1stSEO': 0.8, 'Ahrefs': 1.2, 'SEMrush': 1.15, 'Moz': 1.0, 'Surfer SEO': 0.9},
    'ai seo optimization':          {'AI1stSEO': 1.4, 'Ahrefs': 0.7, 'SEMrush': 0.8, 'Moz': 0.5, 'Surfer SEO': 1.3},
    'keyword research tool':        {'AI1stSEO': 0.6, 'Ahrefs': 1.3, 'SEMrush': 1.25, 'Moz': 1.1, 'Surfer SEO': 0.7},
    'backlink analysis':            {'AI1stSEO': 0.4, 'Ahrefs': 1.4, 'SEMrush': 1.1, 'Moz': 1.2, 'Surfer SEO': 0.5},
    'site audit tool':              {'AI1stSEO': 0.7, 'Ahrefs': 1.1, 'SEMrush': 1.2, 'Moz': 0.9, 'Surfer SEO': 0.8},
    'rank tracking software':       {'AI1stSEO': 0.5, 'Ahrefs': 1.15, 'SEMrush': 1.3, 'Moz': 1.0, 'Surfer SEO': 0.6},
    'content optimization platform':{'AI1stSEO': 1.3, 'Ahrefs': 0.6, 'SEMrush': 0.8, 'Moz': 0.5, 'Surfer SEO': 1.4},
    'seo competitor analysis':      {'AI1stSEO': 0.9, 'Ahrefs': 1.2, 'SEMrush': 1.3, 'Moz': 0.8, 'Surfer SEO': 0.7},
    'technical seo checker':        {'AI1stSEO': 0.6, 'Ahrefs': 1.0, 'SEMrush': 1.1, 'Moz': 1.0, 'Surfer SEO': 0.8},
    'local seo tool':               {'AI1stSEO': 0.7, 'Ahrefs': 0.8, 'SEMrush': 0.9, 'Moz': 1.3, 'Surfer SEO': 0.6},
}


def seed_benchmark_data(weeks_back: int = 8) -> Dict:
    """
    Seed realistic multi-brand data into geo-score-tracker and
    geo-keyword-performance tables for demo purposes.

    Generates `weeks_back` weeks of historical data for all 5 brands.
    Returns summary of what was seeded.
    """
    import random
    random.seed(42)  # Reproducible demo data

    geo_scores = MultiBrandGeoScores()
    kw_perf = MultiBrandKeywordPerformance()
    registry = BenchmarkBrandRegistry()

    now = datetime.now(timezone.utc)
    summary = {'brands_seeded': [], 'weeks': weeks_back, 'geo_entries': 0, 'kw_entries': 0}

    for brand, profile in BRAND_PROFILES.items():
        # Register brand
        registry.add_brand(brand, 'primary' if brand == 'AI1stSEO' else 'benchmark')

        for w in range(weeks_back, 0, -1):
            week_dt = now - timedelta(weeks=w)
            week_str = _week_str(week_dt)
            recorded_at = week_dt.isoformat()

            # Trend adjustment: slight drift per week
            trend_mult = 1.0
            if profile['trend_direction'] == 'up':
                trend_mult = 1.0 + (weeks_back - w) * 0.012
            elif profile['trend_direction'] == 'down':
                trend_mult = 1.0 - (weeks_back - w) * 0.008

            variance = random.uniform(-profile['weekly_variance'], profile['weekly_variance'])
            geo = min(1.0, max(0.0, profile['geo_base'] * trend_mult + variance))
            vis = min(100, max(0, int(profile['vis_base'] * trend_mult + variance * 100)))

            # Provider scores with variance
            prov_scores = {}
            for prov, base in profile['provider_scores'].items():
                prov_scores[prov] = round(min(1.0, max(0.0, base * trend_mult + random.uniform(-0.03, 0.03))), 3)

            kw_count = len(BENCHMARK_KEYWORDS)
            cited_count = int(geo * kw_count)

            # Seed GEO Score Tracker
            geo_scores.seed_brand_score(brand, week_str, {
                'geo_score': round(geo, 4),
                'visibility_score': vis,
                'keywords_probed': kw_count,
                'keywords_cited': cited_count,
                'provider_scores': prov_scores,
                'recorded_at': recorded_at,
            })
            summary['geo_entries'] += 1

            # Seed Keyword Performance for each keyword
            for keyword in BENCHMARK_KEYWORDS:
                kw_mult = KEYWORD_BRAND_STRENGTHS.get(keyword, {}).get(brand, 1.0)
                kw_geo = min(1.0, max(0.0, geo * kw_mult + random.uniform(-0.05, 0.05)))
                kw_vis = min(100, max(0, int(vis * kw_mult + random.uniform(-5, 5))))
                kw_conf = min(1.0, max(0.0, profile['confidence_base'] * kw_mult + random.uniform(-0.1, 0.1)))

                kw_perf.seed_keyword_performance(brand, keyword, week_str, {
                    'geo_score': round(kw_geo, 4),
                    'visibility_score': kw_vis,
                    'confidence': round(kw_conf, 3),
                    'trend': profile['trend_direction'],
                    'priority_flag': kw_geo < 0.3,
                    'recorded_at': recorded_at,
                })
                summary['kw_entries'] += 1

        summary['brands_seeded'].append(brand)

    summary['status'] = 'complete'
    summary['timestamp'] = _now()
    logger.info("Seeded benchmark data: %d geo entries, %d kw entries",
                summary['geo_entries'], summary['kw_entries'])
    return summary
