#!/usr/bin/env python3
"""DynamoDB table definitions and provisioning for GEO Scanner + AEO Month 1.

Run this script once to create the tables:
    python -m dynamo.tables

Tables created:
    aeo-reports  — stores AEO analysis reports (migrated from SQLite reports table)
    geo-scans    — stores GEO readiness scans (new, GEO had no persistence before)

Existing SQLite tables (reports, benchmarks, api_logs, scheduled_jobs, etc.)
are NOT touched.
"""

import boto3
import os

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

AEO_REPORTS_TABLE = f'{TABLE_PREFIX}aeo-reports'
GEO_SCANS_TABLE = f'{TABLE_PREFIX}geo-scans'


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
    """Provision both tables. Safe to call if tables already exist."""
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


if __name__ == '__main__':
    create_all_tables()
