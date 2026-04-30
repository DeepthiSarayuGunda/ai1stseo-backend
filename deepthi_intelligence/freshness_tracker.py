#!/usr/bin/env python3
"""
freshness_tracker.py
Freshness / Time-Stamped Update Service for AI Visibility.

Provides an isolated integration path for:
  - Daily content freshness signals (page last-modified, schema dateModified, etc.)
  - Q&A refresh signals (FAQ page staleness, answer currency)
  - Continuous daily content monitoring for AI visibility freshness

Stores all data in deepthi-freshness-signals table — no writes to existing tables.
Reads from existing aeo_optimizer (page analysis) are read-only.
"""

import json
import logging
import os
import uuid
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
FRESHNESS_TABLE = f'{PREFIX}deepthi-freshness-signals'

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


def _content_id(url: str) -> str:
    """Deterministic content ID from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class FreshnessTracker:
    """
    Track content freshness signals for AI visibility.

    Each check captures:
      - Page last-modified / dateModified from schema markup
      - FAQ/Q&A staleness (days since last update)
      - Content hash (detect actual content changes)
      - Freshness score (0-100): how current the content is for AI engines
      - AI visibility correlation: did freshness change affect GEO score?
    """

    def __init__(self):
        self._table = _get_ddb().Table(FRESHNESS_TABLE)

    # ── record a freshness check ──────────────────────────────────────────

    def record_check(self, url: str, data: Dict) -> str:
        """
        Record a freshness check for a URL.

        data fields:
          - last_modified: ISO date string from HTTP header or schema
          - content_hash: hash of main content body
          - has_faq: bool
          - faq_count: int
          - schema_date_modified: ISO date from JSON-LD dateModified
          - freshness_score: 0-100 computed score
          - geo_score_at_check: current GEO score (for correlation)
          - notes: free text
        """
        content_id = _content_id(url)
        check_ts = _now()

        # Compute freshness score if not provided
        freshness_score = data.get('freshness_score')
        if freshness_score is None:
            freshness_score = self._compute_freshness_score(data)

        item = {
            'content_id': content_id,
            'check_ts': check_ts,
            'url': url,
            'last_modified': data.get('last_modified', ''),
            'content_hash': data.get('content_hash', ''),
            'has_faq': data.get('has_faq', False),
            'faq_count': data.get('faq_count', 0),
            'schema_date_modified': data.get('schema_date_modified', ''),
            'freshness_score': _dec(freshness_score),
            'geo_score_at_check': _dec(data.get('geo_score_at_check', 0)),
            'content_changed': data.get('content_changed', False),
            'notes': data.get('notes', ''),
        }
        self._table.put_item(Item=item)
        logger.info("Freshness check recorded: url=%s score=%s", url, freshness_score)
        return check_ts

    # ── check a page for freshness signals ────────────────────────────────

    def check_page_freshness(self, url: str, brand: str = None) -> Dict:
        """
        Fetch a page and extract freshness signals.
        Optionally correlate with current GEO score for the brand.
        """
        import requests
        from bs4 import BeautifulSoup
        import hashlib as _hashlib

        result = {'url': url, 'checked_at': _now()}

        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; FreshnessBot/1.0)"}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')

            # HTTP Last-Modified
            result['last_modified'] = resp.headers.get('Last-Modified', '')

            # Content hash (main body text)
            body_text = soup.get_text(separator=' ', strip=True)[:5000]
            result['content_hash'] = _hashlib.md5(body_text.encode()).hexdigest()

            # Schema dateModified
            result['schema_date_modified'] = self._extract_schema_date(soup)

            # FAQ detection
            faq_items = self._detect_faq(soup)
            result['has_faq'] = len(faq_items) > 0
            result['faq_count'] = len(faq_items)

            # Check if content changed vs last check
            prev = self.get_latest(url)
            result['content_changed'] = (
                prev is not None and
                prev.get('content_hash', '') != result['content_hash']
            )

            # Compute freshness score
            result['freshness_score'] = self._compute_freshness_score(result)

            # Correlate with GEO score if brand provided
            if brand:
                result['geo_score_at_check'] = self._get_current_geo_score(brand)

            # Persist
            self.record_check(url, result)

        except Exception as e:
            logger.error("Freshness check failed for %s: %s", url, e)
            result['error'] = str(e)
            result['freshness_score'] = 0

        return result

    # ── read ──────────────────────────────────────────────────────────────

    def get_history(self, url: str, limit: int = 30) -> List[Dict]:
        """Get freshness check history for a URL."""
        content_id = _content_id(url)
        resp = self._table.query(
            KeyConditionExpression=Key('content_id').eq(content_id),
            ScanIndexForward=False, Limit=limit)
        return [_deserialize(i) for i in resp.get('Items', [])]

    def get_latest(self, url: str) -> Optional[Dict]:
        history = self.get_history(url, limit=1)
        return history[0] if history else None

    def get_stale_content(self, threshold_score: int = 40, limit: int = 50) -> List[Dict]:
        """Find content below freshness threshold — candidates for refresh."""
        resp = self._table.scan(
            FilterExpression=Attr('freshness_score').lt(_dec(threshold_score)),
            Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('freshness_score', 0))
        return items[:limit]

    def get_freshness_geo_correlation(self, url: str) -> Dict:
        """Analyze correlation between freshness changes and GEO score changes."""
        history = self.get_history(url, limit=20)
        if len(history) < 2:
            return {'url': url, 'data_points': len(history), 'correlation': 'insufficient_data'}

        changes = []
        for i in range(len(history) - 1):
            current = history[i]
            previous = history[i + 1]
            changes.append({
                'timestamp': current.get('check_ts', ''),
                'freshness_delta': (current.get('freshness_score', 0) -
                                    previous.get('freshness_score', 0)),
                'geo_delta': (current.get('geo_score_at_check', 0) -
                              previous.get('geo_score_at_check', 0)),
                'content_changed': current.get('content_changed', False),
            })

        return {
            'url': url,
            'data_points': len(changes),
            'changes': changes,
            'avg_freshness_delta': round(
                sum(c['freshness_delta'] for c in changes) / len(changes), 2
            ) if changes else 0,
            'avg_geo_delta': round(
                sum(c['geo_delta'] for c in changes) / len(changes), 4
            ) if changes else 0,
        }

    # ── internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_schema_date(soup) -> str:
        """Extract dateModified from JSON-LD structured data."""
        import json as _json
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = _json.loads(script.string or '')
                dm = data.get('dateModified', '')
                if dm:
                    return dm
            except Exception:
                pass
        return ''

    @staticmethod
    def _detect_faq(soup) -> list:
        """Detect FAQ items from schema markup or HTML patterns."""
        import json as _json
        faq_items = []
        # Check JSON-LD FAQPage
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = _json.loads(script.string or '')
                if data.get('@type') == 'FAQPage':
                    faq_items.extend(data.get('mainEntity', []))
            except Exception:
                pass
        # Check HTML FAQ patterns
        if not faq_items:
            for tag in soup.find_all(['details', 'summary']):
                faq_items.append(tag.get_text(strip=True)[:100])
        return faq_items

    @staticmethod
    def _compute_freshness_score(data: Dict) -> int:
        """
        Compute freshness score 0-100 based on available signals.
        Higher = fresher content.
        """
        score = 50  # baseline

        # Schema dateModified recency
        schema_date = data.get('schema_date_modified', '')
        if schema_date:
            try:
                mod_date = datetime.fromisoformat(schema_date.replace('Z', '+00:00'))
                days_old = (datetime.now(timezone.utc) - mod_date).days
                if days_old <= 7:
                    score += 30
                elif days_old <= 30:
                    score += 20
                elif days_old <= 90:
                    score += 10
                else:
                    score -= 10
            except Exception:
                pass

        # FAQ presence bonus
        if data.get('has_faq'):
            score += 10
            if data.get('faq_count', 0) >= 5:
                score += 5

        # Content changed recently
        if data.get('content_changed'):
            score += 10

        return max(0, min(100, score))

    @staticmethod
    def _get_current_geo_score(brand: str) -> float:
        """Read-only: get latest GEO score from existing month3 tracker."""
        try:
            from month3_systems.geo_brand_intelligence import GEOScoreTracker
            tracker = GEOScoreTracker()
            latest = tracker.get_latest(brand)
            return float(latest.get('geo_score', 0)) if latest else 0.0
        except Exception:
            return 0.0
