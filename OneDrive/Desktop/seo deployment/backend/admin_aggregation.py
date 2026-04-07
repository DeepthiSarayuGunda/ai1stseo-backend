"""
Admin Metrics Daily Aggregation — Triggered by EventBridge (daily at 02:00 UTC).
Populates admin_metrics table with rolled-up stats from the previous day.
"""
from database import query_one, execute
from datetime import date, timedelta

DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


def aggregate_daily_metrics(target_date=None):
    """
    Compute and upsert one row in admin_metrics for the given date.
    Defaults to yesterday if no date provided.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    d = str(target_date)

    total_users = _count("SELECT count(*) as c FROM users WHERE project_id = %s", d, cumulative=True)
    new_signups = _count(
        "SELECT count(*) as c FROM users WHERE project_id = %s AND DATE(created_at) = %s", d
    )
    active_24h = _count(
        "SELECT count(*) as c FROM users WHERE project_id = %s AND DATE(last_login) = %s", d
    )
    active_7d = _count(
        "SELECT count(*) as c FROM users WHERE project_id = %s "
        "AND last_login >= (%s::date - INTERVAL '6 days') AND last_login < (%s::date + INTERVAL '1 day')",
        d, extra_param=d
    )
    total_scans = _count(
        "SELECT count(*) as c FROM audits WHERE project_id = %s AND DATE(created_at) = %s", d
    )
    avg_score = _val(
        "SELECT ROUND(AVG(overall_score), 2) as v FROM audits "
        "WHERE project_id = %s AND DATE(created_at) = %s AND overall_score IS NOT NULL", d
    )
    total_briefs = _count(
        "SELECT count(*) as c FROM content_briefs WHERE project_id = %s AND DATE(created_at) = %s", d
    )
    total_geo = _count(
        "SELECT count(*) as c FROM geo_probes WHERE project_id = %s AND DATE(probe_timestamp) = %s", d
    )
    scan_errors = _count(
        "SELECT count(*) as c FROM scan_errors WHERE project_id = %s AND DATE(created_at) = %s", d
    )

    # AI usage from ai_usage_log
    ai_stats = query_one(
        "SELECT "
        "COALESCE(SUM(CASE WHEN provider = 'nova_lite' THEN 1 ELSE 0 END), 0) as bedrock, "
        "COALESCE(SUM(CASE WHEN provider != 'nova_lite' THEN 1 ELSE 0 END), 0) as ollama, "
        "COALESCE(SUM(estimated_cost_usd), 0) as cost "
        "FROM ai_usage_log WHERE DATE(created_at) = %s",
        (d,),
    )
    bedrock_calls = int(ai_stats['bedrock']) if ai_stats else 0
    ollama_calls = int(ai_stats['ollama']) if ai_stats else 0
    ai_cost = float(ai_stats['cost']) if ai_stats else 0.0

    # Upsert into admin_metrics
    execute(
        "INSERT INTO admin_metrics "
        "(metric_date, total_users, new_signups, active_users_24h, active_users_7d, "
        "total_scans, total_deep_scans, total_content_briefs, total_geo_probes, "
        "avg_seo_score, bedrock_calls, ollama_fallback_calls, scan_errors_count, "
        "estimated_ai_cost_usd) "
        "VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (metric_date) DO UPDATE SET "
        "total_users = EXCLUDED.total_users, new_signups = EXCLUDED.new_signups, "
        "active_users_24h = EXCLUDED.active_users_24h, active_users_7d = EXCLUDED.active_users_7d, "
        "total_scans = EXCLUDED.total_scans, total_content_briefs = EXCLUDED.total_content_briefs, "
        "total_geo_probes = EXCLUDED.total_geo_probes, avg_seo_score = EXCLUDED.avg_seo_score, "
        "bedrock_calls = EXCLUDED.bedrock_calls, ollama_fallback_calls = EXCLUDED.ollama_fallback_calls, "
        "scan_errors_count = EXCLUDED.scan_errors_count, estimated_ai_cost_usd = EXCLUDED.estimated_ai_cost_usd",
        (d, total_users, new_signups, active_24h, active_7d,
         total_scans, total_briefs, total_geo, avg_score,
         bedrock_calls, ollama_calls, scan_errors, ai_cost),
    )

    return {
        'metric_date': d,
        'total_users': total_users,
        'new_signups': new_signups,
        'total_scans': total_scans,
        'bedrock_calls': bedrock_calls,
        'ollama_calls': ollama_calls,
        'ai_cost_usd': ai_cost,
    }


def _count(sql, d, cumulative=False, extra_param=None):
    """Helper: run a count query and return the integer."""
    if cumulative:
        row = query_one(sql, (DEFAULT_PROJECT_ID,))
    elif extra_param:
        row = query_one(sql, (DEFAULT_PROJECT_ID, d, extra_param))
    else:
        row = query_one(sql, (DEFAULT_PROJECT_ID, d))
    return int(row['c']) if row and row['c'] else 0


def _val(sql, d):
    """Helper: run a query returning a single value 'v'."""
    row = query_one(sql, (DEFAULT_PROJECT_ID, d))
    return float(row['v']) if row and row['v'] else None


def lambda_handler(event, context):
    """EventBridge entry point — runs daily aggregation."""
    result = aggregate_daily_metrics()
    print("Admin metrics aggregated: {}".format(result))
    return {'statusCode': 200, 'body': result}
