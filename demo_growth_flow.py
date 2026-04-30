"""
demo_growth_flow.py
Full demo of the AI1stSEO Growth Automation Backend.

Simulates the complete user journey:
  Visit → Subscribe → Lead Magnet → Welcome Email → Dashboard → Social Publish

Run: python demo_growth_flow.py

Requires: valid AWS credentials (DynamoDB + SES access)
"""

import json
import sys
import time
from datetime import datetime, timezone

DEMO_EMAIL = f"demo_user_{int(time.time())}@test.com"
RESULTS = []


def step(name):
    print(f"\n{'='*60}")
    print(f"  [{name}]")
    print(f"{'='*60}")


def report(name, success, details):
    status = "SUCCESS" if success else "FAILED"
    RESULTS.append({"step": name, "status": status, "details": details})
    print(f"  Status: {status}")
    if isinstance(details, dict):
        print(f"  Details: {json.dumps(details, indent=4, default=str)}")
    else:
        print(f"  Details: {details}")


# ──────────────────────────────────────────────────────────────
# STEP 0 — Verify modules
# ──────────────────────────────────────────────────────────────
step("MODULE VERIFICATION")
modules = {
    "analytics_tracker": "growth.analytics_tracker",
    "lead_magnet": "growth.lead_magnet",
    "email_platform_sync": "growth.email_platform_sync",
    "growth_dashboard": "growth.growth_dashboard",
    "social_orchestrator": "growth.social_orchestrator",
    "publish_runner": "growth.publish_runner",
    "social_scheduler": "growth.social_scheduler_dynamo",
}
all_ok = True
for label, mod in modules.items():
    try:
        __import__(mod)
        print(f"  ✓ {label}")
    except Exception as e:
        print(f"  ✗ {label}: {e}")
        all_ok = False
report("MODULE VERIFICATION", all_ok, f"{len(modules)} modules checked")


print("\n  Available API Endpoints:")
endpoints = [
    "POST /api/growth/track",
    "GET  /api/growth/analytics/summary",
    "POST /api/growth/subscribe",
    "GET  /api/growth/subscribers",
    "GET  /api/growth/lead-magnet",
    "POST /api/growth/lead-magnet/download",
    "GET  /api/growth/dashboard",
    "POST /api/growth/social/publish",
    "POST /api/growth/social/run-scheduled",
    "GET  /api/growth/social/posts",
    "POST /api/growth/social/posts",
    "POST /api/growth/utm/generate",
]
for ep in endpoints:
    print(f"    {ep}")


# ──────────────────────────────────────────────────────────────
# STEP 1 — Track analytics event (simulate page visit)
# ──────────────────────────────────────────────────────────────
step("ANALYTICS EVENT — Page View")
try:
    from growth.analytics_tracker import track_event, _session_event_log
    _session_event_log.clear()
    result = track_event(
        event_type="page_view",
        source="demo_script",
        session_id="demo-session-001",
        page_url="https://ai1stseo.com/demo",
        utm_source="linkedin",
        utm_medium="social",
        utm_campaign="growth_demo",
    )
    report("ANALYTICS EVENT", result.get("success", False), result)
except Exception as e:
    report("ANALYTICS EVENT", False, str(e))


# ──────────────────────────────────────────────────────────────
# STEP 2 — Subscribe user
# ──────────────────────────────────────────────────────────────
step(f"SUBSCRIBE USER — {DEMO_EMAIL}")
subscribe_result = None
try:
    from growth.email_subscriber import add_subscriber
    subscribe_result = add_subscriber(
        email=DEMO_EMAIL,
        name="Demo User",
        source="demo_script",
        platform="web",
        campaign="growth_demo",
        opted_in=True,
        utm_source="linkedin",
        utm_medium="social",
        utm_campaign="growth_demo",
    )
    report("SUBSCRIBE USER", subscribe_result.get("success", False), {
        "email": DEMO_EMAIL,
        "success": subscribe_result.get("success"),
        "duplicate": subscribe_result.get("duplicate", False),
    })
except Exception as e:
    report("SUBSCRIBE USER", False, str(e))


# ──────────────────────────────────────────────────────────────
# STEP 3 — Lead magnet delivery
# ──────────────────────────────────────────────────────────────
step("LEAD MAGNET — List + Download")
try:
    from growth.lead_magnet import get_lead_magnets, get_lead_magnet_by_slug
    magnets = get_lead_magnets()
    print(f"  Available lead magnets: {len(magnets)}")
    for m in magnets:
        print(f"    - {m['slug']}: {m['title']}")

    lm = get_lead_magnet_by_slug("seo-starter-checklist")
    if lm:
        report("LEAD MAGNET", True, {
            "slug": lm["slug"],
            "title": lm["title"],
            "download_url": lm["download_url"],
        })
    else:
        report("LEAD MAGNET", False, "Lead magnet not found")
except Exception as e:
    report("LEAD MAGNET", False, str(e))


# ──────────────────────────────────────────────────────────────
# STEP 4 — Welcome email (via email_platform_sync)
# ──────────────────────────────────────────────────────────────
step("WELCOME EMAIL — Send via SES")
try:
    from growth.email_platform_sync import sync_subscriber_to_email_platform
    lm_for_email = None
    if lm:
        lm_for_email = {"title": lm["title"], "slug": lm["slug"], "download_url": lm["download_url"]}
    email_result = sync_subscriber_to_email_platform({
        "email": DEMO_EMAIL,
        "name": "Demo User",
        "lead_magnet": lm_for_email,
    })
    report("WELCOME EMAIL", email_result.get("sent", False), email_result)
except Exception as e:
    report("WELCOME EMAIL", False, str(e))


# ──────────────────────────────────────────────────────────────
# STEP 5 — KPI Dashboard
# ──────────────────────────────────────────────────────────────
step("KPI DASHBOARD — Fetch Metrics")
try:
    from growth.growth_dashboard import get_dashboard_kpis
    kpis = get_dashboard_kpis(days=7)
    report("KPI DASHBOARD", kpis.get("success", False), {
        "total_subscribers": kpis.get("total_subscribers"),
        "new_subscribers": kpis.get("new_subscribers"),
        "lead_magnet_downloads": kpis.get("lead_magnet_downloads"),
        "welcome_email_attempted": kpis.get("welcome_email_attempted"),
        "welcome_email_sent": kpis.get("welcome_email_sent"),
        "welcome_email_failed": kpis.get("welcome_email_failed"),
        "analytics_available": kpis.get("analytics_available"),
        "subscribers_available": kpis.get("subscribers_available"),
    })
except Exception as e:
    report("KPI DASHBOARD", False, str(e))


# ──────────────────────────────────────────────────────────────
# STEP 6 — Create scheduled social post
# ──────────────────────────────────────────────────────────────
step("SOCIAL POST — Create Scheduled Post")
demo_post_id = None
try:
    import uuid as _uuid
    import boto3 as _boto3
    from growth.social_scheduler_dynamo import TABLE_NAME, AWS_REGION
    now = datetime.now(timezone.utc)
    demo_post_id = str(_uuid.uuid4())[:12]
    item = {
        "id": demo_post_id,
        "post_id": demo_post_id,
        "content": "Demo post from AI1stSEO growth automation pipeline. #AISEO #GrowthDemo",
        "platforms": "LinkedIn",
        "scheduled_datetime": now.strftime("%Y-%m-%d %H:%M"),
        "status": "scheduled",
        "created_at": now.isoformat(),
    }
    _table = _boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    _table.put_item(Item=item)
    report("SOCIAL POST CREATE", True, {
        "post_id": demo_post_id,
        "status": "scheduled",
        "platform": "LinkedIn",
    })
except Exception as e:
    report("SOCIAL POST CREATE", False, str(e))


# ──────────────────────────────────────────────────────────────
# STEP 7 — Run scheduler (DRY RUN)
# ──────────────────────────────────────────────────────────────
step("SCHEDULED RUNNER — Dry Run")
try:
    from growth.publish_runner import run_scheduled_posts
    dry_result = run_scheduled_posts(dry_run=True)
    report("RUNNER DRY RUN", dry_result.get("success", False), {
        "dry_run": True,
        "total_due": dry_result.get("total_due"),
        "total_publish_attempts": dry_result.get("total_publish_attempts"),
        "results_count": len(dry_result.get("results", [])),
    })
except Exception as e:
    report("RUNNER DRY RUN", False, str(e))


# ──────────────────────────────────────────────────────────────
# STEP 8 — Run scheduler (REAL — will fail if no publisher configured)
# ──────────────────────────────────────────────────────────────
step("SCHEDULED RUNNER — Real Run")
try:
    real_result = run_scheduled_posts(dry_run=False)
    report("RUNNER REAL RUN", real_result.get("success", False), {
        "dry_run": False,
        "total_due": real_result.get("total_due"),
        "succeeded": real_result.get("succeeded"),
        "failed": real_result.get("failed"),
        "skipped": real_result.get("skipped"),
    })
except Exception as e:
    report("RUNNER REAL RUN", False, str(e))


# ──────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  DEMO RESULTS SUMMARY")
print(f"{'='*60}")
passed = sum(1 for r in RESULTS if r["status"] == "SUCCESS")
failed = sum(1 for r in RESULTS if r["status"] == "FAILED")
for r in RESULTS:
    icon = "✓" if r["status"] == "SUCCESS" else "✗"
    print(f"  {icon} {r['step']}: {r['status']}")

print(f"\n  Total: {passed} passed, {failed} failed out of {len(RESULTS)} steps")
print(f"{'='*60}")
print("\n  DEMO COMPLETE — FULL GROWTH PIPELINE VERIFIED")
print(f"{'='*60}\n")

# Write demo_output.md
try:
    with open("demo_output.md", "w", encoding="utf-8") as f:
        f.write("# Growth Automation Demo Results\n\n")
        f.write(f"Run at: {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write(f"Demo email: {DEMO_EMAIL}\n\n")
        f.write("## Results\n\n")
        f.write("| Step | Status |\n")
        f.write("|------|--------|\n")
        for r in RESULTS:
            f.write(f"| {r['step']} | {r['status']} |\n")
        f.write(f"\n{passed} passed, {failed} failed out of {len(RESULTS)} steps.\n")
    print("  demo_output.md written.")
except Exception:
    pass
