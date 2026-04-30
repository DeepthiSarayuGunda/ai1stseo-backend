"""
OpenClaw Bridge — Connects site monitor scan events to the OpenClaw agent.
Sends scan results to the agent via /hooks/agent for delivery and conversation.

Usage:
    from openclaw_bridge import notify_agent, request_scan_report

    # After a scan completes:
    notify_agent('audit.created', {'url': 'https://example.com', 'score': 85})

    # Request the agent to generate and deliver a report:
    request_scan_report('https://example.com', channel='whatsapp', to='+15551234567')
"""
import os
import json
import requests
import threading

OPENCLAW_URL = os.environ.get('OPENCLAW_API_URL', 'http://127.0.0.1:18789')
OPENCLAW_TOKEN = os.environ.get('OPENCLAW_TOKEN', '')
MONITOR_URL = os.environ.get('MONITOR_URL', 'http://127.0.0.1:8888')


def _get_headers():
    headers = {'Content-Type': 'application/json'}
    if OPENCLAW_TOKEN:
        headers['Authorization'] = 'Bearer ' + OPENCLAW_TOKEN
    return headers


def notify_agent(event_type, payload, deliver=False, channel=None, to=None):
    """
    Send a scan event to the OpenClaw agent via CLI.
    If deliver=True, the agent will send the response to the specified channel/recipient.
    """
    def _do():
        try:
            import subprocess
            message = _format_event_message(event_type, payload)
            cmd = ['/usr/bin/openclaw', 'agent', '--agent', 'main', '--message', message]
            if deliver and to:
                cmd.extend(['--deliver', '--to', to])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                print('OpenClaw agent notified: {}'.format(event_type))
            else:
                print('OpenClaw agent error: {}'.format(result.stderr[:200]))
        except Exception as e:
            print('OpenClaw bridge failed: {}'.format(e))

    threading.Thread(target=_do, daemon=True).start()


def request_scan_report(url, channel=None, to=None):
    """
    Ask the OpenClaw agent to run a scan and deliver the report via CLI.
    """
    import subprocess
    message = (
        'Run a site scan for {} using the monitor API at {}. '
        'Summarize the results: overall score, top 3 issues, and the #1 recommendation. '
        'Keep it concise.'
    ).format(url, MONITOR_URL)

    cmd = ['/usr/bin/openclaw', 'agent', '--agent', 'main', '--message', message]
    if to:
        cmd.extend(['--deliver', '--to', to])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {'output': result.stdout, 'error': result.stderr} if result.returncode == 0 else {'error': result.stderr}
    except Exception as e:
        return {'error': str(e)}


def wake_agent():
    """Wake the OpenClaw agent via CLI."""
    try:
        import subprocess
        result = subprocess.run(
            ['/usr/bin/openclaw', 'agent', '--agent', 'main', '--message', 'heartbeat check'],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def _format_event_message(event_type, payload):
    """Format a scan event into a human-readable message for the agent."""
    templates = {
        'audit.created': 'New SEO audit completed for {url}. Score: {overall_score}/100. {total_checks} checks run, {passed_checks} passed.',
        'uptime.down': 'ALERT: {url} is DOWN. Status code: {status_code}.',
        'content.changed': 'Content change detected on {url}. Changes: {changes}.',
        'geo_probe.created': 'GEO probe completed for keyword "{keyword}" on {ai_model}. Cited: {cited}.',
        'content_brief.created': 'New content brief generated for keyword "{keyword}".',
    }

    template = templates.get(event_type, 'Event: {} — {}'.format(event_type, json.dumps(payload)))
    if isinstance(template, str) and isinstance(payload, dict):
        try:
            return template.format(**{k: v for k, v in payload.items() if v is not None})
        except (KeyError, IndexError):
            pass
    return 'Event: {} — {}'.format(event_type, json.dumps(payload, default=str)[:500])


# === Integration with web_ui.py scan endpoints ===

def hook_into_monitor(app):
    """
    Register after-request hooks to notify OpenClaw when scans complete.
    Call this from web_ui.py: openclaw_bridge.hook_into_monitor(app)
    """
    @app.after_request
    def _notify_openclaw(response):
        if response.status_code == 200 and response.content_type == 'application/json':
            path = getattr(response, '_request_path', '') or ''
            try:
                data = json.loads(response.get_data(as_text=True))
            except Exception:
                data = {}

            if '/api/scan' in path and 'seo' in data:
                notify_agent('audit.created', {
                    'url': data.get('url', ''),
                    'overall_score': data.get('seo', {}).get('score'),
                    'total_checks': data.get('seo', {}).get('total_checks', 0),
                })
            elif '/api/ai-visibility' in path and 'visibility_score' in str(data):
                notify_agent('geo_probe.created', {
                    'url': data.get('domain', ''),
                    'visibility_score': data.get('visibility_score'),
                })
        return response
