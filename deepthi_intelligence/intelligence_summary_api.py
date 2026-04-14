#!/usr/bin/env python3
"""
intelligence_summary_api.py
Single power endpoint for the GEO Scanner Agent page.

GET /api/m3/deepthi/scanner/intelligence-summary
GET /geo-scanner-intelligence  (serves the dashboard HTML)

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

from flask import Blueprint, jsonify, send_from_directory

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
# SECTION BUILDERS
# =========================================================================

def _build_multi_brand_scores() -> Dict:
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
            'change_vs_last_week': {'delta': delta, 'direction': direction, 'previous_score': prev_geo},
        })
    brands.sort(key=lambda x: x['geo_score'], reverse=True)
    try:
        from deepthi_intelligence.benchmark_brands import MultiBrandKeywordPerformance, BENCHMARK_KEYWORDS
        kw_perf = MultiBrandKeywordPerformance()
        for kw in BENCHMARK_KEYWORDS:
            kw_data = kw_perf.get_keyword_across_brands(kw, BRANDS, limit=1)
            best_brand, best_score = None, -1
            for b, entries in kw_data.items():
                if entries and entries[0].get('geo_score', 0) > best_score:
                    best_score = entries[0]['geo_score']
                    best_brand = b
            if best_brand:
                keyword_winners[kw] = {'winning_brand': best_brand, 'geo_score': best_score}
    except Exception:
        pass
    return {'brands': brands, 'ranking': [b['brand'] for b in brands], 'keyword_winners': keyword_winners}


def _build_keyword_performance() -> Dict:
    result = {'top_cited_keywords': [], 'competitor_beating_us': [], 'engine_brand_citations': {}}
    try:
        from deepthi_intelligence.benchmark_brands import MultiBrandKeywordPerformance, BENCHMARK_KEYWORDS
        kw_perf = MultiBrandKeywordPerformance()
        primary_scores = {}
        competitor_best = {}
        for kw in BENCHMARK_KEYWORDS:
            kw_data = kw_perf.get_keyword_across_brands(kw, BRANDS, limit=1)
            p_entries = kw_data.get(PRIMARY_BRAND, [])
            p_score = p_entries[0].get('geo_score', 0) if p_entries else 0
            primary_scores[kw] = p_score
            best_comp, best_comp_score = None, 0
            for b in BRANDS:
                if b == PRIMARY_BRAND:
                    continue
                entries = kw_data.get(b, [])
                score = entries[0].get('geo_score', 0) if entries else 0
                if score > best_comp_score:
                    best_comp_score = score
                    best_comp = b
            if best_comp_score > p_score:
                competitor_best[kw] = {'keyword': kw, 'competitor': best_comp, 'competitor_score': best_comp_score, 'our_score': p_score, 'gap': round(best_comp_score - p_score, 4)}
        result['top_cited_keywords'] = [{'keyword': kw, 'geo_score': s} for kw, s in sorted(primary_scores.items(), key=lambda x: x[1], reverse=True)[:10]]
        result['competitor_beating_us'] = sorted(competitor_best.values(), key=lambda x: x['gap'], reverse=True)[:10]
    except Exception as e:
        logger.debug("Keyword performance error: %s", e)
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
        for engine, brands_data in engine_stats.items():
            result['engine_brand_citations'][engine] = {
                'brands': {b: {'citation_rate': round(d['cited'] / d['total'], 3) if d['total'] else 0, 'cited': d['cited'], 'total': d['total']} for b, d in brands_data.items()},
                'most_cited_brand': max(brands_data.items(), key=lambda x: x[1]['cited'] / max(x[1]['total'], 1))[0] if brands_data else 'none',
            }
    except Exception as e:
        logger.debug("Engine citation error: %s", e)
    return result


def _build_competitor_matrix() -> Dict:
    result = {'matrix': [], 'engine_preferences': {}}
    try:
        from deepthi_intelligence.benchmark_brands import MultiBrandGeoScores
        all_scores = MultiBrandGeoScores().get_all_brands_scores(BRANDS, limit_per_brand=2)
        for brand in BRANDS:
            entries = all_scores.get(brand, [])
            current = entries[0] if entries else {}
            previous = entries[1] if len(entries) > 1 else {}
            current_geo = current.get('geo_score', 0)
            prev_geo = previous.get('geo_score', 0)
            prov_scores = current.get('provider_scores', {})
            result['matrix'].append({
                'brand': brand, 'geo_score': current_geo, 'visibility_score': current.get('visibility_score', 0),
                'provider_scores': prov_scores, 'wow_change': round(current_geo - prev_geo, 4),
                'wow_direction': 'up' if current_geo > prev_geo + 0.005 else 'down' if current_geo < prev_geo - 0.005 else 'stable',
            })
            for engine, score in prov_scores.items():
                if engine not in result['engine_preferences']:
                    result['engine_preferences'][engine] = []
                result['engine_preferences'][engine].append({'brand': brand, 'score': score})
        result['matrix'].sort(key=lambda x: x['geo_score'], reverse=True)
        for engine in result['engine_preferences']:
            result['engine_preferences'][engine].sort(key=lambda x: x['score'], reverse=True)
    except Exception as e:
        logger.debug("Competitor matrix error: %s", e)
    return result


def _build_automation_status() -> Dict:
    jobs_def = [
        {'task': 'directory_freshness', 'name': 'Directory Freshness', 'interval': 'Every 6 hours'},
        {'task': 'aeo_learning_update', 'name': 'AEO Learning Log', 'interval': 'Every 24 hours'},
        {'task': 'full_geo_scoring', 'name': 'Full GEO Scoring', 'interval': 'Every 7 days'},
        {'task': 'competitor_matrix_update', 'name': 'Competitor Matrix', 'interval': 'Every 7 days'},
    ]
    result = {'jobs': [], 'total_runs_completed': 0}
    try:
        from deepthi_intelligence.eventbridge_scheduler import ScheduleLog
        log = ScheduleLog()
        for job in jobs_def:
            history = log.get_history(task_type=job['task'], limit=5)
            last_run = history[0] if history else None
            result['total_runs_completed'] += len(history)
            result['jobs'].append({
                'task_type': job['task'], 'name': job['name'], 'interval': job['interval'],
                'last_run': last_run.get('completed_at') if last_run else 'never',
                'last_status': last_run.get('status') if last_run else 'not_run',
                'runs_completed': len(history),
            })
    except Exception:
        for job in jobs_def:
            result['jobs'].append({'task_type': job['task'], 'name': job['name'], 'interval': job['interval'], 'last_run': 'never', 'last_status': 'not_run', 'runs_completed': 0})
    return result


def _build_citation_intelligence() -> Dict:
    result = {'citation_rates_by_brand': {}, 'top_cited_contexts': [], 'content_format_performance': []}
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
                    brand_stats[brand]['contexts'].append({'keyword': p.get('keyword', ''), 'context': ctx[:200], 'engine': p.get('ai_model', 'unknown'), 'confidence': p.get('confidence', 0)})
        for brand, stats in brand_stats.items():
            rate = round(stats['cited'] / stats['total'], 3) if stats['total'] else 0
            result['citation_rates_by_brand'][brand] = {'citation_rate': rate, 'citation_rate_pct': round(rate * 100, 1), 'cited_count': stats['cited'], 'total_probes': stats['total']}
            for ctx in stats['contexts'][:3]:
                ctx['brand'] = brand
                result['top_cited_contexts'].append(ctx)
        result['top_cited_contexts'].sort(key=lambda x: x.get('confidence', 0), reverse=True)
        result['top_cited_contexts'] = result['top_cited_contexts'][:10]
    except Exception as e:
        logger.debug("Citation rates error: %s", e)
    try:
        from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
        patterns = CitationLearningEngine().get_learned_patterns(limit=10)
        if patterns:
            result['content_format_performance'] = [{'format': p.get('format_type', ''), 'citation_rate': p.get('citation_rate', 0), 'citation_rate_pct': round(float(p.get('citation_rate', 0)) * 100, 1), 'total_seen': p.get('total_seen', 0)} for p in patterns]
    except Exception:
        pass
    if not result['content_format_performance']:
        result['content_format_performance'] = [{'format': 'faq', 'citation_rate': 0, 'note': 'Run citation learning to populate'}, {'format': 'list', 'citation_rate': 0}, {'format': 'comparison', 'citation_rate': 0}]
    return result


def _build_self_learning_summary() -> Dict:
    result = {'weekly_learnings': [], 'top_performing_templates': [], 'recommended_actions': [], 'impact_summary': {}}
    try:
        from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
        engine = CitationLearningEngine()
        recs = engine.get_recommendations(limit=5)
        result['top_performing_templates'] = [{'format': r.get('format_type', ''), 'citation_rate': r.get('citation_rate', 0), 'confidence': r.get('confidence', 'low'), 'recommendation': r.get('recommendation', '')} for r in recs]
        patterns = engine.get_learned_patterns(limit=5)
        for p in patterns:
            rate = float(p.get('citation_rate', 0))
            fmt = p.get('format_type', '')
            if rate > 0.5:
                result['recommended_actions'].append({'action': f'Increase {fmt} content — {round(rate*100,1)}% citation rate', 'priority': 'high', 'format': fmt})
            elif rate > 0.3:
                result['recommended_actions'].append({'action': f'Optimize {fmt} content — {round(rate*100,1)}% citation rate', 'priority': 'medium', 'format': fmt})
    except Exception:
        pass
    if not result['recommended_actions']:
        result['recommended_actions'] = [
            {'action': 'Add FAQ schema to top landing pages for higher AI citation rates', 'priority': 'high', 'format': 'faq'},
            {'action': 'Create comparison tables for competitive keywords', 'priority': 'medium', 'format': 'comparison'},
            {'action': 'Add step-by-step HowTo schema for tutorial content', 'priority': 'medium', 'format': 'how_to'},
            {'action': 'Cite authoritative sources and studies in content', 'priority': 'medium', 'format': 'statistics'},
        ]
    try:
        from deepthi_intelligence.action_register_automation import AutoActionRegister
        impact = AutoActionRegister().get_impact_summary(PRIMARY_BRAND)
        if impact.get('status') != 'no_data':
            result['impact_summary'] = impact
    except Exception:
        pass
    return result


# =========================================================================
# ENDPOINTS
# =========================================================================

@scanner_intel_bp.route('/intelligence-summary', methods=['GET'])
def intelligence_summary():
    """GET /api/m3/deepthi/scanner/intelligence-summary"""
    response = {
        'generated_at': _now(),
        'primary_brand': PRIMARY_BRAND,
        'brands_tracked': BRANDS,
        'multi_brand_scores': _safe(_build_multi_brand_scores, {}),
        'keyword_performance': _safe(_build_keyword_performance, {}),
        'competitor_matrix': _safe(_build_competitor_matrix, {}),
        'automation_status': _safe(_build_automation_status, {}),
        'citation_intelligence': _safe(_build_citation_intelligence, {}),
        'self_learning_summary': _safe(_build_self_learning_summary, {}),
        '_meta': {
            'tables_read': [
                'geo-score-tracker', 'geo-keyword-performance', 'geo-competitor-matrix',
                'ai1stseo-geo-probes', 'deepthi-schedule-log', 'deepthi-citation-patterns',
                'deepthi-template-recommendations', 'deepthi-auto-actions',
            ],
        },
    }
    return jsonify(response)


@scanner_intel_bp.route('/dashboard', methods=['GET'])
def serve_scanner_dashboard():
    """Serve the GEO Scanner Intelligence Dashboard HTML."""
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..'),
                               'geo-scanner-intelligence.html')
