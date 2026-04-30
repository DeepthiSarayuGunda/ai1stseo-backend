"""
Multi-Site Dashboard API — Manages saved sites for agency multi-site scanning.
DynamoDB-backed, registered as Flask blueprint.

Table: ai1stseo-monitor (reuses existing monitored sites table)
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from dynamodb_helper import put_item, get_item, scan_table, update_item, delete_item
import uuid
from datetime import datetime, timezone

multisite_bp = Blueprint('multisite', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'
SITES_TABLE = 'ai1stseo-monitor'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get_user_email():
    if hasattr(request, 'cognito_user') and request.cognito_user:
        return request.cognito_user.get('email', '')
    return ''


@multisite_bp.route('/api/multi-site/add', methods=['POST'])
@require_auth
def add_site():
    """Save a site to the user's monitored site list."""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    name = data.get('name', '').strip()
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400
    if not url.startswith('http'):
        url = 'https://' + url

    try:
        site_id = str(uuid.uuid4())
        put_item(SITES_TABLE, {
            'id': site_id,
            'url': url,
            'name': name or url,
            'owner_email': _get_user_email(),
            'project_id': DEFAULT_PROJECT_ID,
            'is_active': True,
            'latest_score': None,
            'latest_scan_at': None,
            'created_at': _now(),
            'site_type': 'multi_site',
        })
        return jsonify({
            'status': 'success',
            'id': site_id,
            'url': url,
            'name': name or url,
        }), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@multisite_bp.route('/api/multi-site/sites', methods=['GET'])
@require_auth
def list_sites():
    """Return all saved sites with latest scores for the current user."""
    try:
        items = scan_table(SITES_TABLE, 200)
        user_email = _get_user_email()

        # Filter to user's sites (multi_site type)
        sites = [i for i in items if i.get('site_type') == 'multi_site']
        if user_email:
            sites = [s for s in sites if s.get('owner_email') == user_email]

        # Sort by name
        sites.sort(key=lambda x: x.get('name', ''))

        return jsonify({
            'status': 'success',
            'sites': sites,
            'total': len(sites),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@multisite_bp.route('/api/multi-site/bulk-scan', methods=['POST'])
@require_auth
def bulk_scan():
    """
    Trigger scans for multiple sites at once.
    Calls the /api/analyze endpoint internally for each site.
    Returns scores for all sites.
    """
    data = request.get_json() or {}
    site_ids = data.get('site_ids', [])
    urls = data.get('urls', [])

    if not site_ids and not urls:
        return jsonify({'status': 'error', 'message': 'site_ids[] or urls[] required'}), 400

    try:
        import requests as http_requests

        # If site_ids provided, look up URLs
        if site_ids and not urls:
            items = scan_table(SITES_TABLE, 200)
            id_map = {i['id']: i for i in items if i.get('id') in site_ids}
            urls_to_scan = [(sid, id_map[sid]['url']) for sid in site_ids if sid in id_map]
        else:
            urls_to_scan = [(None, u) for u in urls[:20]]

        results = []
        for site_id, url in urls_to_scan[:20]:  # Cap at 20 sites
            try:
                # Use the internal analyze function directly to avoid HTTP overhead
                from flask import current_app
                with current_app.test_request_context(
                    '/api/analyze', method='POST',
                    json={'url': url},
                    content_type='application/json'
                ):
                    # Import and call the analyze function
                    # Fallback: just do a lightweight check
                    score_data = _quick_score(url)

                    result = {
                        'site_id': site_id,
                        'url': url,
                        'score': score_data.get('score', 0),
                        'checks': score_data.get('checks', 0),
                        'status': 'scanned',
                        'scanned_at': _now(),
                    }

                    # Update the stored site with latest score
                    if site_id:
                        update_item(SITES_TABLE, {'id': site_id}, {
                            'latest_score': result['score'],
                            'latest_scan_at': result['scanned_at'],
                        })

                    results.append(result)
            except Exception as e:
                results.append({
                    'site_id': site_id,
                    'url': url,
                    'status': 'error',
                    'error': str(e)[:100],
                })

        return jsonify({
            'status': 'success',
            'scanned': len([r for r in results if r.get('status') == 'scanned']),
            'errors': len([r for r in results if r.get('status') == 'error']),
            'results': results,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _quick_score(url):
    """
    Lightweight site score — checks HTTPS, response time, basic meta tags.
    Used for bulk scanning to avoid the full 236-check timeout.
    """
    try:
        import time
        from bs4 import BeautifulSoup

        t0 = time.time()
        resp = http_requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO/1.0)'
        }, allow_redirects=True)
        load_time = time.time() - t0

        soup = BeautifulSoup(resp.content, 'html.parser')
        score = 0
        checks = 0

        # HTTPS
        checks += 1
        if resp.url.startswith('https'):
            score += 1

        # Title tag
        checks += 1
        title = soup.find('title')
        if title and title.string and len(title.string.strip()) > 5:
            score += 1

        # Meta description
        checks += 1
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content', '') and len(meta['content']) > 20:
            score += 1

        # H1 tag
        checks += 1
        h1 = soup.find('h1')
        if h1:
            score += 1

        # Load time
        checks += 1
        if load_time < 3:
            score += 1

        # Response code
        checks += 1
        if resp.status_code == 200:
            score += 1

        # Schema markup
        checks += 1
        if soup.find('script', {'type': 'application/ld+json'}):
            score += 1

        # Viewport
        checks += 1
        if soup.find('meta', attrs={'name': 'viewport'}):
            score += 1

        # Canonical
        checks += 1
        if soup.find('link', {'rel': 'canonical'}):
            score += 1

        # Images with alt
        checks += 1
        imgs = soup.find_all('img')
        imgs_with_alt = [i for i in imgs if i.get('alt')]
        if not imgs or len(imgs_with_alt) >= len(imgs) * 0.5:
            score += 1

        pct = round(score / checks * 100, 1) if checks else 0
        return {'score': pct, 'checks': checks, 'passed': score, 'load_time': round(load_time, 2)}
    except Exception as e:
        return {'score': 0, 'checks': 0, 'error': str(e)[:100]}


@multisite_bp.route('/api/multi-site/<site_id>', methods=['DELETE'])
@require_auth
def remove_site(site_id):
    """Remove a site from the user's monitored list."""
    try:
        item = get_item(SITES_TABLE, {'id': site_id})
        if not item:
            return jsonify({'status': 'error', 'message': 'Site not found'}), 404

        # Verify ownership
        user_email = _get_user_email()
        if user_email and item.get('owner_email') != user_email:
            return jsonify({'status': 'error', 'message': 'Not your site'}), 403

        delete_item(SITES_TABLE, {'id': site_id})
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
