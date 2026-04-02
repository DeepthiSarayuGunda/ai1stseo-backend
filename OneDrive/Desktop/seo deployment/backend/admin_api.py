"""
Admin Dashboard API — DynamoDB version.
All endpoints require admin role via require_admin decorator.
"""
from flask import Blueprint, jsonify, request
from auth import require_admin, require_auth
from dynamodb_helper import scan_table, get_item, update_item, query_index, count_items

admin_bp = Blueprint('admin', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


@admin_bp.route('/api/admin/overview', methods=['GET'])
@require_admin
def admin_overview():
    try:
        users = scan_table('ai1stseo-users', 200)
        audits = scan_table('ai1stseo-audits', 200)
        total_users = len(users)
        total_scans = len(audits)
        scores = [a.get('overall_score', 0) for a in audits if a.get('overall_score')]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        return jsonify({
            'status': 'success',
            'users': {'total': total_users, 'new_7d': 0, 'active_24h': 0},
            'scans': {'total': total_scans, 'last_7d': 0, 'avg_score': avg_score},
            'errors': {'unresolved': 0},
            'monitoring': {'active_sites': 0},
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_users():
    limit = request.args.get('limit', 50, type=int)
    try:
        users = scan_table('ai1stseo-users', limit)
        return jsonify({
            'status': 'success', 'users': users,
            'total': len(users), 'limit': limit, 'offset': 0,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/users/<user_id>/role', methods=['PUT'])
@require_admin
def admin_set_role(user_id):
    data = request.get_json()
    new_role = data.get('role', '').strip().lower()
    if new_role not in ('admin', 'member'):
        return jsonify({'error': 'Role must be admin or member'}), 400
    try:
        update_item('ai1stseo-users', {'userId': user_id}, {'role': new_role})
        return jsonify({'status': 'success', 'role': new_role})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/usage', methods=['GET'])
@require_admin
def admin_usage():
    try:
        audits = scan_table('ai1stseo-audits', 200)
        return jsonify({
            'status': 'success',
            'daily_scans': [],
            'top_urls': [],
            'total_audits': len(audits),
            'days': request.args.get('days', 30, type=int),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/errors', methods=['GET'])
@require_admin
def admin_errors():
    return jsonify({'status': 'success', 'errors': [], 'count': 0})


@admin_bp.route('/api/admin/health', methods=['GET'])
@require_admin
def admin_health():
    return jsonify({
        'status': 'success',
        'uptime_pct': 100.0, 'avg_response_ms': 0,
        'total_checks_24h': 0, 'errors_24h': 0,
        'database': 'DynamoDB (serverless)',
    })


@admin_bp.route('/api/admin/ai-costs', methods=['GET'])
@require_admin
def admin_ai_costs():
    try:
        # AI usage logs are in api-logs table with provider field
        return jsonify({
            'status': 'success',
            'by_provider': [], 'daily': [], 'by_trigger': [],
            'days': request.args.get('days', 30, type=int),
            'note': 'AI cost tracking migrated to DynamoDB — aggregation pending',
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/metrics', methods=['GET'])
@require_admin
def admin_metrics_history():
    try:
        items = scan_table('ai1stseo-admin-metrics', 30)
        return jsonify({
            'status': 'success', 'metrics': items,
            'days': request.args.get('days', 30, type=int),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/requests', methods=['GET'])
@require_admin
def admin_requests():
    try:
        logs = scan_table('ai1stseo-api-logs', 100)
        return jsonify({
            'status': 'success',
            'top_endpoints': [], 'hourly': [], 'slow_requests': [],
            'totals': {'requests': len(logs), 'avg_response_ms': 0, 'errors': 0},
            'hours': request.args.get('hours', 24, type=int),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/admin/me', methods=['GET'])
@require_auth
def admin_me():
    user = request.cognito_user
    return jsonify({
        'status': 'success',
        'email': user.get('email', ''),
        'role': user.get('role', 'member'),
        'name': user.get('name', ''),
    })
