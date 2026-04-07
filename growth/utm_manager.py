"""
growth/utm_manager.py
UTM Link Generator & Campaign Tracker.

Generates UTM-tagged URLs for campaigns and stores campaign definitions
in DynamoDB. Pure logic + DynamoDB — no external API dependencies.

This module is part of the ai1stseo.com 5-month growth plan.
It does NOT modify any existing tables or shared logic.

Environment variables:
    GROWTH_UTM_TABLE  — DynamoDB table name (default: ai1stseo-utm-campaigns)
    AWS_REGION        — AWS region (default: us-east-1)
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("GROWTH_UTM_TABLE", "ai1stseo-utm-campaigns")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    return _table


def init_utm_table() -> None:
    """Create the DynamoDB UTM campaigns table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.load()
        logger.info("UTM table %s exists", TABLE_NAME)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating UTM table %s ...", TABLE_NAME)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "campaign_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "campaign_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("UTM table %s created", TABLE_NAME)
    except Exception as e:
        logger.warning("UTM table init: %s", e)


# ---------------------------------------------------------------------------
# UTM link generation (pure logic, no DB needed)
# ---------------------------------------------------------------------------

def generate_utm_url(
    base_url: str,
    source: str,
    medium: str,
    campaign: str,
    content: str = None,
    term: str = None,
) -> dict:
    """Generate a UTM-tagged URL.

    Args:
        base_url: The destination URL (e.g. https://ai1stseo.com)
        source: Traffic source (e.g. linkedin, twitter, email)
        medium: Marketing medium (e.g. social, cpc, newsletter)
        campaign: Campaign name (e.g. launch_2026, starter_kit)
        content: Ad/link variant (optional)
        term: Paid keyword (optional)

    Returns:
        dict with tagged_url and utm params.
    """
    if not base_url:
        return {"success": False, "error": "base_url is required"}
    if not source:
        return {"success": False, "error": "source is required"}
    if not medium:
        return {"success": False, "error": "medium is required"}
    if not campaign:
        return {"success": False, "error": "campaign is required"}

    # Parse and rebuild URL
    parsed = urlparse(base_url.strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + base_url.strip())

    # Build UTM params
    utm_params = {
        "utm_source": source.strip().lower(),
        "utm_medium": medium.strip().lower(),
        "utm_campaign": campaign.strip().lower(),
    }
    if content:
        utm_params["utm_content"] = content.strip().lower()
    if term:
        utm_params["utm_term"] = term.strip().lower()

    # Merge with existing query params
    existing = parse_qs(parsed.query)
    for k, v in utm_params.items():
        existing[k] = [v]

    new_query = urlencode({k: v[0] for k, v in existing.items()})
    tagged_url = urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_query, parsed.fragment,
    ))

    return {
        "success": True,
        "tagged_url": tagged_url,
        "base_url": base_url.strip(),
        "utm_params": utm_params,
    }


# ---------------------------------------------------------------------------
# Campaign CRUD (DynamoDB)
# ---------------------------------------------------------------------------

def save_campaign(
    name: str,
    source: str,
    medium: str,
    base_url: str = "https://ai1stseo.com",
    content: str = None,
    term: str = None,
    notes: str = None,
) -> dict:
    """Save a campaign definition to DynamoDB."""
    if not name:
        return {"success": False, "error": "campaign name is required"}

    campaign_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "campaign_id": campaign_id,
        "name": name.strip().lower(),
        "source": (source or "").strip().lower(),
        "medium": (medium or "").strip().lower(),
        "base_url": base_url.strip(),
        "created_at": now,
    }
    if content:
        item["content"] = content.strip().lower()
    if term:
        item["term"] = term.strip().lower()
    if notes:
        item["notes"] = notes.strip()

    # Generate the tagged URL
    result = generate_utm_url(
        base_url=base_url, source=item["source"],
        medium=item["medium"], campaign=item["name"],
        content=content, term=term,
    )
    if result.get("success"):
        item["tagged_url"] = result["tagged_url"]

    try:
        _get_table().put_item(Item=item)
        logger.info("save_campaign: id=%s name=%s", campaign_id, name)
        return {"success": True, "campaign": item}
    except Exception as e:
        logger.error("save_campaign error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


def list_campaigns(limit: int = 50) -> dict:
    """List all saved campaigns."""
    limit = max(1, min(limit, 200))
    try:
        resp = _get_table().scan(Limit=limit)
        items = resp.get("Items", [])
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"success": True, "campaigns": items, "count": len(items)}
    except Exception as e:
        logger.error("list_campaigns error: %s", e)
        return {"success": False, "error": f"Database error: {e}", "campaigns": []}


def get_campaign(campaign_id: str) -> dict:
    """Get a single campaign by ID."""
    try:
        resp = _get_table().get_item(Key={"campaign_id": campaign_id})
        item = resp.get("Item")
        if not item:
            return {"success": False, "error": "Campaign not found"}
        return {"success": True, "campaign": item}
    except Exception as e:
        logger.error("get_campaign error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}
