#!/usr/bin/env python3
"""DynamoDB repository for AEO reports — drop-in replacement for the reports
portion of database.SEODatabase.

Only covers the methods used by Month 1 / AEO core endpoints:
    save_report, get_reports, get_report_by_id, get_keyword_history,
    get_stats, get_trend_data, get_opportunity_keywords, clear_all_reports

Everything else (benchmarks, api_logs, scheduler) stays on SQLite.
"""

import boto3
import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from boto3.dynamodb.conditions import Key

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
TABLE_NAME = f'{TABLE_PREFIX}aeo-reports'


class _DecimalEncoder(json.JSONEncoder):
    """Handle Decimal values returned by DynamoDB."""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _to_decimal(val):
    """Convert float/int to Decimal for DynamoDB."""
    if val is None:
        return Decimal('0')
    return Decimal(str(val))


class AEORepository:
    """DynamoDB-backed repository matching the SEODatabase report interface."""

    def __init__(self):
        self._ddb = boto3.resource('dynamodb', region_name=REGION)
        self._table = self._ddb.Table(TABLE_NAME)

    # ---- writes ----

    def save_report(self, keyword: str, analysis_data: Dict) -> str:
        """Save an AEO analysis report. Returns report_id (string UUID)."""
        report_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + 'Z'

        aeo = analysis_data.get('aeo', {})
        if aeo:
            seo_score = aeo.get('aeo_score', {}).get('score', 0)
            ai_score = aeo.get('ai_visibility', {}).get('score', 0)
            difficulty = 0
        else:
            seo_analysis = analysis_data.get('seo_analysis', {})
            seo_score = seo_analysis.get('12_overall_seo_score', {}).get('score', 0)
            ai_score = seo_analysis.get('21_ai_visibility_score', {}).get('score', 0)
            difficulty = analysis_data.get('results', {}).get('seo_difficulty', {}).get('score', 0)

        citation_gap = analysis_data.get('seo_analysis', {}).get('25_citation_gap_analysis', {})
        gap_summary = citation_gap.get('summary', {})

        self._table.put_item(Item={
            'keyword': keyword,
            'created_at': now,
            'report_id': report_id,
            'seo_score': _to_decimal(seo_score),
            'ai_visibility_score': _to_decimal(ai_score),
            'difficulty_score': _to_decimal(difficulty),
            'citation_gap': _to_decimal(gap_summary.get('google_only_count', 0)),
            'google_results': _to_decimal(gap_summary.get('total_google_results', 0)),
            'ai_citations': _to_decimal(gap_summary.get('total_ai_citations', 0)),
            'overlap_count': _to_decimal(gap_summary.get('overlap_count', 0)),
            'full_data': json.dumps(analysis_data),
        })
        return report_id

    # ---- reads ----

    def get_reports(self, limit: int = 50, keyword: Optional[str] = None) -> List[Dict]:
        """List recent reports. With keyword filter uses query; without uses scan."""
        fields = 'report_id, keyword, seo_score, ai_visibility_score, difficulty_score, citation_gap, created_at'

        if keyword:
            resp = self._table.query(
                KeyConditionExpression=Key('keyword').eq(keyword),
                ProjectionExpression=fields,
                ScanIndexForward=False,
                Limit=limit,
            )
        else:
            resp = self._table.scan(
                ProjectionExpression=fields,
                Limit=limit,
            )

        items = resp.get('Items', [])
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return [self._format_report_summary(i) for i in items[:limit]]

    def get_report_by_id(self, report_id: str) -> Optional[Dict]:
        """Get full report by report_id using GSI."""
        resp = self._table.query(
            IndexName='report_id-index',
            KeyConditionExpression=Key('report_id').eq(str(report_id)),
            Limit=1,
        )
        items = resp.get('Items', [])
        if not items:
            return None
        item = items[0]
        report = self._format_report_summary(item)
        if item.get('full_data'):
            report['full_data'] = json.loads(item['full_data'])
        return report

    def get_keyword_history(self, keyword: str) -> List[Dict]:
        """Get historical data for a keyword, oldest first."""
        resp = self._table.query(
            KeyConditionExpression=Key('keyword').eq(keyword),
            ProjectionExpression='report_id, seo_score, ai_visibility_score, difficulty_score, citation_gap, created_at',
            ScanIndexForward=True,
        )
        return [self._format_report_summary(i) for i in resp.get('Items', [])]

    def get_stats(self) -> Dict:
        """Compute dashboard statistics via scan. Acceptable for moderate data volumes."""
        try:
            resp = self._table.scan(
                ProjectionExpression='keyword, seo_score, ai_visibility_score',
            )
            items = resp.get('Items', [])

            if not items:
                return self._empty_stats()

            total = len(items)
            keywords = set(i['keyword'] for i in items)
            seo_scores = [float(i.get('seo_score', 0)) for i in items]
            ai_scores = [float(i.get('ai_visibility_score', 0)) for i in items]
            gaps = [s - a for s, a in zip(seo_scores, ai_scores)]

            return {
                'total_reports': total,
                'unique_keywords': len(keywords),
                'avg_seo_score': round(sum(seo_scores) / total, 1),
                'avg_ai_score': round(sum(ai_scores) / total, 1),
                'openclaw_api_calls': 0,  # tracked in SQLite api_logs, not migrated
                'ai_citation_gap': round(sum(gaps) / total, 1),
            }
        except Exception:
            return self._empty_stats()

    def get_trend_data(self, limit: int = 10) -> List[Dict]:
        """Recent reports for trend charts."""
        resp = self._table.scan(
            ProjectionExpression='keyword, seo_score, ai_visibility_score, created_at',
            Limit=limit,
        )
        items = resp.get('Items', [])
        items.sort(key=lambda x: x.get('created_at', ''))
        return [
            {
                'keyword': i['keyword'],
                'seo_score': float(i.get('seo_score', 0)),
                'ai_visibility_score': float(i.get('ai_visibility_score', 0)),
                'created_at': i.get('created_at', ''),
            }
            for i in items[-limit:]
        ]

    def get_opportunity_keywords(self, limit: int = 5) -> List[Dict]:
        """Keywords with high SEO but low AI visibility."""
        try:
            resp = self._table.scan(
                ProjectionExpression='keyword, seo_score, ai_visibility_score',
            )
            items = resp.get('Items', [])
            opps = []
            for i in items:
                seo = float(i.get('seo_score', 0))
                ai = float(i.get('ai_visibility_score', 0))
                if seo > 60 and ai < 60:
                    opps.append({'keyword': i['keyword'], 'seo_score': seo,
                                 'ai_visibility_score': ai, 'gap': seo - ai})
            opps.sort(key=lambda x: x['gap'], reverse=True)
            return opps[:limit]
        except Exception:
            return []

    def clear_all_reports(self) -> bool:
        """Delete all items. Use with caution."""
        try:
            resp = self._table.scan(ProjectionExpression='keyword, created_at')
            with self._table.batch_writer() as batch:
                for item in resp.get('Items', []):
                    batch.delete_item(Key={
                        'keyword': item['keyword'],
                        'created_at': item['created_at'],
                    })
            return True
        except Exception:
            return False

    # ---- helpers ----

    @staticmethod
    def _format_report_summary(item: Dict) -> Dict:
        return {
            'id': item.get('report_id', ''),
            'keyword': item.get('keyword', ''),
            'seo_score': float(item.get('seo_score', 0)),
            'ai_visibility_score': float(item.get('ai_visibility_score', 0)),
            'difficulty_score': float(item.get('difficulty_score', 0)),
            'citation_gap': int(item.get('citation_gap', 0)),
            'created_at': item.get('created_at', ''),
        }

    @staticmethod
    def _empty_stats() -> Dict:
        return {
            'total_reports': 0,
            'unique_keywords': 0,
            'avg_seo_score': 0,
            'avg_ai_score': 0,
            'openclaw_api_calls': 0,
            'ai_citation_gap': 0,
        }
