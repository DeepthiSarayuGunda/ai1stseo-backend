"""
Shared Data API — CRUD endpoints for all team microprojects.
All endpoints require auth. Data is scoped by project_id.

Endpoints:
  Audits (Dev 2 - Samarveer):
    POST /api/data/audits          — save a scan result
    GET  /api/data/audits          — list audits (paginated)
    GET  /api/data/audits/<id>     — get single audit with checks

  GEO Probes (Dev 1 - Deepthi):
    POST /api/data/geo-probes      — save a GEO probe result
    GET  /api/data/geo-probes      — list probes (paginated, filterable)

  AI Visibility (Dev 1 - Deepthi):
    POST /api/data/ai-visibility   — save a visibility snapshot
    GET  /api/data/ai-visibility   — list history for a URL

  Content Briefs (Dev 2 - Samarveer):
    POST /api/data/content-briefs  — save a content brief
    GET  /api/data/content-briefs  — list briefs (paginated)
    GET  /api/data/content-briefs/<id> — get single brief

  Social Posts (Dev 4 - Tabasum):
    POST /api/data/social-posts    — create a scheduled post
    GET  /api/data/social-posts    — list posts (filterable by status)
    PUT  /api/data/social-posts/<id> — update post (status, content, schedule)
    DELETE /api/data/social-posts/<id> — delete a post
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from database import query, query_one, execute, insert_returning
import json

data_bp = Blueprint('data', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


def _get_user_id():
    """Extract user ID from the authenticated request."""
    if hasattr(request, 'cognito_user') and request.cognito_user:
        return request.cognito_user.get('user_id')
    return None


# ===================== AUDITS (Dev 2 — Samarveer) =====================

@data_bp.route('/api/data/audits', methods=['POST'])
@require_auth
def create_audit():
    """Save a scan result. Accepts scores + optional checks array."""
    d = request.get_json() or {}
    url = d.get('url', '').strip()
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400
    try:
        audit_id = insert_returning(
            "INSERT INTO audits (project_id, url, overall_score, technical_score, onpage_score, "
            "content_score, mobile_score, performance_score, security_score, social_score, "
            "local_score, geo_aeo_score, total_checks, passed_checks, failed_checks, "
            "warning_checks, load_time_ms, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (DEFAULT_PROJECT_ID, url, d.get('overall_score'), d.get('technical_score'),
             d.get('onpage_score'), d.get('content_score'), d.get('mobile_score'),
             d.get('performance_score'), d.get('security_score'), d.get('social_score'),
             d.get('local_score'), d.get('geo_aeo_score'), d.get('total_checks', 0),
             d.get('passed_checks', 0), d.get('failed_checks', 0), d.get('warning_checks', 0),
             d.get('load_time_ms'), _get_user_id()),
        )
        # Insert individual checks if provided
        checks = d.get('checks', [])
        for c in checks:
            execute(
                "INSERT INTO audit_checks (audit_id, category, name, status, description, value, recommendation, impact) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (audit_id, c.get('category', ''), c.get('name', ''), c.get('status', 'info'),
                 c.get('description'), c.get('value'), c.get('recommendation'), c.get('impact')),
            )
        return jsonify({'status': 'success', 'id': str(audit_id), 'checks_saved': len(checks)}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/audits', methods=['GET'])
@require_auth
def list_audits():
    """List audits, paginated. ?url=&limit=&offset="""
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    url_filter = request.args.get('url', '')
    try:
        params = [DEFAULT_PROJECT_ID]
        sql = "SELECT id, url, overall_score, total_checks, passed_checks, load_time_ms, created_at FROM audits WHERE project_id = %s"
        if url_filter:
            sql += " AND url ILIKE %s"
            params.append('%' + url_filter + '%')
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        rows = query(sql, tuple(params))
        return jsonify({'status': 'success', 'audits': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/audits/<audit_id>', methods=['GET'])
@require_auth
def get_audit(audit_id):
    """Get a single audit with all its checks."""
    try:
        audit = query_one("SELECT * FROM audits WHERE id = %s AND project_id = %s", (audit_id, DEFAULT_PROJECT_ID))
        if not audit:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        checks = query("SELECT * FROM audit_checks WHERE audit_id = %s ORDER BY category, name", (audit_id,))
        result = dict(audit)
        result['checks'] = [dict(c) for c in checks]
        return jsonify({'status': 'success', 'audit': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== GEO PROBES (Dev 1 — Deepthi) =====================

@data_bp.route('/api/data/geo-probes', methods=['POST'])
@require_auth
def create_geo_probe():
    """Save a GEO citation probe result."""
    d = request.get_json() or {}
    keyword = d.get('keyword', '').strip()
    ai_model = d.get('ai_model', '').strip()
    if not keyword or not ai_model:
        return jsonify({'status': 'error', 'message': 'keyword and ai_model required'}), 400
    try:
        probe_id = insert_returning(
            "INSERT INTO geo_probes (project_id, url, brand_name, keyword, ai_model, cited, "
            "citation_context, response_snippet, citation_rank, sentiment, ai_platform, query_text) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (DEFAULT_PROJECT_ID, d.get('url'), d.get('brand_name'), keyword, ai_model,
             d.get('cited', False), d.get('citation_context'), d.get('response_snippet'),
             d.get('citation_rank'), d.get('sentiment'), d.get('ai_platform'), d.get('query_text')),
        )
        return jsonify({'status': 'success', 'id': str(probe_id)}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/geo-probes', methods=['GET'])
@require_auth
def list_geo_probes():
    """List GEO probes. ?keyword=&ai_model=&limit=&offset="""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    keyword = request.args.get('keyword', '')
    ai_model = request.args.get('ai_model', '')
    try:
        params = [DEFAULT_PROJECT_ID]
        sql = "SELECT * FROM geo_probes WHERE project_id = %s"
        if keyword:
            sql += " AND keyword ILIKE %s"
            params.append('%' + keyword + '%')
        if ai_model:
            sql += " AND ai_model = %s"
            params.append(ai_model)
        sql += " ORDER BY probe_timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        rows = query(sql, tuple(params))
        return jsonify({'status': 'success', 'probes': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== AI VISIBILITY (Dev 1 — Deepthi) =====================

@data_bp.route('/api/data/ai-visibility', methods=['POST'])
@require_auth
def create_ai_visibility():
    """Save an AI visibility snapshot for a URL."""
    d = request.get_json() or {}
    url = d.get('url', '').strip()
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400
    try:
        vid = insert_returning(
            "INSERT INTO ai_visibility_history (project_id, url, visibility_score, citation_count, "
            "extractable_answers, factual_density_score, schema_coverage_score, share_of_voice, "
            "competitor_citations, ai_referral_sessions, citation_sentiment_positive, "
            "citation_sentiment_neutral, citation_sentiment_negative) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (DEFAULT_PROJECT_ID, url, d.get('visibility_score'), d.get('citation_count', 0),
             d.get('extractable_answers', 0), d.get('factual_density_score'),
             d.get('schema_coverage_score'), d.get('share_of_voice'),
             d.get('competitor_citations', 0), d.get('ai_referral_sessions', 0),
             d.get('citation_sentiment_positive', 0), d.get('citation_sentiment_neutral', 0),
             d.get('citation_sentiment_negative', 0)),
        )
        return jsonify({'status': 'success', 'id': str(vid)}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/ai-visibility', methods=['GET'])
@require_auth
def list_ai_visibility():
    """Get AI visibility history for a URL. ?url=&limit="""
    url = request.args.get('url', '')
    limit = request.args.get('limit', 30, type=int)
    try:
        params = [DEFAULT_PROJECT_ID]
        sql = "SELECT * FROM ai_visibility_history WHERE project_id = %s"
        if url:
            sql += " AND url = %s"
            params.append(url)
        sql += " ORDER BY measured_at DESC LIMIT %s"
        params.append(limit)
        rows = query(sql, tuple(params))
        return jsonify({'status': 'success', 'history': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== CONTENT BRIEFS (Dev 2 — Samarveer) =====================

@data_bp.route('/api/data/content-briefs', methods=['POST'])
@require_auth
def create_content_brief():
    """Save a content brief."""
    d = request.get_json() or {}
    keyword = d.get('keyword', '').strip()
    if not keyword:
        return jsonify({'status': 'error', 'message': 'keyword required'}), 400
    try:
        brief_json = d.get('brief_json')
        if brief_json and isinstance(brief_json, dict):
            brief_json = json.dumps(brief_json)
        brief_id = insert_returning(
            "INSERT INTO content_briefs (project_id, keyword, content_type, target_word_count, "
            "brief_json, seo_score, aeo_score, status, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (DEFAULT_PROJECT_ID, keyword, d.get('content_type', 'blog'),
             d.get('target_word_count'), brief_json,
             d.get('seo_score'), d.get('aeo_score'),
             d.get('status', 'draft'), _get_user_id()),
        )
        return jsonify({'status': 'success', 'id': str(brief_id)}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/content-briefs', methods=['GET'])
@require_auth
def list_content_briefs():
    """List content briefs. ?keyword=&status=&limit=&offset="""
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    try:
        params = [DEFAULT_PROJECT_ID]
        sql = ("SELECT id, keyword, content_type, seo_score, aeo_score, status, created_at "
               "FROM content_briefs WHERE project_id = %s")
        if keyword:
            sql += " AND keyword ILIKE %s"
            params.append('%' + keyword + '%')
        if status:
            sql += " AND status = %s"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        rows = query(sql, tuple(params))
        return jsonify({'status': 'success', 'briefs': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/content-briefs/<brief_id>', methods=['GET'])
@require_auth
def get_content_brief(brief_id):
    """Get a single content brief with full JSON."""
    try:
        brief = query_one("SELECT * FROM content_briefs WHERE id = %s AND project_id = %s", (brief_id, DEFAULT_PROJECT_ID))
        if not brief:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        return jsonify({'status': 'success', 'brief': dict(brief)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== SOCIAL POSTS (Dev 4 — Tabasum) =====================

@data_bp.route('/api/data/social-posts', methods=['POST'])
@require_auth
def create_social_post():
    """Create a scheduled social media post."""
    d = request.get_json() or {}
    content = d.get('content', '').strip()
    if not content:
        return jsonify({'status': 'error', 'message': 'content required'}), 400
    try:
        platforms = d.get('platforms', [])
        if isinstance(platforms, list):
            platforms = '{' + ','.join(platforms) + '}'
        post_id = insert_returning(
            "INSERT INTO social_posts (project_id, content, platforms, scheduled_at, status, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (DEFAULT_PROJECT_ID, content, platforms,
             d.get('scheduled_at'), d.get('status', 'draft'), _get_user_id()),
        )
        return jsonify({'status': 'success', 'id': str(post_id)}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/social-posts', methods=['GET'])
@require_auth
def list_social_posts():
    """List social posts. ?status=&limit=&offset="""
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    status = request.args.get('status', '')
    try:
        params = [DEFAULT_PROJECT_ID]
        sql = "SELECT * FROM social_posts WHERE project_id = %s"
        if status:
            sql += " AND status = %s"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        rows = query(sql, tuple(params))
        return jsonify({'status': 'success', 'posts': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/social-posts/<post_id>', methods=['PUT'])
@require_auth
def update_social_post(post_id):
    """Update a social post (content, status, schedule, platforms)."""
    d = request.get_json() or {}
    try:
        sets = []
        params = []
        if 'content' in d:
            sets.append("content = %s")
            params.append(d['content'])
        if 'status' in d:
            sets.append("status = %s")
            params.append(d['status'])
        if 'scheduled_at' in d:
            sets.append("scheduled_at = %s")
            params.append(d['scheduled_at'])
        if 'platforms' in d:
            platforms = d['platforms']
            if isinstance(platforms, list):
                platforms = '{' + ','.join(platforms) + '}'
            sets.append("platforms = %s")
            params.append(platforms)
        if 'published_at' in d:
            sets.append("published_at = %s")
            params.append(d['published_at'])
        if not sets:
            return jsonify({'status': 'error', 'message': 'Nothing to update'}), 400
        params.extend([post_id, DEFAULT_PROJECT_ID])
        updated = execute(
            "UPDATE social_posts SET {} WHERE id = %s AND project_id = %s".format(', '.join(sets)),
            tuple(params),
        )
        if updated == 0:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@data_bp.route('/api/data/social-posts/<post_id>', methods=['DELETE'])
@require_auth
def delete_social_post(post_id):
    """Delete a social post."""
    try:
        deleted = execute(
            "DELETE FROM social_posts WHERE id = %s AND project_id = %s",
            (post_id, DEFAULT_PROJECT_ID),
        )
        if deleted == 0:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
