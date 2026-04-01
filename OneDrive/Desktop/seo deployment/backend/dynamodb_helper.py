"""
DynamoDB helper module — drop-in replacement for database.py (PostgreSQL).
Provides the same interface: query, query_one, execute, insert_returning.
Uses boto3 DynamoDB resource for all operations.
"""
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
import json

_dynamodb = None

def _get_table(table_name):
    """Get a DynamoDB table resource."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    return _dynamodb.Table(table_name)


def _serialize(item):
    """Convert Python types to DynamoDB-compatible types."""
    cleaned = {}
    for k, v in item.items():
        if v is None:
            continue  # DynamoDB doesn't store None
        if isinstance(v, float):
            cleaned[k] = Decimal(str(v))
        elif isinstance(v, (dict, list)):
            cleaned[k] = json.loads(json.dumps(v, default=str))
        elif isinstance(v, datetime):
            cleaned[k] = v.isoformat()
        else:
            cleaned[k] = v
    return cleaned


def _deserialize(item):
    """Convert DynamoDB types back to Python types."""
    if item is None:
        return None
    cleaned = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            cleaned[k] = int(v) if v == int(v) else float(v)
        else:
            cleaned[k] = v
    return cleaned


def put_item(table_name, item):
    """Insert an item into a DynamoDB table. Returns the item ID."""
    table = _get_table(table_name)
    if 'id' not in item:
        item['id'] = str(uuid.uuid4())
    if 'created_at' not in item:
        item['created_at'] = datetime.utcnow().isoformat()
    table.put_item(Item=_serialize(item))
    return item['id']


def get_item(table_name, key):
    """Get a single item by primary key."""
    table = _get_table(table_name)
    resp = table.get_item(Key=key)
    return _deserialize(resp.get('Item'))


def query_index(table_name, index_name, key_name, key_value, limit=50):
    """Query a GSI. Returns list of items."""
    from boto3.dynamodb.conditions import Key
    table = _get_table(table_name)
    resp = table.query(
        IndexName=index_name,
        KeyConditionExpression=Key(key_name).eq(key_value),
        Limit=limit,
    )
    return [_deserialize(i) for i in resp.get('Items', [])]


def scan_table(table_name, limit=50, filter_expression=None, expression_values=None):
    """Scan a table (use sparingly — prefer query_index). Returns list of items."""
    table = _get_table(table_name)
    params = {'Limit': limit}
    if filter_expression:
        params['FilterExpression'] = filter_expression
    if expression_values:
        params['ExpressionAttributeValues'] = expression_values
    resp = table.scan(**params)
    return [_deserialize(i) for i in resp.get('Items', [])]


def update_item(table_name, key, updates):
    """Update specific attributes on an item."""
    table = _get_table(table_name)
    expr_parts = []
    expr_names = {}
    expr_values = {}
    for i, (k, v) in enumerate(updates.items()):
        placeholder = f":v{i}"
        name_placeholder = f"#n{i}"
        expr_parts.append(f"{name_placeholder} = {placeholder}")
        expr_names[name_placeholder] = k
        expr_values[placeholder] = v if not isinstance(v, float) else Decimal(str(v))
    table.update_item(
        Key=key,
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def delete_item(table_name, key):
    """Delete an item by primary key."""
    table = _get_table(table_name)
    table.delete_item(Key=key)


def count_items(table_name):
    """Get approximate item count (updated every ~6 hours by AWS)."""
    table = _get_table(table_name)
    return table.item_count


# === Compatibility layer (matches old database.py interface) ===

def get_conn():
    """No-op for DynamoDB compatibility."""
    return None

def query(sql, params=None):
    """Legacy compatibility — not used with DynamoDB. Raises error to catch stale code."""
    raise NotImplementedError("SQL queries not supported. Use dynamodb_helper functions instead.")

def query_one(sql, params=None):
    raise NotImplementedError("SQL queries not supported. Use dynamodb_helper functions instead.")

def execute(sql, params=None):
    raise NotImplementedError("SQL queries not supported. Use dynamodb_helper functions instead.")

def insert_returning(sql, params=None):
    raise NotImplementedError("SQL queries not supported. Use dynamodb_helper functions instead.")
