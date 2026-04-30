"""
growth/dm_engine.py
DM Engine — automated engagement messaging.

Generates and queues direct messages for:
    - New followers (welcome DM with resource link)
    - Engaged users (follow-up with relevant content)
    - Lead nurturing (drive to email signup)

Messages are stored in DynamoDB as a queue. Actual sending
requires platform API keys (Postiz/Buffer). Without keys,
messages are queued for manual review or future automation.

Feeds into: email_subscriber (via CTA links)
Tracks: analytics events for DM lifecycle
"""

import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)

DM_TABLE = os.environ.get("GROWTH_DM_TABLE", "ai1stseo-dm-queue")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(DM_TABLE)
    return _table


def init_dm_table() -> None:
    """Create the DM queue table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(DM_TABLE)
        table.load()
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        dynamodb.create_table(
            TableName=DM_TABLE,
            KeySchema=[{"AttributeName": "dm_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "dm_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("DM table %s created", DM_TABLE)
    except Exception as e:
        logger.warning("DM table init: %s", e)


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

WELCOME_TEMPLATE = (
    "Hey {name}! Thanks for the follow. 🙌\n\n"
    "We help brands get discovered by AI search engines (ChatGPT, Perplexity, Gemini).\n\n"
    "Want to check your AI visibility? It's free:\n"
    "→ https://ai1stseo.com?utm_source={platform}&utm_medium=dm&utm_campaign=welcome_dm\n\n"
    "Plus grab our free SEO Starter Kit:\n"
    "→ https://ai1stseo.com/api/growth/lead-magnet/download"
)

ENGAGEMENT_TEMPLATE = (
    "Hey {name}! Noticed you're interested in {topic}. 👀\n\n"
    "We just published something you might find useful — "
    "it covers how AI engines decide which brands to cite.\n\n"
    "Check it out: https://ai1stseo.com?utm_source={platform}&utm_medium=dm&utm_campaign=engagement_dm\n\n"
    "Also, join our email list for weekly AI SEO insights:\n"
    "→ https://ai1stseo.com#subscribe"
)

NURTURE_TEMPLATE = (
    "Quick question, {name} — are you tracking how AI search engines "
    "see your brand?\n\n"
    "Most brands rank on Google but are invisible to ChatGPT and Perplexity.\n\n"
    "Run a free AI visibility check in 30 seconds:\n"
    "→ https://ai1stseo.com?utm_source={platform}&utm_medium=dm&utm_campaign=nurture_dm"
)


def _queue_dm(
    recipient: str,
    platform: str,
    message: str,
    dm_type: str,
    metadata: dict = None,
) -> dict:
    """Queue a DM for sending."""
    dm_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "dm_id": dm_id,
        "recipient": recipient,
        "platform": platform,
        "message": message,
        "dm_type": dm_type,
        "status": "queued",
        "created_at": now,
    }
    if metadata:
        item["metadata"] = metadata

    try:
        _get_table().put_item(Item=item)
        return {"success": True, "dm_id": dm_id}
    except Exception as e:
        logger.error("Failed to queue DM: %s", e)
        return {"success": False, "error": str(e)}


def send_welcome_dm(user: str, platform: str = "x") -> dict:
    """Queue a welcome DM for a new follower."""
    name = user.split("@")[0] if "@" in user else user
    message = WELCOME_TEMPLATE.format(name=name, platform=platform)
    return _queue_dm(user, platform, message, "welcome")


def send_engagement_dm(user: str, topic: str, platform: str = "x") -> dict:
    """Queue an engagement DM for an active user."""
    name = user.split("@")[0] if "@" in user else user
    message = ENGAGEMENT_TEMPLATE.format(name=name, topic=topic, platform=platform)
    return _queue_dm(user, platform, message, "engagement", {"topic": topic})


def send_nurture_dm(user: str, platform: str = "x") -> dict:
    """Queue a nurture DM to drive conversions."""
    name = user.split("@")[0] if "@" in user else user
    message = NURTURE_TEMPLATE.format(name=name, platform=platform)
    return _queue_dm(user, platform, message, "nurture")


def process_new_followers(followers: list, platform: str = "x") -> dict:
    """Process a batch of new followers — queue welcome DMs."""
    queued = 0
    for user in followers:
        result = send_welcome_dm(user, platform)
        if result.get("success"):
            queued += 1
    return {"success": True, "queued": queued, "total": len(followers)}


def process_engaged_users(users: list, platform: str = "x") -> dict:
    """Process engaged users — queue engagement DMs."""
    queued = 0
    for entry in users:
        user = entry if isinstance(entry, str) else entry.get("user", "")
        topic = entry.get("topic", "AI SEO") if isinstance(entry, dict) else "AI SEO"
        result = send_engagement_dm(user, topic, platform)
        if result.get("success"):
            queued += 1
    return {"success": True, "queued": queued, "total": len(users)}


def get_queued_dms(status: str = "queued", limit: int = 50) -> dict:
    """Get DMs by status."""
    try:
        resp = _get_table().scan(Limit=min(limit, 200))
        items = resp.get("Items", [])
        if status:
            items = [i for i in items if i.get("status") == status]
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"success": True, "dms": items, "count": len(items)}
    except Exception as e:
        return {"success": False, "error": str(e), "dms": []}


def mark_dm_sent(dm_id: str) -> dict:
    """Mark a DM as sent."""
    try:
        _get_table().update_item(
            Key={"dm_id": dm_id},
            UpdateExpression="SET #s = :s, sent_at = :t",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "sent",
                ":t": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
