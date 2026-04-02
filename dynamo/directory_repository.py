#!/usr/bin/env python3
"""DynamoDB repository for AI Business Directory listings.

Follows the same pattern as dynamo/aeo_repository.py — drop-in replacement
for directory/database.py when USE_DYNAMO_DIRECTORY=true.

Tables:
  - {prefix}directory-listings  (PK: category, SK: slug)
  - {prefix}directory-categories (PK: slug)

Only touches directory-* tables. Does NOT affect aeo-reports, geo-scans,
or any other existing DynamoDB tables.
"""

import boto3
import json
import os
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from boto3.dynamodb.conditions import Key, Attr

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
LISTINGS_TABLE = f'{TABLE_PREFIX}directory-listings'
CATEGORIES_TABLE = f'{TABLE_PREFIX}directory-categories'


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _to_decimal(val):
    if val is None:
        return Decimal('0')
    return Decimal(str(val))


def _slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


class DirectoryRepository:
    """DynamoDB-backed repository for business directory listings."""

    def __init__(self):
        self._ddb = boto3.resource('dynamodb', region_name=REGION)
        self._listings = self._ddb.Table(LISTINGS_TABLE)
        self._categories = self._ddb.Table(CATEGORIES_TABLE)

    # ---- Listing writes ----

    def add_listing(self, data: Dict) -> str:
        """Add or update a business listing. Returns slug."""
        slug = data.get('slug') or _slugify(data['name'])
        now = datetime.utcnow().isoformat() + 'Z'

        item = {
            'category': data['category'],
            'slug': slug,
            'name': data['name'],
            'subcategories': data.get('subcategories', []),
            'address': data.get('address', ''),
            'city': data.get('city', 'Ottawa'),
            'province': data.get('province', 'ON'),
            'postal_code': data.get('postal_code', ''),
            'phone': data.get('phone', ''),
            'website': data.get('website', ''),
            'latitude': _to_decimal(data.get('latitude', 0)),
            'longitude': _to_decimal(data.get('longitude', 0)),
            'rating': _to_decimal(data.get('rating', 0)),
            'review_count': data.get('review_count', 0),
            'price_range': data.get('price_range', ''),
            'hours_json': json.dumps(data.get('hours', {})),
            'ai_summary': data.get('ai_summary', ''),
            'faq_json': json.dumps(data.get('faq_json', [])) if isinstance(data.get('faq_json'), list) else data.get('faq_json', ''),
            'schema_markup': data.get('schema_markup', ''),
            'comparison_tags': json.dumps(data.get('comparison_tags', [])) if isinstance(data.get('comparison_tags'), list) else data.get('comparison_tags', ''),
            'freshness_score': data.get('freshness_score', 50),
            'ai_score': data.get('ai_score', 0),
            'citation_chatgpt': data.get('citation_chatgpt', 0),
            'citation_gemini': data.get('citation_gemini', 0),
            'citation_perplexity': data.get('citation_perplexity', 0),
            'citation_claude': data.get('citation_claude', 0),
            'source': data.get('source', 'manual'),
            'scraped_at': data.get('scraped_at', ''),
            'ai_generated_at': data.get('ai_generated_at', ''),
            'updated_at': now,
            'created_at': data.get('created_at', now),
        }

        self._listings.put_item(Item=item)
        return slug

    def update_ai_content(self, slug: str, category: str, ai_summary: str,
                          faq_json: str, schema_markup: str):
        """Update AI-generated content for a listing."""
        now = datetime.utcnow().isoformat() + 'Z'
        self._listings.update_item(
            Key={'category': category, 'slug': slug},
            UpdateExpression='SET ai_summary=:s, faq_json=:f, schema_markup=:m, ai_generated_at=:t, updated_at=:t',
            ExpressionAttributeValues={
                ':s': ai_summary, ':f': faq_json,
                ':m': schema_markup, ':t': now,
            }
        )

    def update_citations(self, slug: str, category: str, citations: Dict):
        """Update AI citation status for a listing."""
        now = datetime.utcnow().isoformat() + 'Z'
        ai_score = sum(1 for v in citations.values() if v) * 25
        self._listings.update_item(
            Key={'category': category, 'slug': slug},
            UpdateExpression='SET citation_chatgpt=:cg, citation_gemini=:ge, citation_perplexity=:pe, citation_claude=:cl, ai_score=:ai, updated_at=:t',
            ExpressionAttributeValues={
                ':cg': citations.get('chatgpt', 0),
                ':ge': citations.get('gemini', 0),
                ':pe': citations.get('perplexity', 0),
                ':cl': citations.get('claude', 0),
                ':ai': ai_score, ':t': now,
            }
        )

    def update_freshness(self, slug: str, category: str, score: int):
        now = datetime.utcnow().isoformat() + 'Z'
        self._listings.update_item(
            Key={'category': category, 'slug': slug},
            UpdateExpression='SET freshness_score=:s, updated_at=:t',
            ExpressionAttributeValues={':s': score, ':t': now}
        )

    # ---- Listing reads ----

    def get_listing(self, slug: str) -> Optional[Dict]:
        """Get a single listing by slug (scans across categories)."""
        resp = self._listings.query(
            IndexName='slug-index',
            KeyConditionExpression=Key('slug').eq(slug),
            Limit=1,
        )
        items = resp.get('Items', [])
        return self._format_listing(items[0]) if items else None

    def get_listings_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        """Get listings in a category, sorted by ai_score desc."""
        resp = self._listings.query(
            KeyConditionExpression=Key('category').eq(category),
            Limit=limit,
        )
        items = resp.get('Items', [])
        items.sort(key=lambda x: int(x.get('ai_score', 0)), reverse=True)
        return [self._format_listing(i) for i in items[:limit]]

    def search_listings(self, query: str, limit: int = 20) -> List[Dict]:
        """Search listings by name (scan with filter)."""
        resp = self._listings.scan(
            FilterExpression=Attr('name').contains(query),
            Limit=limit,
        )
        items = resp.get('Items', [])
        items.sort(key=lambda x: int(x.get('ai_score', 0)), reverse=True)
        return [self._format_listing(i) for i in items[:limit]]

    def get_all_listings(self, limit: int = 100) -> List[Dict]:
        """Get all listings across categories."""
        resp = self._listings.scan(Limit=limit)
        items = resp.get('Items', [])
        items.sort(key=lambda x: int(x.get('ai_score', 0)), reverse=True)
        return [self._format_listing(i) for i in items[:limit]]

    def get_listings_needing_ai(self, limit: int = 50) -> List[Dict]:
        """Get listings that don't have AI content yet (for batch job)."""
        resp = self._listings.scan(
            FilterExpression=Attr('ai_summary').eq('') | Attr('ai_summary').not_exists(),
            Limit=limit,
        )
        return [self._format_listing(i) for i in resp.get('Items', [])]

    # ---- Categories ----

    def add_category(self, name: str, slug: str, description: str = ''):
        self._categories.put_item(Item={
            'slug': slug, 'name': name, 'description': description,
            'created_at': datetime.utcnow().isoformat() + 'Z',
        })

    def get_categories(self) -> List[Dict]:
        resp = self._categories.scan()
        items = resp.get('Items', [])
        items.sort(key=lambda x: x.get('name', ''))
        return [dict(i) for i in items]

    # ---- Compare ----

    def compare_listings(self, slug_a: str, slug_b: str) -> Optional[Dict]:
        """Compare two listings side by side."""
        a = self.get_listing(slug_a)
        b = self.get_listing(slug_b)
        if not a or not b:
            return None
        score_a = (a.get('ai_score', 0) or 0) + (a.get('rating', 0) or 0) * 10
        score_b = (b.get('ai_score', 0) or 0) + (b.get('rating', 0) or 0) * 10
        return {
            'listing_a': a, 'listing_b': b,
            'winner': a['name'] if score_a >= score_b else b['name'],
            'score_a': score_a, 'score_b': score_b,
        }

    # ---- Helpers ----

    def _format_listing(self, item: Dict) -> Dict:
        """Normalize DynamoDB item to standard dict."""
        d = dict(item)
        # Convert Decimals to native types
        for k, v in d.items():
            if isinstance(v, Decimal):
                d[k] = float(v) if '.' in str(v) else int(v)
        # Parse JSON fields
        for key in ('faq_json', 'hours_json', 'subcategories', 'comparison_tags'):
            if d.get(key) and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
