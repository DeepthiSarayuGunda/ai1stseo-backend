"""
growth/lifecycle_engine.py
Lifecycle Engine — keeps users engaged continuously.

Classifies each subscriber into a lifecycle state and triggers
the appropriate action (DM, email, referral push, or skip).

States:
    new         — subscribed within 3 days
    active      — subscribed 3-14 days, has engagement signals
    inactive    — no engagement for 14+ days
    power_user  — has referrals or high engagement

Actions per state:
    new         → welcome DM + lead magnet email
    active      → engagement DM + referral invite
    inactive    → re-engagement email
    power_user  → referral leaderboard update + thank-you

Connects to: dm_engine, email_automation_engine, referral_engine
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def classify_user_state(subscriber: dict, referral_count: int = 0) -> str:
    """Classify a subscriber into a lifecycle state.

    Args:
        subscriber: Dict with at least 'email' and 'subscribed_at'.
        referral_count: Number of referrals this user has made.

    Returns:
        One of: "power_user", "new", "active", "inactive"
    """
    if referral_count >= 3:
        return "power_user"

    now = datetime.now(timezone.utc)
    subscribed_at = subscriber.get("subscribed_at", "")

    try:
        sub_date = datetime.fromisoformat(subscribed_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "inactive"

    days = (now - sub_date).days

    if days <= 3:
        return "new"
    if days <= 14:
        return "active"
    return "inactive"


def _get_referral_counts() -> dict:
    """Fetch referral counts for all users."""
    try:
        from growth.referral_engine import get_leaderboard
        lb = get_leaderboard(limit=200)
        if lb.get("success"):
            return {e["referrer_id"]: e.get("count", 0) for e in lb.get("leaderboard", [])}
    except Exception:
        pass
    return {}


def trigger_actions(email: str, state: str) -> dict:
    """Execute lifecycle actions for a user based on their state.

    Returns summary of actions taken.
    """
    actions = []

    if state == "new":
        # Welcome DM
        try:
            from growth.dm_engine import send_welcome_dm
            result = send_welcome_dm(email, platform="x")
            if result.get("success"):
                actions.append("welcome_dm_queued")
        except Exception as e:
            logger.warning("Welcome DM failed for %s: %s", email, e)

        # Referral link generation
        try:
            from growth.referral_engine import generate_referral_link
            generate_referral_link(email)
            actions.append("referral_link_created")
        except Exception:
            pass

    elif state == "active":
        # Engagement DM with referral push
        try:
            from growth.dm_engine import send_engagement_dm
            result = send_engagement_dm(email, topic="AI SEO", platform="x")
            if result.get("success"):
                actions.append("engagement_dm_queued")
        except Exception as e:
            logger.warning("Engagement DM failed for %s: %s", email, e)

        # Nudge referral
        try:
            from growth.dm_engine import send_nurture_dm
            send_nurture_dm(email, platform="linkedin")
            actions.append("nurture_dm_queued")
        except Exception:
            pass

    elif state == "inactive":
        # Re-engagement email
        try:
            from growth.email_automation_engine import send_reengagement
            result = send_reengagement(emails=[email])
            if result.get("sent", 0) > 0:
                actions.append("reengagement_email_sent")
        except Exception as e:
            logger.warning("Re-engagement failed for %s: %s", email, e)

    elif state == "power_user":
        # Thank-you DM
        try:
            from growth.dm_engine import send_engagement_dm
            send_engagement_dm(email, topic="your referral impact", platform="x")
            actions.append("power_user_dm_queued")
        except Exception:
            pass

    return {"email": email, "state": state, "actions": actions}


def run_lifecycle_cycle() -> dict:
    """Run the full lifecycle engine for all subscribers.

    Classifies each subscriber and triggers appropriate actions.
    """
    # Get all subscribers
    try:
        from growth.email_subscriber import list_subscribers
        result = list_subscribers(page=1, per_page=10000)
        if not result.get("success"):
            return {"success": False, "error": "Failed to fetch subscribers"}
        subscribers = result.get("subscribers", [])
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not subscribers:
        return {"success": True, "processed": 0, "message": "No subscribers"}

    referral_counts = _get_referral_counts()

    state_counts = {"new": 0, "active": 0, "inactive": 0, "power_user": 0}
    action_counts = {}
    processed = 0

    for sub in subscribers:
        email = sub.get("email", "")
        if not email:
            continue

        ref_count = referral_counts.get(email, 0)
        state = classify_user_state(sub, ref_count)
        state_counts[state] = state_counts.get(state, 0) + 1

        result = trigger_actions(email, state)
        for action in result.get("actions", []):
            action_counts[action] = action_counts.get(action, 0) + 1

        processed += 1

    # Track lifecycle run
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="auto_pipeline_run",
            event_data={"lifecycle_run": True, "processed": processed, "states": state_counts},
        )
    except Exception:
        pass

    return {
        "success": True,
        "processed": processed,
        "states": state_counts,
        "actions": action_counts,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
