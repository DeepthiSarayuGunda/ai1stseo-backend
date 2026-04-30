#!/usr/bin/env python3
"""
Deepthi Intelligence Layer — API Blueprint

All endpoints under /api/deepthi/*
Isolated from existing routes — no modifications to app.py routes or month3 API.

Sections:
  1. Multi-Brand Benchmarking
  2. Brand GEO History & Comparison
  3. Keyword-Brand Matrix
  4. Freshness Tracking
  5. Data Hooks / Aggregation
"""

from flask import Blueprint, request, jsonify

deepthi_bp = Blueprint('deepthi', __name__, url_prefix='/api/deepthi')


# ═══════════════════════════════════════════════════════════════════════════════
# 1. MULTI-BRAND BENCHMARKING
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/benchmark/run', methods=['POST'])
def benchmark_run():
    """
    Run a multi-brand benchmark.
    Body: {
      "primary_brand": "AI1stSEO",
      "benchmark_brands": ["Ahrefs", "SEMrush", "Moz"],
      "keywords": ["best seo tool", "ai seo optimization", ...],
      "provider": "nova"  (optional, default: nova)
    }
    """
    from deepthi_intelligence.multi_brand_benchmark import MultiBrandBenchmark
    data = request.get_json() or {}
    primary = data.get('primary_brand', '').strip()
    if not primary:
        return jsonify({'error': 'primary_brand required'}), 400
    benchmarks = [b.strip() for b in data.get('benchmark_brands', []) if b.strip()]
    keywords = [k.strip() for k in data.get('keywords', []) if k.strip()]
    if not keywords:
        return jsonify({'error': 'keywords list required'}), 400
    provider = data.get('provider', 'nova')

    bench = MultiBrandBenchmark()
    result = bench.run_benchmark(primary, benchmarks, keywords, provider)
    return jsonify(result), 201


@deepthi_bp.route('/benchmark/snapshots', methods=['GET'])
def benchmark_snapshots():
    """List past benchmark snapshots."""
    from deepthi_intelligence.multi_brand_benchmark import MultiBrandBenchmark
    limit = int(request.args.get('limit', 20))
    return jsonify({'snapshots': MultiBrandBenchmark().list_snapshots(limit)})


@deepthi_bp.route('/benchmark/<benchmark_id>', methods=['GET'])
def benchmark_detail(benchmark_id):
    """Get a specific benchmark snapshot."""
    from deepthi_intelligence.multi_brand_benchmark import MultiBrandBenchmark
    snap = MultiBrandBenchmark().get_snapshot(benchmark_id)
    if not snap:
        return jsonify({'error': 'not found'}), 404
    return jsonify(snap)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BRAND GEO HISTORY & COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/brand-history/<brand>', methods=['GET'])
def brand_history(brand):
    """Get GEO score time-series for a brand."""
    from deepthi_intelligence.multi_brand_benchmark import BrandGEOHistory
    limit = int(request.args.get('limit', 30))
    return jsonify({'brand': brand, 'trend': BrandGEOHistory().get_trend(brand, limit)})


@deepthi_bp.route('/brand-compare', methods=['POST'])
def brand_compare():
    """
    Compare multiple brands side-by-side.
    Body: {"brands": ["AI1stSEO", "Ahrefs", "SEMrush"], "limit": 10}
    """
    from deepthi_intelligence.multi_brand_benchmark import BrandGEOHistory
    data = request.get_json() or {}
    brands = [b.strip() for b in data.get('brands', []) if b.strip()]
    if not brands:
        return jsonify({'error': 'brands list required'}), 400
    limit = data.get('limit', 10)
    return jsonify(BrandGEOHistory().compare_brands(brands, limit))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. KEYWORD-BRAND MATRIX
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/keyword-matrix/<keyword>', methods=['GET'])
def keyword_matrix(keyword):
    """Get multi-brand comparison for a specific keyword."""
    from deepthi_intelligence.multi_brand_benchmark import KeywordBrandMatrix
    limit = int(request.args.get('limit', 10))
    return jsonify({'keyword': keyword,
                    'entries': KeywordBrandMatrix().get_keyword_brands(keyword, limit)})


@deepthi_bp.route('/keyword-matrix', methods=['GET'])
def keyword_matrix_full():
    """Get full keyword-brand matrix for a benchmark."""
    from deepthi_intelligence.multi_brand_benchmark import KeywordBrandMatrix
    benchmark_id = request.args.get('benchmark_id')
    limit = int(request.args.get('limit', 200))
    return jsonify({'matrix': KeywordBrandMatrix().get_latest_matrix(benchmark_id, limit)})


# ═══════════════════════════════════════════════════════════════════════════════
# 4. FRESHNESS TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/freshness/check', methods=['POST'])
def freshness_check():
    """
    Check freshness of a page.
    Body: {"url": "https://example.com/page", "brand": "AI1stSEO" (optional)}
    """
    from deepthi_intelligence.freshness_tracker import FreshnessTracker
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'url required'}), 400
    brand = data.get('brand', '').strip() or None
    result = FreshnessTracker().check_page_freshness(url, brand)
    return jsonify(result)


@deepthi_bp.route('/freshness/history', methods=['GET'])
def freshness_history():
    """Get freshness check history for a URL."""
    from deepthi_intelligence.freshness_tracker import FreshnessTracker
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'error': 'url query param required'}), 400
    limit = int(request.args.get('limit', 30))
    return jsonify({'url': url, 'history': FreshnessTracker().get_history(url, limit)})


@deepthi_bp.route('/freshness/stale', methods=['GET'])
def freshness_stale():
    """Find stale content below freshness threshold."""
    from deepthi_intelligence.freshness_tracker import FreshnessTracker
    threshold = int(request.args.get('threshold', 40))
    limit = int(request.args.get('limit', 50))
    return jsonify({'stale': FreshnessTracker().get_stale_content(threshold, limit)})


@deepthi_bp.route('/freshness/correlation', methods=['GET'])
def freshness_correlation():
    """Analyze freshness-to-GEO-score correlation for a URL."""
    from deepthi_intelligence.freshness_tracker import FreshnessTracker
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'error': 'url query param required'}), 400
    return jsonify(FreshnessTracker().get_freshness_geo_correlation(url))


@deepthi_bp.route('/freshness/record', methods=['POST'])
def freshness_record():
    """
    Manually record a freshness signal (for external/scheduled checks).
    Body: {"url": "...", "freshness_score": 75, "content_hash": "...", ...}
    """
    from deepthi_intelligence.freshness_tracker import FreshnessTracker
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'url required'}), 400
    ts = FreshnessTracker().record_check(url, data)
    return jsonify({'recorded_at': ts}), 201


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DATA HOOKS / AGGREGATION
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/intelligence/brand-summary/<brand>', methods=['GET'])
def brand_summary(brand):
    """Full intelligence summary for a brand — aggregates all data sources."""
    from deepthi_intelligence.data_hooks import aggregate_brand_metrics
    return jsonify(aggregate_brand_metrics(brand))


@deepthi_bp.route('/intelligence/compare', methods=['POST'])
def intelligence_compare():
    """
    Quick side-by-side brand comparison from stored data (no new probes).
    Body: {"brands": ["AI1stSEO", "Ahrefs", "SEMrush"]}
    """
    from deepthi_intelligence.data_hooks import compare_brands_summary
    data = request.get_json() or {}
    brands = [b.strip() for b in data.get('brands', []) if b.strip()]
    if not brands:
        return jsonify({'error': 'brands list required'}), 400
    return jsonify(compare_brands_summary(brands))


@deepthi_bp.route('/intelligence/providers', methods=['GET'])
def intelligence_providers():
    """List available AI providers."""
    from deepthi_intelligence.data_hooks import get_available_providers
    return jsonify({'providers': get_available_providers()})


# ═══════════════════════════════════════════════════════════════════════════════
# 6. FRESHNESS DIGEST — daily aggregated freshness signals
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/freshness/digest/<brand>', methods=['GET'])
def freshness_digest(brand):
    """Get daily freshness digest trend for a brand."""
    from deepthi_intelligence.freshness_integration import FreshnessDigest
    days = int(request.args.get('days', 30))
    return jsonify({'brand': brand, 'digest': FreshnessDigest().get_digest_trend(brand, days)})


@deepthi_bp.route('/freshness/digest/<brand>/compute', methods=['POST'])
def freshness_digest_compute(brand):
    """Compute and store today's freshness digest for a brand."""
    from deepthi_intelligence.freshness_integration import FreshnessDigest
    result = FreshnessDigest().compute_digest_from_freshness(brand)
    return jsonify(result), 201


# ═══════════════════════════════════════════════════════════════════════════════
# 7. AI-GENERATED DASHBOARD EXPLANATIONS (Amazon Bedrock / Nova)
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/explain-dashboard', methods=['GET'])
def explain_dashboard():
    """
    Generate plain-English explanations of current dashboard metrics
    using Amazon Bedrock (Nova Lite). Returns cached result if < 1 hour old.
    """
    import time
    import json as _json

    # Simple in-memory cache (1 hour TTL)
    now = time.time()
    cache = getattr(explain_dashboard, '_cache', None)
    if cache and (now - cache['ts']) < 3600:
        return jsonify(cache['data'])

    try:
        # Fetch current intelligence summary
        from deepthi_intelligence.intelligence_summary_api import _build_summary
        summary = _build_summary()

        # Build a concise data snapshot for the LLM
        brands = summary.get('multi_brand_scores', {}).get('brands', [])
        brand_lines = []
        for b in brands[:5]:
            score = round((b.get('geo_score', 0)) * 100)
            delta = b.get('change_vs_last_week', {}).get('delta', 0)
            brand_lines.append(f"{b['brand']}: {score}% GEO (Δ {delta:+.1%})")

        top_kw = summary.get('keyword_performance', {}).get('top_cited_keywords', [])[:3]
        kw_lines = [f"{k['keyword']}: {round(k['geo_score']*100)}%" for k in top_kw]

        gaps = summary.get('keyword_performance', {}).get('competitor_beating_us', [])[:3]
        gap_lines = [f"{g['keyword']}: {g['competitor']} leads by {round(g['gap']*100)}%" for g in gaps]

        prompt = (
            "You are an SEO analytics assistant. Given these dashboard metrics, "
            "write 1-2 sentence plain-English insights for a non-technical business user. "
            "Be specific about what the numbers mean and what action to take.\n\n"
            f"Brand Scores: {'; '.join(brand_lines)}\n"
            f"Top Keywords: {'; '.join(kw_lines)}\n"
            f"Competitor Gaps: {'; '.join(gap_lines) if gap_lines else 'None'}\n\n"
            "Return JSON with keys: brand_scores, geo_tracker, keyword_performance, "
            "competitor_matrix, citations. Each value is a 1-2 sentence insight."
        )

        from ai_provider import ask_ai
        raw = ask_ai(prompt, provider='nova')
        # Try to parse JSON from the response
        try:
            # Find JSON in the response
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                explanations = _json.loads(raw[start:end])
            else:
                explanations = {'brand_scores': raw[:200]}
        except Exception:
            explanations = {'brand_scores': raw[:200]}

        result = {'explanations': explanations, 'generated_at': now}
        explain_dashboard._cache = {'ts': now, 'data': result}
        return jsonify(result)

    except Exception as e:
        return jsonify({'explanations': {}, 'error': str(e)}), 200


# ═══════════════════════════════════════════════════════════════════════════════
# 8. DATABASE STATS — row counts for admin dashboard
# ═══════════════════════════════════════════════════════════════════════════════

@deepthi_bp.route('/db-stats', methods=['GET'])
def db_stats():
    """Return row counts for all major database tables."""
    try:
        from db import get_conn as get_main_conn
        tables_main = [
            'seo_scans', 'geo_probes', 'ai_visibility', 'content_briefs',
            'users', 'scan_errors', 'ai_usage_log', 'daily_metrics'
        ]
        counts = {}
        with get_main_conn() as conn:
            cur = conn.cursor()
            for t in tables_main:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {t}")  # noqa: S608
                    counts[t] = cur.fetchone()[0]
                except Exception:
                    counts[t] = None
                    conn.rollback()
    except Exception:
        counts = {}

    # Sports tables
    try:
        from directory.sports_db import get_conn as get_sports_conn
        sports_tables = [
            'sports', 'sports_matches', 'sports_teams',
            'sports_rankings', 'sports_news'
        ]
        with get_sports_conn() as conn:
            cur = conn.cursor()
            for t in sports_tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {t}")  # noqa: S608
                    counts[t] = cur.fetchone()[0]
                except Exception:
                    counts[t] = None
                    conn.rollback()
    except Exception:
        pass

    # Directory tables
    try:
        from directory.directory_db import get_conn as get_dir_conn
        dir_tables = ['directory_categories', 'directory_items']
        with get_dir_conn() as conn:
            cur = conn.cursor()
            for t in dir_tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {t}")  # noqa: S608
                    counts[t] = cur.fetchone()[0]
                except Exception:
                    counts[t] = None
                    conn.rollback()
    except Exception:
        pass

    total = sum(v for v in counts.values() if v is not None)
    return jsonify({'counts': counts, 'total_rows': total})
