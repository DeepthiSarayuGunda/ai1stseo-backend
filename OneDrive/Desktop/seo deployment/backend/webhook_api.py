"""
Webhook API — Register URLs to receive event notifications.
Events: audit.created, geo_probe.created, content_brief.created,
        social_post.created, social_post.updated, competitor.created,
        benchmark.created, report.created, uptime.down, content.changed

Usage from other services:
    from webhook_api import dispatch_event
    dispatch_event('audit.created', {'id': audit_id, 'url': url, 'score': 85})
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from database import query, query_one, execute, insert_returning
import json
import hmac
import hashlib
import threading
import requests as http_requests

webhook_bp = Blueprint('webhooks', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'

# Valid event types
VALID_EVENTS = {
    'audit.created', 'geo_probe.created', 'ai_visibility.created',
    'content_brief.created', 'social_post.created', 'social_post.updated',
    'social_post.deleted', 'competitor.created', 'benchmark.created',
    'report.created', 'uptime.down', 'content.changed', '*',
}


def _get_user_id():
    if hasattr(request, 'cognito_user') and request.cognito_user:
        return request.cognito_user.get('user_id')
    return None


@webhook_bp.route('/api/webhooks', methods=['POST'])
@require_auth
def create_webhook():
    """Register a webhook URL for specific events."""
    d = request.get_json() or {}
    url = d.get('url', '').strip()
    events = d.get('events', [])
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400
    if not events:
        return jsonify({'status': 'error', 'message': 'events array required (e.g. ["audit.created", "*"])'}), 400
    invalid = [e for e in events if e not in VALID_EVENTS]
    if invalid:
        return jsonify({'status': 'error', 'message': 'Invalid events: ' + ', '.join(invalid),
                        'valid_events': sorted(VALID_EVENTS)}), 400
    try:
        events_pg = '{' + ','.join(events) + '}'
        wh_id = insert_returning(
            "INSERT INTO webhooks (project_id, url, events, secret, created_by) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (DEFAULT_PROJECT_ID, url, events_pg, d.get('secret'), _get_user_id()),
        )
        return jsonify({'status': 'success', 'id': str(wh_id), 'events': events}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks', methods=['GET'])
@require_auth
def list_webhooks():
    """List registered webhooks."""
    try:
        rows = query(
            "SELECT id, url, events, is_active, created_at FROM webhooks "
            "WHERE project_id = %s ORDER BY created_at DESC",
            (DEFAULT_PROJECT_ID,),
        )
        return jsonify({'status': 'success', 'webhooks': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks/<wh_id>', methods=['DELETE'])
@require_auth
def delete_webhook(wh_id):
    """Remove a webhook registration."""
    try:
        deleted = execute(
            "DELETE FROM webhooks WHERE id = %s AND project_id = %s",
            (wh_id, DEFAULT_PROJECT_ID),
        )
        if deleted == 0:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks/<wh_id>/toggle', methods=['POST'])
@require_auth
def toggle_webhook(wh_id):
    """Enable or disable a webhook."""
    try:
        execute(
            "UPDATE webhooks SET is_active = NOT is_active WHERE id = %s AND project_id = %s",
            (wh_id, DEFAULT_PROJECT_ID),
        )
        row = query_one("SELECT is_active FROM webhooks WHERE id = %s", (wh_id,))
        return jsonify({'status': 'success', 'is_active': row['is_active'] if row else False})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks/events', methods=['GET'])
def list_event_types():
    """List all valid event types (no auth required — documentation endpoint)."""
    return jsonify({'status': 'success', 'events': sorted(VALID_EVENTS)})


# === Event Dispatch (called by other modules) ===

def dispatch_event(event_type, payload):
    """
    Fire all registered webhooks for this event type.
    Runs in background threads to not block the caller.
    """
    def _dispatch():
        try:
            rows = query(
                "SELECT id, url, secret, events FROM webhooks "
                "WHERE project_id = %s AND is_active = true",
                (DEFAULT_PROJECT_ID,),
            )
            for wh in rows:
                events = wh.get('events', [])
                if '*' not in events and event_type not in events:
                    continue
                _deliver(wh['id'], wh['url'], wh.get('secret'), event_type, payload)
        except Exception:
            pass

    threading.Thread(target=_dispatch, daemon=True).start()


def _deliver(webhook_id, url, secret, event_type, payload):
    """Send a single webhook delivery."""
    body = json.dumps({'event': event_type, 'data': payload, 'timestamp': __import__('datetime').datetime.utcnow().isoformat()})
    headers = {'Content-Type': 'application/json', 'X-Webhook-Event': event_type}
    if secret:
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers['X-Webhook-Signature'] = sig
    try:
        r = http_requests.post(url, data=body, headers=headers, timeout=10)
        _log_delivery(webhook_id, event_type, payload, r.status_code, r.text[:500], r.status_code < 400)
    except Exception as e:
        _log_delivery(webhook_id, event_type, payload, 0, str(e)[:500], False)


def _log_delivery(webhook_id, event_type, payload, status_code, response_body, success):
    """Log webhook delivery attempt."""
    try:
        execute(
            "INSERT INTO webhook_deliveries (webhook_id, event_type, payload, status_code, response_body, success) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (webhook_id, event_type, json.dumps(payload) if payload else None,
             status_code, response_body, success),
        )
    except Exception:
        pass
