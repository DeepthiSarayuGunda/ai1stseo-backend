"""
Scheduled Backlink Monitor — EventBridge-triggered Lambda.
Runs weekly to re-score tracked domains and check competitor DA changes.
Sends SNS/Slack alerts when significant changes are detected.

Triggered by: EventBridge rule (rate: 7 days)
"""
import boto3
import json
from datetime import datetime, timezone
from decimal import Decimal


dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
ses = boto3.client('ses', region_name='us-east-1')

BACKLINKS_TABLE = 'ai1stseo-backlinks'
ALERT_THRESHOLD = 5  # DA change of ±5 triggers an alert
SES_SENDER = 'no-reply@ai1stseo.com'
ALERT_RECIPIENTS = ['saur0024@algonquinlive.com']  # Troy gets alerts


def _now():
    return datetime.now(timezone.utc).isoformat()


def _scan_tracked_domains():
    """Get all unique domains that have been scored before."""
    table = dynamodb.Table(BACKLINKS_TABLE)
    items = table.scan(
        FilterExpression='#t = :ds',
        ExpressionAttributeNames={'#t': 'type'},
        ExpressionAttributeValues={':ds': 'domain_score'},
        Limit=500,
    ).get('Items', [])

    # Deduplicate by domain, keep the most recent score
    domains = {}
    for item in items:
        domain = item.get('domain', '')
        scored_at = item.get('scored_at', '')
        if domain and (domain not in domains or scored_at > domains[domain].get('scored_at', '')):
            domains[domain] = item

    return domains


def _get_competitor_domains():
    """Get domains from competitor alert history."""
    table = dynamodb.Table(BACKLINKS_TABLE)
    items = table.scan(
        FilterExpression='#t = :ca',
        ExpressionAttributeNames={'#t': 'type'},
        ExpressionAttributeValues={':ca': 'competitor_alert'},
        Limit=200,
    ).get('Items', [])

    competitors = set()
    for item in items:
        comp = item.get('competitor', '')
        if comp:
            competitors.add(comp)
    return competitors


def _estimate_domain_authority_light(domain):
    """
    Lightweight DA estimation — checks HTTPS, response time, and basic signals.
    Avoids full HTML parsing to stay within Lambda timeout.
    """
    import requests as http_requests
    from urllib.parse import urlparse

    score = 0
    signals = {}
    url = 'https://' + domain if not domain.startswith('http') else domain

    try:
        resp = http_requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO-Monitor/1.0)'
        }, allow_redirects=True)

        # HTTPS
        if resp.url.startswith('https'):
            score += 15
            signals['https'] = True

        # Response time
        elapsed_ms = int(resp.elapsed.total_seconds() * 1000)
        signals['response_time_ms'] = elapsed_ms
        if elapsed_ms < 500:
            score += 10
        elif elapsed_ms < 1500:
            score += 5

        # Security headers
        if resp.headers.get('Strict-Transport-Security'):
            score += 5
            signals['hsts'] = True
        if resp.headers.get('Content-Security-Policy'):
            score += 5
            signals['csp'] = True

        # Content length as proxy for depth
        content_len = len(resp.content)
        if content_len > 50000:
            score += 10
        elif content_len > 10000:
            score += 5
        signals['content_bytes'] = content_len

        # Robots.txt
        try:
            robots = http_requests.get(url.rstrip('/') + '/robots.txt', timeout=5)
            if robots.status_code == 200:
                score += 5
                signals['robots_txt'] = True
        except Exception:
            pass

        score = min(score, 100)

    except Exception as e:
        signals['error'] = str(e)[:200]
        score = 0

    return {
        'domain': domain,
        'da_score': score,
        'signals': signals,
        'scored_at': _now(),
    }


def _store_score(domain, da_score, signals):
    """Store a new domain score in DynamoDB."""
    import uuid
    table = dynamodb.Table(BACKLINKS_TABLE)
    table.put_item(Item={
        'id': str(uuid.uuid4()),
        'type': 'domain_score',
        'domain': domain,
        'da_score': da_score,
        'signals': signals,
        'scored_at': _now(),
        'source': 'scheduled_monitor',
        'project_id': '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2',
    })


def _send_alert_email(subject, body):
    """Send an alert email via SES."""
    try:
        ses.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': ALERT_RECIPIENTS},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}},
            },
        )
    except Exception as e:
        print('Alert email failed: {}'.format(e))


def lambda_handler(event, context):
    """
    EventBridge entry point. Runs weekly.
    1. Re-scores all tracked domains
    2. Compares against previous scores
    3. Sends alerts for significant changes
    """
    print('Scheduled backlink monitor starting at {}'.format(_now()))

    # Get all tracked domains
    tracked = _scan_tracked_domains()
    competitors = _get_competitor_domains()
    all_domains = set(tracked.keys()) | competitors

    if not all_domains:
        print('No tracked domains found. Exiting.')
        return {'status': 'no_domains', 'count': 0}

    print('Monitoring {} domains ({} scored, {} competitors)'.format(
        len(all_domains), len(tracked), len(competitors)))

    alerts = []
    scores_updated = 0
    errors = 0

    for domain in all_domains:
        try:
            # Score the domain
            result = _estimate_domain_authority_light(domain)
            new_score = result['da_score']

            # Compare to previous
            prev = tracked.get(domain)
            prev_score = int(prev.get('da_score', 0)) if prev else None

            # Store the new score
            _store_score(domain, new_score, result['signals'])
            scores_updated += 1

            # Check for significant change
            if prev_score is not None:
                change = new_score - prev_score
                if abs(change) >= ALERT_THRESHOLD:
                    direction = 'gained' if change > 0 else 'lost'
                    alert = {
                        'domain': domain,
                        'previous_da': prev_score,
                        'current_da': new_score,
                        'change': change,
                        'direction': direction,
                        'is_competitor': domain in competitors,
                    }
                    alerts.append(alert)
                    print('ALERT: {} {} {} DA points ({} -> {})'.format(
                        domain, direction, abs(change), prev_score, new_score))

        except Exception as e:
            errors += 1
            print('Error scoring {}: {}'.format(domain, e))

    # Send alert email if there are significant changes
    if alerts:
        subject = 'AI1stSEO Backlink Alert: {} domain(s) changed'.format(len(alerts))
        body_lines = [
            'Scheduled Backlink Monitor — {}'.format(_now()),
            '',
            '{} domain(s) had significant DA changes (threshold: ±{}):'.format(len(alerts), ALERT_THRESHOLD),
            '',
        ]
        for a in alerts:
            tag = '[COMPETITOR] ' if a['is_competitor'] else ''
            body_lines.append('  {}{}: {} {} points ({} -> {})'.format(
                tag, a['domain'], a['direction'], abs(a['change']), a['previous_da'], a['current_da']))
        body_lines.extend([
            '',
            'Total domains monitored: {}'.format(len(all_domains)),
            'Scores updated: {}'.format(scores_updated),
            'Errors: {}'.format(errors),
            '',
            '---',
            'AI 1st SEO Scheduled Monitor',
        ])
        _send_alert_email(subject, '\n'.join(body_lines))

    # Store the run summary
    import uuid
    table = dynamodb.Table(BACKLINKS_TABLE)
    table.put_item(Item={
        'id': str(uuid.uuid4()),
        'type': 'monitor_run',
        'domains_checked': len(all_domains),
        'scores_updated': scores_updated,
        'alerts_fired': len(alerts),
        'errors': errors,
        'created_at': _now(),
    })

    result = {
        'status': 'complete',
        'domains_checked': len(all_domains),
        'scores_updated': scores_updated,
        'alerts': len(alerts),
        'errors': errors,
    }
    print('Monitor complete: {}'.format(json.dumps(result)))
    return result
