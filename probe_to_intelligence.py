"""
probe_to_intelligence.py
Transformation bridge: raw GEO probe data → Month 3 intelligence tables.

Reads from:  ai1stseo-geo-probes (DynamoDB)
Writes to:   geo-score-tracker, geo-keyword-performance, geo-competitor-matrix

Flow: GEO scan → raw probe storage → THIS MODULE → Month 3 tables → dashboard

Can be triggered:
  - Manually via POST /api/m3/transform
  - Automatically by the scheduler after each GEO probe cycle
"""

import logging
import os
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _week():
    return datetime.now(timezone.utc).strftime('%Y-W%W')


def _load_raw_probes(brand: str = None, limit: int = 500) -> list:
    """Load raw probe results from ai1stseo-geo-probes."""
    use_dynamo = not bool(os.environ.get("USE_RDS"))
    if use_dynamo:
        from db_dynamo import get_probes
    else:
        from db import get_probes
    return get_probes(limit=limit, brand=brand)


def transform_probes_to_intelligence(brand: str, competitors: list = None) -> dict:
    """
    Main bridge function. Reads raw probes, aggregates, writes to Month 3 tables.

    Returns summary of what was written.
    """
    week = _week()
    results = {'week': week, 'brand': brand, 'status': 'complete'}

    # 1. Load all raw probes for this brand
    probes = _load_raw_probes(brand=brand, limit=500)
    if not probes:
        results['status'] = 'no_data'
        results['message'] = f'No probe data found for brand: {brand}'
        return results

    # 2. Aggregate keyword-level metrics
    kw_metrics = _aggregate_keyword_metrics(probes)

    # 3. Write to Keyword Performance Register
    kw_count = _write_keyword_performance(week, kw_metrics)
    results['keywords_written'] = kw_count

    # 4. Compute and write overall GEO Score Tracker
    _write_geo_score_tracker(brand, week, probes, kw_metrics)
    results['geo_tracker_updated'] = True

    # 5. Process competitors if provided
    if competitors:
        comp_count = _process_competitors(competitors, week)
        results['competitors_written'] = comp_count

    results['total_probes_processed'] = len(probes)
    results['timestamp'] = datetime.now(timezone.utc).isoformat()
    return results


def _aggregate_keyword_metrics(probes: list) -> dict:
    """
    Aggregate raw probes into per-keyword metrics.

    Returns: {keyword: {geo_score, visibility_score, confidence, cited_count, total, providers}}
    """
    kw_data = defaultdict(lambda: {
        'cited': 0, 'total': 0, 'confidence_sum': 0.0,
        'providers': set(), 'providers_cited': set(),
    })

    for p in probes:
        kw = p.get('keyword', '')
        if not kw or kw == '__monitor__':
            continue
        entry = kw_data[kw]
        entry['total'] += 1
        provider = p.get('ai_model', p.get('ai_platform', 'unknown'))
        entry['providers'].add(provider)
        if p.get('cited'):
            entry['cited'] += 1
            entry['providers_cited'].add(provider)
        entry['confidence_sum'] += float(p.get('confidence', 0))

    # Compute scores
    metrics = {}
    for kw, d in kw_data.items():
        geo_score = round(d['cited'] / d['total'], 2) if d['total'] else 0
        vis_score = round(len(d['providers_cited']) / len(d['providers']) * 100) if d['providers'] else 0
        avg_conf = round(d['confidence_sum'] / d['total'], 2) if d['total'] else 0
        metrics[kw] = {
            'keyword': kw,
            'geo_score': geo_score,
            'visibility_score': vis_score,
            'confidence': avg_conf,
            'cited_count': d['cited'],
            'total_probes': d['total'],
            'providers_queried': list(d['providers']),
            'providers_cited': list(d['providers_cited']),
        }

    return metrics


def _compute_trend(keyword: str, current_geo: float) -> str:
    """Compare current geo_score to previous week to determine trend."""
    try:
        from month3_systems.geo_brand_intelligence import KeywordPerformanceRegister
        kpr = KeywordPerformanceRegister()
        history = kpr.get_keyword_history(keyword, limit=1)
        if history:
            prev = float(history[0].get('geo_score', 0))
            if current_geo > prev + 0.05:
                return 'up'
            elif current_geo < prev - 0.05:
                return 'down'
        return 'stable'
    except Exception:
        return 'stable'


def _write_keyword_performance(week: str, kw_metrics: dict) -> int:
    """Write aggregated keyword metrics to geo-keyword-performance table."""
    try:
        from month3_systems.geo_brand_intelligence import KeywordPerformanceRegister
        kpr = KeywordPerformanceRegister()
        records = []
        for kw, m in kw_metrics.items():
            trend = _compute_trend(kw, m['geo_score'])
            priority = m['geo_score'] < 0.3 and m['total_probes'] >= 2
            records.append({
                'keyword': kw,
                'geo_score': m['geo_score'],
                'visibility_score': m['visibility_score'],
                'confidence': m['confidence'],
                'trend': trend,
                'priority_flag': priority,
            })
        count = kpr.bulk_record(week, records)
        logger.info("Wrote %d keyword records to performance register (week %s)", count, week)
        return count
    except Exception as e:
        logger.error("Failed to write keyword performance: %s", e)
        return 0


def _write_geo_score_tracker(brand: str, week: str, probes: list, kw_metrics: dict):
    """Compute overall GEO score and write to geo-score-tracker table."""
    try:
        from month3_systems.geo_brand_intelligence import GEOScoreTracker

        total_cited = sum(1 for p in probes if p.get('cited'))
        total_probes = len(probes)
        overall_geo = round(total_cited / total_probes, 2) if total_probes else 0

        # Visibility: average across keywords
        vis_scores = [m['visibility_score'] for m in kw_metrics.values()]
        avg_vis = round(sum(vis_scores) / len(vis_scores)) if vis_scores else 0

        # Per-provider breakdown
        provider_stats = defaultdict(lambda: {'cited': 0, 'total': 0})
        for p in probes:
            prov = p.get('ai_model', p.get('ai_platform', 'unknown'))
            provider_stats[prov]['total'] += 1
            if p.get('cited'):
                provider_stats[prov]['cited'] += 1
        provider_scores = {
            prov: round(d['cited'] / d['total'], 2) if d['total'] else 0
            for prov, d in provider_stats.items()
        }

        tracker = GEOScoreTracker()
        tracker.record_week(brand, {
            'week': week,
            'geo_score': overall_geo,
            'visibility_score': avg_vis,
            'keywords_probed': len(kw_metrics),
            'keywords_cited': sum(1 for m in kw_metrics.values() if m['geo_score'] > 0),
            'provider_scores': provider_scores,
        })
        logger.info("GEO Score Tracker updated: brand=%s week=%s geo=%.2f vis=%d",
                     brand, week, overall_geo, avg_vis)
    except Exception as e:
        logger.error("Failed to write GEO score tracker: %s", e)


def _process_competitors(competitors: list, week: str) -> int:
    """Load probe data for competitors and write to competitor matrix."""
    count = 0
    try:
        from month3_systems.geo_brand_intelligence import CompetitorVisibilityMatrix
        matrix = CompetitorVisibilityMatrix()

        for comp in competitors:
            probes = _load_raw_probes(brand=comp, limit=200)
            if not probes:
                continue
            kw_metrics = _aggregate_keyword_metrics(probes)
            total_cited = sum(1 for p in probes if p.get('cited'))
            total = len(probes)
            vis = round(total_cited / total * 100) if total else 0

            # Provider breakdown
            prov_stats = defaultdict(lambda: {'cited': 0, 'total': 0})
            for p in probes:
                prov = p.get('ai_model', 'unknown')
                prov_stats[prov]['total'] += 1
                if p.get('cited'):
                    prov_stats[prov]['cited'] += 1

            top_kws = sorted(kw_metrics.values(), key=lambda x: x['geo_score'], reverse=True)[:5]

            matrix.record(comp, week, {
                'visibility_score': vis,
                'keywords_cited': sum(1 for m in kw_metrics.values() if m['geo_score'] > 0),
                'total_keywords': len(kw_metrics),
                'provider_breakdown': {
                    prov: round(d['cited'] / d['total'], 2) if d['total'] else 0
                    for prov, d in prov_stats.items()
                },
                'top_keywords': [k['keyword'] for k in top_kws],
            })
            count += 1
            logger.info("Competitor matrix updated: %s week=%s vis=%d", comp, week, vis)
    except Exception as e:
        logger.error("Failed to process competitors: %s", e)
    return count
