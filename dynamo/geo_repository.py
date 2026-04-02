#!/usr/bin/env python3
"""DynamoDB repository for GEO Scanner scans.

GEO currently has no persistence (results are computed and returned).
This adds optional persistence so scan history can be tracked over time.
"""

import boto3
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from boto3.dynamodb.conditions import Key

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
TABLE_NAME = f'{TABLE_PREFIX}geo-scans'


def _to_decimal(val):
    if val is None:
        return Decimal('0')
    return Decimal(str(val))


class GEORepository:
    """DynamoDB-backed persistence for GEO readiness scans."""

    def __init__(self):
        self._ddb = boto3.resource('dynamodb', region_name=REGION)
        self._table = self._ddb.Table(TABLE_NAME)

    def save_scan(self, keyword: str, result: Dict) -> str:
        """Persist a GEO scan result. Returns created_at timestamp as ID."""
        now = datetime.utcnow().isoformat() + 'Z'

        self._table.put_item(Item={
            'keyword': keyword,
            'created_at': now,
            'geo_score': _to_decimal(result.get('geo_score', 0)),
            'grade': result.get('grade', ''),
            'metrics': json.dumps(result.get('metrics', {})),
            'suggestions': json.dumps(result.get('suggestions', [])),
            'missing': json.dumps(result.get('missing', [])),
            'verdict': result.get('verdict', ''),
        })
        return now

    def get_scans(self, keyword: str, limit: int = 20) -> List[Dict]:
        """Get scan history for a keyword, newest first."""
        resp = self._table.query(
            KeyConditionExpression=Key('keyword').eq(keyword),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [self._format(i) for i in resp.get('Items', [])]

    def get_latest_scan(self, keyword: str) -> Optional[Dict]:
        """Get the most recent scan for a keyword."""
        scans = self.get_scans(keyword, limit=1)
        return scans[0] if scans else None

    @staticmethod
    def _format(item: Dict) -> Dict:
        return {
            'keyword': item.get('keyword', ''),
            'created_at': item.get('created_at', ''),
            'geo_score': float(item.get('geo_score', 0)),
            'grade': item.get('grade', ''),
            'metrics': json.loads(item.get('metrics', '{}')),
            'suggestions': json.loads(item.get('suggestions', '[]')),
            'missing': json.loads(item.get('missing', '[]')),
            'verdict': item.get('verdict', ''),
        }
