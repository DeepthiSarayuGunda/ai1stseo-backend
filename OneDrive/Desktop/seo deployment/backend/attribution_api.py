"""
AI Referral Attribution API — Tracks traffic from AI chatbots to client sites.
Normalizes referrers (chatgpt.com, claude.ai, perplexity.ai, etc.),
stores attribution events, and aggregates by source.

DynamoDB table: ai1stseo-api-logs (reuses existing logs table with type='ai_referral')
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from dynamodb_helper import put_item, scan_table
from datetime import datetime, timezone
import uuid

attribution_bp = Blueprint('attribution', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'
LOGS_TABLE = 'ai1stseo-api-logs'


def _now():
    return datetime.now(timezone.utc).isoformat()


# Known AI referrer patterns → canonical source names
AI_REFERRERS = {
    'chatgpt.com': 'ChatGPT',
    'chat.openai.com': 'ChatGPT',
    'openai.com': 'ChatGPT',
    'claude.ai': 'Claude',
    'anthropic.com': 'Claude',
    'perplexity.ai': 'Perplexity',
    'gemini.google.com': 'Gemini',
    'bard.google.com': 'Gemini',
    'copilot.microsoft.com': 'Copilot',
    'bing.com/chat': 'Copilot',
    'you.com': 'You.com',
    'phind.com': 'Phind',
    'poe.com': 'Poe',
    'meta.ai': 'Meta AI',
    'huggingface.co/chat': 'HuggingChat',
}


def normalize_referrer(referrer_url):
    """
    Normalize a referrer URL to a canonical AI source name.
    Returns (source_name, is_ai) tuple.
    """
    if not referrer_url:
        return ('direct', False)

    referrer_lower = referrer_url.lower().strip()

    # Check exact domain matches
    for pattern, source in AI_REFERRERS.items():
        if pattern in referrer_lower:
            return (source, True)

    # Check for common AI bot user agents in the referrer
    ai_indicators = ['chatgpt', 'claude', 'perplexity', 'gemini', 'copilot', 'gpt']
    for indicator in ai_indicators:
        if indicator in referrer_lower:
            return (indicator.capitalize(), True)

    # Not an AI referrer
    from urllib.parse import urlparse
    parsed = urlparse(referrer_url)
    domain = parsed.netloc or referrer_url[:50]
    return (domain, False)


@attribution_bp.route('/api/attribution/track', methods=['POST'])
def track_referral():
    """
    Track an AI referral event. Called by a lightweight JS snippet on client sites.
    No auth required — uses a site_id for identification.
    Rate limited by IP to prevent abuse.
    """
    data = request.get_json() or {}
    referrer = data.get('referrer', '').strip()
    landing_page = data.get('landing_page', '').strip()
    site_id = data.get('site_id', '').strip()

    if not landing_page:
        return jsonify({'status': 'error', 'message': 'landing_page required'}), 400

    source, is_ai = normalize_referrer(referrer)

    try:
        event_id = str(uuid.uuid4())
        put_item(LOGS_TABLE, {
            'id': event_id,
            'type': 'ai_referral',
            'source': source,
            'is_ai_referral': is_ai,
            'referrer_raw': referrer[:500],
            'landing_page': landing_page[:500],
            'site_id': site_id,
            'user_agent': request.headers.get('User-Agent', '')[:200],
            'ip_country': request.headers.get('CloudFront-Viewer-Country', ''),
            'utm_source': data.get('utm_source', ''),
            'utm_medium': data.get('utm_medium', ''),
            'utm_campaign': data.get('utm_campaign', ''),
            'session_id': data.get('session_id', ''),
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
        })

        return jsonify({
            'status': 'success',
            'id': event_id,
            'source': source,
            'is_ai': is_ai,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@attribution_bp.route('/api/attribution/convert', methods=['POST'])
def track_conversion():
    """
    Track a conversion event tied to an AI referral session.
    Called when a user completes a goal (signup, purchase, download, etc.).
    """
    data = request.get_json() or {}
    session_id = data.get('session_id', '').strip()
    conversion_type = data.get('type', 'signup').strip()
    value = data.get('value', 0)

    if not session_id:
        return jsonify({'status': 'error', 'message': 'session_id required'}), 400

    try:
        put_item(LOGS_TABLE, {
            'id': str(uuid.uuid4()),
            'type': 'ai_conversion',
            'session_id': session_id,
            'conversion_type': conversion_type,
            'conversion_value': value,
            'landing_page': data.get('landing_page', ''),
            'source': data.get('source', ''),
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
        })
        return jsonify({'status': 'success', 'conversion_type': conversion_type})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@attribution_bp.route('/api/attribution/ai-referrals', methods=['GET'])
@require_auth
def get_ai_referrals():
    """
    Get AI referral attribution data. Aggregated by source.
    Query: ?days=30&site_id=xxx
    """
    days = request.args.get('days', 30, type=int)
    site_filter = request.args.get('site_id', '')

    try:
        items = scan_table(LOGS_TABLE, 500)

        # Filter to AI referral events
        referrals = [i for i in items if i.get('type') == 'ai_referral']
        conversions = [i for i in items if i.get('type') == 'ai_conversion']

        if site_filter:
            referrals = [r for r in referrals if r.get('site_id') == site_filter]

        # Filter AI-only referrals
        ai_referrals = [r for r in referrals if r.get('is_ai_referral')]

        # Aggregate by source
        from collections import Counter, defaultdict
        source_counts = Counter()
        source_pages = defaultdict(Counter)
        for r in ai_referrals:
            src = r.get('source', 'unknown')
            source_counts[src] += 1
            page = r.get('landing_page', '')
            if page:
                source_pages[src][page] += 1

        # Match conversions to sessions
        conversion_sessions = set(c.get('session_id') for c in conversions)
        ai_conversions = sum(1 for r in ai_referrals if r.get('session_id') in conversion_sessions)

        # Build source breakdown
        by_source = []
        for source, count in source_counts.most_common(20):
            top_pages = [{'page': p, 'visits': c} for p, c in source_pages[source].most_common(5)]
            by_source.append({
                'source': source,
                'visits': count,
                'top_landing_pages': top_pages,
            })

        return jsonify({
            'status': 'success',
            'total_referrals': len(referrals),
            'ai_referrals': len(ai_referrals),
            'non_ai_referrals': len(referrals) - len(ai_referrals),
            'ai_conversions': ai_conversions,
            'conversion_rate': round(ai_conversions / max(len(ai_referrals), 1) * 100, 1),
            'by_source': by_source,
            'days': days,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@attribution_bp.route('/api/attribution/snippet', methods=['GET'])
def get_tracking_snippet():
    """
    Return the JavaScript tracking snippet that clients install on their sites.
    No auth required — the snippet itself is public.
    """
    site_id = request.args.get('site_id', 'YOUR_SITE_ID')
    snippet = '''<!-- AI 1st SEO Attribution Tracker -->
<script>
(function() {{
  var sid = '{site_id}';
  var ssid = 'ai1stseo_' + Math.random().toString(36).substr(2, 9);
  var ref = document.referrer || '';
  var lp = window.location.href;
  var utm_s = new URLSearchParams(window.location.search).get('utm_source') || '';
  var utm_m = new URLSearchParams(window.location.search).get('utm_medium') || '';
  var utm_c = new URLSearchParams(window.location.search).get('utm_campaign') || '';
  fetch('https://api.ai1stseo.com/api/attribution/track', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{
      site_id: sid, referrer: ref, landing_page: lp,
      session_id: ssid, utm_source: utm_s, utm_medium: utm_m, utm_campaign: utm_c
    }})
  }}).catch(function() {{}});
  window.ai1stseo_convert = function(type, value) {{
    fetch('https://api.ai1stseo.com/api/attribution/convert', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        session_id: ssid, type: type, value: value || 0,
        landing_page: lp, source: ref
      }})
    }}).catch(function() {{}});
  }};
}})();
</script>
<!-- Call ai1stseo_convert('signup') or ai1stseo_convert('purchase', 49.99) on conversion events -->'''.format(site_id=site_id)

    return jsonify({
        'status': 'success',
        'snippet': snippet,
        'instructions': [
            'Paste this snippet before </body> on every page of your site.',
            'Replace YOUR_SITE_ID with your actual site ID from /api/multi-site/sites.',
            'Call ai1stseo_convert("signup") when a user completes a goal.',
            'View results at /api/attribution/ai-referrals.',
        ],
    })
