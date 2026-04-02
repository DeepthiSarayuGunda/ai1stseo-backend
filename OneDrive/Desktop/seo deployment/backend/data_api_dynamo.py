"""
Shared Data API — DynamoDB version.
Drop-in replacement for data_api.py (PostgreSQL).
Same routes, same JSON responses, backed by DynamoDB tables.
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from dynamodb_helper import put_item, get_item, query_index, scan_table, update_item, delete_item
import json, uuid
from datetime import datetime

data_bp = Blueprint('data', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


def _get_user_id():
    if hasattr(request, 'cognito_user') and request.cognito_user:
        return request.cognito_user.get('user_id')
    return None


def _dispatch(event_type, payload):
    try:
        from webhook_api import dispatch_event
        dispatch_event(event_type, payload)
    except Exception:
        pass


# ===================== AUDITS =====================

@data_bp.route('/api/data/audits', methods=['POST'])
@require_auth
def create_audit():
    d = request.get_json() or {}
    url = d.get('url', '').strip()
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400
    try:
        item = {
            'project_id': DEFAULT_PROJECT_ID, 'url': url,
            'overall_score': d.get('overall_score'), 'technical_score': d.get('technical_score'),
            'onpage_score': d.get('onpage_score'), 'content_score': d.get('content_score'),
            'total_checks': d.get('total_checks', 0), 'passed_checks': d.get('passed_checks', 0),
            'failed_checks': d.get('failed_checks', 0), 'load_time_ms': d.get('load_time_ms'),
            'created_by': _get_user_id(),
            'checks': d.get('checks', []),
        }
        audit_id = put_item('ai1stseo-audits', item)
        _dispatch('audit.created', {'id': audit_id, 'url': url, 'overall_score': d.get('overall_score')})
        return jsonify({'status': 'success', 'id': audit_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/audits', methods=['GET'])
@require_auth
def list_audits():
    url_filter = request.args.get('url', '')
    limit = request.args.get('limit', 20, type=int)
    try:
        if url_filter:
            items = query_index('ai1stseo-audits', 'url-index', 'url', url_filter, limit)
        else:
            items = scan_table('ai1stseo-audits', limit)
        return jsonify({'status': 'success', 'audits': items})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/audits/<audit_id>', methods=['GET'])
@require_auth
def get_audit(audit_id):
    try:
        item = get_item('ai1stseo-audits', {'id': audit_id})
        if not item:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        return jsonify({'status': 'success', 'audit': item})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== GEO PROBES =====================

@data_bp.route('/api/data/geo-probes', methods=['POST'])
@require_auth
def create_geo_probe():
    d = request.get_json() or {}
    keyword = d.get('keyword', '').strip()
    ai_model = d.get('ai_model', '').strip()
    if not keyword or not ai_model:
        return jsonify({'status': 'error', 'message': 'keyword and ai_model required'}), 400
    try:
        item = {
            'project_id': DEFAULT_PROJECT_ID, 'keyword': keyword, 'ai_model': ai_model,
            'url': d.get('url'), 'brand_name': d.get('brand_name'),
            'cited': d.get('cited', False), 'citation_context': d.get('citation_context'),
            'response_snippet': d.get('response_snippet'), 'sentiment': d.get('sentiment'),
            'ai_platform': d.get('ai_platform'), 'query_text': d.get('query_text'),
        }
        probe_id = put_item('ai1stseo-geo-probes', item)
        _dispatch('geo_probe.created', {'id': probe_id, 'keyword': keyword, 'ai_model': ai_model})
        return jsonify({'status': 'success', 'id': probe_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/geo-probes', methods=['GET'])
@require_auth
def list_geo_probes():
    keyword = request.args.get('keyword', '')
    limit = request.args.get('limit', 50, type=int)
    try:
        if keyword:
            items = query_index('ai1stseo-geo-probes', 'keyword-index', 'keyword', keyword, limit)
        else:
            items = scan_table('ai1stseo-geo-probes', limit)
        return jsonify({'status': 'success', 'probes': items})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== CONTENT BRIEFS =====================

@data_bp.route('/api/data/content-briefs', methods=['POST'])
@require_auth
def create_content_brief():
    d = request.get_json() or {}
    keyword = d.get('keyword', '').strip()
    if not keyword:
        return jsonify({'status': 'error', 'message': 'keyword required'}), 400
    try:
        item = {
            'project_id': DEFAULT_PROJECT_ID, 'keyword': keyword,
            'content_type': d.get('content_type', 'blog'),
            'target_word_count': d.get('target_word_count'),
            'brief_json': d.get('brief_json'),
            'seo_score': d.get('seo_score'), 'aeo_score': d.get('aeo_score'),
            'status': d.get('status', 'draft'), 'created_by': _get_user_id(),
        }
        brief_id = put_item('ai1stseo-content-briefs', item)
        _dispatch('content_brief.created', {'id': brief_id, 'keyword': keyword})
        return jsonify({'status': 'success', 'id': brief_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/content-briefs', methods=['GET'])
@require_auth
def list_content_briefs():
    limit = request.args.get('limit', 20, type=int)
    try:
        items = scan_table('ai1stseo-content-briefs', limit)
        return jsonify({'status': 'success', 'briefs': items})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/content-briefs/<brief_id>', methods=['GET'])
@require_auth
def get_content_brief(brief_id):
    try:
        item = get_item('ai1stseo-content-briefs', {'id': brief_id})
        if not item:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        return jsonify({'status': 'success', 'brief': item})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== SOCIAL POSTS =====================

@data_bp.route('/api/data/social-posts', methods=['POST'])
@require_auth
def create_social_post():
    d = request.get_json() or {}
    content = d.get('content', '').strip()
    if not content:
        return jsonify({'status': 'error', 'message': 'content required'}), 400
    try:
        item = {
            'project_id': DEFAULT_PROJECT_ID, 'content': content,
            'platforms': d.get('platforms', []),
            'scheduled_at': d.get('scheduled_at'),
            'status': d.get('status', 'draft'), 'created_by': _get_user_id(),
        }
        post_id = put_item('ai1stseo-social-posts', item)
        _dispatch('social_post.created', {'id': post_id})
        return jsonify({'status': 'success', 'id': post_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/social-posts', methods=['GET'])
@require_auth
def list_social_posts():
    limit = request.args.get('limit', 20, type=int)
    try:
        items = scan_table('ai1stseo-social-posts', limit)
        return jsonify({'status': 'success', 'posts': items})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/social-posts/<post_id>', methods=['PUT'])
@require_auth
def update_social_post(post_id):
    d = request.get_json() or {}
    try:
        updates = {k: v for k, v in d.items() if k in ('content', 'status', 'scheduled_at', 'platforms', 'published_at')}
        if not updates:
            return jsonify({'status': 'error', 'message': 'Nothing to update'}), 400
        update_item('ai1stseo-social-posts', {'id': post_id}, updates)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/social-posts/<post_id>', methods=['DELETE'])
@require_auth
def delete_social_post(post_id):
    try:
        delete_item('ai1stseo-social-posts', {'id': post_id})
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== COMPETITORS =====================

@data_bp.route('/api/data/competitors', methods=['POST'])
@require_auth
def create_competitor():
    d = request.get_json() or {}
    domain = d.get('domain', '').strip().lower()
    if not domain:
        return jsonify({'status': 'error', 'message': 'domain required'}), 400
    try:
        item = {'project_id': DEFAULT_PROJECT_ID, 'domain': domain, 'label': d.get('label', ''), 'benchmarks': []}
        comp_id = put_item('ai1stseo-competitors', item)
        _dispatch('competitor.created', {'id': comp_id, 'domain': domain})
        return jsonify({'status': 'success', 'id': comp_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/competitors', methods=['GET'])
@require_auth
def list_competitors():
    try:
        items = scan_table('ai1stseo-competitors', 50)
        return jsonify({'status': 'success', 'competitors': items})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/competitors/<comp_id>', methods=['DELETE'])
@require_auth
def delete_competitor(comp_id):
    try:
        delete_item('ai1stseo-competitors', {'id': comp_id})
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== REPORTS =====================

@data_bp.route('/api/data/reports', methods=['POST'])
@require_auth
def create_report():
    d = request.get_json() or {}
    report_type = d.get('report_type', '').strip()
    data_payload = d.get('data')
    if not report_type or not data_payload:
        return jsonify({'status': 'error', 'message': 'report_type and data required'}), 400
    try:
        item = {
            'project_id': DEFAULT_PROJECT_ID, 'report_type': report_type,
            'title': d.get('title', ''), 'data': data_payload,
            'format': d.get('format', 'json'), 'created_by': _get_user_id(),
        }
        report_id = put_item('ai1stseo-audits', item)  # Reuse audits table for reports
        _dispatch('report.created', {'id': report_id, 'report_type': report_type})
        return jsonify({'status': 'success', 'id': report_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/reports', methods=['GET'])
@require_auth
def list_reports():
    try:
        items = scan_table('ai1stseo-audits', 20)
        reports = [i for i in items if i.get('report_type')]
        return jsonify({'status': 'success', 'reports': reports})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
