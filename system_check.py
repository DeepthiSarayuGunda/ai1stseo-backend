"""
system_check.py
Standalone system health check — verifies all modules are wired and operational.

Can run in two modes:
  1. In-process (no server needed):  python system_check.py
  2. Against live server:            python system_check.py http://127.0.0.1:5001

In-process mode uses Flask test client. Live mode uses HTTP requests.
"""

import json
import sys


def run_system_check(base_url=None):
    """Check all system components. Returns (pass_count, fail_count)."""

    results = []

    def check(name, fn):
        try:
            ok, detail = fn()
            status = "PASS" if ok else "FAIL"
            results.append((name, status, detail))
            print(f"  [{status}] {name}: {detail}")
        except Exception as e:
            results.append((name, "FAIL", str(e)))
            print(f"  [FAIL] {name}: {e}")

    print()
    print("=" * 56)
    print("  SYSTEM CHECK")
    print("=" * 56)

    if base_url:
        _check_live(base_url, check)
    else:
        _check_in_process(check)

    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")

    print()
    print(f"  Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("  ALL SYSTEMS OPERATIONAL")
    else:
        print("  SOME SYSTEMS NEED ATTENTION")
    print()

    return passed, failed


def _check_in_process(check):
    """Run checks using Flask test client (no server needed)."""
    print("  Mode: in-process (Flask test client)\n")

    # 1. Publishing API importable
    def check_publish_api():
        from social_publishing.api import publish_bp
        return True, f"Blueprint '{publish_bp.name}' at {publish_bp.url_prefix}"
    check("Publishing API module", check_publish_api)

    # 2. Queue module
    def check_queue():
        from social_publishing.queue import get_queue_status, enqueue, flush_queue
        return True, "enqueue/flush/status importable"
    check("Queue module", check_queue)

    # 3. Duplicate detector
    def check_dup():
        from social_publishing.duplicate_detector import generate_content_hash, is_duplicate, store_hash
        h = generate_content_hash({"text": "system_check"})
        return bool(h), f"hash={h[:16]}..."
    check("Duplicate detector", check_dup)

    # 4. Content bridge
    def check_bridge():
        from social_publishing.content_bridge import on_content_generated, detect_content_type
        ct = detect_content_type({"caption": "test", "image_url": "http://x.png"})
        return ct == "text_with_image", f"content_type={ct}"
    check("Content bridge", check_bridge)

    # 5. Video generator
    def check_video():
        from social_publishing.video_generator import generate_video
        r = generate_video("SEO tips")
        return r.get("success"), f"script={r.get('word_count', 0)} words"
    check("Video generator", check_video)

    # 6. Visitor tracking
    def check_tracker():
        from visitor_tracking.tracker_api import track_bp
        return True, f"Blueprint '{track_bp.name}' at {track_bp.url_prefix}"
    check("Visitor tracking module", check_tracker)

    # 7. Formatter
    def check_formatter():
        from social_publishing.formatter import format_for_platform
        r = format_for_platform("Hello world! #test", "twitter")
        return bool(r.get("text")), f"twitter format ok"
    check("Content formatter", check_formatter)

    # 8. Post logger
    def check_logger():
        from social_publishing.post_logger import log_post, get_logs
        return True, "log_post/get_logs importable"
    check("Post logger", check_logger)

    # 9. Flask app integration
    def check_flask():
        from flask import Flask
        from social_publishing.api import register_blueprint as reg_pub
        from visitor_tracking.tracker_api import register_blueprint as reg_track

        app = Flask(__name__)
        reg_pub(app)
        reg_track(app)

        routes = [r.rule for r in app.url_map.iter_rules() if r.rule.startswith("/api/")]
        publish_routes = [r for r in routes if "/publish/" in r]
        track_routes = [r for r in routes if "/track/" in r]
        return len(publish_routes) > 0 and len(track_routes) > 0, \
            f"{len(publish_routes)} publish + {len(track_routes)} track endpoints"
    check("Flask route registration", check_flask)

    # 10. Endpoint response test
    def check_endpoints():
        from flask import Flask
        from social_publishing.api import register_blueprint as reg_pub
        from visitor_tracking.tracker_api import register_blueprint as reg_track

        app = Flask(__name__)
        reg_pub(app)
        reg_track(app)

        with app.test_client() as c:
            # Tracking endpoints are public (no auth)
            r1 = c.post("/api/track/visit", json={"page": "/system-check"})
            r2 = c.get("/api/track/stats")

            visit_ok = r1.status_code == 200
            stats_ok = r2.status_code == 200

            # Publishing endpoints require auth — 401 is correct
            r3 = c.post("/api/publish/control/pause", json={})
            pause_ok = r3.status_code == 401  # auth required = endpoint exists

        return visit_ok and stats_ok and pause_ok, \
            f"visit={r1.status_code} stats={r2.status_code} pause={r3.status_code}(auth)"
    check("Endpoint responses", check_endpoints)


def _check_live(base_url, check):
    """Run checks against a live server using HTTP requests."""
    import requests

    print(f"  Mode: live server ({base_url})\n")

    def _get(path):
        return requests.get(f"{base_url}{path}", json={}, timeout=30)

    def _post(path, data=None):
        return requests.post(f"{base_url}{path}", json=data or {},
                             headers={"Content-Type": "application/json"}, timeout=30)

    # 1. Server reachable
    def check_server():
        r = _get("/")
        return r.status_code in (200, 404), f"HTTP {r.status_code}"
    check("Server reachable", check_server)

    # 2. Visitor tracking — POST visit
    def check_visit():
        r = _post("/api/track/visit", {"page": "/system-check"})
        d = r.json()
        return r.status_code == 200 and d.get("success"), f"visitor_id={d.get('visitor_id')}"
    check("POST /api/track/visit", check_visit)

    # 3. Visitor tracking — GET stats
    def check_stats():
        r = _get("/api/track/stats")
        d = r.json()
        return r.status_code == 200 and d.get("success"), f"total={d.get('total_visits')}"
    check("GET /api/track/stats", check_stats)

    # 4. Publishing dashboard (auth required — 401 = endpoint exists)
    def check_dashboard():
        r = _get("/api/publish/dashboard/summary")
        return r.status_code == 401, f"HTTP {r.status_code} (auth required = reachable)"
    check("GET /api/publish/dashboard/summary", check_dashboard)

    # 5. Publishing control (auth required)
    def check_control():
        r = _post("/api/publish/control/pause")
        return r.status_code == 401, f"HTTP {r.status_code} (auth required = reachable)"
    check("POST /api/publish/control/pause", check_control)

    # 6. Queue enqueue (auth required)
    def check_queue():
        r = _post("/api/publish/queue/enqueue", {"text": "check"})
        return r.status_code == 401, f"HTTP {r.status_code} (auth required = reachable)"
    check("POST /api/publish/queue/enqueue", check_queue)

    # 7. System status (auth required)
    def check_sys_status():
        r = _get("/api/publish/dashboard/system-status")
        return r.status_code == 401, f"HTTP {r.status_code} (auth required = reachable)"
    check("GET /api/publish/dashboard/system-status", check_sys_status)

    # 8. Static assets
    def check_static():
        r = _get("/assets/visitor-tracker.js")
        return r.status_code == 200, f"HTTP {r.status_code}, {len(r.content)} bytes"
    check("GET /assets/visitor-tracker.js", check_static)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    passed, failed = run_system_check(base_url=url)
    sys.exit(0 if failed == 0 else 1)
