"""
Webhook API — Register URLs to receive event notifications (DynamoDB version).
Events: audit.created, geo_probe.created, content_brief.created, etc.

Usage from other services:
    from webhook_api import dispatch_event
    dispatch_event('audit.created', {'id': audit_id, 'url': url, 'score': 85})
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from dynamodb_helper import put_item, get_item, scan_table, update_item, delete_item, query_index
import json
import hmac
import hashlib
import threading
import requests as http_requests

webhook_bp = Blueprint('webhooks', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'

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
    d = request.get_json() or {}
    url = d.get('url', '').strip()
    events = d.get('events', [])
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400
    if not events:
        return jsonify({'status': 'error', 'message': 'events array required'}), 400
    invalid = [e for e in events if e not in VALID_EVENTS]
    if invalid:
        return jsonify({'status': 'error', 'message': 'Invalid events: ' + ', '.join(invalid)}), 400
    try:
        wh_id = put_item('ai1stseo-webhooks', {
            'project_id': DEFAULT_PROJECT_ID, 'url': url,
            'events': events, 'secret': d.get('secret'),
            'is_active': True, 'created_by': _get_user_id(),
        })
        return jsonify({'status': 'success', 'id': wh_id, 'events': events}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks', methods=['GET'])
@require_auth
def list_webhooks():
    try:
        items = scan_table('ai1stseo-webhooks', 50)
        return jsonify({'status': 'success', 'webhooks': items})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks/<wh_id>', methods=['DELETE'])
@require_auth
def delete_webhook(wh_id):
    try:
        delete_item('ai1stseo-webhooks', {'id': wh_id})
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks/<wh_id>/toggle', methods=['POST'])
@require_auth
def toggle_webhook(wh_id):
    try:
        item = get_item('ai1stseo-webhooks', {'id': wh_id})
        if not item:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        new_state = not item.get('is_active', True)
        update_item('ai1stseo-webhooks', {'id': wh_id}, {'is_active': new_state})
        return jsonify({'status': 'success', 'is_active': new_state})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/webhooks/events', methods=['GET'])
def list_event_types():
    return jsonify({'status': 'success', 'events': sorted(VALID_EVENTS)})


def dispatch_event(event_type, payload):
    """Fire all registered webhooks for this event type."""
    def _dispatch():
        try:
            items = scan_table('ai1stseo-webhooks', 100)
            for wh in items:
                if not wh.get('is_active', True):
                    continue
                events = wh.get('events', [])
                if '*' not in events and event_type not in events:
                    continue
                _deliver(wh['id'], wh['url'], wh.get('secret'), event_type, payload)
        except Exception:
            pass
    threading.Thread(target=_dispatch, daemon=True).start()


def _deliver(webhook_id, url, secret, event_type, payload):
    body = json.dumps({'event': event_type, 'data': payload,
                       'timestamp': __import__('datetime').datetime.utcnow().isoformat()})
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
    try:
        put_item('ai1stseo-webhooks', {
            'id': 'delivery_' + __import__('uuid').uuid4().hex[:12],
            'webhook_id': webhook_id, 'event_type': event_type,
            'payload': json.dumps(payload) if payload else None,
            'status_code': status_code, 'response_body': response_body,
            'success': success, 'delivery': True,
        })
    except Exception:
        pass
