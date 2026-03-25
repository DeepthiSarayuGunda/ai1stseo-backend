"""
Admin Dashboard API — Backend endpoints for the admin dashboard.
All endpoints require admin role via require_admin decorator.
"""
from flask import Blueprint, jsonify, request
from auth import require_admin, require_auth
from database import query, query_one, execute

admin_bp = Blueprint('admin', __name__)

DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


@admin_bp.route('/api/admin/overview', methods=['GET'])
@require_admin
def admin_overview():
    """Top-level stats for the admin dashboard."""
    try:
        users = query_one("SELECT count(*) as total FROM users WHERE project_id = %s", (DEFAULT_PROJECT_ID,))
        new_7d = query_one(
            "SELECT count(*) as total FROM users WHERE project_id = %s AND created_at >= NOW() - INTERVAL '7 days'",
            (DEFAULT_PROJECT_ID,),
        )
        active_24h = query_one(
            "SELECT count(*) as total FROM users WHERE project_id = %s AND last_login >= NOW() - INTERVAL '24 hours'",
            (DEFAULT_PROJECT_ID,),
        )
        total_scans = query_one("SELECT count(*) as total FROM audits WHERE project_id = %s", (DEFAULT_PROJECT_ID,))
        scans_7d = query_one(
            "SELECT count(*) as total FROM audits WHERE project_id = %s AND created_at >= NOW() - INTERVAL '7 days'",
            (DEFAULT_PROJECT_ID,),
        )
        avg_score = query_one(
            "SELECT ROUND(AVG(overall_score), 1) as avg FROM audits WHERE project_id = %s AND overall_score IS NOT NULL",
            (DEFAULT_PROJECT_ID,),
        )
        errors = query_one(
            "SELECT count(*) as total FROM scan_errors WHERE project_id = %s AND resolved = false",
            (DEFAULT_PROJECT_ID,),
        )
        monitored = query_one(
            "SELECT count(*) as total FROM monitored_sites WHERE project_id = %s AND is_active = true",
            (DEFAULT_PROJECT_ID,),
        )
        return jsonify({
            'status': 'success',
            'users': {
                'total': users['total'] if users else 0,
                'new_7d': new_7d['total'] if new_7d else 0,
                'active_24h': active_24h['total'] if active_24h else 0,
            },
            'scans': {
                'total': total_scans['total'] if total_scans else 0,
                'last_7d': scans_7d['total'] if scans_7d else 0,
                'avg_score': float(avg_score['avg']) if avg_score and avg_score['avg'] else 0,
            },
            'errors': {
                'unresolved': errors['total'] if errors else 0,
            },
            'monitoring': {
                'active_sites': monitored['total'] if monitored else 0,
            },
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_users():
    """Paginated user list with last login, plan, scan count."""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    try:
        rows = query(
            "SELECT u.id, u.email, u.name, u.role, u.created_at, u.last_login, "
            "(SELECT count(*) FROM audits a WHERE a.created_by = u.id) as scan_count "
            "FROM users u WHERE u.project_id = %s "
            "ORDER BY u.created_at DESC LIMIT %s OFFSET %s",
            (DEFAULT_PROJECT_ID, limit, offset),
        )
        total = query_one("SELECT count(*) as total FROM users WHERE project_id = %s", (DEFAULT_PROJECT_ID,))
        return jsonify({
            'status': 'success',
            'users': [dict(r) for r in rows],
            'total': total['total'] if total else 0,
            'limit': limit,
            'offset': offset,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/users/<user_id>/role', methods=['PUT'])
@require_admin
def admin_set_role(user_id):
    """Set a user's role (admin or member)."""
    data = request.get_json()
    new_role = data.get('role', '').strip().lower()
    if new_role not in ('admin', 'member'):
        return jsonify({'error': 'Role must be admin or member'}), 400
    try:
        updated = execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        if updated == 0:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({'status': 'success', 'role': new_role})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/usage', methods=['GET'])
@require_admin
def admin_usage():
    """Scan volume over time for charts."""
    days = request.args.get('days', 30, type=int)
    try:
        daily_scans = query(
            "SELECT DATE(created_at) as date, count(*) as scans, "
            "ROUND(AVG(overall_score), 1) as avg_score "
            "FROM audits WHERE project_id = %s "
            "AND created_at >= NOW() - INTERVAL '{} days' "
            "GROUP BY DATE(created_at) ORDER BY date".format(days),
            (DEFAULT_PROJECT_ID,),
        )
        top_urls = query(
            "SELECT url, count(*) as scan_count, ROUND(AVG(overall_score), 1) as avg_score "
            "FROM audits WHERE project_id = %s "
            "AND created_at >= NOW() - INTERVAL '{} days' "
            "GROUP BY url ORDER BY scan_count DESC LIMIT 10".format(days),
            (DEFAULT_PROJECT_ID,),
        )
        return jsonify({
            'status': 'success',
            'daily_scans': [dict(r) for r in daily_scans],
            'top_urls': [dict(r) for r in top_urls],
            'days': days,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/errors', methods=['GET'])
@require_admin
def admin_errors():
    """Scan errors dashboard."""
    hours = request.args.get('hours', 48, type=int)
    try:
        errors = query(
            "SELECT id, url, scan_type, error_message, source, resolved, created_at "
            "FROM scan_errors WHERE project_id = %s "
            "AND created_at >= NOW() - INTERVAL '{} hours' "
            "ORDER BY created_at DESC LIMIT 100".format(hours),
            (DEFAULT_PROJECT_ID,),
        )
        return jsonify({
            'status': 'success',
            'errors': [dict(r) for r in errors],
            'count': len(errors),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/health', methods=['GET'])
@require_admin
def admin_health():
    """System health: uptime %, error rate, avg response time."""
    try:
        uptime = query_one(
            "SELECT "
            "ROUND(100.0 * SUM(CASE WHEN uc.is_up THEN 1 ELSE 0 END) / NULLIF(count(*), 0), 1) as uptime_pct, "
            "ROUND(AVG(uc.response_time_ms), 0) as avg_response_ms, "
            "count(*) as total_checks "
            "FROM uptime_checks uc "
            "JOIN monitored_sites ms ON uc.site_id = ms.id "
            "WHERE ms.project_id = %s AND uc.checked_at >= NOW() - INTERVAL '24 hours'",
            (DEFAULT_PROJECT_ID,),
        )
        error_rate = query_one(
            "SELECT count(*) as errors_24h FROM scan_errors "
            "WHERE project_id = %s AND created_at >= NOW() - INTERVAL '24 hours'",
            (DEFAULT_PROJECT_ID,),
        )
        return jsonify({
            'status': 'success',
            'uptime_pct': float(uptime['uptime_pct']) if uptime and uptime['uptime_pct'] else 100.0,
            'avg_response_ms': int(uptime['avg_response_ms']) if uptime and uptime['avg_response_ms'] else 0,
            'total_checks_24h': uptime['total_checks'] if uptime else 0,
            'errors_24h': error_rate['errors_24h'] if error_rate else 0,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/ai-costs', methods=['GET'])
@require_admin
def admin_ai_costs():
    """AI provider usage and estimated costs."""
    days = request.args.get('days', 30, type=int)
    try:
        by_provider = query(
            "SELECT provider, model, count(*) as calls, "
            "SUM(input_tokens_est) as input_tokens, "
            "SUM(output_tokens_est) as output_tokens, "
            "ROUND(SUM(estimated_cost_usd)::numeric, 4) as total_cost, "
            "ROUND(AVG(latency_ms)::numeric, 0) as avg_latency_ms, "
            "SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes, "
            "SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures "
            "FROM ai_usage_log WHERE created_at >= NOW() - INTERVAL '{} days' "
            "GROUP BY provider, model ORDER BY calls DESC".format(days),
            (),
        )
        daily = query(
            "SELECT DATE(created_at) as date, provider, count(*) as calls, "
            "ROUND(SUM(estimated_cost_usd)::numeric, 4) as cost "
            "FROM ai_usage_log WHERE created_at >= NOW() - INTERVAL '{} days' "
            "GROUP BY DATE(created_at), provider ORDER BY date".format(days),
            (),
        )
        by_trigger = query(
            "SELECT triggered_by, count(*) as calls, "
            "ROUND(SUM(estimated_cost_usd)::numeric, 4) as cost "
            "FROM ai_usage_log WHERE created_at >= NOW() - INTERVAL '{} days' "
            "GROUP BY triggered_by ORDER BY calls DESC".format(days),
            (),
        )
        return jsonify({
            'status': 'success',
            'by_provider': [dict(r) for r in by_provider],
            'daily': [dict(r) for r in daily],
            'by_trigger': [dict(r) for r in by_trigger],
            'days': days,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/metrics', methods=['GET'])
@require_admin
def admin_metrics_history():
    """Historical admin metrics from the daily aggregation table."""
    days = request.args.get('days', 30, type=int)
    try:
        rows = query(
            "SELECT * FROM admin_metrics "
            "WHERE metric_date >= CURRENT_DATE - INTERVAL '{} days' "
            "ORDER BY metric_date DESC".format(days),
            (),
        )
        return jsonify({
            'status': 'success',
            'metrics': [dict(r) for r in rows],
            'days': days,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/me', methods=['GET'])
@require_auth
def admin_me():
    """Return current user's role — used by frontend to decide admin access."""
    user = request.cognito_user
    return jsonify({
        'status': 'success',
        'email': user.get('email', ''),
        'role': user.get('role', 'member'),
        'name': user.get('name', ''),
    })
