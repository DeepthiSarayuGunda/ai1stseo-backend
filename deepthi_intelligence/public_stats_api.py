#!/usr/bin/env python3
"""
public_stats_api.py
Public live statistics endpoint for the main page.

GET /api/public/live-stats — no auth required.

Returns:
  - total_brands_monitored
  - total_ai_probes_run
  - avg_geo_score
  - top_citing_engine
  - last_updated
"""

from flask import Blueprint, jsonify

public_stats_bp = Blueprint('public_stats', __name__, url_prefix='/api/public')


@public_stats_bp.route('/live-stats', methods=['GET'])
def live_stats():
    """
    Public endpoint — no auth required.
    Returns live platform statistics for the main page.
    """
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    stats = {
        'total_brands_monitored': 0,
        'total_ai_probes_run': 0,
        'avg_geo_score': 0,
        'top_citing_engine': {'name': 'unknown', 'citation_rate': 0},
        'last_updated': datetime.now(timezone.utc).isoformat(),
    }

    # 1. Total brands monitored — from geo-score-tracker
    try:
        from deepthi_intelligence.benchmark_brands import BenchmarkBrandRegistry
        brands = BenchmarkBrandRegistry().list_brands()
        stats['total_brands_monitored'] = len(brands)
    except Exception as e:
        logger.debug("Brand count fallback: %s", e)
        # Fallback: try reading from scheduler monitored brands
        try:
            from scheduler import get_monitored_brands
            stats['total_brands_monitored'] = len(get_monitored_brands())
        except Exception:
            pass

    # 2. Total AI probes run — from geo-probes table
    try:
        import os
        use_dynamo = not bool(os.environ.get("USE_RDS"))
        if use_dynamo:
            import boto3
            region = os.environ.get('AWS_REGION', 'us-east-1')
            client = boto3.client('dynamodb', region_name=region)
            prefix = os.environ.get('DYNAMO_TABLE_PREFIX', '')
            table_name = f'{prefix}ai1stseo-geo-probes'
            try:
                desc = client.describe_table(TableName=table_name)
                stats['total_ai_probes_run'] = desc['Table'].get('ItemCount', 0)
            except Exception:
                stats['total_ai_probes_run'] = 0
        else:
            from db import get_conn
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM geo_probes")
                row = cur.fetchone()
                stats['total_ai_probes_run'] = row[0] if row else 0
    except Exception as e:
        logger.debug("Probe count fallback: %s", e)

    # 3. Average GEO score across all brands — from geo-score-tracker
    try:
        from deepthi_intelligence.benchmark_brands import MultiBrandGeoScores
        scorer = MultiBrandGeoScores()
        comparison = scorer.get_latest_comparison()
        if comparison:
            scores = [b.get('geo_score', 0) for b in comparison if b.get('geo_score')]
            stats['avg_geo_score'] = round(sum(scores) / len(scores), 3) if scores else 0
    except Exception as e:
        logger.debug("Avg GEO score fallback: %s", e)

    # 4. Top citing AI engine — from probe history provider breakdown
    try:
        from collections import defaultdict
        from deepthi_intelligence.data_hooks import get_raw_probes
        probes = get_raw_probes(limit=500)
        if probes:
            prov_stats = defaultdict(lambda: {'cited': 0, 'total': 0})
            for p in probes:
                prov = p.get('ai_model', p.get('ai_platform', 'unknown'))
                prov_stats[prov]['total'] += 1
                if p.get('cited'):
                    prov_stats[prov]['cited'] += 1
            if prov_stats:
                best_prov = max(prov_stats.items(),
                                key=lambda x: x[1]['cited'] / max(x[1]['total'], 1))
                rate = round(best_prov[1]['cited'] / max(best_prov[1]['total'], 1), 3)
                stats['top_citing_engine'] = {
                    'name': best_prov[0],
                    'citation_rate': rate,
                    'total_probes': best_prov[1]['total'],
                    'cited_count': best_prov[1]['cited'],
                }
    except Exception as e:
        logger.debug("Top engine fallback: %s", e)

    return jsonify(stats)
