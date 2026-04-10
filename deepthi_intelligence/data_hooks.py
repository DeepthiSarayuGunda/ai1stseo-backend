#!/usr/bin/env python3
"""
data_hooks.py
Safe Data Plumbing / Hooks for the Deepthi Intelligence Layer.

Provides clean read-only accessors and transformation utilities so the
intelligence layer can consume data from existing systems without modifying them.

All functions are READ-ONLY against existing tables/services.
Writes go only to Deepthi-specific tables.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _week():
    return datetime.now(timezone.utc).strftime('%Y-W%W')


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY HOOKS INTO EXISTING SYSTEMS
# ═══════════════════════════════════════════════════════════════════════════════

def get_raw_probes(brand: str = None, limit: int = 500) -> List[Dict]:
    """Read raw probe data from existing geo-probes table (RDS or DynamoDB)."""
    import os
    use_dynamo = not bool(os.environ.get("USE_RDS"))
    if use_dynamo:
        from db_dynamo import get_probes
    else:
        from db import get_probes
    return get_probes(limit=limit, brand=brand)


def get_visibility_history(brand: str = None, limit: int = 50) -> List[Dict]:
    """Read visibility batch history from existing tables."""
    import os
    use_dynamo = not bool(os.environ.get("USE_RDS"))
    if use_dynamo:
        from db_dynamo import get_visibility_history as _get_vis
    else:
        from db import get_visibility_history as _get_vis
    return _get_vis(limit=limit, brand=brand)


def get_probe_trend(brand: str, limit: int = 30) -> List[Dict]:
    """Read daily probe trend from existing tables."""
    import os
    use_dynamo = not bool(os.environ.get("USE_RDS"))
    if use_dynamo:
        from db_dynamo import get_probe_trend as _get_trend
    else:
        from db import get_probe_trend as _get_trend
    return _get_trend(brand=brand, limit=limit)


def get_m3_geo_score(brand: str) -> Optional[Dict]:
    """Read latest GEO score from Month 3 GEO Score Tracker (read-only)."""
    try:
        from month3_systems.geo_brand_intelligence import GEOScoreTracker
        return GEOScoreTracker().get_latest(brand)
    except Exception as e:
        logger.warning("Could not read M3 GEO score: %s", e)
        return None


def get_m3_keyword_performance(week: str = None) -> List[Dict]:
    """Read keyword performance from Month 3 register (read-only)."""
    try:
        from month3_systems.geo_brand_intelligence import KeywordPerformanceRegister
        return KeywordPerformanceRegister().get_all_latest(week)
    except Exception as e:
        logger.warning("Could not read M3 keyword performance: %s", e)
        return []


def get_m3_competitor_matrix(week: str = None) -> List[Dict]:
    """Read competitor matrix from Month 3 (read-only)."""
    try:
        from month3_systems.geo_brand_intelligence import CompetitorVisibilityMatrix
        return CompetitorVisibilityMatrix().get_matrix(week)
    except Exception as e:
        logger.warning("Could not read M3 competitor matrix: %s", e)
        return []


def get_available_providers() -> List[Dict]:
    """Read available AI providers from existing provider abstraction."""
    try:
        from ai_provider import get_available_providers
        return get_available_providers()
    except Exception as e:
        logger.warning("Could not read providers: %s", e)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# AGGREGATION / TRANSFORMATION UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def aggregate_brand_metrics(brand: str) -> Dict:
    """
    Aggregate all available metrics for a brand into a single intelligence summary.
    Pulls from raw probes, M3 tracker, and Deepthi history.
    """
    summary = {
        'brand': brand,
        'timestamp': _now(),
        'week': _week(),
    }

    # Raw probe stats
    probes = get_raw_probes(brand=brand, limit=200)
    if probes:
        total = len(probes)
        cited = sum(1 for p in probes if p.get('cited'))
        summary['raw_probe_count'] = total
        summary['raw_cited_count'] = cited
        summary['raw_geo_score'] = round(cited / total, 3) if total else 0

        # Provider breakdown
        prov_stats = defaultdict(lambda: {'cited': 0, 'total': 0})
        for p in probes:
            prov = p.get('ai_model', p.get('ai_platform', 'unknown'))
            prov_stats[prov]['total'] += 1
            if p.get('cited'):
                prov_stats[prov]['cited'] += 1
        summary['provider_breakdown'] = {
            prov: {
                'geo_score': round(d['cited'] / d['total'], 3) if d['total'] else 0,
                'cited': d['cited'],
                'total': d['total'],
            }
            for prov, d in prov_stats.items()
        }

        # Confidence stats
        confs = [float(p.get('confidence', 0)) for p in probes if p.get('confidence')]
        summary['avg_confidence'] = round(sum(confs) / len(confs), 3) if confs else 0
    else:
        summary['raw_probe_count'] = 0
        summary['raw_geo_score'] = 0
        summary['provider_breakdown'] = {}
        summary['avg_confidence'] = 0

    # M3 GEO score
    m3 = get_m3_geo_score(brand)
    if m3:
        summary['m3_geo_score'] = m3.get('geo_score', 0)
        summary['m3_visibility_score'] = m3.get('visibility_score', 0)
    else:
        summary['m3_geo_score'] = None
        summary['m3_visibility_score'] = None

    # Deepthi brand history
    try:
        from deepthi_intelligence.multi_brand_benchmark import BrandGEOHistory
        latest = BrandGEOHistory().get_latest(brand)
        if latest:
            summary['deepthi_latest_geo'] = latest.get('geo_score', 0)
            summary['deepthi_latest_confidence'] = latest.get('confidence', 0)
    except Exception:
        pass

    # Probe trend (last 7 days)
    trend = get_probe_trend(brand, limit=7)
    summary['trend_7d'] = trend

    return summary


def compare_brands_summary(brands: List[str]) -> Dict:
    """
    Quick side-by-side summary for multiple brands using existing data.
    No new probes — reads only from stored data.
    """
    result = {
        'timestamp': _now(),
        'brands': {},
    }
    for brand in brands:
        metrics = aggregate_brand_metrics(brand)
        result['brands'][brand] = {
            'geo_score': metrics.get('raw_geo_score', 0),
            'probe_count': metrics.get('raw_probe_count', 0),
            'avg_confidence': metrics.get('avg_confidence', 0),
            'provider_breakdown': metrics.get('provider_breakdown', {}),
            'm3_geo_score': metrics.get('m3_geo_score'),
        }

    # Ranking
    result['ranking'] = sorted(
        [{'brand': b, 'geo_score': d['geo_score']}
         for b, d in result['brands'].items()],
        key=lambda x: x['geo_score'], reverse=True
    )

    return result
