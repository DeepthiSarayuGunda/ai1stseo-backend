#!/usr/bin/env python3
"""
intelligence_summary_api.py
Single power endpoint for the GEO Scanner Agent page.

GET /api/m3/deepthi/scanner/intelligence-summary

Returns all intelligence data in one call:
  1. Multi-brand GEO Scores (current + change vs last week)
  2. Keyword Performance (top cited, competitor wins, engine breakdown)
  3. Competitor Visibility Matrix (side-by-side, engine preferences)
  4. Automation Status (4 scheduled jobs, last/next run, total runs)
  5. Citation Intelligence (cited pages, rates, content format analysis)
  6. Self-Learning Summary (weekly learnings, template performance, recommendations)

Reads from existing DynamoDB tables only — no new tables needed.
Does NOT modify any existing files.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

scanner_intel_bp = Blueprint('scanner_intel', __name__, url_prefix='/api/m3/deepthi/scanner')

BRANDS = ['AI1stSEO', 'Ahrefs', 'SEMrush', 'Moz', 'Surfer SEO']
PRIMARY_BRAND = 'AI1stSEO'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe(fn, default=None):
    """Run fn, return default on any error."""
    try:
        return fn()
    except Exception as e:
        logger.debug("intelligence-summary safe fallback: %s", e)
        return default


# =========================================================================
# SECTION BUILDERS — each returns a dict for one section of the response
# =========================================================================

def _build_multi_brand_scores() -> Dict:
    """
    Multi-brand GEO Scores with week-over-week change.
    Reads: geo-score-tracker (existing M3 table)
    """
    from deepthi_intelligence.benchmark_brands import MultiBrandGeoScores

    scorer = MultiBrandGeoScores()
    all_scores = scorer.get_all_brands_scores(BRANDS, limit_per_brand=2)

    brands = []
    keyword_winners = {}

    for brand in BRANDS:
        entries = all_scores.get(brand, [])
        current = entries[0] if entries else {}
        previous = entries[1] if len(entries) > 1 else {}

        current_geo = current.get('geo_score', 0)
        prev_geo = previous.get('geo_score', 0)
        delta = round(current_geo - prev_geo, 4)
        direction = 'up' if delta > 0.005 else 'down' if delta < -0.005 else 'stable'

        brands.append({
            'brand': brand,
            'geo_score': current_geo,
            'visibility_score': current.get('visibility_score', 0),
            'keywords_probed': current.get('keywords_probed', 0),
            'keywords_cited': current.get('keywords_cited', 0),
            'provider_scores': current.get('provider_scores', {}),
            'week': current.get('week', ''),
            'change_vs_last_week': {
                'delta': delta,
                'direction': direction,
                'previous_score': prev_geo,
            },
        })

    # Sort by geo_score descending
    brands.sort(key=lambda x: x['geo_score'], reverse=True)

    # Keyword winners — which brand wins per keyword
    try:
        from deepthi_intelligence.benchmark_brands import MultiBrandKeywordPerformance
        kw_perf = MultiBrandKeywordPerformance()
        from deepthi_intelligence.benchmark_brands import BENCHMARK_KEYWORDS
        for kw in BENCHMARK_KEYWORDS:
            kw_data = kw_perf.get_keyword_across_brands(kw, BRANDS, limit=1)
            best_brand = None
            best_score = -1
            for b, entries in kw_data.items():
                if entries and entries[0].get('geo_score', 0) > best_score:
                    best_score = entries[0]['geo_score']
                    best_brand = b
            if best_brand:
                keyword_winners[kw] = {
                    'winning_brand': best_brand,
                    'geo_score': best_score,
                }
    except Exception:
        pass

    return {
        'brands': brands,
        'ranking': [b['brand'] for b in brands],
        'keyword_winners': keyword_winners,
    }


def _build_keyword_performance() -> Dict:
    """
    Keyword performance: top cited for primary, competitor wins, engine breakdown.
    Reads: geo-keyword-performance, ai1stseo-geo-probes
    """
    result = {
        'top_cited_keywords': [],
        'competitor_beating_us': [],
        'engine_brand_citations': {},
    }

    try:
        from deepthi_intelligence.benchmark_brands import (
            MultiBrandKeywordPerformance, BENCHMARK_KEYWORDS,
        )
        kw_perf = MultiBrandKeywordPerformance()

        primary_scores = {}
        competitor_best = {}

        for kw in BENCHMARK_KEYWORDS:
            kw_data = kw_perf.get_keyword_across_brands(kw, BRANDS, limit=1)

            # Primary brand score
            primary_entries = kw_data.get(PRIMARY_BRAND, [])
            p_score = primary_entries[0].get('geo_score', 0) if primary_entries else 0
            primary_scores[kw] = p_score

            # Best competitor score
            best_comp = None
            best_comp_score = 0
            for b in BRANDS:
                if b == PRIMARY_BRAND:
                    continue
                entries = kw_data.get(b, [])
                score = entries[0].get('geo_score', 0) if entries else 0
                if score > best_comp_score:
                    best_comp_score = score
                    best_comp = b

            if best_comp_score > p_score:
                competitor_best[kw] = {
                    'keyword': kw,
                    'competitor': best_comp,
                    'competitor_score': best_comp_score,
                    'our_score': p_score,
                    'gap': round(best_comp_score - p_score, 4),
                }

        # Top 10 keywords where AI1stSEO is cited
        sorted_primary = sorted(primary_scores.items(), key=lambda x: x[1], reverse=True)
        result['top_cited_keywords'] = [
            {'keyword': kw, 'geo_score': score}
            for kw, score in sorted_primary[:10]
        ]

        # Top 10 keywords where competitors beat us
        sorted_gaps = sorted(competitor_best.values(), key=lambda x: x['gap'], reverse=True)
        result['competitor_beating_us'] = sorted_gaps[:10]

    except Exception as e:
        logger.debug("Keyword performance error: %s", e)

    # Engine-brand citation breakdown from raw probes
    try:
        from deepthi_intelligence.data_hooks import get_raw_probes
        probes = get_raw_probes(limit=500)
        engine_stats = defaultdict(lambda: defaultdict(lambda: {'cited': 0, 'total': 0}))
        for p in probes:
            engine = p.get('ai_model', p.get('ai_platform', 'unknown'))
            brand = p.get('brand_name', 'unknown')
            engine_stats[engine][brand]['total'] += 1
            if p.get('cited'):
                engine_stats[engine][brand]['cited'] += 1

        engine_summary = {}
        for engine, brands_data in engine_stats.items():
            engine_summary[engine] = {
                'brands': {
                    b: {
                        'citation_rate': round(d['cited'] / d['total'], 3) if d['total'] else 0,
                        'cited': d['cited'],
                        'total': d['total'],
                    }
                    for b, d in brands_data.items()
                },
                'most_cited_brand': max(
                    brands_data.items(),
                    key=lambda x: x[1]['cited'] / max(x[1]['total'], 1)
                )[0] if brands_data else 'none',
            }
        result['engine_brand_citations'] = engine_summary
    except Exception as e:
        logger.debug("Engine citation error: %s", e)

    return result


def _build_competitor_matrix() -> Dict:
    """
    Competitor visibility matrix: side-by-side, engine preferences, WoW change.
    Reads: geo-score-tracker, geo-competitor-matrix
    """
    result = {'matrix': [], 'engine_preferences': {}}

    try:
        from deepthi_intelligence.benchmark_brands import MultiBrandGeoScores
        scorer = MultiBrandGeoScores()
        all_scores = scorer.get_all_brands_scores(BRANDS, limit_per_brand=2)

        for brand in BRANDS:
            entries = all_scores.get(brand, [])
            current = entries[0] if entries else {}
            previous = entries[1] if len(entries) > 1 else {}

            current_geo = current.get('geo_score', 0)
            prev_geo = previous.get('geo_score', 0)
            prov_scores = current.get('provider_scores', {})

            result['matrix'].append({
                'brand': brand,
                'geo_score': current_geo,
                'visibility_score': current.get('visibility_score', 0),
                'provider_scores': prov_scores,
                'wow_change': round(current_geo - prev_geo, 4),
                'wow_direction': 'up' if current_geo > prev_geo + 0.005
                                 else 'down' if current_geo < prev_geo - 0.005
                                 else 'stable',
            })

            # Track which brand each engine prefers
            for engine, score in prov_scores.items():
                if engine not in result['engine_preferences']:
                    result['engine_preferences'][engine] = []
                result['engine_preferences'][engine].append({
                    'brand': brand, 'score': score,
                })

        result['matrix'].sort(key=lambda x: x['geo_score'], reverse=True)

        # Sort engine preferences
        for engine in result['engine_preferences']:
            result['engine_preferences'][engine].sort(
                key=lambda x: x['score'], reverse=True)

    except Exception as e:
        logger.debug("Competitor matrix error: %s", e)

    return result


def _build_automation_status() -> Dict:
    """
    Automation status for all 4 scheduled jobs.
    Reads: deepthi-schedule-log
    """
    jobs = [
        {'task': 'directory_freshness', 'name': 'Directory Freshness', 'interval': 'Every 6 hours'},
        {'task': 'aeo_learning_update', 'name': 'AEO Learning Log', 'interval': 'Every 24 hours'},
        {'task': 'full_geo_scoring', 'name': 'Full GEO Scoring', 'interval': 'Every 7 days'},
        {'task': 'competitor_matrix_update', 'name': 'Competitor Matrix', 'interval': 'Every 7 days'},
    ]

    result = {'jobs': [], 'total_runs_completed': 0}

    try:
        from deepthi_intelligence.eventbridge_scheduler import ScheduleLog
        log = ScheduleLog()

        for job in jobs:
            history = log.get_history(task_type=job['task'], limit=5)
            last_run = history[0] if history else None
            total_for_task = len(history)
            result['total_runs_completed'] += total_for_task

            result['jobs'].append({
                'task_type': job['task'],
                'name': job['name'],
                'interval': job['interval'],
                'last_run': last_run.get('completed_at') if last_run else 'never',
                'last_status': last_run.get('status') if last_run else 'not_run',
                'runs_completed': total_for_task,
            })
    except Exception as e:
        logger.debug("Automation status error: %s", e)
        for job in jobs:
            result['jobs'].append({
                'task_type': job['task'],
                'name': job['name'],
                'interval': job['interval'],
                'last_run': 'never',
                'last_status': 'not_run',
                'runs_completed': 0,
            })

    return result


def _build_citation_intelligence() -> Dict:
    """
    Citation intelligence: cited pages, rates per brand, content format analysis.
    Reads: ai1stseo-geo-probes, deepthi-citation-patterns
    """
    result = {
        'citation_rates_by_brand': {},
        'top_cited_contexts': [],
        'content_format_performance': [],
    }

    # Citation rates per brand from raw probes
    try:
        from deepthi_intelligence.data_hooks import get_raw_probes
        probes = get_raw_probes(limit=500)

        brand_stats = defaultdict(lambda: {'cited': 0, 'total': 0, 'contexts': []})
        for p in probes:
            brand = p.get('brand_name', 'unknown')
            brand_stats[brand]['total'] += 1
            if p.get('cited'):
                brand_stats[brand]['cited'] += 1
                ctx = p.get('citation_context', '')
                if ctx:
                    brand_stats[brand]['contexts'].append({
                        'keyword': p.get('keyword', ''),
                        'context': ctx[:200],
                        'engine': p.get('ai_model', 'unknown'),
                        'confidence': p.get('confidence', 0),
                    })

        for brand, stats in brand_stats.items():
            rate = round(stats['cited'] / stats['total'], 3) if stats['total'] else 0
            result['citation_rates_by_brand'][brand] = {
                'citation_rate': rate,
                'citation_rate_pct': round(rate * 100, 1),
                'cited_count': stats['cited'],
                'total_probes': stats['total'],
            }
            # Collect top contexts
            for ctx in stats['contexts'][:3]:
                ctx['brand'] = brand
                result['top_cited_contexts'].append(ctx)

        # Sort contexts by confidence
        result['top_cited_contexts'].sort(
            key=lambda x: x.get('confidence', 0), reverse=True)
        result['top_cited_contexts'] = result['top_cited_contexts'][:10]

    except Exception as e:
        logger.debug("Citation rates error: %s", e)

    # Content format performance from citation learning
    try:
        from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
        engine = CitationLearningEngine()
        patterns = engine.get_learned_patterns(limit=10)
        if patterns:
            result['content_format_performance'] = [
                {
                    'format': p.get('format_type', 'unknown'),
                    'citation_rate': p.get('citation_rate', 0),
                    'citation_rate_pct': round(float(p.get('citation_rate', 0)) * 100, 1),
                    'total_seen': p.get('total_seen', 0),
                }
                for p in patterns
            ]
        else:
            # Provide defaults if no learning data yet
            result['content_format_performance'] = [
                {'format': 'faq', 'citation_rate': 0, 'citation_rate_pct': 0, 'total_seen': 0, 'note': 'Run citation learning to populate'},
                {'format': 'list', 'citation_rate': 0, 'citation_rate_pct': 0, 'total_seen': 0},
                {'format': 'comparison', 'citation_rate': 0, 'citation_rate_pct': 0, 'total_seen': 0},
            ]
    except Exception as e:
        logger.debug("Content format error: %s", e)

    return result


def _build_self_learning_summary() -> Dict:
    """
    Self-learning summary: weekly learnings, template performance, recommendations.
    Reads: deepthi-citation-patterns, deepthi-template-recommendations, deepthi-auto-actions
    """
    result = {
        'weekly_learnings': [],
        'top_performing_templates': [],
        'recommended_actions': [],
        'impact_summary': {},
    }

    # Template recommendations
    try:
        from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
        engine = CitationLearningEngine()
        recs = engine.get_recommendations(limit=5)
        result['top_performing_templates'] = [
            {
                'format': r.get('format_type', 'unknown'),
                'citation_rate': r.get('citation_rate', 0),
                'confidence': r.get('confidence', 'low'),
                'recommendation': r.get('recommendation', ''),
            }
            for r in recs
        ]

        # Generate recommended actions from patterns
        patterns = engine.get_learned_patterns(limit=5)
        for p in patterns:
            fmt = p.get('format_type', '')
            rate = float(p.get('citation_rate', 0))
            if rate > 0.5:
                result['recommended_actions'].append({
                    'action': f'Increase {fmt} content — {round(rate*100,1)}% citation rate',
                    'priority': 'high',
                    'format': fmt,
                })
            elif rate > 0.3:
                result['recommended_actions'].append({
                    'action': f'Optimize {fmt} content — {round(rate*100,1)}% citation rate, room to grow',
                    'priority': 'medium',
                    'format': fmt,
                })
    except Exception as e:
        logger.debug("Self-learning recs error: %s", e)

    # If no recommendations yet, provide smart defaults
    if not result['recommended_actions']:
        result['recommended_actions'] = [
            {'action': 'Run citation learning (POST /api/m3/deepthi/citation-learning/learn) to populate insights', 'priority': 'high', 'format': 'system'},
            {'action': 'Add FAQ schema to top landing pages for higher AI citation rates', 'priority': 'high', 'format': 'faq'},
            {'action': 'Create comparison tables for competitive keywords', 'priority': 'medium', 'format': 'comparison'},
            {'action': 'Add step-by-step HowTo schema for tutorial content', 'priority': 'medium', 'format': 'how_to'},
        ]

    # Impact summary from action register
    try:
        from deepthi_intelligence.action_register_automation import AutoActionRegister
        register = AutoActionRegister()
        impact = register.get_impact_summary(PRIMARY_BRAND)
        if impact.get('status') != 'no_data':
            result['impact_summary'] = impact
    except Exception as e:
        logger.debug("Impact summary error: %s", e)

    # Weekly learnings — aggregate from recent schedule runs
    try:
        from deepthi_intelligence.eventbridge_scheduler import ScheduleLog
        log = ScheduleLog()
        recent = log.get_history(limit=10)
        for entry in recent[:5]:
            summary = entry.get('summary', {})
            if isinstance(summary, str):
                try:
                    summary = json.loads(summary)
                except Exception:
                    pass
            result['weekly_learnings'].append({
                'task': entry.get('task_type', ''),
                'status': entry.get('status', ''),
                'completed_at': entry.get('completed_at', ''),
                'key_finding': _extract_key_finding(entry.get('task_type', ''), summary),
            })
    except Exception as e:
        logger.debug("Weekly learnings error: %s", e)

    if not result['weekly_learnings']:
        result['weekly_learnings'] = [
            {'task': 'system', 'status': 'info',
             'key_finding': 'Run scheduled tasks to generate weekly learnings. '
                            'POST /api/m3/deepthi/scheduler/run/aeo_learning_update'},
        ]

    return result


def _extract_key_finding(task_type: str, summary: Dict) -> str:
    """Extract a human-readable key finding from a schedule run summary."""
    if not summary or not isinstance(summary, dict):
        return 'No details available'

    if task_type == 'directory_freshness':
        brands = summary.get('brands', {})
        if brands:
            stale_total = sum(b.get('pages_stale', 0) for b in brands.values())
            return f'{stale_total} stale pages detected across {len(brands)} brands'
    elif task_type == 'aeo_learning_update':
        formats = summary.get('formats_detected', 0)
        recs = summary.get('recommendations_generated', 0)
        return f'{formats} content formats analyzed, {recs} new recommendations'
    elif task_type == 'full_geo_scoring':
        total = summary.get('total_brands', 0)
        return f'GEO scores updated for {total} brands'
    elif task_type == 'competitor_matrix_update':
        updated = summary.get('brands_updated', 0)
        return f'Competitor matrix updated for {updated} brands'

    return summary.get('status', 'completed')


# =========================================================================
# THE ENDPOINT
# =========================================================================

@scanner_intel_bp.route('/intelligence-summary', methods=['GET'])
def intelligence_summary():
    """
    GET /api/m3/deepthi/scanner/intelligence-summary

    Single power endpoint that feeds the entire GEO Scanner Agent page.
    Aggregates data from 8+ DynamoDB tables into one response.
    """
    response = {
        'generated_at': _now(),
        'primary_brand': PRIMARY_BRAND,
        'brands_tracked': BRANDS,
    }

    # Build each section — each is fault-tolerant
    response['multi_brand_scores'] = _safe(_build_multi_brand_scores, {})
    response['keyword_performance'] = _safe(_build_keyword_performance, {})
    response['competitor_matrix'] = _safe(_build_competitor_matrix, {})
    response['automation_status'] = _safe(_build_automation_status, {})
    response['citation_intelligence'] = _safe(_build_citation_intelligence, {})
    response['self_learning_summary'] = _safe(_build_self_learning_summary, {})

    # Tables this endpoint reads from (for documentation)
    response['_meta'] = {
        'tables_read': [
            'geo-score-tracker',
            'geo-keyword-performance',
            'geo-competitor-matrix',
            'ai1stseo-geo-probes',
            'deepthi-schedule-log',
            'deepthi-citation-patterns',
            'deepthi-template-recommendations',
            'deepthi-auto-actions',
        ],
        'endpoint': '/api/m3/deepthi/scanner/intelligence-summary',
        'method': 'GET',
    }

    return jsonify(response)
