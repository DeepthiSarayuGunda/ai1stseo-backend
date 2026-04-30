# ======================================================================
# WARNING: SHARED FILE - DO NOT OVERWRITE WITHOUT PULLING FIRST
# Owner: Troy (Dev 3) | Uses DynamoDB (NOT RDS)
# BEFORE EDITING: git pull origin main
# BEFORE PUSHING: git diff backend/webhook_api.py (verify no endpoints removed)
# Key features: webhooks CRUD, Slack/email notifications, dispatch_event, webhook branding, answer.changed event
# If any are missing after your edit, you broke it.
# ======================================================================
"""
Webhook API ΓÇö Register URLs to receive event notifications (DynamoDB version).
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
    'report.created', 'uptime.down', 'content.changed', 'answer.changed', '*',
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
    """Fire all registered webhooks + Slack/email notifications for this event type."""
    def _dispatch():
        try:
            items = scan_table('ai1stseo-webhooks', 100)
            for wh in items:
                if not wh.get('is_active', True):
                    continue
                events = wh.get('events', [])
                if '*' not in events and event_type not in events:
                    continue
                # Skip notification subscriptions (handled separately)
                if wh.get('notification'):
                    continue
                if wh.get('url'):
                    _deliver(wh['id'], wh['url'], wh.get('secret'), event_type, payload)
        except Exception:
            pass
    threading.Thread(target=_dispatch, daemon=True).start()
    # Also dispatch to Slack/email notification subscribers
    _dispatch_notifications(event_type, payload)


def _get_webhook_branding():
    """Load white-label branding for webhook payloads. Returns minimal branding dict."""
    try:
        config = get_item('ai1stseo-webhooks', {'id': '_white_label_cache'})
        if config:
            return {
                'brand': config.get('brand_name', 'AI 1st SEO'),
                'url': config.get('custom_domain', 'https://ai1stseo.com'),
            }
    except Exception:
        pass
    # Fallback: try admin metrics table where white-label config is stored
    try:
        from dynamodb_helper import get_item as _get
        config = _get('ai1stseo-admin-metrics', {'metric_date': 'white_label_config'})
        if config:
            return {
                'brand': config.get('brand_name', 'AI 1st SEO'),
                'url': config.get('custom_domain', 'https://ai1stseo.com'),
            }
    except Exception:
        pass
    return {'brand': 'AI 1st SEO', 'url': 'https://ai1stseo.com'}


def _deliver(webhook_id, url, secret, event_type, payload):
    # Inject white-label branding into payload if available
    branding = _get_webhook_branding()
    body = json.dumps({'event': event_type, 'data': payload,
                       'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
                       'source': branding})
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


# ===================== NOTIFICATION CHANNELS (Slack + Email) =====================

import os as _os
import boto3 as _boto3

_ses = _boto3.client('ses', region_name='us-east-1')
_SES_SENDER = 'no-reply@ai1stseo.com'


def send_slack_notification(webhook_url, event_type, payload):
    """Send a formatted Slack message via incoming webhook."""
    try:
        branding = _get_webhook_branding()
        brand_name = branding.get('brand', 'AI 1st SEO')
        emoji = {'audit.created': ':mag:', 'uptime.down': ':rotating_light:',
                 'content.changed': ':pencil2:', 'geo_probe.created': ':robot_face:',
                 'content_brief.created': ':page_facing_up:', 'competitor.created': ':chart_with_upwards_trend:',
                 'answer.changed': ':warning:',
                 }.get(event_type, ':bell:')
        text = '{} *{}*\n'.format(emoji, event_type)
        if isinstance(payload, dict):
            for k, v in list(payload.items())[:6]:
                text += '> *{}:* {}\n'.format(k, v)
        blocks = [{'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}},
                  {'type': 'context', 'elements': [{'type': 'mrkdwn', 'text': '{} | {}'.format(
                      brand_name, __import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))}]}]
        http_requests.post(webhook_url, json={'blocks': blocks, 'text': text}, timeout=10)
    except Exception as e:
        print('Slack notification failed: {}'.format(e))


def send_email_notification(to_email, event_type, payload):
    """Send an email notification via SES."""
    try:
        subject = 'AI1stSEO Alert: {}'.format(event_type)
        body_lines = ['Event: {}'.format(event_type), '']
        if isinstance(payload, dict):
            for k, v in payload.items():
                body_lines.append('{}: {}'.format(k, v))
        body_lines.extend(['', '---', 'AI 1st SEO Notifications', 'https://ai1stseo.com'])
        _ses.send_email(
            Source=_SES_SENDER,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': '\n'.join(body_lines)}}
            },
        )
    except Exception as e:
        print('Email notification failed: {}'.format(e))


@webhook_bp.route('/api/notifications/subscribe', methods=['POST'])
@require_auth
def subscribe_notifications():
    """Subscribe to event notifications via Slack or email."""
    d = request.get_json() or {}
    channel = d.get('channel', '').strip()  # 'slack' or 'email'
    target = d.get('target', '').strip()    # slack webhook URL or email address
    events = d.get('events', ['*'])
    if channel not in ('slack', 'email'):
        return jsonify({'status': 'error', 'message': 'channel must be slack or email'}), 400
    if not target:
        return jsonify({'status': 'error', 'message': 'target required (webhook URL or email)'}), 400
    try:
        sub_id = put_item('ai1stseo-webhooks', {
            'project_id': DEFAULT_PROJECT_ID,
            'channel': channel, 'target': target,
            'events': events, 'is_active': True,
            'created_by': _get_user_id(),
            'notification': True,
        })
        return jsonify({'status': 'success', 'id': sub_id, 'channel': channel}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@webhook_bp.route('/api/notifications', methods=['GET'])
@require_auth
def list_notifications():
    """List notification subscriptions."""
    try:
        items = scan_table('ai1stseo-webhooks', 100)
        notifs = [i for i in items if i.get('notification')]
        return jsonify({'status': 'success', 'notifications': notifs})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _dispatch_notifications(event_type, payload):
    """Send notifications to all Slack/email subscribers for this event."""
    def _do():
        try:
            items = scan_table('ai1stseo-webhooks', 100)
            for sub in items:
                if not sub.get('notification') or not sub.get('is_active', True):
                    continue
                events = sub.get('events', [])
                if '*' not in events and event_type not in events:
                    continue
                ch = sub.get('channel')
                target = sub.get('target', '')
                if ch == 'slack' and target:
                    send_slack_notification(target, event_type, payload)
                elif ch == 'email' and target:
                    send_email_notification(target, event_type, payload)
        except Exception:
            pass
    threading.Thread(target=_do, daemon=True).start()
