#!/usr/bin/env python3
"""DynamoDB table provisioning for Month 3 Intelligence Systems.

Run: python -m month3_systems.tables

Creates 14 tables across the 3 systems.
"""

import boto3
import os

REGION = os.environ.get('AWS_REGION', 'us-east-1')
PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

TABLES = {
    # 3.1 AEO Answer Intelligence
    f'{PREFIX}aeo-question-intelligence': {'pk': 'keyword'},
    f'{PREFIX}aeo-answer-templates': {'pk': 'format_type'},
    f'{PREFIX}aeo-content-calendar': {'pk': 'entry_id'},
    f'{PREFIX}aeo-citation-register': {'pk': 'page_id'},
    f'{PREFIX}aeo-learning-log': {'pk': 'entry_id'},
    # 3.2 GEO Brand Intelligence
    f'{PREFIX}geo-score-tracker': {'pk': 'brand', 'sk': 'week'},
    f'{PREFIX}geo-keyword-performance': {'pk': 'keyword', 'sk': 'week'},
    f'{PREFIX}geo-competitor-matrix': {'pk': 'competitor', 'sk': 'week'},
    f'{PREFIX}geo-action-register': {'pk': 'action_id'},
    f'{PREFIX}geo-provider-sensitivity': {'pk': 'provider'},
    # 3.3 SEO Foundation
    f'{PREFIX}seo-technical-debt': {'pk': 'issue_id'},
    f'{PREFIX}seo-eeat-pipeline': {'pk': 'gap_id'},
    f'{PREFIX}seo-content-queue': {'pk': 'page_id'},
    f'{PREFIX}seo-authority-map': {'pk': 'topic_id'},
}


def create_all_month3_tables():
    ddb = boto3.resource('dynamodb', region_name=REGION)
    client = boto3.client('dynamodb', region_name=REGION)
    existing = client.list_tables()['TableNames']

    created = 0
    for name, schema in TABLES.items():
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

    print(f'\nMonth 3: {created} tables created, {len(TABLES) - created} already existed')
    return created


if __name__ == '__main__':
    create_all_month3_tables()
