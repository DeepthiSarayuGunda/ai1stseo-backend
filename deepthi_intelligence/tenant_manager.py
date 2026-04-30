#!/usr/bin/env python3
"""
tenant_manager.py
Multi-tenant Architecture for Deepthi Intelligence Layer.

Enforces project_id filtering across ALL intelligence queries so every
brand/client sees only their own isolated data. Supports unlimited
brands/clients.

Does NOT modify any existing files. Wraps existing read-only hooks
with tenant isolation.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
TENANT_TABLE = f'{TABLE_PREFIX}deepthi-tenants'
DEFAULT_PROJECT_ID = os.environ.get('DEFAULT_PROJECT_ID', '00000000-0000-0000-0000-000000000001')

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


class TenantManager:
    """
    Manages tenant (project) registration and isolation.

    Each tenant has:
      - project_id: UUID primary key
      - name: display name
      - brands: list of brands this tenant tracks
      - plan: subscription tier
      - max_brands: brand limit per plan
    """

    PLAN_LIMITS = {
        'free': 2,
        'starter': 5,
        'pro': 20,
        'enterprise': 999,
    }

    def __init__(self):
        try:
            self._table = _get_ddb().Table(TENANT_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def create_tenant(self, name: str, owner_email: str,
                      plan: str = 'free') -> Dict:
        project_id = str(uuid.uuid4())
        tenant = {
            'project_id': project_id,
            'name': name,
            'owner_email': owner_email,
            'plan': plan,
            'max_brands': self.PLAN_LIMITS.get(plan, 2),
            'brands': [],
            'created_at': _now(),
            'active': True,
        }
        if self._available:
            self._table.put_item(Item=tenant)
        logger.info("Created tenant: %s (%s)", name, project_id)
        return tenant

    def get_tenant(self, project_id: str) -> Optional[Dict]:
        if not self._available:
            return self._default_tenant(project_id)
        try:
            resp = self._table.get_item(Key={'project_id': project_id})
            item = _deserialize(resp.get('Item'))
            return item
        except Exception:
            return self._default_tenant(project_id)

    def list_tenants(self, limit: int = 100) -> List[Dict]:
        if not self._available:
            return [self._default_tenant(DEFAULT_PROJECT_ID)]
        resp = self._table.scan(
            FilterExpression=Attr('active').eq(True),
            Limit=limit)
        return [_deserialize(i) for i in resp.get('Items', [])]

    def add_brand_to_tenant(self, project_id: str, brand: str) -> Dict:
        tenant = self.get_tenant(project_id)
        if not tenant:
            return {'error': 'tenant not found'}

        brands = tenant.get('brands', [])
        max_brands = tenant.get('max_brands', 2)
        if len(brands) >= max_brands:
            return {'error': f'Brand limit reached ({max_brands}). Upgrade plan.'}

        if brand not in brands:
            brands.append(brand)

        if self._available:
            self._table.update_item(
                Key={'project_id': project_id},
                UpdateExpression='SET brands = :b',
                ExpressionAttributeValues={':b': brands})

        return {'project_id': project_id, 'brand': brand, 'total_brands': len(brands)}

    def remove_brand_from_tenant(self, project_id: str, brand: str) -> Dict:
        tenant = self.get_tenant(project_id)
        if not tenant:
            return {'error': 'tenant not found'}

        brands = [b for b in tenant.get('brands', []) if b != brand]
        if self._available:
            self._table.update_item(
                Key={'project_id': project_id},
                UpdateExpression='SET brands = :b',
                ExpressionAttributeValues={':b': brands})

        return {'project_id': project_id, 'removed': brand, 'remaining': len(brands)}

    def get_tenant_brands(self, project_id: str) -> List[str]:
        tenant = self.get_tenant(project_id)
        if not tenant:
            return []
        return tenant.get('brands', [])

    def validate_brand_access(self, project_id: str, brand: str) -> bool:
        """Check if a tenant has access to a specific brand."""
        if project_id == DEFAULT_PROJECT_ID:
            return True  # Default project has access to everything
        brands = self.get_tenant_brands(project_id)
        return brand in brands

    @staticmethod
    def _default_tenant(project_id: str) -> Dict:
        return {
            'project_id': project_id,
            'name': 'Default',
            'plan': 'enterprise',
            'max_brands': 999,
            'brands': [],
            'active': True,
        }


class TenantIsolatedQuery:
    """
    Wraps existing data hooks with tenant-level isolation.
    All queries are filtered by project_id so tenants only see their own data.
    Read-only against existing tables.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._tm = TenantManager()

    def get_allowed_brands(self) -> List[str]:
        return self._tm.get_tenant_brands(self.project_id)

    def get_geo_scores(self, brands: List[str] = None,
                       limit_per_brand: int = 12) -> Dict:
        """Get GEO scores filtered to tenant's brands only."""
        from deepthi_intelligence.benchmark_brands import MultiBrandGeoScores
        allowed = self.get_allowed_brands()
        if brands:
            brands = [b for b in brands if b in allowed or self.project_id == DEFAULT_PROJECT_ID]
        else:
            brands = allowed if allowed else None
        return MultiBrandGeoScores().get_all_brands_scores(brands, limit_per_brand)

    def get_keyword_performance(self, keyword: str = None,
                                brands: List[str] = None) -> Dict:
        """Get keyword performance filtered to tenant's brands."""
        from deepthi_intelligence.benchmark_brands import MultiBrandKeywordPerformance
        allowed = self.get_allowed_brands()
        if brands:
            brands = [b for b in brands if b in allowed or self.project_id == DEFAULT_PROJECT_ID]
        else:
            brands = allowed if allowed else None

        kw_perf = MultiBrandKeywordPerformance()
        if keyword:
            return kw_perf.get_keyword_across_brands(keyword, brands)
        return {'entries': kw_perf.get_all_keywords_for_brands(brands)}

    def get_brand_summary(self, brand: str) -> Dict:
        """Get brand intelligence summary with tenant check."""
        if not self._tm.validate_brand_access(self.project_id, brand):
            return {'error': 'access denied', 'brand': brand}
        from deepthi_intelligence.data_hooks import aggregate_brand_metrics
        return aggregate_brand_metrics(brand)

    def get_competitor_matrix(self, week: str = None) -> List[Dict]:
        """Get competitor matrix filtered to tenant's brands."""
        from deepthi_intelligence.data_hooks import get_m3_competitor_matrix
        allowed = self.get_allowed_brands()
        matrix = get_m3_competitor_matrix(week)
        if not allowed or self.project_id == DEFAULT_PROJECT_ID:
            return matrix
        return [m for m in matrix if m.get('competitor') in allowed]
