"""
Site Monitor Web UI - Vaporwave Design
With Cognito auth, RDS subscriptions, response caching, async scans, and daily reports.
"""
from flask import Flask, jsonify, request, render_template_string, make_response
from flask_cors import CORS
import sys, os, json, time, uuid, threading
from datetime import datetime
sys.path.insert(0, ".")

from tools.seo_scanner import scan_site, deep_scan_site
from tools.uptime_monitor import check_uptime
from tools.content_monitor import check_content_changes
from tools.ai_citation_tracker import check_ai_visibility
from tools.transaction_monitor import test_critical_paths
from tools.notifier import send_alert, get_channel_status

app = Flask(__name__)
CORS(app)

# === Gzip compression for all responses ===
import gzip as _gzip

@app.after_request
def compress_response(response):
    if (response.status_code < 200 or response.status_code >= 300
            or response.direct_passthrough
            or 'Content-Encoding' in response.headers
            or len(response.get_data()) < 500):
        return response
    accept_enc = request.headers.get('Accept-Encoding', '')
    if 'gzip' not in accept_enc:
        return response
    response.set_data(_gzip.compress(response.get_data()))
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = len(response.get_data())
    response.headers['Vary'] = 'Accept-Encoding'
    return response


@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = "default-src 'self' https://api.ai1stseo.com; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.ai1stseo.com; font-src 'self'"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response

# === RDS Persistence via Backend Data API ===
import threading as _threading
import requests as _http

_BACKEND_API = 'https://api.ai1stseo.com'

def _persist_to_rds(endpoint, payload, auth_token=None):
    """Fire-and-forget: POST scan results to the backend data API."""
    def _do():
        try:
            headers = {'Content-Type': 'application/json'}
            if auth_token:
                headers['Authorization'] = 'Bearer ' + auth_token
            _http.post(_BACKEND_API + endpoint, json=payload, headers=headers, timeout=10)
        except Exception:
            pass
    _threading.Thread(target=_do, daemon=True).start()

def _fire_webhook_event(event_type, payload):
    """Dispatch a webhook event via the backend."""
    def _do():
        try:
            from database import query, execute
            import json, hmac, hashlib
            rows = query(
                "SELECT id, url, secret, events FROM webhooks WHERE project_id = %s AND is_active = true",
                ('24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2',),
            )
            for wh in rows:
                events = wh.get('events', [])
                if '*' not in events and event_type not in events:
                    continue
                body = json.dumps({'event': event_type, 'data': payload})
                hdrs = {'Content-Type': 'application/json', 'X-Webhook-Event': event_type}
                if wh.get('secret'):
                    sig = hmac.new(wh['secret'].encode(), body.encode(), hashlib.sha256).hexdigest()
                    hdrs['X-Webhook-Signature'] = sig
                try:
                    r = _http.post(wh['url'], data=body, headers=hdrs, timeout=10)
                    execute(
                        "INSERT INTO webhook_deliveries (webhook_id, event_type, payload, status_code, success) VALUES (%s,%s,%s,%s,%s)",
                        (wh['id'], event_type, body, r.status_code, r.status_code < 400),
                    )
                except Exception:
                    pass
        except Exception:
            pass
    _threading.Thread(target=_do, daemon=True).start()


# === Data paths (JSON fallback for EC2) ===
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
DATA_DIR = "/tmp/data" if IS_LAMBDA else os.path.join(os.path.dirname(__file__), "data")
SUBS_FILE = os.path.join(DATA_DIR, "subscriptions.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Default project ID for monitor scans
DEFAULT_PROJECT_ID = "24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2"


def _load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# === Cognito auth helper ===
def _auth_user(req):
    """Validate Cognito token from request. Returns user dict or None."""
    try:
        from cognito_auth import validate_token
        return validate_token(req)
    except Exception:
        return None


# === Response cache (120s TTL, max 50 entries) ===
_cache = {}
_CACHE_TTL = 120
_CACHE_MAX = 50


def _cached_call(key, fn, *args, **kwargs):
    """Return cached result if fresh, otherwise call fn and cache."""
    now = time.time()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < _CACHE_TTL:
            return val
    if len(_cache) >= _CACHE_MAX:
        stale = [k for k, (ts, _) in _cache.items() if now - ts >= _CACHE_TTL]
        for k in stale:
            del _cache[k]
    result = fn(*args, **kwargs)
    _cache[key] = (now, result)
    return result


# === Subscription storage: RDS primary, JSON fallback ===
def _load_subs():
    """Load all subscriptions from RDS, fall back to JSON."""
    try:
        from db import query
        rows = query("SELECT email, data FROM subscriptions WHERE active = true")
        return {r["email"]: json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows}
    except Exception:
        return _load_json(SUBS_FILE)


def _save_sub(email, sub_data):
    """Save a subscription to RDS, fall back to JSON."""
    try:
        from db import execute
        execute(
            "INSERT INTO subscriptions (email, data, active, updated_at) "
            "VALUES (%s, %s, %s, NOW()) "
            "ON CONFLICT (email) DO UPDATE SET data = %s, active = %s, updated_at = NOW()",
            (email, json.dumps(sub_data, default=str), sub_data.get("active", True),
             json.dumps(sub_data, default=str), sub_data.get("active", True)),
        )
        return
    except Exception:
        pass
    subs = _load_json(SUBS_FILE)
    subs[email] = sub_data
    _save_json(SUBS_FILE, subs)


# === Scan history: persist to RDS ===
def _save_scan_history(url, scan_type, data):
    """Save a scan result to the audits table in RDS."""
    try:
        from db import insert_returning
        score = data.get("score") or data.get("overall_score") or data.get("overallScore")
        insert_returning(
            "INSERT INTO audits (project_id, url, overall_score, total_checks, "
            "passed_checks, load_time_ms, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id",
            (
                DEFAULT_PROJECT_ID,
                url,
                int(score) if score else None,
                data.get("totalChecks") or data.get("total_checks") or 0,
                data.get("totalPassed") or data.get("passed_checks") or 0,
                int(float(data.get("load_time", 0)) * 1000),
            ),
        )
    except Exception as e:
        print("Failed to save scan history: {}".format(e))


def _save_uptime_history(url, data):
    """Save an uptime check to the uptime_checks table in RDS."""
    try:
        from db import execute, query_one
        site = query_one(
            "SELECT id FROM monitored_sites WHERE url = %s AND project_id = %s",
            (url, DEFAULT_PROJECT_ID),
        )
        if not site:
            from db import insert_returning
            site_id = insert_returning(
                "INSERT INTO monitored_sites (project_id, url) VALUES (%s, %s) RETURNING id",
                (DEFAULT_PROJECT_ID, url),
            )
        else:
            site_id = site["id"]
        execute(
            "INSERT INTO uptime_checks (site_id, is_up, status_code, response_time_ms, checked_at) "
            "VALUES (%s, %s, %s, %s, NOW())",
            (
                site_id,
                data.get("is_up", False),
                data.get("status_code"),
                data.get("response_time_ms"),
            ),
        )
    except Exception as e:
        print("Failed to save uptime history: {}".format(e))


# === Async scan jobs ===
_jobs = {}
_JOBS_MAX = 100


def _start_async_scan(scan_fn, url, scan_type, extra_args=None):
    """Start a scan in a background thread, return job ID."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "url": url, "type": scan_type, "started_at": time.time()}
    # Evict old completed jobs
    if len(_jobs) > _JOBS_MAX:
        now = time.time()
        old = [k for k, v in _jobs.items() if v["status"] != "running" and now - v.get("finished_at", now) > 600]
        for k in old:
            del _jobs[k]

    def _run():
        try:
            if extra_args:
                result = scan_fn(url, *extra_args)
            else:
                result = scan_fn(url)
            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["result"] = result
            _jobs[job_id]["finished_at"] = time.time()
            # Persist to history
            if scan_type in ("scan", "deep-scan", "full-scan"):
                _save_scan_history(url, scan_type, result if isinstance(result, dict) else {})
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["finished_at"] = time.time()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return job_id


# === Load HTML template ===
template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
if os.path.exists(template_path):
    with open(template_path) as f:
        HTML_TEMPLATE = f.read()
else:
    HTML_TEMPLATE = "<h1>Template not found</h1>"


# ===================== AUTH ROUTES (Cognito) =====================

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    try:
        from cognito_auth import signup as cognito_signup
        result, status = cognito_signup(data)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    try:
        from cognito_auth import login as cognito_login
        result, status = cognito_login(data)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/verify", methods=["POST"])
def verify():
    data = request.get_json() or {}
    try:
        from cognito_auth import verify_email
        result, status = verify_email(data)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/resend-code", methods=["POST"])
def resend_code():
    data = request.get_json() or {}
    try:
        from cognito_auth import resend_code as cognito_resend
        result, status = cognito_resend(data)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    try:
        from cognito_auth import forgot_password as cognito_forgot
        result, status = cognito_forgot(data)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    try:
        from cognito_auth import reset_password as cognito_reset
        result, status = cognito_reset(data)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/me")
def me():
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    subs = _load_subs()
    my_sub = subs.get(user["email"], {})
    return jsonify({"status": "success", "email": user["email"], "name": user["name"], "subscription": my_sub})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    return jsonify({"status": "success"})


# ===================== SUBSCRIPTION ROUTES =====================

@app.route("/api/subscribe", methods=["POST"])
def subscribe():
    user = _auth_user(request)
    if not user:
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
    sub_data = {
        "name": user["name"],
        "channels": channels,
        "sites": sites,
        "frequency": frequency,
        "channel_config": channel_config,
        "active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_sub(user["email"], sub_data)
    return jsonify({"status": "success", "message": "Subscribed to {} reports via {}".format(frequency, ", ".join(channels))})


@app.route("/api/unsubscribe", methods=["POST"])
def unsubscribe():
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Login required"}), 401
    subs = _load_subs()
    if user["email"] in subs:
        sub = subs[user["email"]]
        sub["active"] = False
        sub["updated_at"] = datetime.now().isoformat()
        _save_sub(user["email"], sub)
    return jsonify({"status": "success", "message": "Unsubscribed from daily reports"})


@app.route("/api/subscription")
def get_subscription():
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Login required"}), 401
    subs = _load_subs()
    my_sub = subs.get(user["email"], {})
    return jsonify({"status": "success", "subscription": my_sub})


# ===================== MONITORING ROUTES (cached + history) =====================

@app.route("/")
def index():
    resp = make_response(render_template_string(HTML_TEMPLATE))
    resp.headers["Last-Modified"] = "Tue, 18 Mar 2026 12:00:00 GMT"
    resp.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    resp.headers["ETag"] = '"monitor-v4.0"'
    resp.headers["Link"] = "<https://api.ai1stseo.com>; rel=preconnect, <https://api.ai1stseo.com>; rel=dns-prefetch"
    return resp


@app.route("/llms.txt")
def llms_txt():
    txt = (
        "# AI 1st SEO Site Monitor\n"
        "# https://monitor.ai1stseo.com\n"
        "# AI crawler guidance\n\n"
        "User-agent: *\nAllow: /\n\n"
        "# About\n"
        "name: AI 1st SEO Site Monitor\n"
        "description: Free AI-powered site monitoring dashboard.\n"
        "url: https://monitor.ai1stseo.com\n"
        "author: AI 1st SEO\n"
        "contact: support@ai1stseo.com\n\n"
        "# Related\n"
        "main-site: https://ai1stseo.com\n"
        "seo-audit: https://seoaudit.ai1stseo.com\n"
        "guides: https://ai1stseo.com/guides\n"
    )
    resp = make_response(txt)
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    return resp


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "site-monitor", "version": "4.0",
                     "features": ["cognito-auth", "subscriptions", "caching",
                                  "deep-scan", "scan-history", "async-scans", "daily-reports"]})


@app.route("/api/scan")
def scan():
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        def _do_scan():
            seo = scan_site(url)
            up = check_uptime(url)
            _save_scan_history(url, "scan", seo)
            _save_uptime_history(url, up)
            # Persist to RDS
            if seo.get("score"):
                _persist_to_rds("/api/data/audits", {"url": url, "overall_score": seo.get("score"), "total_checks": seo.get("total_checks", 0), "passed_checks": seo.get("passed_checks", 0)}, token)
            if not up.get("is_up", True):
                _fire_webhook_event("uptime.down", {"url": url, "status_code": up.get("status_code")})
            return {"seo": seo, "uptime": up, "url": url}
        return jsonify(_cached_call("scan:" + url, _do_scan))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/uptime")
def uptime():
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        def _do():
            result = check_uptime(url)
            _save_uptime_history(url, result)
            return result
        return jsonify(_cached_call("uptime:" + url, _do))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/content")
def content():
    """Content monitor - NOT cached (needs fresh change detection)."""
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        result = check_content_changes(url)
        if result.get("changes_detected"):
            _fire_webhook_event("content.changed", {"url": url, "changes": result.get("changes", [])})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai-visibility")
def ai_visibility():
    domain = request.args.get("domain", "https://ai1stseo.com")
    brand = request.args.get("brand", "AI 1st SEO")
    try:
        result = _cached_call("ai:" + domain + brand, check_ai_visibility, domain, brand)
        # Persist AI visibility to RDS
        if isinstance(result, dict) and result.get("visibility_score") is not None:
            _persist_to_rds("/api/data/ai-visibility", {
                "url": domain,
                "visibility_score": result.get("visibility_score"),
                "citation_count": result.get("citation_count", 0),
            }, token)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/transaction")
def transaction():
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        return jsonify(_cached_call("tx:" + url, test_critical_paths, url))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/full-scan")
def full_scan():
    url = request.args.get("url", "https://ai1stseo.com")
    brand = request.args.get("brand", "AI 1st SEO")
    try:
        def _do():
            seo = scan_site(url)
            up = check_uptime(url)
            _save_scan_history(url, "full-scan", seo)
            _save_uptime_history(url, up)
            return {
                "seo": seo,
                "uptime": up,
                "content": check_content_changes(url),
                "ai": check_ai_visibility(url, brand),
                "transaction": test_critical_paths(url),
                "url": url,
            }
        return jsonify(_cached_call("full:" + url, _do))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/deep-scan")
def deep_scan():
    """Full 216-check deep scan. Sync for quick results, or use /api/async-deep-scan."""
    url = request.args.get("url", "https://ai1stseo.com")
    try:
        def _do():
            result = deep_scan_site(url)
            _save_scan_history(url, "deep-scan", result)
            return result
        result = _cached_call("deep:" + url, _do)
        # Persist deep scan to RDS
        if isinstance(result, dict) and result.get("overall_score"):
            _persist_to_rds("/api/data/audits", {
                "url": url, "overall_score": result.get("overall_score"),
                "technical_score": result.get("technical_score"),
                "onpage_score": result.get("onpage_score"),
                "content_score": result.get("content_score"),
                "total_checks": result.get("total_checks", 0),
                "passed_checks": result.get("passed_checks", 0),
            }, token)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ASYNC SCAN ROUTES =====================

@app.route("/api/async-deep-scan", methods=["POST"])
def async_deep_scan():
    """Start a deep scan in the background, return job ID immediately."""
    data = request.get_json() or {}
    url = data.get("url", request.args.get("url", "https://ai1stseo.com"))
    job_id = _start_async_scan(deep_scan_site, url, "deep-scan")
    return jsonify({"status": "accepted", "job_id": job_id, "poll_url": "/api/scan-status/{}".format(job_id)})


@app.route("/api/async-full-scan", methods=["POST"])
def async_full_scan():
    """Start a full scan in the background, return job ID immediately."""
    data = request.get_json() or {}
    url = data.get("url", request.args.get("url", "https://ai1stseo.com"))
    brand = data.get("brand", "AI 1st SEO")

    def _full(u):
        seo = scan_site(u)
        up = check_uptime(u)
        _save_scan_history(u, "full-scan", seo)
        _save_uptime_history(u, up)
        return {
            "seo": seo, "uptime": up,
            "content": check_content_changes(u),
            "ai": check_ai_visibility(u, brand),
            "transaction": test_critical_paths(u),
            "url": u,
        }

    job_id = _start_async_scan(_full, url, "full-scan")
    return jsonify({"status": "accepted", "job_id": job_id, "poll_url": "/api/scan-status/{}".format(job_id)})


@app.route("/api/scan-status/<job_id>")
def scan_status(job_id):
    """Poll for async scan result."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    if job["status"] == "running":
        elapsed = time.time() - job["started_at"]
        return jsonify({"status": "running", "elapsed_seconds": round(elapsed, 1)})
    if job["status"] == "error":
        return jsonify({"status": "error", "message": job.get("error", "Unknown error")}), 500
    return jsonify({"status": "complete", "result": job["result"]})


# ===================== SCAN HISTORY API =====================

@app.route("/api/history")
def scan_history():
    """Return scan history for a URL. Supports ?url=...&limit=...&offset=..."""
    url = request.args.get("url", "https://ai1stseo.com")
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    try:
        from db import query
        rows = query(
            "SELECT id, url, overall_score, total_checks, passed_checks, "
            "load_time_ms, created_at FROM audits "
            "WHERE project_id = %s AND url = %s "
            "ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (DEFAULT_PROJECT_ID, url, limit, offset),
        )
        return jsonify({"status": "success", "url": url, "scans": rows, "limit": limit, "offset": offset})
    except Exception as e:
        return jsonify({"status": "error", "message": "History unavailable: {}".format(e)}), 500


@app.route("/api/history/uptime")
def uptime_history():
    """Return uptime check history for a URL."""
    url = request.args.get("url", "https://ai1stseo.com")
    limit = min(int(request.args.get("limit", 100)), 500)
    try:
        from db import query
        rows = query(
            "SELECT uc.id, uc.is_up, uc.status_code, uc.response_time_ms, uc.checked_at "
            "FROM uptime_checks uc "
            "JOIN monitored_sites ms ON uc.site_id = ms.id "
            "WHERE ms.project_id = %s AND ms.url = %s "
            "ORDER BY uc.checked_at DESC LIMIT %s",
            (DEFAULT_PROJECT_ID, url, limit),
        )
        return jsonify({"status": "success", "url": url, "checks": rows, "limit": limit})
    except Exception as e:
        return jsonify({"status": "error", "message": "Uptime history unavailable: {}".format(e)}), 500


@app.route("/api/history/summary")
def history_summary():
    """Return a summary of recent scan trends for a URL."""
    url = request.args.get("url", "https://ai1stseo.com")
    days = min(int(request.args.get("days", 30)), 90)
    try:
        from db import query
        scores = query(
            "SELECT overall_score, created_at FROM audits "
            "WHERE project_id = %s AND url = %s "
            "AND created_at >= NOW() - INTERVAL \'{} days\' "
            "ORDER BY created_at ASC".format(days),
            (DEFAULT_PROJECT_ID, url),
        )
        uptime_stats = query(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN uc.is_up THEN 1 ELSE 0 END) as up_count, "
            "AVG(uc.response_time_ms) as avg_response "
            "FROM uptime_checks uc "
            "JOIN monitored_sites ms ON uc.site_id = ms.id "
            "WHERE ms.project_id = %s AND ms.url = %s "
            "AND uc.checked_at >= NOW() - INTERVAL \'{} days\'".format(days),
            (DEFAULT_PROJECT_ID, url),
        )
        up_row = uptime_stats[0] if uptime_stats else {}
        total = up_row.get("total", 0) or 0
        up_count = up_row.get("up_count", 0) or 0
        return jsonify({
            "status": "success",
            "url": url,
            "days": days,
            "score_trend": scores,
            "uptime_pct": round((up_count / total) * 100, 2) if total else None,
            "avg_response_ms": round(float(up_row.get("avg_response", 0) or 0), 1),
            "total_checks": total,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": "Summary unavailable: {}".format(e)}), 500


# ===================== SCAN ERROR TRACKING =====================

@app.route("/api/scan-errors", methods=["GET"])
def scan_errors():
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    hours = request.args.get("hours", 24, type=int)
    errors = _get_recent_errors(hours=hours)
    return jsonify({
        "status": "success",
        "errors": [dict(e) for e in errors],
        "count": len(errors),
        "hours": hours,
    })


@app.route("/api/scan-errors/resolve", methods=["POST"])
def resolve_scan_errors():
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    try:
        from db import execute
        resolved = execute(
            "UPDATE scan_errors SET resolved = true "
            "WHERE project_id = %s AND resolved = false",
            (DEFAULT_PROJECT_ID,),
        )
        return jsonify({"status": "success", "resolved": resolved})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ===================== DAILY REPORT SENDER =====================

def send_daily_reports():
    """Called by scheduler / EventBridge - sends reports to all active subscribers."""
    subs = _load_subs()
    sent = 0
    recent_errors = _get_recent_errors(hours=24)
    for email, sub in subs.items():
        if not sub.get("active", False):
            continue
        try:
            report_parts = []
            for site_url in sub.get("sites", []):
                try:
                    seo = scan_site(site_url)
                    up = check_uptime(site_url)
                    _save_scan_history(site_url, "daily_report", seo)
                    _save_uptime_history(site_url, up)
                    report_parts.append(
                        "=== {} ===\n"
                        "SEO Score: {}/100\n"
                        "Status: {}\n"
                        "Response: {}ms\n"
                        "Critical Issues: {}\n".format(
                            site_url,
                            seo.get("score", "N/A"),
                            "UP" if up.get("is_up") else "DOWN",
                            up.get("response_time_ms", "N/A"),
                            len(seo.get("critical_issues", [])),
                        )
                    )
                except Exception as e:
                    err_msg = str(e)
                    _log_scan_error(site_url, "daily_report_scan", err_msg, source="daily_report")
                    report_parts.append(
                        "=== {} ===\n"
                        "ERROR: Scan failed - {}\n".format(site_url, err_msg[:200])
                    )
            error_section = ""
            if recent_errors:
                error_lines = []
                for err in recent_errors[:10]:
                    error_lines.append("  - {} | {} | {}".format(
                        err.get("url", "unknown"),
                        err.get("scan_type", "unknown"),
                        str(err.get("error_message", ""))[:100],
                    ))
                error_section = (
                    "\n--- SCAN ERRORS (last 24h) ---\n"
                    "{} error(s) detected:\n{}\n".format(
                        len(recent_errors), "\n".join(error_lines)
                    )
                )
            report = (
                "Daily Site Monitor Report - {}\n"
                "Subscriber: {}\n\n{}{}".format(
                    datetime.now().strftime("%Y-%m-%d"),
                    sub.get("name", email),
                    "\n".join(report_parts),
                    error_section,
                )
            )
            for channel in sub.get("channels", []):
                if channel == "email":
                    send_alert(report, channel="email", severity="info", recipient=email)
                else:
                    send_alert(report, channel=channel, severity="info")
            sent += 1
        except Exception as e:
            print("Failed to send report to {}: {}".format(email, e))
    return {"sent": sent, "total_subscribers": len([s for s in subs.values() if s.get("active")]), "errors_flagged": len(recent_errors)}


def _log_scan_error(url, scan_type, error_msg, source="scheduled"):
    """Log a scan error to the scan_errors table in RDS."""
    try:
        from db import execute
        execute(
            "INSERT INTO scan_errors (project_id, url, scan_type, error_message, source) "
            "VALUES (%s, %s, %s, %s, %s)",
            (DEFAULT_PROJECT_ID, url, scan_type, str(error_msg)[:2000], source),
        )
    except Exception as e:
        print("Failed to log scan error: {}".format(e))


def _get_recent_errors(hours=24):
    """Get unresolved scan errors from the last N hours."""
    try:
        from db import query
        rows = query(
            "SELECT url, scan_type, error_message, source, created_at "
            "FROM scan_errors WHERE project_id = %s AND resolved = false "
            "AND created_at >= NOW() - INTERVAL '24 hours' "
            "ORDER BY created_at DESC",
            (DEFAULT_PROJECT_ID,),
        )
        return rows
    except Exception:
        return []


def run_scheduled_scan():
    """Called by EventBridge every 6 hours - scans all monitored sites and saves history."""
    try:
        from db import query
        sites = query(
            "SELECT url FROM monitored_sites WHERE project_id = %s AND is_active = true",
            (DEFAULT_PROJECT_ID,),
        )
    except Exception:
        sites = [{"url": "https://ai1stseo.com"}]
    scanned = 0
    errors = []
    for site in sites:
        url = site["url"]
        try:
            seo = scan_site(url)
            up = check_uptime(url)
            _save_scan_history(url, "scheduled", seo)
            _save_uptime_history(url, up)
            scanned += 1
        except Exception as e:
            err_msg = str(e)
            print("Scheduled scan failed for {}: {}".format(url, err_msg))
            _log_scan_error(url, "scheduled_scan", err_msg)
            errors.append({"url": url, "error": err_msg})
    return {"scanned": scanned, "total_sites": len(sites), "errors": errors}


@app.route("/api/send-report-now", methods=["POST"])
def send_report_now():
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Login required"}), 401
    subs = _load_subs()
    my_sub = subs.get(user["email"])
    if not my_sub or not my_sub.get("active"):
        return jsonify({"status": "error", "message": "No active subscription. Subscribe first."}), 400
    try:
        report_parts = []
        for site_url in my_sub.get("sites", []):
            seo = scan_site(site_url)
            up = check_uptime(site_url)
            report_parts.append(
                "=== {} ===\n"
                "SEO Score: {}/100\n"
                "Status: {}\n"
                "Response: {}ms\n"
                "Critical Issues: {}\n".format(
                    site_url,
                    seo.get("score", "N/A"),
                    "UP" if up.get("is_up") else "DOWN",
                    up.get("response_time_ms", "N/A"),
                    len(seo.get("critical_issues", [])),
                )
            )
        report = (
            "Site Monitor Report - {}\n"
            "Requested by: {}\n\n{}".format(
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                my_sub.get("name", user["email"]),
                "\n".join(report_parts),
            )
        )
        sent_to = []
        for channel in my_sub.get("channels", []):
            if channel == "email":
                send_alert(report, channel=channel, severity="info", recipient=user["email"])
            else:
                send_alert(report, channel=channel, severity="info")
            sent_to.append(channel)
        return jsonify({"status": "success", "message": "Report sent via {}".format(", ".join(sent_to))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ===================== EMAIL STATUS ROUTES =====================

@app.route("/api/email-status")
def email_status():
    """Check email/notification channel configuration."""
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Login required"}), 401
    channels = get_channel_status()
    return jsonify({"status": "success", "channels": channels})


@app.route("/api/test-email", methods=["POST"])
def test_email():
    """Send a test email to the authenticated user."""
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Login required"}), 401
    try:
        result = send_alert(
            "This is a test email from AI 1st SEO Site Monitor.\n\n"
            "If you received this, email notifications are working correctly.\n\n"
            "- Site Monitor (monitor.ai1stseo.com)",
            channel="email",
            severity="info",
            recipient=user["email"],
        )
        email_result = result.get("email", {})
        if email_result.get("success"):
            return jsonify({"status": "success",
                            "message": "Test email sent to {}".format(user["email"]),
                            "provider": email_result.get("provider")})
        else:
            return jsonify({"status": "error",
                            "message": "Email send failed: {}".format(email_result.get("error", "unknown"))}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ===================== AGENT CHAT ROUTE =====================

@app.route("/api/chat", methods=["POST"])
def agent_chat():
    user = _auth_user(request)
    if not user:
        return jsonify({"status": "error", "message": "Login required"}), 401
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"status": "error", "message": "Message required"}), 400
    try:
        from tools.conversation_handler import handle_message
        response = handle_message(user["email"], message)
        return jsonify({"status": "success", "response": response})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=False)
