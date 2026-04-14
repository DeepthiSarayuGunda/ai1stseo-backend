#!/usr/bin/env python3
"""
citation_learning_engine.py
Self-Learning Citation Engine for Deepthi Intelligence Layer.

After every probe cycle, the system:
  1. Learns which content format got cited (FAQ, list, table, how-to, etc.)
  2. Tracks which keywords + format combos produce the best citation rates
  3. Automatically updates AEO answer template recommendations
  4. Compounds intelligence over time without manual input

Does NOT modify aeo_optimizer.py or any existing AEO logic.
Reads probe data via existing data_hooks (read-only).
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
CITATION_PATTERNS_TABLE = f'{TABLE_PREFIX}deepthi-citation-patterns'
TEMPLATE_RECS_TABLE = f'{TABLE_PREFIX}deepthi-template-recommendations'

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


# Content format patterns detected in citation contexts
FORMAT_PATTERNS = {
    'faq': [r'(?:FAQ|frequently asked|Q&A|question.*answer)', r'\?.*\n'],
    'list': [r'(?:top \d|best \d|\d+\.\s|\d+\))', r'(?:bullet|numbered list)'],
    'comparison': [r'(?:vs\.?|versus|compared? to|alternative)', r'(?:comparison table|side.by.side)'],
    'how_to': [r'(?:how to|step.by.step|guide|tutorial)', r'(?:instructions|walkthrough)'],
    'review': [r'(?:review|rating|pros and cons|verdict)', r'(?:our pick|editor.?s choice)'],
    'definition': [r'(?:what is|definition|meaning of|refers to)', r'(?:in simple terms|explained)'],
    'statistics': [r'(?:\d+%|\d+ percent|according to|study|research)', r'(?:data shows|survey)'],
    'table': [r'(?:table|comparison chart|feature matrix)', r'(?:pricing table|spec sheet)'],
}


class CitationLearningEngine:
    """
    Learns from probe results which content formats get cited most.
    Builds a knowledge base of keyword + format -> citation success rate.
    """

    def __init__(self):
        try:
            self._patterns_table = _get_ddb().Table(CITATION_PATTERNS_TABLE)
            self._patterns_table.load()
            self._recs_table = _get_ddb().Table(TEMPLATE_RECS_TABLE)
            self._recs_table.load()
            self._available = True
        except Exception:
            self._available = False

    def learn_from_recent_probes(self, limit: int = 200) -> Dict:
        """
        Analyze recent probe results to learn citation patterns.
        Returns summary of what was learned.
        """
        import re
        from deepthi_intelligence.data_hooks import get_raw_probes

        probes = get_raw_probes(limit=limit)
        if not probes:
            return {'status': 'no_data', 'probes_analyzed': 0}

        # Analyze each probe for format patterns
        format_stats = defaultdict(lambda: {'cited': 0, 'total': 0, 'keywords': set()})
        keyword_format_stats = defaultdict(lambda: defaultdict(lambda: {'cited': 0, 'total': 0}))

        for probe in probes:
            context = probe.get('citation_context', '') or probe.get('response_snippet', '')
            keyword = probe.get('keyword', '')
            cited = probe.get('cited', False)

            if not context or not keyword:
                continue

            # Detect which formats appear in the response
            detected_formats = self._detect_formats(context)

            for fmt in detected_formats:
                format_stats[fmt]['total'] += 1
                format_stats[fmt]['keywords'].add(keyword)
                keyword_format_stats[keyword][fmt]['total'] += 1
                if cited:
                    format_stats[fmt]['cited'] += 1
                    keyword_format_stats[keyword][fmt]['cited'] += 1

        # Compute citation rates per format
        format_rates = {}
        for fmt, stats in format_stats.items():
            rate = round(stats['cited'] / stats['total'], 3) if stats['total'] else 0
            format_rates[fmt] = {
                'citation_rate': rate,
                'total_seen': stats['total'],
                'cited_count': stats['cited'],
                'unique_keywords': len(stats['keywords']),
            }

        # Store learned patterns
        self._store_patterns(format_rates, keyword_format_stats)

        # Generate template recommendations
        recommendations = self._generate_recommendations(format_rates, keyword_format_stats)

        return {
            'status': 'complete',
            'probes_analyzed': len(probes),
            'formats_detected': len(format_rates),
            'format_rates': format_rates,
            'recommendations_generated': len(recommendations),
            'timestamp': _now(),
        }

    def _detect_formats(self, text: str) -> List[str]:
        """Detect content formats present in a text snippet."""
        import re
        detected = []
        text_lower = text.lower()
        for fmt, patterns in FORMAT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    detected.append(fmt)
                    break
        return detected if detected else ['unstructured']

    def _store_patterns(self, format_rates: Dict,
                        keyword_format_stats: Dict):
        """Persist learned citation patterns."""
        if not self._available:
            return
        timestamp = _now()
        for fmt, rates in format_rates.items():
            self._patterns_table.put_item(Item={
                'format_type': fmt,
                'timestamp': timestamp,
                'citation_rate': _dec(rates['citation_rate']),
                'total_seen': rates['total_seen'],
                'cited_count': rates['cited_count'],
                'unique_keywords': rates['unique_keywords'],
            })

    def _generate_recommendations(self, format_rates: Dict,
                                  keyword_format_stats: Dict) -> List[Dict]:
        """Generate AEO template recommendations based on learned patterns."""
        recommendations = []

        # Sort formats by citation rate
        ranked = sorted(format_rates.items(),
                        key=lambda x: x[1]['citation_rate'], reverse=True)

        for fmt, rates in ranked:
            if rates['total_seen'] < 3:
                continue  # Not enough data
            rec = {
                'format': fmt,
                'citation_rate': rates['citation_rate'],
                'confidence': 'high' if rates['total_seen'] >= 20 else
                              'medium' if rates['total_seen'] >= 10 else 'low',
                'recommendation': self._format_recommendation(fmt, rates),
            }
            recommendations.append(rec)

            # Store recommendation
            if self._available:
                self._recs_table.put_item(Item={
                    'rec_id': f'{fmt}-{_now()[:10]}',
                    'format_type': fmt,
                    'citation_rate': _dec(rates['citation_rate']),
                    'confidence': rec['confidence'],
                    'recommendation': rec['recommendation'],
                    'generated_at': _now(),
                })

        return recommendations

    @staticmethod
    def _format_recommendation(fmt: str, rates: Dict) -> str:
        rate_pct = round(rates['citation_rate'] * 100, 1)
        templates = {
            'faq': f'FAQ format achieves {rate_pct}% citation rate. Add FAQ schema with 5-10 questions.',
            'list': f'Numbered/bullet lists achieve {rate_pct}% citation rate. Structure content as ranked lists.',
            'comparison': f'Comparison content achieves {rate_pct}% citation rate. Add vs. tables and alternatives.',
            'how_to': f'How-to guides achieve {rate_pct}% citation rate. Add step-by-step HowTo schema.',
            'review': f'Review format achieves {rate_pct}% citation rate. Include pros/cons and ratings.',
            'definition': f'Definition format achieves {rate_pct}% citation rate. Lead with clear definitions.',
            'statistics': f'Data-backed content achieves {rate_pct}% citation rate. Cite studies and stats.',
            'table': f'Table format achieves {rate_pct}% citation rate. Add comparison/feature tables.',
            'unstructured': f'Unstructured content has {rate_pct}% citation rate. Consider adding structure.',
        }
        return templates.get(fmt, f'{fmt} format achieves {rate_pct}% citation rate.')

    def get_learned_patterns(self, limit: int = 50) -> List[Dict]:
        """Get all learned citation patterns."""
        if not self._available:
            return []
        resp = self._patterns_table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('citation_rate', 0), reverse=True)
        return items

    def get_recommendations(self, limit: int = 20) -> List[Dict]:
        """Get current template recommendations."""
        if not self._available:
            return []
        resp = self._recs_table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('citation_rate', 0), reverse=True)
        return items[:limit]

    def get_keyword_insights(self, keyword: str) -> Dict:
        """Get format insights for a specific keyword from learned data."""
        import re
        from deepthi_intelligence.data_hooks import get_raw_probes

        probes = get_raw_probes(limit=500)
        kw_probes = [p for p in probes if p.get('keyword', '').lower() == keyword.lower()]

        if not kw_probes:
            return {'keyword': keyword, 'status': 'no_data'}

        format_stats = defaultdict(lambda: {'cited': 0, 'total': 0})
        for probe in kw_probes:
            context = probe.get('citation_context', '') or probe.get('response_snippet', '')
            cited = probe.get('cited', False)
            formats = self._detect_formats(context)
            for fmt in formats:
                format_stats[fmt]['total'] += 1
                if cited:
                    format_stats[fmt]['cited'] += 1

        insights = {
            'keyword': keyword,
            'total_probes': len(kw_probes),
            'formats': {
                fmt: {
                    'citation_rate': round(s['cited'] / s['total'], 3) if s['total'] else 0,
                    'cited': s['cited'],
                    'total': s['total'],
                }
                for fmt, s in format_stats.items()
            },
            'best_format': max(format_stats.items(),
                               key=lambda x: x[1]['cited'] / max(x[1]['total'], 1))[0]
                          if format_stats else 'unknown',
        }
        return insights
