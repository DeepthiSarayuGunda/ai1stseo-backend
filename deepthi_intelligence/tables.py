#!/usr/bin/env python3
"""
DynamoDB table provisioning for Deepthi Intelligence Layer.

Run: python -m deepthi_intelligence.tables

Creates 4 new tables — does NOT touch any existing Month 3 or core tables.
"""

import boto3
import os

REGION = os.environ.get('AWS_REGION', 'us-east-1')
PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

DEEPTHI_TABLES = {
    # Multi-brand benchmark snapshots (PK: benchmark_id)
    f'{PREFIX}deepthi-brand-benchmarks': {'pk': 'benchmark_id'},
    # Per-brand GEO score history with provider breakdown (PK: brand, SK: timestamp)
    f'{PREFIX}deepthi-brand-geo-history': {'pk': 'brand', 'sk': 'timestamp'},
    # Keyword-level multi-brand comparison (PK: keyword, SK: brand#timestamp)
    f'{PREFIX}deepthi-keyword-brand-matrix': {'pk': 'keyword', 'sk': 'brand_ts'},
    # Freshness / daily content refresh signals (PK: content_id, SK: check_ts)
    f'{PREFIX}deepthi-freshness-signals': {'pk': 'content_id', 'sk': 'check_ts'},
    # Benchmark brand registry (PK: brand)
    f'{PREFIX}deepthi-brand-registry': {'pk': 'brand'},
    # Daily freshness digest per brand (PK: brand, SK: date)
    f'{PREFIX}deepthi-freshness-digest': {'pk': 'brand', 'sk': 'date'},
    # Schedule execution log (PK: run_id)
    f'{PREFIX}deepthi-schedule-log': {'pk': 'run_id'},
    # Multi-tenant registry (PK: project_id)
    f'{PREFIX}deepthi-tenants': {'pk': 'project_id'},
    # Parallel probe jobs (PK: job_id)
    f'{PREFIX}deepthi-probe-jobs': {'pk': 'job_id'},
    # Industry benchmark snapshots (PK: category_id, SK: week)
    f'{PREFIX}deepthi-industry-benchmarks': {'pk': 'category_id', 'sk': 'week'},
    # Weekly benchmark reports (PK: report_id)
    f'{PREFIX}deepthi-weekly-reports': {'pk': 'report_id'},
    # Citation learning patterns (PK: format_type, SK: timestamp)
    f'{PREFIX}deepthi-citation-patterns': {'pk': 'format_type', 'sk': 'timestamp'},
    # AEO template recommendations (PK: rec_id)
    f'{PREFIX}deepthi-template-recommendations': {'pk': 'rec_id'},
    # Automated action register (PK: action_id)
    f'{PREFIX}deepthi-auto-actions': {'pk': 'action_id'},
}


def create_deepthi_tables():
    ddb = boto3.resource('dynamodb', region_name=REGION)
    client = boto3.client('dynamodb', region_name=REGION)
    existing = client.list_tables()['TableNames']

    created = 0
    for name, schema in DEEPTHI_TABLES.items():
        if name in existing:
            print(f'  ⏭️  {name} already exists')
            continue
        key_schema = [{'AttributeName': schema['pk'], 'KeyType': 'HASH'}]
        attr_defs = [{'AttributeName': schema['pk'], 'AttributeType': 'S'}]
        if 'sk' in schema:
            key_schema.append({'AttributeName': schema['sk'], 'KeyType': 'RANGE'})
            attr_defs.append({'AttributeName': schema['sk'], 'AttributeType': 'S'})
        ddb.create_table(
            TableName=name,
            KeySchema=key_schema,
            AttributeDefinitions=attr_defs,
            BillingMode='PAY_PER_REQUEST',
        )
        print(f'  ✅ Created {name}')
        created += 1

    print(f'\nDeepthi Intelligence: {created} tables created, '
          f'{len(DEEPTHI_TABLES) - created} already existed')
    return created


if __name__ == '__main__':
    create_deepthi_tables()
