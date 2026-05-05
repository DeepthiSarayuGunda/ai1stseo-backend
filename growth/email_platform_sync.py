"""
growth/email_platform_sync.py
Integration hook for syncing subscribers to external email platforms
and sending welcome emails via SES.

Currently sends a welcome email via AWS SES when a subscriber signs up.
Future: connect to Brevo or MailerLite for drip campaigns.

Environment variables:
    EMAIL_PLATFORM          — "ses" | "brevo" | "mailerlite" | "" (disabled)
    EMAIL_PLATFORM_API_KEY  — API key for Brevo/MailerLite (not needed for SES)
    SES_SENDER_EMAIL        — sender address (default: marketing@ai1stseo.com)
    AWS_REGION              — AWS region (default: us-east-1)
"""

import logging
import os

import boto3

logger = logging.getLogger(__name__)

PLATFORM = os.environ.get("EMAIL_PLATFORM", "ses")
API_KEY = os.environ.get("EMAIL_PLATFORM_API_KEY", "")
SES_SENDER = os.environ.get("SES_SENDER_EMAIL", "marketing@ai1stseo.com")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_ses_client = None


def _get_ses():
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses", region_name=AWS_REGION)
    return _ses_client


def _send_welcome_email(email: str, name: str = None, lead_magnet: dict = None) -> dict:
    """Send a welcome email via AWS SES, optionally including lead magnet download link."""
    display_name = name or "there"
    subject = "Welcome to AI1stSEO — Your Free AEO/GEO & SEO Analysis"

    # Build optional lead magnet section
    lead_magnet_html = ""
    lead_magnet_text = ""
    if lead_magnet and lead_magnet.get("download_url"):
        lm_title = lead_magnet.get("title", "Your Free Resource")
        lm_url = lead_magnet["download_url"]
        lead_magnet_html = f"""
            <div style="background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);border-radius:12px;padding:20px;margin:20px 0;">
                <p style="color:#00d4ff;font-weight:600;margin:0 0 8px;">&#127873; {lm_title}</p>
                <a href="{lm_url}" style="display:inline-block;padding:10px 24px;background:#7b2cbf;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Download Now</a>
            </div>
        """
        lead_magnet_text = f"\n\nYour free resource: {lm_title}\nDownload: {lm_url}"

    html_body = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;color:#fff;padding:40px;">
        <div style="max-width:560px;margin:0 auto;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:40px;">
            <h1 style="background:linear-gradient(90deg,#00d4ff,#7b2cbf);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;font-size:1.8rem;">AI1stSEO</h1>
            <h2 style="color:#00d4ff;text-align:center;font-size:1.2rem;">Hey {display_name}!</h2>
            <p style="color:rgba(255,255,255,0.7);line-height:1.8;font-size:0.95rem;">
                Thanks for signing up for your free AEO/GEO & SEO analysis. Here's what you can do:
            </p>
            <ul style="color:rgba(255,255,255,0.7);line-height:2;font-size:0.95rem;">
                <li><strong>Run a free SEO audit</strong> — 236 checks across 10 categories</li>
                <li><strong>Check your AI visibility</strong> — see if ChatGPT and Gemini mention your brand</li>
                <li><strong>Get a PDF report</strong> — download and share with your team</li>
            </ul>{lead_magnet_html}
            <div style="text-align:center;margin:28px 0;">
                <a href="https://ai1stseo.com" style="display:inline-block;padding:12px 32px;background:#00d4ff;color:#0a0a0a;text-decoration:none;border-radius:8px;font-weight:600;font-size:0.95rem;">Start Your Free Analysis</a>
            </div>
            <div style="text-align:center;margin-top:24px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);">
                <p style="color:rgba(255,255,255,0.4);font-size:0.8rem;">
                    AI1stSEO — Optimize for AI Discovery<br>
                    <a href="https://ai1stseo.com" style="color:#00d4ff;text-decoration:none;">ai1stseo.com</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    text_body = f"Hey {display_name}! Thanks for signing up at AI1stSEO. Start your free AEO/GEO & SEO analysis at https://ai1stseo.com{lead_magnet_text}"

    try:
        _get_ses().send_email(
            Source=SES_SENDER,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info("Welcome email sent to %s via SES", email)
        return {"sent": True, "provider": "ses"}
    except Exception as e:
        logger.warning("SES welcome email failed for %s: %s", email, e)
        return {"sent": False, "provider": "ses", "error": str(e)}


def sync_subscriber_to_email_platform(subscriber_data: dict) -> dict:
    """Sync a new subscriber — send welcome email and/or sync to platform."""
    email = subscriber_data.get("email")
    name = subscriber_data.get("name")
    lead_magnet = subscriber_data.get("lead_magnet")

    if PLATFORM == "ses":
        return _send_welcome_email(email, name, lead_magnet)

    if not PLATFORM or not API_KEY:
        logger.debug("email_platform_sync: no-op (platform=%s)", PLATFORM or "(not set)")
        return {"synced": False, "provider": None, "reason": "no platform configured"}

    logger.warning("email_platform_sync: unknown platform '%s'", PLATFORM)
    return {"synced": False, "provider": PLATFORM, "reason": "unknown platform"}
