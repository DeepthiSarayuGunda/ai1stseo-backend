#!/usr/bin/env python3
"""
multi_brand_benchmark.py
Multi-Brand / Benchmark Brand Support for GEO Score Tracker & Keyword Performance Register.

Provides:
  - MultiBrandBenchmark: run side-by-side GEO probes for N brands on the same keyword set,
    store structured comparison snapshots, and expose historical trend per brand.
  - BrandGEOHistory: per-brand time-series with provider-wise breakdown (extends
    the existing GEOScoreTracker concept without modifying it).
  - KeywordBrandMatrix: keyword-level multi-brand comparison register.

All data stored in Deepthi-specific DynamoDB tables — no writes to existing tables.
Reads from existing geo_probe_service (batch probe) and month3 tables are read-only.
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
PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

BENCHMARK_TABLE = f'{PREFIX}deepthi-brand-benchmarks'
BRAND_GEO_HIST_TABLE = f'{PREFIX}deepthi-brand-geo-history'
KW_BRAND_MATRIX_TABLE = f'{PREFIX}deepthi-keyword-brand-matrix'

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


# ═══════════════════════════════════════════════════════════════════════════════
# 1. MULTI-BRAND BENCHMARK — side-by-side GEO comparison snapshots
# ═══════════════════════════════════════════════════════════════════════════════

class MultiBrandBenchmark:
    """
    Run and store multi-brand GEO benchmark snapshots.

    Each snapshot probes N brands on the same keyword set and stores:
      - per-brand geo_score, visibility_score, confidence, cited_count
      - per-brand provider-wise results
      - keyword-level comparison matrix
      - gap analysis (who leads where)
    """

    def __init__(self):
        self._table = _get_ddb().Table(BENCHMARK_TABLE)

    # ── run benchmark ─────────────────────────────────────────────────────

    def run_benchmark(self, primary_brand: str, benchmark_brands: List[str],
                      keywords: List[str], provider: str = 'nova') -> Dict:
        """
        Execute a multi-brand benchmark. Calls existing geo_probe_batch for each brand.
        Returns structured comparison and persists snapshot.
        """
        from geo_probe_service import geo_probe_batch

        all_brands = [primary_brand] + [b for b in benchmark_brands if b != primary_brand]
        brand_results = {}

        for brand in all_brands:
            logger.info("Benchmarking brand=%s keywords=%d provider=%s",
                        brand, len(keywords), provider)
            try:
                batch = geo_probe_batch(brand, keywords, ai_model=provider)
                brand_results[brand] = {
                    'geo_score': batch.get('geo_score', 0),
                    'cited_count': batch.get('cited_count', 0),
                    'total_prompts': batch.get('total_prompts', 0),
                    'confidence_avg': self._avg_confidence(batch.get('results', [])),
                    'provider': provider,
                    'keyword_results': self._extract_keyword_results(batch.get('results', [])),
                }
            except Exception as e:
                logger.error("Benchmark failed for %s: %s", brand, e)
                brand_results[brand] = {
                    'geo_score': 0, 'cited_count': 0, 'total_prompts': 0,
                    'confidence_avg': 0, 'provider': provider,
                    'keyword_results': {}, 'error': str(e),
                }

        # Build comparison
        snapshot = self._build_snapshot(primary_brand, all_brands, brand_results, keywords, provider)

        # Persist
        self._save_snapshot(snapshot)

        # Also write per-brand history entries
        history = BrandGEOHistory()
        for brand, data in brand_results.items():
            history.record(brand, {
                'geo_score': data['geo_score'],
                'visibility_score': round(data['cited_count'] / max(data['total_prompts'], 1) * 100),
                'confidence': data['confidence_avg'],
                'provider': provider,
                'keywords_probed': len(keywords),
                'keywords_cited': data['cited_count'],
                'provider_scores': {provider: data['geo_score']},
                'benchmark_id': snapshot['benchmark_id'],
            })

        # Write keyword-brand matrix entries
        matrix = KeywordBrandMatrix()
        matrix.record_from_benchmark(all_brands, brand_results, snapshot['benchmark_id'])

        return snapshot

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _avg_confidence(results: list) -> float:
        confs = [r.get('confidence', 0) for r in results if r.get('confidence')]
        return round(sum(confs) / len(confs), 3) if confs else 0.0

    @staticmethod
    def _extract_keyword_results(results: list) -> Dict:
        out = {}
        for r in results:
            kw = r.get('keyword', '')
            if kw:
                out[kw] = {
                    'cited': r.get('brand_present', r.get('cited', False)),
                    'confidence': r.get('confidence', 0),
                    'context': r.get('citation_context', ''),
                }
        return out

    def _build_snapshot(self, primary: str, brands: list, results: Dict,
                        keywords: list, provider: str) -> Dict:
        benchmark_id = str(uuid.uuid4())[:12]
        ts = _now()

        # Gap analysis
        gaps = {'primary_leads': [], 'competitors_lead': [], 'unclaimed': []}
        primary_kw = results.get(primary, {}).get('keyword_results', {})
        for kw in keywords:
            p_cited = primary_kw.get(kw, {}).get('cited', False)
            any_comp_cited = any(
                results.get(b, {}).get('keyword_results', {}).get(kw, {}).get('cited', False)
                for b in brands if b != primary
            )
            if p_cited and not any_comp_cited:
                gaps['primary_leads'].append(kw)
            elif not p_cited and any_comp_cited:
                gaps['competitors_lead'].append(kw)
            elif not p_cited and not any_comp_cited:
                gaps['unclaimed'].append(kw)

        # Ranking
        ranking = sorted(
            [{'brand': b, 'geo_score': d['geo_score'], 'confidence_avg': d['confidence_avg']}
             for b, d in results.items()],
            key=lambda x: x['geo_score'], reverse=True
        )

        return {
            'benchmark_id': benchmark_id,
            'timestamp': ts,
            'primary_brand': primary,
            'brands': brands,
            'provider': provider,
            'total_keywords': len(keywords),
            'brand_scores': {b: {
                'geo_score': d['geo_score'],
                'cited_count': d['cited_count'],
                'total_prompts': d['total_prompts'],
                'confidence_avg': d['confidence_avg'],
            } for b, d in results.items()},
            'ranking': ranking,
            'gap_analysis': gaps,
        }

    def _save_snapshot(self, snapshot: Dict):
        item = {
            'benchmark_id': snapshot['benchmark_id'],
            'timestamp': snapshot['timestamp'],
            'primary_brand': snapshot['primary_brand'],
            'brands': json.dumps(snapshot['brands']),
            'provider': snapshot['provider'],
            'total_keywords': snapshot['total_keywords'],
            'brand_scores': json.dumps(snapshot['brand_scores']),
            'ranking': json.dumps(snapshot['ranking']),
            'gap_analysis': json.dumps(snapshot['gap_analysis']),
        }
        self._table.put_item(Item=item)
        logger.info("Saved benchmark snapshot: %s", snapshot['benchmark_id'])

    # ── read ──────────────────────────────────────────────────────────────

    def get_snapshot(self, benchmark_id: str) -> Optional[Dict]:
        resp = self._table.get_item(Key={'benchmark_id': benchmark_id})
        item = _deserialize(resp.get('Item'))
        if item:
            for f in ('brands', 'brand_scores', 'ranking', 'gap_analysis'):
                if isinstance(item.get(f), str):
                    try:
                        item[f] = json.loads(item[f])
                    except Exception:
                        pass
        return item

    def list_snapshots(self, limit: int = 20) -> List[Dict]:
        resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for item in items:
            for f in ('brands', 'brand_scores', 'ranking', 'gap_analysis'):
                if isinstance(item.get(f), str):
                    try:
                        item[f] = json.loads(item[f])
                    except Exception:
                        pass
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return items[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BRAND GEO HISTORY — per-brand time-series with provider breakdown
# ═══════════════════════════════════════════════════════════════════════════════

class BrandGEOHistory:
    """
    Per-brand GEO score time-series with provider-wise breakdown.
    Extends the concept of GEOScoreTracker (month3) but stores in a separate
    Deepthi-specific table with richer fields (confidence, benchmark_id link).
    """

    def __init__(self):
        self._table = _get_ddb().Table(BRAND_GEO_HIST_TABLE)

    def record(self, brand: str, data: Dict) -> str:
        ts = _now()
        item = {
            'brand': brand,
            'timestamp': ts,
            'geo_score': _dec(data.get('geo_score', 0)),
            'visibility_score': _dec(data.get('visibility_score', 0)),
            'confidence': _dec(data.get('confidence', 0)),
            'provider': data.get('provider', 'nova'),
            'keywords_probed': data.get('keywords_probed', 0),
            'keywords_cited': data.get('keywords_cited', 0),
            'provider_scores': json.dumps(data.get('provider_scores', {})),
            'benchmark_id': data.get('benchmark_id', ''),
        }
        self._table.put_item(Item=item)
        return ts

    def get_trend(self, brand: str, limit: int = 30) -> List[Dict]:
        resp = self._table.query(
            KeyConditionExpression=Key('brand').eq(brand),
            ScanIndexForward=False, Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('provider_scores'), str):
                try:
                    i['provider_scores'] = json.loads(i['provider_scores'])
                except Exception:
                    pass
        return items

    def get_latest(self, brand: str) -> Optional[Dict]:
        trend = self.get_trend(brand, limit=1)
        return trend[0] if trend else None

    def compare_brands(self, brands: List[str], limit: int = 10) -> Dict:
        """Get latest N entries for each brand for side-by-side comparison."""
        result = {}
        for brand in brands:
            result[brand] = self.get_trend(brand, limit=limit)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3. KEYWORD-BRAND MATRIX — keyword-level multi-brand comparison
# ═══════════════════════════════════════════════════════════════════════════════

class KeywordBrandMatrix:
    """
    Keyword-level multi-brand comparison register.
    For each keyword, stores which brands were cited, with confidence and context.
    """

    def __init__(self):
        self._table = _get_ddb().Table(KW_BRAND_MATRIX_TABLE)

    def record_from_benchmark(self, brands: List[str], brand_results: Dict,
                              benchmark_id: str):
        """Populate matrix from a benchmark run."""
        ts = _now()
        all_keywords = set()
        for b, data in brand_results.items():
            all_keywords.update(data.get('keyword_results', {}).keys())

        for kw in all_keywords:
            brand_data = {}
            for b in brands:
                kw_result = brand_results.get(b, {}).get('keyword_results', {}).get(kw, {})
                brand_data[b] = {
                    'cited': kw_result.get('cited', False),
                    'confidence': kw_result.get('confidence', 0),
                }

            item = {
                'keyword': kw,
                'brand_ts': f"{benchmark_id}#{ts}",
                'benchmark_id': benchmark_id,
                'timestamp': ts,
                'brands': json.dumps(brands),
                'brand_data': json.dumps(brand_data),
            }
            self._table.put_item(Item=item)

    def get_keyword_brands(self, keyword: str, limit: int = 10) -> List[Dict]:
        """Get multi-brand comparison history for a keyword."""
        resp = self._table.query(
            KeyConditionExpression=Key('keyword').eq(keyword),
            ScanIndexForward=False, Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            for f in ('brands', 'brand_data'):
                if isinstance(i.get(f), str):
                    try:
                        i[f] = json.loads(i[f])
                    except Exception:
                        pass
        return items

    def get_latest_matrix(self, benchmark_id: str = None, limit: int = 200) -> List[Dict]:
        """Get the full keyword-brand matrix for a benchmark (or latest)."""
        if benchmark_id:
            resp = self._table.scan(
                FilterExpression=Attr('benchmark_id').eq(benchmark_id),
                Limit=limit)
        else:
            resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            for f in ('brands', 'brand_data'):
                if isinstance(i.get(f), str):
                    try:
                        i[f] = json.loads(i[f])
                    except Exception:
                        pass
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return items[:limit]
