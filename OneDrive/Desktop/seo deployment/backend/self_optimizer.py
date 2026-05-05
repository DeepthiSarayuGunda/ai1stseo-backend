"""
AI 1st SEO Self-Optimization Pipeline — Scheduled Lambda.
Runs our own backlinking tools against ai1stseo.com weekly.
Generates a summary report and emails the team.

Triggered by: EventBridge rule (weekly, Fridays 06:00 UTC)
"""
import boto3
import json
import requests as http_requests
from datetime import datetime, timezone

ses = boto3.client('ses', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

OUR_DOMAIN = 'ai1stseo.com'
OUR_BRAND = 'AI 1st SEO'
OUR_NICHE = 'SEO tools'
COMPETITORS = ['semrush.com', 'ahrefs.com', 'surferseo.com', 'moz.com']
API_BASE = 'https://api.ai1stseo.com'
# Use the internal API key for auth
API_KEY = 'ai1st_7170551944621d62337254acffc55daccb69b9e5'
ALERT_RECIPIENTS = ['saur0024@algonquinlive.com', 'gurbachan@ai1stseo.com']
SES_SENDER = 'no-reply@ai1stseo.com'


def _headers():
    return {'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json'}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _api_post(endpoint, body):
    """Call our own API."""
    try:
        r = http_requests.post(API_BASE + endpoint, json=body, headers=_headers(), timeout=30)
        if r.status_code == 200:
            return r.json()
        return {'error': 'HTTP {}'.format(r.status_code), 'detail': r.text[:200]}
    except Exception as e:
        return {'error': str(e)[:200]}


def _api_get(endpoint):
    """Call our own API."""
    try:
        r = http_requests.get(API_BASE + endpoint, headers=_headers(), timeout=30)
        if r.status_code == 200:
            return r.json()
        return {'error': 'HTTP {}'.format(r.status_code)}
    except Exception as e:
        return {'error': str(e)[:200]}


def lambda_handler(event, context):
    """Run all self-optimization checks and email results."""
    print('Self-optimization pipeline starting at {}'.format(_now()))
    results = {}

    # 1. Score our own domain authority
    print('[1/7] Scoring our DA...')
    results['da_score'] = _api_post('/api/backlinks/score', {'domain': OUR_DOMAIN})

    # 2. Scan for unlinked brand mentions
    print('[2/7] Scanning for mentions...')
    results['mentions'] = _api_post('/api/mentions/scan', {'brand': OUR_BRAND, 'domain': OUR_DOMAIN})

    # 3. Run link gap analysis vs competitors
    print('[3/7] Running link gap analysis...')
    results['link_gap'] = _api_post('/api/backlinks/link-gap', {
        'domain': OUR_DOMAIN, 'competitors': COMPETITORS[:3]
    })

    # 4. Check AI citation authority
    print('[4/7] Probing AI citation authority...')
    results['citation'] = _api_post('/api/backlinks/citation-authority', {
        'queries': [
            'What are the best AI SEO tools?',
            'Best GEO optimization platform',
            'How to optimize for AI search engines',
        ],
        'niche': OUR_NICHE,
    })

    # 5. Generate content seeding plan
    print('[5/7] Generating seeding plan...')
    results['seeding'] = _api_post('/api/backlinks/seeding-plan', {
        'niche': OUR_NICHE, 'brand': OUR_BRAND
    })

    # 6. Fingerprint how AI talks about us
    print('[6/7] Fingerprinting AI responses...')
    results['fingerprint'] = _api_post('/api/backlinks/fingerprint-probe', {
        'query': 'What is AI 1st SEO and is it any good?',
        'model': 'default',
        'brand': OUR_BRAND,
    })

    # 7. Get priority queue
    print('[7/7] Getting priority queue...')
    results['queue'] = _api_get('/api/backlinks/priority-queue')

    # Build email summary
    summary_lines = [
        'AI 1st SEO — Weekly Self-Optimization Report',
        '=' * 50,
        'Generated: {}'.format(_now()[:10]),
        '',
    ]

    # DA Score
    da = results.get('da_score', {})
    if 'da_score' in da:
        summary_lines.append('DOMAIN AUTHORITY: {}/100'.format(da['da_score']))
    else:
        summary_lines.append('DOMAIN AUTHORITY: Error - {}'.format(da.get('error', 'unknown')))

    # Mentions
    mentions = results.get('mentions', {})
    if 'total_mentions' in mentions:
        summary_lines.append('')
        summary_lines.append('BRAND MENTIONS: {} total, {} unlinked (outreach opportunities)'.format(
            mentions['total_mentions'], mentions['unlinked_count']))
    
    # Link Gap
    gap = results.get('link_gap', {})
    if 'gaps' in gap:
        summary_lines.append('')
        summary_lines.append('LINK GAPS vs COMPETITORS: {} gaps found'.format(gap.get('total_gaps', 0)))
        for g in gap.get('gaps', [])[:3]:
            summary_lines.append('  - {} (DA: {}, advantage: {} points)'.format(
                g.get('competitor', ''), g.get('competitor_da', 0), g.get('advantage', 0)))

    # Citation
    citation = results.get('citation', {})
    if 'total_domains_cited' in citation:
        summary_lines.append('')
        summary_lines.append('AI CITATION: {} domains cited by AI models'.format(citation['total_domains_cited']))
        our_cited = any(OUR_DOMAIN in (c.get('domain', '') or '') for c in citation.get('top_cited', []))
        summary_lines.append('  AI 1st SEO cited: {}'.format('YES' if our_cited else 'NO — action needed'))

    # Seeding Plan
    seeding = results.get('seeding', {})
    if 'platforms' in seeding:
        summary_lines.append('')
        summary_lines.append('CONTENT SEEDING PRIORITIES:')
        for p in seeding.get('platforms', [])[:5]:
            summary_lines.append('  [{}] {} — {}'.format(p.get('priority', ''), p.get('platform', ''), p.get('action', '')[:60]))

    # Fingerprint
    fp = results.get('fingerprint', {})
    if 'changed' in fp:
        summary_lines.append('')
        summary_lines.append('AI ANSWER FINGERPRINT: {}'.format('CHANGED' if fp['changed'] else 'Stable (no change)'))
        if fp.get('brand_mentioned'):
            summary_lines.append('  Brand mentioned in AI response: YES')
        else:
            summary_lines.append('  Brand mentioned in AI response: NO — need more visibility')

    # Priority Queue
    queue = results.get('queue', {})
    if 'total' in queue:
        summary_lines.append('')
        summary_lines.append('OPPORTUNITY QUEUE: {} total opportunities'.format(queue['total']))
        summary_lines.append('  By type: {}'.format(json.dumps(queue.get('by_type', {}))))

    # Action items
    summary_lines.extend([
        '',
        '=' * 50,
        'ACTION ITEMS:',
    ])
    if mentions.get('unlinked_count', 0) > 0:
        summary_lines.append('  1. Send outreach to {} unlinked mentions'.format(mentions['unlinked_count']))
    if not any(OUR_DOMAIN in (c.get('domain', '') or '') for c in citation.get('top_cited', [])):
        summary_lines.append('  2. Increase AI visibility — post on Reddit, GitHub, answer Stack Overflow questions')
    if gap.get('total_gaps', 0) > 0:
        summary_lines.append('  3. Close {} competitive gaps — focus on domains where competitors outperform'.format(gap.get('total_gaps', 0)))
    if not fp.get('brand_mentioned'):
        summary_lines.append('  4. AI models not mentioning our brand — need content seeding on trusted platforms')

    summary_lines.extend(['', '---', 'AI 1st SEO Self-Optimization Pipeline', 'https://ai1stseo.com'])

    # Send email
    body = '\n'.join(summary_lines)
    try:
        ses.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': ALERT_RECIPIENTS},
            Message={
                'Subject': {'Data': 'AI 1st SEO — Weekly Self-Optimization Report ({})'.format(_now()[:10])},
                'Body': {'Text': {'Data': body}},
            },
        )
        print('Report emailed to {}'.format(ALERT_RECIPIENTS))
    except Exception as e:
        print('Email failed: {}'.format(e))

    # Store results
    table = dynamodb.Table('ai1stseo-backlinks')
    import uuid
    table.put_item(Item={
        'id': str(uuid.uuid4()),
        'type': 'self_optimization_report',
        'domain': OUR_DOMAIN,
        'da_score': da.get('da_score', 0),
        'mentions_found': mentions.get('total_mentions', 0),
        'unlinked_mentions': mentions.get('unlinked_count', 0),
        'gaps_found': gap.get('total_gaps', 0),
        'ai_cited': any(OUR_DOMAIN in (c.get('domain', '') or '') for c in citation.get('top_cited', [])),
        'queue_size': queue.get('total', 0),
        'created_at': _now(),
    })

    print('Self-optimization complete')
    return {
        'status': 'complete',
        'da_score': da.get('da_score', 0),
        'mentions': mentions.get('total_mentions', 0),
        'gaps': gap.get('total_gaps', 0),
        'queue_size': queue.get('total', 0),
    }
