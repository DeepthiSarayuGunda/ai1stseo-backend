"""
growth/referral_engine.py
Referral Engine — viral email list growth.

Generates unique referral links per subscriber, tracks conversions,
and rewards users who hit referral thresholds.

DynamoDB table: ai1stseo-referrals
Integrates with: email_subscriber, analytics_tracker

Reward tiers:
    3 referrals  → SEO Starter Kit (lead magnet)
    10 referrals → Priority AI visibility report
    25 referrals → Featured in newsletter
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)

REF_TABLE = os.environ.get("GROWTH_REFERRAL_TABLE", "ai1stseo-referrals")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

BASE_URL = "https://ai1stseo.com"

REWARD_TIERS = [
    {"threshold": 3, "reward": "seo_starter_kit", "label": "SEO Starter Kit download"},
    {"threshold": 10, "reward": "priority_report", "label": "Priority AI visibility report"},
    {"threshold": 25, "reward": "newsletter_feature", "label": "Featured in newsletter"},
]

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(REF_TABLE)
    return _table


def init_referral_table() -> None:
    """Create the referrals table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(REF_TABLE)
        table.load()
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        dynamodb.create_table(
            TableName=REF_TABLE,
            KeySchema=[{"AttributeName": "referrer_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "referrer_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("Referral table %s created", REF_TABLE)
    except Exception as e:
        logger.warning("Referral table init: %s", e)


def generate_referral_link(user_id: str) -> dict:
    """Generate a unique referral link for a subscriber.

    The referral code is a short hash of the user_id for consistency.
    """
    if not user_id:
        return {"success": False, "error": "user_id is required"}

    ref_code = hashlib.md5(user_id.encode()).hexdigest()[:8]
    ref_url = (
        f"{BASE_URL}?utm_source=referral&utm_medium=link"
        f"&utm_campaign=referral_program&ref={ref_code}"
    )

    now = datetime.now(timezone.utc).isoformat()

    # Upsert referrer record
    try:
        resp = _get_table().get_item(Key={"referrer_id": user_id})
        if not resp.get("Item"):
            _get_table().put_item(Item={
                "referrer_id": user_id,
                "ref_code": ref_code,
                "referral_count": 0,
                "referrals": [],
                "rewards_earned": [],
                "created_at": now,
            })
    except Exception as e:
        logger.warning("Referral upsert failed: %s", e)

    return {
        "success": True,
        "user_id": user_id,
        "ref_code": ref_code,
        "referral_url": ref_url,
    }


def track_referral(ref_code: str, new_user_email: str) -> dict:
    """Track a successful referral conversion.

    Called when a new subscriber signs up with a ref= parameter.
    """
    if not ref_code or not new_user_email:
        return {"success": False, "error": "ref_code and new_user_email required"}

    # Find referrer by ref_code
    try:
        resp = _get_table().scan()
        items = resp.get("Items", [])
        referrer = None
        for item in items:
            if item.get("ref_code") == ref_code:
                referrer = item
                break

        if not referrer:
            return {"success": False, "error": "Invalid referral code"}

        referrer_id = referrer["referrer_id"]
        current_referrals = referrer.get("referrals", [])

        # Prevent duplicate tracking
        if new_user_email in current_referrals:
            return {"success": True, "duplicate": True, "referrer_id": referrer_id}

        new_count = int(referrer.get("referral_count", 0)) + 1
        current_referrals.append(new_user_email)

        _get_table().update_item(
            Key={"referrer_id": referrer_id},
            UpdateExpression="SET referral_count = :c, referrals = :r",
            ExpressionAttributeValues={
                ":c": new_count,
                ":r": current_referrals,
            },
        )

        # Check reward thresholds
        new_rewards = _check_rewards(referrer_id, new_count, referrer.get("rewards_earned", []))

        # Track analytics
        try:
            from growth.analytics_tracker import track_event
            track_event(
                event_type="email_signup_completed",
                event_data={
                    "referral": True,
                    "ref_code": ref_code,
                    "referrer_id": referrer_id,
                    "new_count": new_count,
                },
            )
        except Exception:
            pass

        return {
            "success": True,
            "referrer_id": referrer_id,
            "new_count": new_count,
            "new_rewards": new_rewards,
        }
    except Exception as e:
        logger.error("track_referral error: %s", e)
        return {"success": False, "error": str(e)}


def _check_rewards(referrer_id: str, count: int, existing_rewards: list) -> list:
    """Check if referrer has earned new rewards."""
    new_rewards = []
    for tier in REWARD_TIERS:
        if count >= tier["threshold"] and tier["reward"] not in existing_rewards:
            new_rewards.append(tier["reward"])
            existing_rewards.append(tier["reward"])

    if new_rewards:
        try:
            _get_table().update_item(
                Key={"referrer_id": referrer_id},
                UpdateExpression="SET rewards_earned = :r",
                ExpressionAttributeValues={":r": existing_rewards},
            )
        except Exception as e:
            logger.warning("Failed to update rewards: %s", e)

    return new_rewards


def get_referral_count(user_id: str) -> dict:
    """Get referral stats for a user."""
    try:
        resp = _get_table().get_item(Key={"referrer_id": user_id})
        item = resp.get("Item")
        if not item:
            return {"success": True, "count": 0, "rewards": []}
        return {
            "success": True,
            "count": int(item.get("referral_count", 0)),
            "ref_code": item.get("ref_code", ""),
            "rewards": item.get("rewards_earned", []),
            "next_reward": _next_reward(int(item.get("referral_count", 0))),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _next_reward(current_count: int) -> dict | None:
    """Find the next reward tier the user hasn't reached."""
    for tier in REWARD_TIERS:
        if current_count < tier["threshold"]:
            return {
                "threshold": tier["threshold"],
                "reward": tier["label"],
                "remaining": tier["threshold"] - current_count,
            }
    return None


def get_leaderboard(limit: int = 10) -> dict:
    """Get top referrers."""
    try:
        resp = _get_table().scan()
        items = resp.get("Items", [])
        items.sort(key=lambda x: int(x.get("referral_count", 0)), reverse=True)
        top = items[:limit]
        return {
            "success": True,
            "leaderboard": [
                {
                    "referrer_id": i["referrer_id"],
                    "count": int(i.get("referral_count", 0)),
                    "rewards": i.get("rewards_earned", []),
                }
                for i in top
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
