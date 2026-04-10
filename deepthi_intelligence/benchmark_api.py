#!/usr/bin/env python3
"""
benchmark_api.py
New API endpoints under /api/m3/benchmark/ for multi-brand benchmarking.

Deepthi-specific — isolated Blueprint, no modifications to existing M3 or Deepthi routes.

Endpoints:
  GET  /api/m3/benchmark/geo-scores          — scores for all brands over time
  GET  /api/m3/benchmark/keyword-performance  — keyword data across all brands
  POST /api/m3/benchmark/add-brand            — add a new benchmark brand
  POST /api/m3/benchmark/seed                 — seed demo data (dev/demo only)
  GET  /api/m3/benchmark/brands               — list registered benchmark brands
"""

from flask import Blueprint, request, jsonify

benchmark_bp = Blueprint('benchmark', __name__, url_prefix='/api/m3/benchmark')


@benchmark_bp.route('/geo-scores', methods=['GET'])
def benchmark_geo_scores():
    """
    Returns GEO scores for all benchmark brands over time.

    Query params:
      brands  — comma-separated brand names (optional, defaults to all registered)
      limit   — max weeks per brand (default 12)
      latest  — if "true", returns only the most recent score per brand
    """
    from deepthi_intelligence.benchmark_brands import (
        MultiBrandGeoScores, BenchmarkBrandRegistry,
    )

    brands_param = request.args.get('brands', '').strip()
    brands = [b.strip() for b in brands_param.split(',') if b.strip()] if brands_param else None
    limit = int(request.args.get('limit', 12))
    latest_only = request.args.get('latest', '').lower() == 'true'

    scorer = MultiBrandGeoScores()

    if latest_only:
        comparison = scorer.get_latest_comparison(brands)
        return jsonify({
            'type': 'latest_comparison',
            'brands': comparison,
            'count': len(comparison),
        })

    all_scores = scorer.get_all_brands_scores(brands, limit_per_brand=limit)
    return jsonify({
        'type': 'time_series',
        'brands': all_scores,
        'brand_count': len(all_scores),
        'limit_per_brand': limit,
    })


@benchmark_bp.route('/keyword-performance', methods=['GET'])
def benchmark_keyword_performance():
    """
    Returns keyword performance data across all benchmark brands.

    Query params:
      keyword — specific keyword to compare across brands (optional)
      brands  — comma-separated brand names (optional, defaults to all)
      week    — specific week string like "2025-W20" (optional, defaults to current)
      limit   — max entries (default 500)
    """
    from deepthi_intelligence.benchmark_brands import (
        MultiBrandKeywordPerformance, BenchmarkBrandRegistry,
    )

    brands_param = request.args.get('brands', '').strip()
    brands = [b.strip() for b in brands_param.split(',') if b.strip()] if brands_param else None
    keyword = request.args.get('keyword', '').strip()
    week = request.args.get('week', '').strip() or None
    limit = int(request.args.get('limit', 500))

    kw_perf = MultiBrandKeywordPerformance()

    if keyword:
        # Single keyword across all brands
        result = kw_perf.get_keyword_across_brands(keyword, brands, limit=limit)
        return jsonify({
            'type': 'keyword_comparison',
            'keyword': keyword,
            'brands': result,
        })

    # All keywords for all brands for a given week
    entries = kw_perf.get_all_keywords_for_brands(brands, week=week, limit=limit)
    return jsonify({
        'type': 'all_keywords',
        'week': week,
        'entries': entries,
        'count': len(entries),
    })


@benchmark_bp.route('/add-brand', methods=['POST'])
def benchmark_add_brand():
    """
    Add a new benchmark brand to track.

    Body: {"brand": "BrandName", "category": "benchmark"}
    """
    from deepthi_intelligence.benchmark_brands import BenchmarkBrandRegistry

    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    if not brand:
        return jsonify({'error': 'brand name required'}), 400

    category = data.get('category', 'benchmark').strip()
    entry = BenchmarkBrandRegistry().add_brand(brand, category)
    return jsonify({'status': 'added', 'brand': entry}), 201


@benchmark_bp.route('/brands', methods=['GET'])
def benchmark_list_brands():
    """List all registered benchmark brands."""
    from deepthi_intelligence.benchmark_brands import BenchmarkBrandRegistry
    brands = BenchmarkBrandRegistry().list_brands()
    return jsonify({'brands': brands, 'count': len(brands)})


@benchmark_bp.route('/seed', methods=['POST'])
def benchmark_seed_data():
    """
    Seed realistic demo data for all benchmark brands.
    Writes to geo-score-tracker and geo-keyword-performance tables.

    Body (optional): {"weeks_back": 8}
    """
    from deepthi_intelligence.benchmark_brands import seed_benchmark_data

    data = request.get_json() or {}
    weeks_back = int(data.get('weeks_back', 8))
    result = seed_benchmark_data(weeks_back=weeks_back)
    return jsonify(result), 201
