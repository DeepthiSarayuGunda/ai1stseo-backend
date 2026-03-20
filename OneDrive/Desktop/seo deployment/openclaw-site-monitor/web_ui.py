"""
Site Monitor Web UI - Vaporwave Design
With user auth (shared with main site) and daily report subscriptions
"""
from flask import Flask, jsonify, request, render_template_string, make_response
from flask_cors import CORS
import sys, os, json, hashlib, secrets
from datetime import datetime, timedelta
sys.path.insert(0, ".")

from tools.seo_scanner import scan_site
from tools.uptime_monitor import check_uptime
from tools.content_monitor import check_content_changes
from tools.ai_citation_tracker import check_ai_visibility
from tools.transaction_monitor import test_critical_paths
from tools.notifier import send_alert, get_channel_status

app = Flask(__name__)
CORS(app)

# === Data paths ===
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "monitor_users.json")
TOKENS_FILE = os.path.join(DATA_DIR, "monitor_tokens.json")
SUBS_FILE = os.path.join(DATA_DIR, "subscriptions.json")
# Also check main site users for shared auth
MAIN_USERS_FILE = os.path.join(os.path.dirname(__file__), "..", "users.json")

os.makedirs(DATA_DIR, exist_ok=True)

def _load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def _hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _get_user(email):
    """Check monitor users first, then main site users (shared auth)"""
    users = _load_json(USERS_FILE)
    if email in users:
        return users[email], "monitor"
    main_users = _load_json(MAIN_USERS_FILE)
    if email in main_users:
        return main_users[email], "main"
    return None, None

def _auth_token(req):
    """Extract and validate auth token from request"""
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = req.args.get("token", "")
    tokens = _load_json(TOKENS_FILE)
    info = tokens.get(token)
    if not info:
        return None
    if datetime.fromisoformat(info["expiry"]) < datetime.now():
        del tokens[token]
        _save_json(TOKENS_FILE, tokens)
        return None
    return info

# === Load HTML template ===
template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
if os.path.exists(template_path):
    with open(template_path) as f:
        HTML_TEMPLATE = f.read()
else:
    HTML_TEMPLATE = "<h1>Template not found</h1>"

# ===================== AUTH ROUTES =====================

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not name or not email or not password:
        return jsonify({"status": "error", "message": "All fields required"}), 400
    if "@" not in email or "." not in email:
        return jsonify({"status": "error", "message": "Invalid email"}), 400
    existing, _ = _get_user(email)
    if existing:
        return jsonify({"status": "error", "message": "Email already registered. If you have an AI1stSEO account, use those credentials to log in."}), 400
    users = _load_json(USERS_FILE)
    users[email] = {"name": name, "password_hash": _hash_pw(password), "created_at": datetime.now().isoformat()}
    _save_json(USERS_FILE, users)
    return jsonify({"status": "success", "message": "Account created"})

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required"}), 400
    user, source = _get_user(email)
    if not user or user.get("password_hash") != _hash_pw(password):
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401
    token = secrets.token_urlsafe(32)
    tokens = _load_json(TOKENS_FILE)
    tokens[token] = {"email": email, "name": user["name"], "expiry": (datetime.now() + timedelta(hours=72)).isoformat(), "source": source}
    _save_json(TOKENS_FILE, tokens)
    return jsonify({"status": "success", "token": token, "name": user["name"], "email": email, "source": source})

@app.route("/api/auth/me")
def me():
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    subs = _load_json(SUBS_FILE)
    my_sub = subs.get(info["email"], {})
    return jsonify({"status": "success", "email": info["email"], "name": info["name"], "subscription": my_sub})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    tokens = _load_json(TOKENS_FILE)
    tokens.pop(token, None)
    _save_json(TOKENS_FILE, tokens)
    return jsonify({"status": "success"})

# ===================== SUBSCRIPTION ROUTES =====================

@app.route("/api/subscribe", methods=["POST"])
def subscribe():
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Login required"}), 401
    data = request.get_json() or {}
    channels = data.get("channels", [])
    sites = data.get("sites", ["https://ai1stseo.com"])
    frequency = data.get("frequency", "daily")
    channel_config = data.get("channel_config", {})
    if not channels:
        return jsonify({"status": "error", "message": "Select at least one channel"}), 400
    valid_channels = ["email", "whatsapp", "slack", "telegram", "discord"]
    channels = [c for c in channels if c in valid_channels]
    subs = _load_json(SUBS_FILE)
    subs[info["email"]] = {
        "name": info["name"],
        "channels": channels,
        "sites": sites,
        "frequency": frequency,
        "channel_config": channel_config,
        "active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    _save_json(SUBS_FILE, subs)
    return jsonify({"status": "success", "message": f"Subscribed to {frequency} reports via {', '.join(channels)}"})

@app.route("/api/unsubscribe", methods=["POST"])
def unsubscribe():
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Login required"}), 401
    subs = _load_json(SUBS_FILE)
    if info["email"] in subs:
        subs[info["email"]]["active"] = False
        subs[info["email"]]["updated_at"] = datetime.now().isoformat()
        _save_json(SUBS_FILE, subs)
    return jsonify({"status": "success", "message": "Unsubscribed from daily reports"})

@app.route("/api/subscription")
def get_subscription():
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Login required"}), 401
    subs = _load_json(SUBS_FILE)
    my_sub = subs.get(info["email"], {})
    return jsonify({"status": "success", "subscription": my_sub})

# ===================== MONITORING ROUTES =====================

@app.route("/")
def index():
    resp = make_response(render_template_string(HTML_TEMPLATE))
    resp.headers['Last-Modified'] = 'Tue, 18 Mar 2026 12:00:00 GMT'
    return resp

@app.route("/llms.txt")
def llms_txt():
    txt = """# AI 1st SEO Site Monitor
# https://monitor.ai1stseo.com
# AI crawler guidance

User-agent: *
Allow: /

# About
name: AI 1st SEO Site Monitor
description: Free AI-powered site monitoring dashboard for SEO health, uptime, and AI citation tracking.
url: https://monitor.ai1stseo.com
author: AI 1st SEO
contact: support@ai1stseo.com

# Content
topics: SEO monitoring, uptime checking, AI citation tracking, AEO, GEO, content change detection
content-type: web application, documentation, FAQ
language: en

# Related
main-site: https://ai1stseo.com
seo-audit: https://seoaudit.ai1stseo.com
seo-analysis: https://seoanalysis.ai1stseo.com
guides: https://ai1stseo.com/guides
doc-summarizer: https://docsummarizer.ai1stseo.com
"""
    resp = make_response(txt)
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return resp

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "site-monitor", "version": "3.0", "features": ["auth", "subscriptions", "daily-reports"]})

@app.route("/api/scan")
def scan():
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        seo = scan_site(url)
        uptime = check_uptime(url)
        return jsonify({"seo": seo, "uptime": uptime, "url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/uptime")
def uptime():
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        return jsonify(check_uptime(url))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/content")
def content():
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        return jsonify(check_content_changes(url))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai-visibility")
def ai_visibility():
    domain = request.args.get("domain", "https://ai1stseo.com")
    brand = request.args.get("brand", "AI 1st SEO")
    try:
        return jsonify(check_ai_visibility(domain, brand))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/transaction")
def transaction():
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        return jsonify(test_critical_paths(url))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/full-scan")
def full_scan():
    url = request.args.get("url", "https://ai1stseo.com")
    brand = request.args.get("brand", "AI 1st SEO")
    try:
        return jsonify({
            "seo": scan_site(url),
            "uptime": check_uptime(url),
            "content": check_content_changes(url),
            "ai": check_ai_visibility(url, brand),
            "transaction": test_critical_paths(url),
            "url": url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===================== DAILY REPORT SENDER =====================

def send_daily_reports():
    """Called by scheduler - sends reports to all active subscribers"""
    subs = _load_json(SUBS_FILE)
    sent = 0
    for email, sub in subs.items():
        if not sub.get("active", False):
            continue
        try:
            report_parts = []
            for site_url in sub.get("sites", []):
                seo = scan_site(site_url)
                uptime = check_uptime(site_url)
                report_parts.append(
                    f"=== {site_url} ===\n"
                    f"SEO Score: {seo.get('score', 'N/A')}/100\n"
                    f"Status: {'UP' if uptime.get('is_up') else 'DOWN'}\n"
                    f"Response: {uptime.get('response_time_ms', 'N/A')}ms\n"
                    f"Critical Issues: {len(seo.get('critical_issues', []))}\n"
                )
            report = (
                f"Daily Site Monitor Report - {datetime.now().strftime('%Y-%m-%d')}\n"
                f"Subscriber: {sub.get('name', email)}\n\n"
                + "\n".join(report_parts)
            )
            for channel in sub.get("channels", []):
                cfg = sub.get("channel_config", {}).get(channel, {})
                if channel == "email":
                    send_alert(report, channel="email", severity="info", recipient=email)
                elif channel == "whatsapp":
                    send_alert(report, channel="whatsapp", severity="info")
                elif channel == "slack":
                    send_alert(report, channel="slack", severity="info")
                elif channel == "telegram":
                    send_alert(report, channel="telegram", severity="info")
                elif channel == "discord":
                    send_alert(report, channel="discord", severity="info")
            sent += 1
        except Exception as e:
            print(f"Failed to send report to {email}: {e}")
    return {"sent": sent, "total_subscribers": len([s for s in subs.values() if s.get("active")])}



@app.route("/api/send-report-now", methods=["POST"])
def send_report_now():
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Login required"}), 401
    subs = _load_json(SUBS_FILE)
    my_sub = subs.get(info["email"])
    if not my_sub or not my_sub.get("active"):
        return jsonify({"status": "error", "message": "No active subscription. Subscribe first."}), 400
    try:
        report_parts = []
        for site_url in my_sub.get("sites", []):
            seo = scan_site(site_url)
            uptime = check_uptime(site_url)
            report_parts.append(
                f"=== {site_url} ===\n"
                f"SEO Score: {seo.get('score', 'N/A')}/100\n"
                f"Status: {'UP' if uptime.get('is_up') else 'DOWN'}\n"
                f"Response: {uptime.get('response_time_ms', 'N/A')}ms\n"
                f"Critical Issues: {len(seo.get('critical_issues', []))}\n"
            )
        report = (
            f"Site Monitor Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Requested by: {my_sub.get('name', info['email'])}\n\n"
            + "\n".join(report_parts)
        )
        sent_to = []
        for channel in my_sub.get("channels", []):
            if channel == "email":
                send_alert(report, channel=channel, severity="info", recipient=info["email"])
            else:
                send_alert(report, channel=channel, severity="info")
            sent_to.append(channel)
        return jsonify({"status": "success", "message": f"Report sent via {', '.join(sent_to)}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ===================== EMAIL STATUS ROUTES =====================

@app.route("/api/email-status")
def email_status():
    """Check email/notification channel configuration"""
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Login required"}), 401
    channels = get_channel_status()
    return jsonify({"status": "success", "channels": channels})

@app.route("/api/test-email", methods=["POST"])
def test_email():
    """Send a test email to the authenticated user"""
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Login required"}), 401
    try:
        result = send_alert(
            "This is a test email from AI 1st SEO Site Monitor.\n\n"
            "If you received this, email notifications are working correctly.\n\n"
            "- Site Monitor (monitor.ai1stseo.com)",
            channel="email",
            severity="info",
            recipient=info["email"]
        )
        email_result = result.get("email", {})
        if email_result.get("success"):
            return jsonify({"status": "success", "message": "Test email sent to {}".format(info["email"]), "provider": email_result.get("provider")})
        else:
            return jsonify({"status": "error", "message": "Email send failed: {}".format(email_result.get("error", "unknown"))}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ===================== AGENT CHAT ROUTE =====================

@app.route("/api/chat", methods=["POST"])
def agent_chat():
    info = _auth_token(request)
    if not info:
        return jsonify({"status": "error", "message": "Login required"}), 401
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"status": "error", "message": "Message required"}), 400
    try:
        from tools.conversation_handler import handle_message
        user_id = info["email"]
        response = handle_message(user_id, message)
        return jsonify({"status": "success", "response": response})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=False)

