"""
growth/email_automation_engine.py
Email Automation Engine — newsletters, segmentation, and drip sequences.

Turns email into the primary retention + growth channel by:
    - Generating weekly newsletters from top-performing content
    - Segmenting subscribers by engagement level
    - Running trigger-based email sequences (signup, inactive, click)
    - Re-engaging dormant subscribers

Sends via AWS SES (reuses email_platform_sync._get_ses()).
Tracks all email events via analytics_tracker.

Does NOT modify existing modules.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import boto3

logger = logging.getLogger(__name__)

SES_SENDER = os.environ.get("SES_SENDER_EMAIL", "marketing@ai1stseo.com")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

INACTIVE_DAYS = 14  # Days before a subscriber is considered inactive


def _get_ses():
    try:
        from growth.email_platform_sync import _get_ses as _ses
        return _ses()
    except Exception:
        return boto3.client("ses", region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Newsletter generation
# ---------------------------------------------------------------------------

def generate_newsletter_content() -> dict:
    """Build newsletter content from top-performing posts and trends.

    Pulls from performance_optimizer, content_discovery, and ugc_collector
    to assemble a newsletter with: 1 tip, 1 tool highlight, 1 trend, 1 CTA.
    """
    sections = {"tip": "", "tool": "", "trend": "", "cta": ""}

    # Top performing content → tip
    try:
        from growth.performance_optimizer import get_top_posts
        top = get_top_posts(limit=3)
        if top.get("success") and top.get("posts"):
            best = top["posts"][0]
            sections["tip"] = (
                f"This week's top-performing content was on {best.get('platform', 'social')} "
                f"with a score of {float(best.get('score', 0))}. "
                f"Content type: {best.get('content_type', 'post')}."
            )
    except Exception:
        pass

    if not sections["tip"]:
        sections["tip"] = (
            "Quick tip: Add FAQ sections with schema markup to your key pages. "
            "AI engines extract structured Q&A content first — it's the fastest "
            "way to get cited by ChatGPT and Perplexity."
        )

    # Tool highlight
    sections["tool"] = (
        "AI1stSEO's AEO Analyzer scans any webpage and scores how ready it is "
        "for AI extraction. It flags missing FAQ schema, weak content structure, "
        "and low authority signals — then prioritizes what to fix first."
    )

    # Trend from discovery
    try:
        from growth.content_discovery import fetch_trending_topics
        trends = fetch_trending_topics()
        if trends:
            sections["trend"] = trends[0].get("content", "")[:300]
    except Exception:
        pass

    if not sections["trend"]:
        sections["trend"] = (
            "AI Overviews are now appearing in 40%+ of Google searches. "
            "Brands that optimize for both traditional SEO and AI citation "
            "are seeing 2-3x more organic visibility."
        )

    sections["cta"] = (
        "Run your free AI visibility check at ai1stseo.com — "
        "see how ChatGPT, Perplexity, and Gemini see your brand in 30 seconds."
    )

    return {"success": True, "sections": sections}


def _build_newsletter_html(sections: dict) -> tuple:
    """Build newsletter HTML and text bodies."""
    tip = sections.get("tip", "")
    tool = sections.get("tool", "")
    trend = sections.get("trend", "")
    cta = sections.get("cta", "")

    html = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;color:#fff;padding:40px;">
        <div style="max-width:560px;margin:0 auto;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:40px;">
            <h1 style="background:linear-gradient(90deg,#00d4ff,#7b2cbf);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;font-size:1.6rem;">AI1stSEO Weekly</h1>
            <h3 style="color:#00d4ff;">💡 Tip of the Week</h3>
            <p style="color:rgba(255,255,255,0.7);line-height:1.8;">{tip}</p>
            <h3 style="color:#00d4ff;">🔧 Tool Spotlight</h3>
            <p style="color:rgba(255,255,255,0.7);line-height:1.8;">{tool}</p>
            <h3 style="color:#00d4ff;">📈 Trend Watch</h3>
            <p style="color:rgba(255,255,255,0.7);line-height:1.8;">{trend}</p>
            <div style="text-align:center;margin:28px 0;">
                <a href="https://ai1stseo.com?utm_source=email&utm_medium=newsletter&utm_campaign=weekly" style="display:inline-block;padding:12px 32px;background:#00d4ff;color:#0a0a0a;text-decoration:none;border-radius:8px;font-weight:600;">{cta[:60]}</a>
            </div>
            <p style="color:rgba(255,255,255,0.3);font-size:0.75rem;text-align:center;">AI1stSEO — Optimize for AI Discovery | <a href="https://ai1stseo.com" style="color:#00d4ff;">ai1stseo.com</a></p>
        </div>
    </body>
    </html>
    """
    text = f"AI1stSEO Weekly\n\nTip: {tip}\n\nTool: {tool}\n\nTrend: {trend}\n\n{cta}\n\nhttps://ai1stseo.com"
    subject = "AI1stSEO Weekly — AI SEO Tips, Tools & Trends"
    return subject, html, text


def send_weekly_newsletter() -> dict:
    """Generate and send the weekly newsletter to all subscribers."""
    content = generate_newsletter_content()
    if not content.get("success"):
        return {"success": False, "error": "Failed to generate newsletter content"}

    subject, html, text = _build_newsletter_html(content["sections"])

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
        return {"success": True, "sent": 0, "message": "No subscribers"}

    ses = _get_ses()
    sent = 0
    failed = 0

    for sub in subscribers:
        email = sub.get("email")
        if not email:
            continue
        try:
            ses.send_email(
                Source=SES_SENDER,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html, "Charset": "UTF-8"},
                        "Text": {"Data": text, "Charset": "UTF-8"},
                    },
                },
            )
            sent += 1
        except Exception as e:
            logger.warning("Newsletter send failed for %s: %s", email, e)
            failed += 1

    # Track event
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="welcome_email_sent",
            event_data={"newsletter": True, "sent": sent, "failed": failed},
        )
    except Exception:
        pass

    return {
        "success": True,
        "sent": sent,
        "failed": failed,
        "total_subscribers": len(subscribers),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def segment_subscribers() -> dict:
    """Segment subscribers into engagement tiers.

    Tiers:
        power_user  — has referrals OR high activity
        active      — subscribed within 7 days
        beginner    — subscribed within 30 days
        inactive    — subscribed > 30 days ago
    """
    try:
        from growth.email_subscriber import list_subscribers
        result = list_subscribers(page=1, per_page=10000)
        if not result.get("success"):
            return {"success": False, "error": "Failed to fetch subscribers"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    now = datetime.now(timezone.utc)
    segments = {"power_user": [], "active": [], "beginner": [], "inactive": []}

    # Check referral counts
    referral_counts = {}
    try:
        from growth.referral_engine import get_leaderboard
        lb = get_leaderboard(limit=100)
        if lb.get("success"):
            for entry in lb.get("leaderboard", []):
                referral_counts[entry["referrer_id"]] = entry.get("count", 0)
    except Exception:
        pass

    for sub in result.get("subscribers", []):
        email = sub.get("email", "")
        subscribed_at = sub.get("subscribed_at", "")

        # Parse subscription date
        try:
            sub_date = datetime.fromisoformat(subscribed_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            sub_date = now - timedelta(days=60)

        days_since = (now - sub_date).days

        # Classify
        if referral_counts.get(email, 0) >= 3:
            segments["power_user"].append(email)
        elif days_since <= 7:
            segments["active"].append(email)
        elif days_since <= 30:
            segments["beginner"].append(email)
        else:
            segments["inactive"].append(email)

    return {
        "success": True,
        "segments": {k: len(v) for k, v in segments.items()},
        "details": segments,
        "segmented_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Trigger-based sequences
# ---------------------------------------------------------------------------

def _send_email(email: str, subject: str, html: str, text: str) -> bool:
    """Send a single email via SES. Returns True on success."""
    try:
        _get_ses().send_email(
            Source=SES_SENDER,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            },
        )
        return True
    except Exception as e:
        logger.warning("Email send failed for %s: %s", email, e)
        return False


def send_reengagement(emails: list = None) -> dict:
    """Send re-engagement emails to inactive subscribers.

    If no emails provided, auto-detects inactive subscribers.
    """
    if emails is None:
        seg = segment_subscribers()
        if not seg.get("success"):
            return seg
        emails = seg.get("details", {}).get("inactive", [])

    if not emails:
        return {"success": True, "sent": 0, "message": "No inactive subscribers"}

    subject = "We miss you! Here's what's new at AI1stSEO"
    html = """
    <html><body style="font-family:sans-serif;background:#0a0a0a;color:#fff;padding:40px;">
    <div style="max-width:560px;margin:0 auto;padding:40px;">
        <h2 style="color:#00d4ff;">Hey! It's been a while 👋</h2>
        <p style="color:rgba(255,255,255,0.7);">AI search is evolving fast. Here's what you might have missed:</p>
        <ul style="color:rgba(255,255,255,0.7);">
            <li>AI Overviews now appear in 40%+ of Google searches</li>
            <li>New AEO Analyzer with prioritized fix recommendations</li>
            <li>Cross-model visibility tracking (ChatGPT + Perplexity + Gemini)</li>
        </ul>
        <div style="text-align:center;margin:24px 0;">
            <a href="https://ai1stseo.com?utm_source=email&utm_medium=reengagement&utm_campaign=comeback" style="padding:12px 32px;background:#00d4ff;color:#0a0a0a;text-decoration:none;border-radius:8px;font-weight:600;">Check Your AI Visibility</a>
        </div>
    </div></body></html>
    """
    text = "Hey! AI search is evolving fast. Check your AI visibility at https://ai1stseo.com"

    sent = sum(1 for e in emails if _send_email(e, subject, html, text))

    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="welcome_email_sent",
            event_data={"reengagement": True, "sent": sent, "total": len(emails)},
        )
    except Exception:
        pass

    return {"success": True, "sent": sent, "total": len(emails)}
