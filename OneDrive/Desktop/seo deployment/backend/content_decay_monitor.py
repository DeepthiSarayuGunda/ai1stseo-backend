"""
Content Decay Monitor — Scheduled Lambda.
Detects pages whose SEO audit scores have declined over time.
Compares recent audits against historical baselines and flags pages
that need content refreshes.

Triggered by: EventBridge rule (weekly, Wednesdays 06:00 UTC)
"""
import boto3
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
ses = boto3.client('ses', region_name='us-east-1')

AUDITS_TABLE = 'ai1stseo-audits'
SES_SENDER = 'no-reply@ai1stseo.com'
ALERT_RECIPIENTS = ['saur0024@algonquinlive.com']
DECAY_THRESHOLD = 10  # Score drop of 10+ points triggers alert
PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _scan_audits():
    """Get all audits from DynamoDB."""
    table = dynamodb.Table(AUDITS_TABLE)
    items = []
    response = table.scan(Limit=500)
    items.extend(response.get('Items', []))
    return items


def _detect_decay(audits):
    """
    Group audits by URL, compare most recent score to historical average.
    Flag URLs where score dropped by more than DECAY_THRESHOLD.
    """
    by_url = defaultdict(list)
    for audit in audits:
        url = audit.get('url', '')
        score = audit.get('overall_score')
        created = audit.get('created_at', '')
        # Skip content-freshness records
        if audit.get('update_type'):
            continue
        if url and score is not None and created:
            by_url[url].append({
                'score': float(score),
                'created_at': created,
                'id': audit.get('id', ''),
            })

    decaying = []
    stable = []
    improving = []

    for url, url_audits in by_url.items():
        if len(url_audits) < 2:
            continue

        # Sort by date
        url_audits.sort(key=lambda x: x['created_at'])
        latest = url_audits[-1]
        previous = url_audits[-2]

        # Calculate trend
        change = latest['score'] - previous['score']

        # Also calculate average of all historical scores
        all_scores = [a['score'] for a in url_audits]
        avg_score = sum(all_scores) / len(all_scores)

        entry = {
            'url': url,
            'latest_score': latest['score'],
            'previous_score': previous['score'],
            'change': round(change, 1),
            'historical_avg': round(avg_score, 1),
            'audit_count': len(url_audits),
            'latest_audit_id': latest['id'],
            'latest_date': latest['created_at'],
        }

        if change <= -DECAY_THRESHOLD:
            entry['status'] = 'decaying'
            entry['severity'] = 'critical' if change <= -20 else 'warning'
            decaying.append(entry)
        elif change >= DECAY_THRESHOLD:
            entry['status'] = 'improving'
            improving.append(entry)
        else:
            entry['status'] = 'stable'
            stable.append(entry)

    return decaying, stable, improving


def _store_decay_report(decaying, stable, improving):
    """Store the decay analysis in DynamoDB."""
    import uuid
    table = dynamodb.Table(AUDITS_TABLE)
    report_id = str(uuid.uuid4())
    table.put_item(Item={
        'id': report_id,
        'update_type': 'decay_report',
        'url': 'system:decay-monitor',
        'decaying_count': len(decaying),
        'stable_count': len(stable),
        'improving_count': len(improving),
        'decaying_urls': decaying[:20],
        'improving_urls': improving[:10],
        'created_at': _now(),
        'project_id': PROJECT_ID,
    })
    return report_id


def _send_decay_alert(decaying, improving):
    """Send email alert if pages are decaying."""
    if not decaying:
        return

    subject = 'AI1stSEO Content Decay Alert: {} page(s) declining'.format(len(decaying))
    lines = [
        'Content Decay Monitor — {}'.format(_now()[:10]),
        '',
        '{} page(s) have declining SEO scores (threshold: -{} points):'.format(
            len(decaying), DECAY_THRESHOLD),
        '',
    ]
    for d in decaying[:10]:
        severity_icon = '🔴' if d['severity'] == 'critical' else '🟡'
        lines.append('  {} {} — dropped {} points ({} → {})'.format(
            severity_icon, d['url'][:60], abs(d['change']),
            d['previous_score'], d['latest_score']))

    if improving:
        lines.extend(['', '{} page(s) improving:'.format(len(improving)), ''])
        for i in improving[:5]:
            lines.append('  🟢 {} — gained {} points ({} → {})'.format(
                i['url'][:60], i['change'], i['previous_score'], i['latest_score']))

    lines.extend([
        '',
        'Action: Review decaying pages and update content to maintain rankings.',
        'Use POST /api/content-freshness to record updates after refreshing.',
        '',
        '---',
        'AI 1st SEO Content Decay Monitor',
    ])

    try:
        ses.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': ALERT_RECIPIENTS},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': '\n'.join(lines)}},
            },
        )
    except Exception as e:
        print('Decay alert email failed: {}'.format(e))


def lambda_handler(event, context):
    """EventBridge entry point. Runs weekly."""
    print('Content decay monitor starting at {}'.format(_now()))

    audits = _scan_audits()
    print('Found {} audits'.format(len(audits)))

    if not audits:
        return {'status': 'no_audits', 'count': 0}

    decaying, stable, improving = _detect_decay(audits)

    report_id = _store_decay_report(decaying, stable, improving)
    _send_decay_alert(decaying, improving)

    result = {
        'status': 'complete',
        'report_id': report_id,
        'total_urls_analyzed': len(decaying) + len(stable) + len(improving),
        'decaying': len(decaying),
        'stable': len(stable),
        'improving': len(improving),
    }
    print('Decay monitor complete: {}'.format(json.dumps(result)))
    return result
