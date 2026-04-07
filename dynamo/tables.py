#!/usr/bin/env python3
"""DynamoDB table definitions and provisioning for GEO Scanner + AEO.

Run this script once to create the tables:
    python -m dynamo.tables

Tables created:
    aeo-reports           — stores AEO analysis reports
    geo-scans             — stores GEO readiness scans
    ai1stseo-geo-probes   — stores individual GEO probe results + visibility batches
    ai1stseo-content-briefs — stores content briefs

Existing SQLite tables (reports, benchmarks, api_logs, scheduled_jobs, etc.)
are NOT touched.
"""

import boto3
import os

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

AEO_REPORTS_TABLE = f'{TABLE_PREFIX}aeo-reports'
GEO_SCANS_TABLE = f'{TABLE_PREFIX}geo-scans'
GEO_PROBES_TABLE = 'ai1stseo-geo-probes'
CONTENT_BRIEFS_TABLE = 'ai1stseo-content-briefs'


def get_dynamodb_resource():
    return boto3.resource('dynamodb', region_name=REGION)


def get_dynamodb_client():
    return boto3.client('dynamodb', region_name=REGION)


def create_aeo_reports_table(ddb=None):
    """Create aeo-reports table.

    PK: keyword (S)
    SK: created_at (S)  — ISO-8601 timestamp, gives natural time ordering
    GSI: report_id-index on report_id (S) — for GET /api/report/<id>
    """
    ddb = ddb or get_dynamodb_resource()
    table = ddb.create_table(
        TableName=AEO_REPORTS_TABLE,
        KeySchema=[
            {'AttributeName': 'keyword', 'KeyType': 'HASH'},
            {'AttributeName': 'created_at', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'keyword', 'AttributeType': 'S'},
            {'AttributeName': 'created_at', 'AttributeType': 'S'},
            {'AttributeName': 'report_id', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'report_id-index',
                'KeySchema': [
                    {'AttributeName': 'report_id', 'KeyType': 'HASH'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'BillingMode': 'PAY_PER_REQUEST',
            }
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    table.wait_until_exists()
    print(f'✅ Created table: {AEO_REPORTS_TABLE}')
    return table


def create_geo_scans_table(ddb=None):
    """Create geo-scans table.

    PK: keyword (S)
    SK: created_at (S)
    """
    ddb = ddb or get_dynamodb_resource()
    table = ddb.create_table(
        TableName=GEO_SCANS_TABLE,
        KeySchema=[
            {'AttributeName': 'keyword', 'KeyType': 'HASH'},
            {'AttributeName': 'created_at', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'keyword', 'AttributeType': 'S'},
            {'AttributeName': 'created_at', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    table.wait_until_exists()
    print(f'✅ Created table: {GEO_SCANS_TABLE}')
    return table


def create_all_tables():
    """Provision all tables. Safe to call if tables already exist."""
    ddb = get_dynamodb_resource()
    client = get_dynamodb_client()
    existing = client.list_tables()['TableNames']

    if AEO_REPORTS_TABLE not in existing:
        create_aeo_reports_table(ddb)
    else:
        print(f'⏭️  Table already exists: {AEO_REPORTS_TABLE}')

    if GEO_SCANS_TABLE not in existing:
        create_geo_scans_table(ddb)
    else:
        print(f'⏭️  Table already exists: {GEO_SCANS_TABLE}')

    if GEO_PROBES_TABLE not in existing:
        create_geo_probes_table(ddb)
    else:
        print(f'⏭️  Table already exists: {GEO_PROBES_TABLE}')

    if CONTENT_BRIEFS_TABLE not in existing:
        create_content_briefs_table(ddb)
    else:
        print(f'⏭️  Table already exists: {CONTENT_BRIEFS_TABLE}')


def create_geo_probes_table(ddb=None):
    """Create ai1stseo-geo-probes table.

    PK: id (S)
    GSI: keyword-index on keyword (S) — for querying probes by keyword
    GSI: brand-index on brand_name (S), probe_timestamp (S) — for trend queries
    """
    ddb = ddb or get_dynamodb_resource()
    table = ddb.create_table(
        TableName=GEO_PROBES_TABLE,
        KeySchema=[
            {'AttributeName': 'id', 'KeyType': 'HASH'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'keyword', 'AttributeType': 'S'},
            {'AttributeName': 'brand_name', 'AttributeType': 'S'},
            {'AttributeName': 'probe_timestamp', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'keyword-index',
                'KeySchema': [
                    {'AttributeName': 'keyword', 'KeyType': 'HASH'},
                    {'AttributeName': 'probe_timestamp', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
            {
                'IndexName': 'brand-index',
                'KeySchema': [
                    {'AttributeName': 'brand_name', 'KeyType': 'HASH'},
                    {'AttributeName': 'probe_timestamp', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    table.wait_until_exists()
    print(f'✅ Created table: {GEO_PROBES_TABLE}')
    return table


def create_content_briefs_table(ddb=None):
    """Create ai1stseo-content-briefs table.

    PK: id (S)
    """
    ddb = ddb or get_dynamodb_resource()
    table = ddb.create_table(
        TableName=CONTENT_BRIEFS_TABLE,
        KeySchema=[
            {'AttributeName': 'id', 'KeyType': 'HASH'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    table.wait_until_exists()
    print(f'✅ Created table: {CONTENT_BRIEFS_TABLE}')
    return table


if __name__ == '__main__':
    create_all_tables()
