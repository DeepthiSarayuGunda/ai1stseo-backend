"""
Notification Tool for OpenClaw
Sends alerts via WhatsApp, Slack, Telegram, Discord, or Email (SES SMTP)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from typing import Literal


def send_alert(
    message: str,
    channel: Literal["whatsapp", "slack", "telegram", "discord", "email", "all"] = "whatsapp",
    severity: Literal["info", "warning", "critical"] = "info",
    recipient: str = None
) -> dict:
    """
    OpenClaw Tool: Send notification to configured channel(s)
    
    Args:
        message: Alert message to send
        channel: Notification channel (whatsapp/slack/telegram/discord/email/all)
        severity: Alert severity level
        recipient: Email address for email channel (overrides SES_RECIPIENT_EMAIL env var)
    
    Returns:
        Dict with success status per channel
    """
    severity_label = {"info": "[INFO]", "warning": "[WARNING]", "critical": "[CRITICAL]"}
    formatted = "{} {}".format(severity_label.get(severity, ''), message)
    
    results = {}
    
    # If "all", send to all configured channels
    channels_to_send = ["whatsapp", "slack", "telegram", "discord", "email"] if channel == "all" else [channel]
    
    for ch in channels_to_send:
        try:
            if ch == "whatsapp":
                results["whatsapp"] = _send_whatsapp(formatted)
            elif ch == "slack":
                results["slack"] = _send_slack(formatted)
            elif ch == "telegram":
                results["telegram"] = _send_telegram(formatted)
            elif ch == "discord":
                results["discord"] = _send_discord(formatted)
            elif ch == "email":
                results["email"] = _send_email(formatted, severity, recipient=recipient)
        except Exception as e:
            results[ch] = {"success": False, "error": str(e)}
    
    return results


def _send_whatsapp(message: str) -> dict:
    """Send via WhatsApp Business API or OpenClaw gateway"""
    # Option 1: OpenClaw gateway
    openclaw_url = os.getenv("OPENCLAW_API_URL", "http://127.0.0.1:18789")
    whatsapp_number = os.getenv("WHATSAPP_NUMBER", "")
    
    # Option 2: Twilio WhatsApp API
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")  # e.g., "whatsapp:+14155238886"
    
    if twilio_sid and twilio_token and twilio_whatsapp and whatsapp_number:
        # Use Twilio
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
            auth=(twilio_sid, twilio_token),
            data={
                "From": twilio_whatsapp,
                "To": f"whatsapp:{whatsapp_number}",
                "Body": message
            },
            timeout=10
        )
        return {"success": response.status_code == 201, "provider": "twilio"}
    
    elif whatsapp_number:
        # Use OpenClaw gateway
        response = requests.post(
            f"{openclaw_url}/api/send",
            json={"channel": "whatsapp", "to": whatsapp_number, "message": message},
            timeout=10
        )
        return {"success": response.status_code == 200, "provider": "openclaw"}
    
    print(f"[WhatsApp - Not Configured] {message}")
    return {"success": False, "error": "Not configured"}


def _send_slack(message: str) -> dict:
    """Send via Slack webhook"""
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    
    if not webhook:
        print(f"[Slack - Not Configured] {message}")
        return {"success": False, "error": "SLACK_WEBHOOK_URL not set"}
    
    # Rich formatting for Slack
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message}
            }
        ],
        "text": message  # Fallback
    }
    
    response = requests.post(webhook, json=payload, timeout=10)
    return {"success": response.status_code == 200}


def _send_telegram(message: str) -> dict:
    """Send via Telegram Bot API"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print(f"[Telegram - Not Configured] {message}")
        return {"success": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        },
        timeout=10
    )
    return {"success": response.status_code == 200}


def _send_discord(message: str) -> dict:
    """Send via Discord webhook"""
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook:
        print(f"[Discord - Not Configured] {message}")
        return {"success": False, "error": "DISCORD_WEBHOOK_URL not set"}
    
    # Rich embed for Discord
    payload = {
        "embeds": [{
            "description": message,
            "color": 16711680 if "[CRITICAL]" in message else 16776960 if "[WARNING]" in message else 65280
        }],
        "content": message  # Fallback
    }
    
    response = requests.post(webhook, json=payload, timeout=10)
    return {"success": response.status_code == 204}


def _send_email(message: str, severity: str, recipient: str = None) -> dict:
    """Send via SES SMTP (primary) or SES API (fallback)
    
    Uses SMTP credentials which work regardless of EC2 IAM role.
    Env vars needed:
        SES_SENDER_EMAIL - From address (e.g. no-reply@ai1stseo.com)
        SES_SMTP_USER    - SES SMTP username
        SES_SMTP_PASS    - SES SMTP password
        SES_RECIPIENT_EMAIL - Default recipient (used if no recipient param)
    """
    ses_sender = os.getenv("SES_SENDER_EMAIL")
    to_addr = recipient or os.getenv("SES_RECIPIENT_EMAIL")
    smtp_user = os.getenv("SES_SMTP_USER")
    smtp_pass = os.getenv("SES_SMTP_PASS")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    if not ses_sender or not to_addr:
        print("[Email - Not Configured] Missing sender or recipient")
        return {"success": False, "error": "Email not configured - need SES_SENDER_EMAIL and recipient"}

    subject = "[Site Monitor] {} Alert".format(severity.upper())

    # Primary: SES SMTP (works without IAM SES permissions)
    if smtp_user and smtp_pass:
        try:
            smtp_host = "email-smtp.{}.amazonaws.com".format(aws_region)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = ses_sender
            msg["To"] = to_addr

            # Plain text body
            msg.attach(MIMEText(message, "plain"))

            # HTML body with basic formatting
            html_body = "<html><body><pre style='font-family:monospace;'>{}</pre></body></html>".format(
                message.replace("<", "&lt;").replace(">", "&gt;")
            )
            msg.attach(MIMEText(html_body, "html"))

            server = smtplib.SMTP(smtp_host, 587)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(ses_sender, [to_addr], msg.as_string())
            server.close()
            return {"success": True, "provider": "ses-smtp", "recipient": to_addr}
        except Exception as e:
            print("[Email SMTP Error] {}".format(str(e)))
            # Fall through to SES API attempt

    # Fallback: SES API (only works if IAM role has ses:SendEmail)
    try:
        import boto3
        ses = boto3.client('ses', region_name=aws_region)
        ses.send_email(
            Source=ses_sender,
            Destination={"ToAddresses": [to_addr]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": message}}
            }
        )
        return {"success": True, "provider": "ses-api", "recipient": to_addr}
    except Exception as e:
        return {"success": False, "error": "Both SMTP and API failed. SMTP: check SES_SMTP_USER/SES_SMTP_PASS. API: {}".format(str(e))}


def send_report(report: dict, channels: list = None) -> dict:
    """Send a formatted monitoring report to specified channels"""
    if channels is None:
        channels = ["whatsapp"]
    
    lines = ["*SITE MONITOR REPORT*", ""]
    
    for site in report.get("results", []):
        seo = site.get("results", {}).get("seo", {})
        score = seo.get("score", "N/A")
        status = "[PASS]" if score >= 70 else "[WARN]" if score >= 50 else "[FAIL]"
        lines.append(f"{status} *{site['site']}*: {score}/100")
        
        # Add critical issues
        issues = seo.get("critical_issues", [])
        if issues:
            for issue in issues[:2]:
                lines.append(f"   - {issue}")
        
        # Add top recommendations
        recs = seo.get("recommendations", [])
        critical_recs = [r for r in recs if r.get("priority") == "Critical"]
        if critical_recs:
            lines.append("   Action needed:")
            for rec in critical_recs[:2]:
                lines.append(f"   -> {rec['action']}")
    
    lines.append("")
    lines.append(f"Scanned at {report.get('timestamp', 'N/A')}")
    
    message = "\n".join(lines)
    
    results = {}
    for channel in channels:
        results[channel] = send_alert(message, channel=channel, severity="info")
    
    return results


def get_channel_status() -> dict:
    """Check which notification channels are configured"""
    smtp_configured = bool(os.getenv("SES_SMTP_USER") and os.getenv("SES_SMTP_PASS"))
    api_configured = bool(os.getenv("SES_SENDER_EMAIL") and os.getenv("SES_RECIPIENT_EMAIL"))
    return {
        "whatsapp": {
            "configured": bool(os.getenv("WHATSAPP_NUMBER")),
            "provider": "twilio" if os.getenv("TWILIO_ACCOUNT_SID") else "openclaw"
        },
        "slack": {
            "configured": bool(os.getenv("SLACK_WEBHOOK_URL"))
        },
        "telegram": {
            "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
        },
        "discord": {
            "configured": bool(os.getenv("DISCORD_WEBHOOK_URL"))
        },
        "email": {
            "configured": bool(os.getenv("SES_SENDER_EMAIL") and (smtp_configured or api_configured)),
            "provider": "ses-smtp" if smtp_configured else "ses-api",
            "sender": os.getenv("SES_SENDER_EMAIL", "not set"),
            "smtp_ready": smtp_configured
        }
    }


# OpenClaw tool registration
TOOL_SCHEMA = {
    "name": "notifier",
    "description": "Send alert notifications via WhatsApp, Slack, Telegram, Discord, or Email",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Alert message"},
            "channel": {"type": "string", "enum": ["whatsapp", "slack", "telegram", "discord", "email", "all"]},
            "severity": {"type": "string", "enum": ["info", "warning", "critical"]}
        },
        "required": ["message"]
    }
}
