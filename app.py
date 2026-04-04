"""
SEO Analyzer Backend - Flask API
200 Comprehensive SEO Checks across 10 categories
Based on SEMrush, Moz, Ahrefs, and industry best practices
"""

from flask import Flask, jsonify, request, send_from_directory, redirect, render_template
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
import time
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from collections import Counter
import json
import os

import boto3
import hmac
import base64

# Detect Lambda environment
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

app = Flask(__name__, static_folder='assets', static_url_path='/assets')
CORS(app, origins=[
    'https://ai1stseo.com',
    'https://www.ai1stseo.com',
    'https://automationhub.ai1stseo.com',
    'https://d6ugqfyp4h9y3.cloudfront.net',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'http://localhost:5001',
    'http://127.0.0.1:5001'
])

# --- Load .env for local development (Lambda sets env vars natively) ---
if not IS_LAMBDA:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # python-dotenv not installed — load .env manually
        _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(_env_path):
            with open(_env_path) as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith('#') and '=' in _line:
                        _k, _v = _line.split('=', 1)
                        os.environ.setdefault(_k.strip(), _v.strip())

# --- Blueprint registrations (auth, admin, data, webhooks, API keys) ---
try:
    from auth import auth_bp
    app.register_blueprint(auth_bp)
except Exception:
    pass
try:
    from admin_api import admin_bp
    app.register_blueprint(admin_bp)
except Exception:
    pass
try:
    from data_api import data_bp
    app.register_blueprint(data_bp)
except Exception:
    pass
try:
    from webhook_api import webhook_bp
    app.register_blueprint(webhook_bp)
except Exception:
    pass
try:
    from apikey_api import apikey_bp
    app.register_blueprint(apikey_bp)
except Exception:
    pass

# --- AI Business Directory routes (isolated module) ---
try:
    from directory.routes import register_directory_routes
    register_directory_routes(app)
except Exception:
    pass

# --- Month 3 Intelligence Systems API ---
try:
    from month3_systems.api import m3_bp
    app.register_blueprint(m3_bp)
except Exception as e:
    print(f"⚠ Month 3 systems: {e}")

# --- Troy's blueprints: auth, admin, data API, webhooks, API keys ---
try:
    from auth import auth_bp
    app.register_blueprint(auth_bp)
    print("✓ auth blueprint registered")
except Exception as e:
    print(f"⚠ auth blueprint: {e}")

try:
    from admin_api import admin_bp
    app.register_blueprint(admin_bp)
    print("✓ admin_api blueprint registered")
except Exception as e:
    print(f"⚠ admin_api blueprint: {e}")

try:
    from data_api import data_bp
    app.register_blueprint(data_bp)
    print("✓ data_api blueprint registered")
except Exception as e:
    print(f"⚠ data_api blueprint: {e}")

try:
    from webhook_api import webhook_bp
    app.register_blueprint(webhook_bp)
    print("✓ webhook_api blueprint registered")
except Exception as e:
    print(f"⚠ webhook_api blueprint: {e}")

try:
    from apikey_api import apikey_bp
    app.register_blueprint(apikey_bp)
    print("✓ apikey_api blueprint registered")
except Exception as e:
    print(f"⚠ apikey_api blueprint: {e}")

# ── Global JSON error handlers (prevent HTML error pages for API routes) ──────
@app.errorhandler(500)
def handle_500(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500
    return e

@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found', 'status': 'error'}), 404
    return e

@app.errorhandler(405)
def handle_405(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Method not allowed', 'status': 'error'}), 405
    return e

@app.errorhandler(400)
def handle_400(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Bad request', 'status': 'error'}), 400
    return e

# ── Database initialization ────────────────────────────────────────────────────
# RDS is stopped per Gurbachan/Troy directive — use DynamoDB directly.
# Set USE_DYNAMODB=True to skip the RDS connection attempt (avoids 10s+ timeout on Lambda cold start).
# To re-enable RDS: set env var USE_RDS=1
USE_DYNAMODB = not bool(os.environ.get("USE_RDS"))
if not USE_DYNAMODB:
    try:
        from db import init_db
        init_db()
        print("✓ RDS tables initialized (geo_probes, ai_visibility_history)")
    except Exception as e:
        print(f"⚠ RDS init failed, switching to DynamoDB: {e}")
        USE_DYNAMODB = True

if USE_DYNAMODB:
    try:
        from db_dynamo import init_db
        init_db()
        print("✓ DynamoDB mode active")
    except Exception as e2:
        print(f"⚠ DynamoDB init also failed: {e2}")

# AWS Cognito Configuration
COGNITO_USER_POOL_ID = 'us-east-1_DVvth47zH'
COGNITO_CLIENT_ID = '7scsae79o2g9idc92eputcrvrg'
COGNITO_CLIENT_SECRET = '1qg2tetso18gkhsmfte0c565ull6lp02la484ojaj5k85pvk9p49'
AWS_REGION = 'us-east-1'
SES_SENDER = 'no-reply@ai1stseo.com'
COGNITO_ENDPOINT = f'https://cognito-idp.{AWS_REGION}.amazonaws.com/'

# SES client - only works if AWS credentials are available (App Runner instance role)
ses_client = None
try:
    ses_client = boto3.client('ses', region_name=AWS_REGION)
except Exception:
    print("SES client not available - welcome emails will be skipped")

def get_secret_hash(username):
    """Compute Cognito SECRET_HASH for client with secret"""
    msg = username + COGNITO_CLIENT_ID
    dig = hmac.new(
        COGNITO_CLIENT_SECRET.encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()

def cognito_request(action, payload):
    """Make a direct HTTP request to Cognito (no AWS credentials needed for public APIs)"""
    headers = {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': f'AWSCognitoIdentityProviderService.{action}'
    }
    resp = requests.post(COGNITO_ENDPOINT, json=payload, headers=headers)
    return resp.json(), resp.status_code

def send_welcome_email(email, name):
    """Send welcome email via SES"""
    if not ses_client:
        print(f"SES not available - skipping welcome email for {email}")
        return False
    try:
        subject = "Welcome to AI1stSEO — Your AI-First SEO Platform"
        html_body = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #ffffff; padding: 40px;">
            <div style="max-width: 600px; margin: 0 auto; background: rgba(255,255,255,0.05); border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); padding: 40px;">
                <h1 style="background: linear-gradient(90deg, #00d4ff, #7b2cbf); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; font-size: 2rem;">AISEO Master</h1>
                <h2 style="color: #00d4ff; text-align: center;">Welcome, {name}!</h2>
                <p style="color: rgba(255,255,255,0.8); line-height: 1.8; font-size: 1rem;">
                    Thank you for joining <strong>AI1stSEO</strong> — the AI-First SEO Platform. We're excited to have you on board!
                </p>
                <p style="color: rgba(255,255,255,0.8); line-height: 1.8; font-size: 1rem;">
                    Here's what you can do with your account:
                </p>
                <ul style="color: rgba(255,255,255,0.8); line-height: 2; font-size: 1rem;">
                    <li><strong>SEO Analyzer</strong> — Run comprehensive 180-point SEO audits on any website</li>
                    <li><strong>9 Audit Categories</strong> — Technical, On-Page, Content, Mobile, Performance, Security, Social, Local, and GEO/AEO</li>
                    <li><strong>AI Optimization</strong> — Get insights for ChatGPT, Perplexity, Claude, and Gemini discovery</li>
                    <li><strong>Detailed Reports</strong> — Actionable recommendations with impact ratings</li>
                </ul>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://ai1stseo.com" style="display: inline-block; padding: 14px 40px; background: linear-gradient(90deg, #00d4ff, #7b2cbf); color: #fff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 1rem;">Start Analyzing →</a>
                </div>
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <p style="color: rgba(255,255,255,0.5); font-size: 0.85rem;">
                        AI1stSEO — Optimize for AI Discovery<br>
                        <a href="https://ai1stseo.com" style="color: #00d4ff; text-decoration: none;">ai1stseo.com</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"Welcome to AI1stSEO, {name}! Start analyzing websites at https://ai1stseo.com"

        ses_client.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                }
            }
        )
        print(f"Welcome email sent to {email}")
        return True
    except Exception as e:
        print(f"Failed to send welcome email to {email}: {e}")
        return False

def fetch_website(url):
    """Fetch website content with timing"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    start_time = time.time()
    response = requests.get(url, headers=headers, timeout=15)
    load_time = time.time() - start_time
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    return response, soup, load_time

def safe_get(url, timeout=5):
    """Safe GET request"""
    try:
        return requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=timeout)
    except:
        return None

def add_check(checks, name, status, desc, value, rec, impact, cat=None):
    """Add a check to the list"""
    checks.append({'name': name, 'status': status, 'description': desc, 
                   'value': str(value)[:200], 'recommendation': rec, 
                   'impact': impact, 'category': cat or 'General'})


# ============== TECHNICAL SEO (35 checks) ==============
def analyze_technical_seo(url, soup, response, load_time):
    checks = []
    parsed = urlparse(url)
    html = str(soup)
    
    # 1-7: Crawlability
    robots = safe_get(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    add_check(checks, 'Robots.txt', 'pass' if robots and robots.status_code == 200 else 'warning',
              'Robots.txt accessibility', 'Found' if robots and robots.status_code == 200 else 'Not found',
              'Create robots.txt file', 'High', 'Crawlability')
    
    meta_robots = soup.find('meta', {'name': 'robots'})
    robots_content = meta_robots.get('content', '').lower() if meta_robots else ''
    add_check(checks, 'Meta Robots', 'pass' if 'noindex' not in robots_content else 'fail',
              'Page indexability', robots_content or 'Not set (indexable)', 'Remove noindex if needed', 'Critical', 'Crawlability')
    
    sitemap = safe_get(f"{parsed.scheme}://{parsed.netloc}/sitemap.xml")
    add_check(checks, 'XML Sitemap', 'pass' if sitemap and sitemap.status_code == 200 else 'warning',
              'Sitemap availability', 'Found' if sitemap and sitemap.status_code == 200 else 'Not found',
              'Create XML sitemap', 'High', 'Crawlability')
    
    canonical = soup.find('link', {'rel': 'canonical'})
    add_check(checks, 'Canonical URL', 'pass' if canonical else 'warning',
              'Canonical tag presence', canonical.get('href', '')[:60] if canonical else 'Not set',
              'Add canonical tag', 'High', 'Crawlability')
    
    # Check if canonical is self-referencing
    canonical_href = canonical.get('href', '') if canonical else ''
    is_self_canonical = url in canonical_href or canonical_href in url
    add_check(checks, 'Self-Referencing Canonical', 'pass' if is_self_canonical or not canonical else 'warning',
              'Canonical points to self', 'Yes' if is_self_canonical else 'No',
              'Use self-referencing canonical', 'Medium', 'Crawlability')
    
    hreflang = soup.find_all('link', {'hreflang': True})
    add_check(checks, 'Hreflang Tags', 'pass' if hreflang else 'info',
              'International targeting', f'{len(hreflang)} tags', 'Add for multi-language sites', 'Medium', 'Crawlability')
    
    # Check for noindex in X-Robots-Tag header
    x_robots = response.headers.get('X-Robots-Tag', '')
    add_check(checks, 'X-Robots-Tag', 'pass' if 'noindex' not in x_robots.lower() else 'fail',
              'HTTP header indexability', x_robots or 'Not set', 'Remove noindex from header', 'High', 'Crawlability')
    
    # 8-14: Security
    add_check(checks, 'HTTPS', 'pass' if parsed.scheme == 'https' else 'fail',
              'Secure protocol', parsed.scheme.upper(), 'Enable SSL certificate', 'Critical', 'Security')
    
    hsts = response.headers.get('Strict-Transport-Security', '')
    add_check(checks, 'HSTS Header', 'pass' if hsts else 'warning',
              'HTTP Strict Transport Security', 'Enabled' if hsts else 'Not set', 'Enable HSTS', 'Medium', 'Security')
    
    xcto = response.headers.get('X-Content-Type-Options', '')
    add_check(checks, 'X-Content-Type-Options', 'pass' if xcto else 'warning',
              'MIME sniffing protection', xcto or 'Not set', 'Add nosniff header', 'Medium', 'Security')
    
    xfo = response.headers.get('X-Frame-Options', '')
    add_check(checks, 'X-Frame-Options', 'pass' if xfo else 'warning',
              'Clickjacking protection', xfo or 'Not set', 'Add X-Frame-Options', 'Medium', 'Security')
    
    csp = response.headers.get('Content-Security-Policy', '')
    add_check(checks, 'Content-Security-Policy', 'pass' if csp else 'info',
              'CSP header', 'Set' if csp else 'Not set', 'Implement CSP', 'Medium', 'Security')
    
    mixed = len(soup.find_all(src=re.compile(r'^http://')))
    add_check(checks, 'No Mixed Content', 'pass' if mixed == 0 else 'warning',
              'All resources HTTPS', f'{mixed} insecure resources', 'Fix mixed content', 'High', 'Security')
    
    # Check for password fields on HTTP
    password_fields = soup.find_all('input', {'type': 'password'})
    add_check(checks, 'Secure Password Fields', 'pass' if parsed.scheme == 'https' or not password_fields else 'fail',
              'Password fields on HTTPS', f'{len(password_fields)} fields', 'Use HTTPS for login pages', 'Critical', 'Security')
    
    # 15-23: URL Structure
    add_check(checks, 'URL Length', 'pass' if len(url) < 75 else 'warning',
              'URL characters', f'{len(url)} chars', 'Keep under 75 characters', 'Medium', 'URL Structure')
    
    add_check(checks, 'URL Lowercase', 'pass' if url == url.lower() else 'warning',
              'Lowercase URL', 'Yes' if url == url.lower() else 'Has uppercase', 'Use lowercase URLs', 'Medium', 'URL Structure')
    
    add_check(checks, 'URL Hyphens', 'pass' if '_' not in parsed.path else 'warning',
              'Word separators', 'Hyphens' if '_' not in parsed.path else 'Has underscores', 'Use hyphens not underscores', 'Medium', 'URL Structure')
    
    depth = len([p for p in parsed.path.split('/') if p])
    add_check(checks, 'URL Depth', 'pass' if depth <= 3 else 'warning',
              'Directory levels', f'{depth} levels', 'Keep within 3 levels', 'Medium', 'URL Structure')
    
    # Check for URL parameters
    params = parsed.query
    param_count = len(params.split('&')) if params else 0
    add_check(checks, 'URL Parameters', 'pass' if param_count <= 2 else 'warning',
              'Query parameters', f'{param_count} parameters', 'Minimize URL parameters', 'Medium', 'URL Structure')
    
    # Check for special characters in URL
    special_chars = re.findall(r'[^a-zA-Z0-9\-\_\/\.\:]', parsed.path)
    add_check(checks, 'Clean URL', 'pass' if not special_chars else 'warning',
              'Special characters', f'{len(special_chars)} found', 'Remove special characters', 'Medium', 'URL Structure')
    
    # 24-30: Internal Linking
    all_links = soup.find_all('a', href=True)
    internal = [l for l in all_links if parsed.netloc in urljoin(url, l.get('href', ''))]
    add_check(checks, 'Internal Links', 'pass' if len(internal) >= 3 else 'warning',
              'Internal linking', f'{len(internal)} links', 'Add 3-10 internal links', 'High', 'Internal Linking')
    
    external = [l for l in all_links if l.get('href', '').startswith('http') and parsed.netloc not in l.get('href', '')]
    add_check(checks, 'External Links', 'pass' if external else 'info',
              'Outbound links', f'{len(external)} links', 'Link to authority sites', 'Medium', 'Internal Linking')
    
    # Check for broken link indicators (empty hrefs)
    empty_links = [l for l in all_links if not l.get('href', '').strip() or l.get('href', '') == '#']
    add_check(checks, 'Valid Link Hrefs', 'pass' if len(empty_links) < 3 else 'warning',
              'Empty/placeholder links', f'{len(empty_links)} found', 'Fix empty href attributes', 'Medium', 'Internal Linking')
    
    # Check for nofollow on internal links
    nofollow_internal = [l for l in internal if 'nofollow' in str(l.get('rel', []))]
    add_check(checks, 'Internal Nofollow', 'pass' if not nofollow_internal else 'warning',
              'Nofollow on internal links', f'{len(nofollow_internal)} found', 'Remove nofollow from internal links', 'Medium', 'Internal Linking')
    
    # Check anchor text quality
    generic_anchors = ['click here', 'read more', 'learn more', 'here', 'link']
    generic_links = [l for l in all_links if l.get_text().strip().lower() in generic_anchors]
    add_check(checks, 'Descriptive Anchors', 'pass' if len(generic_links) <= 2 else 'warning',
              'Generic anchor text', f'{len(generic_links)} generic', 'Use descriptive anchor text', 'Medium', 'Internal Linking')
    
    # 31-35: Structured Data & Technical
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    add_check(checks, 'Schema.org JSON-LD', 'pass' if json_ld else 'warning',
              'Structured data', f'{len(json_ld)} blocks', 'Add Schema.org markup', 'High', 'Structured Data')
    
    microdata = soup.find_all(attrs={'itemtype': True})
    add_check(checks, 'Microdata', 'pass' if microdata or json_ld else 'info',
              'Microdata markup', f'{len(microdata)} items', 'Consider adding microdata', 'Low', 'Structured Data')
    
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    add_check(checks, 'Viewport Meta', 'pass' if viewport else 'fail',
              'Mobile viewport', viewport.get('content', '')[:40] if viewport else 'Not set', 'Add viewport meta tag', 'Critical', 'Technical')
    
    doctype = '<!doctype' in html.lower()[:100]
    add_check(checks, 'DOCTYPE Declaration', 'pass' if doctype else 'warning',
              'HTML DOCTYPE', 'Present' if doctype else 'Missing', 'Add DOCTYPE declaration', 'Medium', 'Technical')
    
    charset = soup.find('meta', charset=True) or soup.find('meta', {'http-equiv': 'Content-Type'})
    add_check(checks, 'Character Encoding', 'pass' if charset else 'warning',
              'Charset declaration', 'UTF-8' if charset else 'Not set', 'Declare character encoding', 'High', 'Technical')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== ON-PAGE SEO (25 checks) ==============
def analyze_onpage_seo(url, soup, response, load_time):
    checks = []
    text = soup.get_text()
    
    # 1-8: Title & Meta
    title = soup.find('title')
    title_text = title.string.strip() if title and title.string else ''
    add_check(checks, 'Title Tag Present', 'pass' if title_text else 'fail',
              'Title tag exists', title_text[:50] + '...' if len(title_text) > 50 else title_text or 'Missing',
              'Add descriptive title tag', 'Critical', 'Title & Meta')
    
    add_check(checks, 'Title Length', 'pass' if 30 <= len(title_text) <= 60 else 'warning',
              'Title characters', f'{len(title_text)} chars', 'Optimize to 50-60 characters', 'High', 'Title & Meta')
    
    # Check for duplicate words in title
    title_words = title_text.lower().split()
    unique_title_words = set(title_words)
    add_check(checks, 'Title Uniqueness', 'pass' if len(unique_title_words) >= len(title_words) * 0.7 else 'warning',
              'Unique words in title', f'{len(unique_title_words)}/{len(title_words)}', 'Avoid repetitive words', 'Medium', 'Title & Meta')
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_text = meta_desc.get('content', '').strip() if meta_desc else ''
    add_check(checks, 'Meta Description', 'pass' if desc_text else 'fail',
              'Description presence', desc_text[:60] + '...' if len(desc_text) > 60 else desc_text or 'Missing',
              'Add meta description', 'High', 'Title & Meta')
    
    add_check(checks, 'Description Length', 'pass' if 120 <= len(desc_text) <= 160 else 'warning',
              'Description characters', f'{len(desc_text)} chars', 'Optimize to 150-160 characters', 'High', 'Title & Meta')
    
    meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
    add_check(checks, 'Meta Keywords', 'info',
              'Keywords meta tag', 'Present' if meta_keywords else 'Not set (OK - deprecated)',
              'Meta keywords are deprecated', 'Low', 'Title & Meta')
    
    html_tag = soup.find('html')
    lang = html_tag.get('lang', '') if html_tag else ''
    add_check(checks, 'Language Attribute', 'pass' if lang else 'warning',
              'HTML lang attribute', lang or 'Not set', 'Add lang attribute', 'Medium', 'Title & Meta')
    
    favicon = soup.find('link', rel=re.compile(r'icon', re.I))
    add_check(checks, 'Favicon', 'pass' if favicon else 'warning',
              'Site icon', 'Present' if favicon else 'Missing', 'Add favicon', 'Low', 'Title & Meta')
    
    # 9-15: Headings
    h1_tags = soup.find_all('h1')
    add_check(checks, 'H1 Tag', 'pass' if len(h1_tags) == 1 else ('fail' if not h1_tags else 'warning'),
              'H1 count', f'{len(h1_tags)} H1 tag(s)', 'Use exactly one H1', 'Critical', 'Headings')
    
    h1_text = h1_tags[0].get_text().strip() if h1_tags else ''
    add_check(checks, 'H1 Content', 'pass' if len(h1_text) >= 10 else 'warning',
              'H1 text length', f'{len(h1_text)} chars' if h1_text else 'Empty', 'Write descriptive H1', 'High', 'Headings')
    
    h2_tags = soup.find_all('h2')
    add_check(checks, 'H2 Tags', 'pass' if 2 <= len(h2_tags) <= 10 else 'warning',
              'H2 count', f'{len(h2_tags)} H2 tag(s)', 'Use 2-6 H2 tags for structure', 'High', 'Headings')
    
    h3_tags = soup.find_all('h3')
    add_check(checks, 'H3 Tags', 'pass' if h3_tags else 'info',
              'H3 count', f'{len(h3_tags)} H3 tag(s)', 'Use H3 for subsections', 'Low', 'Headings')
    
    all_headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    empty_h = [h for h in all_headings if not h.get_text().strip()]
    add_check(checks, 'No Empty Headings', 'pass' if not empty_h else 'warning',
              'Empty headings', f'{len(empty_h)} empty', 'Fill or remove empty headings', 'Medium', 'Headings')
    
    # Check heading hierarchy
    heading_order = [int(h.name[1]) for h in all_headings]
    hierarchy_ok = all(heading_order[i] <= heading_order[i-1] + 1 for i in range(1, len(heading_order))) if heading_order else True
    add_check(checks, 'Heading Hierarchy', 'pass' if hierarchy_ok else 'warning',
              'Proper heading order', 'Correct' if hierarchy_ok else 'Skipped levels', 'Follow H1>H2>H3 order', 'Medium', 'Headings')
    
    # 16-21: Images
    images = soup.find_all('img')
    imgs_alt = [i for i in images if i.get('alt')]
    add_check(checks, 'Image Alt Text', 'pass' if len(imgs_alt) == len(images) or not images else 'warning',
              'Alt attributes', f'{len(imgs_alt)}/{len(images)}', 'Add alt to all images', 'High', 'Images')
    
    imgs_dims = [i for i in images if i.get('width') and i.get('height')]
    add_check(checks, 'Image Dimensions', 'pass' if len(imgs_dims) == len(images) or not images else 'warning',
              'Width/height set', f'{len(imgs_dims)}/{len(images)}', 'Specify dimensions to prevent CLS', 'Medium', 'Images')
    
    lazy_imgs = [i for i in images if i.get('loading') == 'lazy']
    add_check(checks, 'Lazy Loading', 'pass' if lazy_imgs or len(images) <= 3 else 'warning',
              'Lazy loaded images', f'{len(lazy_imgs)}/{len(images)}', 'Add loading="lazy"', 'Medium', 'Images')
    
    srcset = [i for i in images if i.get('srcset')]
    add_check(checks, 'Responsive Images', 'pass' if srcset or len(images) <= 2 else 'info',
              'Srcset usage', f'{len(srcset)} with srcset', 'Use srcset for responsive images', 'Medium', 'Images')
    
    # Check for large images without optimization hints
    webp_imgs = [i for i in images if '.webp' in str(i.get('src', ''))]
    add_check(checks, 'Modern Image Formats', 'pass' if webp_imgs or not images else 'info',
              'WebP images', f'{len(webp_imgs)} WebP', 'Consider WebP format', 'Low', 'Images')
    
    # Empty alt vs missing alt
    empty_alt = [i for i in images if i.get('alt') == '']
    add_check(checks, 'Meaningful Alt Text', 'pass' if len(empty_alt) <= len(images) * 0.2 else 'warning',
              'Non-empty alt text', f'{len(images) - len(empty_alt)}/{len(images)}', 'Add descriptive alt text', 'Medium', 'Images')
    
    # 22-25: Content Structure
    paragraphs = soup.find_all('p')
    add_check(checks, 'Paragraph Count', 'pass' if len(paragraphs) >= 3 else 'warning',
              'Paragraphs', f'{len(paragraphs)} paragraphs', 'Use paragraphs for readability', 'Medium', 'Content Structure')
    
    lists = soup.find_all(['ul', 'ol'])
    add_check(checks, 'List Usage', 'pass' if lists else 'info',
              'Lists present', f'{len(lists)} lists', 'Use lists for scannability', 'Low', 'Content Structure')
    
    word_count = len(text.split())
    add_check(checks, 'Word Count', 'pass' if word_count >= 300 else 'warning',
              'Content length', f'{word_count} words', 'Aim for 300+ words', 'Medium', 'Content Structure')
    
    # Check for thin content
    add_check(checks, 'Content Depth', 'pass' if word_count >= 500 else ('warning' if word_count >= 200 else 'fail'),
              'Content substance', 'Comprehensive' if word_count >= 500 else 'Thin content', 'Add more valuable content', 'High', 'Content Structure')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== CONTENT SEO (20 checks) ==============
def analyze_content_seo(url, soup, response, load_time):
    checks = []
    text = soup.get_text()
    words = text.split()
    word_count = len(words)
    parsed = urlparse(url)
    
    # 1-7: Content Quality
    add_check(checks, 'Content Length', 'pass' if word_count >= 1000 else ('warning' if word_count >= 300 else 'fail'),
              'Word count', f'{word_count} words', '1000+ words for comprehensive content', 'High', 'Content Quality')
    
    paragraphs = soup.find_all('p')
    para_count = len([p for p in paragraphs if len(p.get_text().strip()) > 20])
    add_check(checks, 'Paragraph Structure', 'pass' if para_count >= 5 else 'warning',
              'Substantial paragraphs', f'{para_count} paragraphs', 'Use 5+ meaningful paragraphs', 'Medium', 'Content Quality')
    
    # Readability - Flesch-like simple check
    sentences = re.split(r'[.!?]+', text)
    sent_count = len([s for s in sentences if len(s.split()) > 3])
    avg_sentence_len = word_count / sent_count if sent_count else 0
    add_check(checks, 'Sentence Length', 'pass' if 10 <= avg_sentence_len <= 20 else 'warning',
              'Average sentence length', f'{avg_sentence_len:.1f} words', 'Aim for 15-20 words per sentence', 'Medium', 'Content Quality')
    
    # Vocabulary diversity
    unique_words = len(set(w.lower() for w in words if len(w) > 3))
    ratio = unique_words / word_count if word_count else 0
    add_check(checks, 'Vocabulary Diversity', 'pass' if ratio > 0.3 else 'warning',
              'Unique words ratio', f'{ratio*100:.0f}% unique', 'Use varied vocabulary', 'Low', 'Content Quality')
    
    # Questions for engagement
    questions = text.count('?')
    add_check(checks, 'Engaging Questions', 'pass' if questions >= 1 else 'info',
              'Questions in content', f'{questions} questions', 'Include questions for engagement', 'Low', 'Content Quality')
    
    # Statistics and data
    numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?%?\b', text)
    add_check(checks, 'Data & Statistics', 'pass' if len(numbers) >= 3 else 'info',
              'Numerical data', f'{len(numbers)} data points', 'Include statistics for credibility', 'Medium', 'Content Quality')
    
    # Bold/emphasis usage
    bold = soup.find_all(['strong', 'b', 'em'])
    add_check(checks, 'Text Emphasis', 'pass' if bold else 'info',
              'Emphasized text', f'{len(bold)} elements', 'Use bold for key points', 'Low', 'Content Quality')
    
    # 8-13: Linking
    all_links = soup.find_all('a', href=True)
    internal = [l for l in all_links if parsed.netloc in urljoin(url, l.get('href', ''))]
    add_check(checks, 'Internal Links', 'pass' if 3 <= len(internal) <= 100 else 'warning',
              'Internal linking', f'{len(internal)} links', 'Add 3-10 internal links', 'High', 'Linking')
    
    external = [l for l in all_links if l.get('href', '').startswith('http') and parsed.netloc not in l.get('href', '')]
    add_check(checks, 'External Links', 'pass' if external else 'info',
              'Outbound links', f'{len(external)} links', 'Link to authority sources', 'Medium', 'Linking')
    
    link_density = len(all_links) / (word_count / 100) if word_count else 0
    add_check(checks, 'Link Density', 'pass' if 1 <= link_density <= 10 else 'warning',
              'Links per 100 words', f'{link_density:.1f}', 'Maintain 1-5 links per 100 words', 'Medium', 'Linking')
    
    # Nofollow on external
    nofollow_ext = [l for l in external if 'nofollow' in str(l.get('rel', []))]
    add_check(checks, 'External Nofollow', 'info',
              'Nofollow external links', f'{len(nofollow_ext)}/{len(external)}', 'Consider nofollow for untrusted links', 'Low', 'Linking')
    
    # Check for affiliate/sponsored links
    sponsored = [l for l in all_links if 'sponsored' in str(l.get('rel', [])) or 'ugc' in str(l.get('rel', []))]
    add_check(checks, 'Link Qualification', 'pass' if not external or sponsored or nofollow_ext else 'info',
              'Qualified links', f'{len(sponsored)} sponsored/ugc', 'Use rel attributes appropriately', 'Low', 'Linking')
    
    # 14-20: E-E-A-T Signals
    author = any(p in str(soup).lower() for p in ['author', 'written by', 'posted by', 'byline'])
    add_check(checks, 'Author Attribution', 'pass' if author else 'warning',
              'Author info', 'Present' if author else 'Not found', 'Add author bio for E-E-A-T', 'High', 'E-E-A-T')
    
    date_shown = any(p in str(soup).lower() for p in ['updated', 'published', 'modified', 'date'])
    add_check(checks, 'Content Date', 'pass' if date_shown else 'warning',
              'Date visible', 'Present' if date_shown else 'Not found', 'Show publish/update date', 'Medium', 'E-E-A-T')
    
    # About/Contact pages linked
    about_link = soup.find('a', href=re.compile(r'about|contact|team', re.I))
    add_check(checks, 'Trust Pages Linked', 'pass' if about_link else 'info',
              'About/Contact links', 'Found' if about_link else 'Not found', 'Link to About/Contact pages', 'Medium', 'E-E-A-T')
    
    # Citations/Sources
    citations = any(p in text.lower() for p in ['according to', 'source:', 'study shows', 'research', 'cited'])
    add_check(checks, 'Source Citations', 'pass' if citations else 'info',
              'Citations present', 'Found' if citations else 'Not found', 'Cite authoritative sources', 'Medium', 'E-E-A-T')
    
    # Expertise indicators
    expertise = any(p in text.lower() for p in ['years of experience', 'certified', 'expert', 'professional', 'specialist'])
    add_check(checks, 'Expertise Signals', 'pass' if expertise else 'info',
              'Expertise indicators', 'Found' if expertise else 'Not found', 'Demonstrate expertise', 'Medium', 'E-E-A-T')
    
    # Contact information
    contact_info = re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', text) or re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text)
    add_check(checks, 'Contact Information', 'pass' if contact_info else 'info',
              'Contact details', 'Found' if contact_info else 'Not found', 'Provide contact information', 'Medium', 'E-E-A-T')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== MOBILE SEO (15 checks) ==============
def analyze_mobile_seo(url, soup, response, load_time):
    checks = []
    html = str(soup)
    
    # 1-5: Viewport & Responsiveness
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    add_check(checks, 'Viewport Meta Tag', 'pass' if viewport else 'fail',
              'Viewport defined', viewport.get('content', '')[:50] if viewport else 'Missing',
              'Add viewport meta tag', 'Critical', 'Viewport')
    
    viewport_content = viewport.get('content', '') if viewport else ''
    has_width = 'width=' in viewport_content
    add_check(checks, 'Viewport Width', 'pass' if has_width else 'fail',
              'Width specified', 'Yes' if has_width else 'No', 'Set width=device-width', 'Critical', 'Viewport')
    
    has_scale = 'initial-scale' in viewport_content
    add_check(checks, 'Initial Scale', 'pass' if has_scale else 'warning',
              'Initial scale set', 'Yes' if has_scale else 'No', 'Set initial-scale=1', 'High', 'Viewport')
    
    # Check for user-scalable=no (bad for accessibility)
    no_scale = 'user-scalable=no' in viewport_content or 'maximum-scale=1' in viewport_content
    add_check(checks, 'Zoom Enabled', 'pass' if not no_scale else 'warning',
              'User can zoom', 'Yes' if not no_scale else 'Disabled', 'Allow user zooming for accessibility', 'Medium', 'Viewport')
    
    # Check for responsive CSS
    media_queries = '@media' in html
    add_check(checks, 'Media Queries', 'pass' if media_queries else 'warning',
              'Responsive CSS', 'Found' if media_queries else 'Not found', 'Use CSS media queries', 'High', 'Responsiveness')
    
    # 6-10: Touch & Mobile UX
    # Check for touch-friendly elements
    buttons = soup.find_all(['button', 'a'])
    small_targets = [b for b in buttons if b.get('style') and ('font-size: 1' in b.get('style', '') or 'padding: 0' in b.get('style', ''))]
    add_check(checks, 'Touch Targets', 'pass' if len(small_targets) < len(buttons) * 0.1 else 'warning',
              'Touch-friendly buttons', f'{len(buttons) - len(small_targets)}/{len(buttons)}', 'Use 48px minimum touch targets', 'Medium', 'Touch UX')
    
    # Check for mobile-unfriendly plugins
    flash = soup.find_all(['object', 'embed'])
    flash_content = [f for f in flash if 'flash' in str(f).lower() or 'swf' in str(f).lower()]
    add_check(checks, 'No Flash Content', 'pass' if not flash_content else 'fail',
              'Flash elements', f'{len(flash_content)} found', 'Remove Flash content', 'Critical', 'Mobile Compatibility')
    
    # Check for frames
    frames = soup.find_all(['frame', 'frameset'])
    add_check(checks, 'No Frames', 'pass' if not frames else 'fail',
              'Frame elements', f'{len(frames)} found', 'Remove frames', 'High', 'Mobile Compatibility')
    
    # Check for horizontal scroll indicators
    fixed_width = re.findall(r'width:\s*\d{4,}px', html)
    add_check(checks, 'No Fixed Width', 'pass' if not fixed_width else 'warning',
              'Fixed width elements', f'{len(fixed_width)} found', 'Use responsive widths', 'Medium', 'Responsiveness')
    
    # Check for mobile-friendly font sizes
    small_fonts = re.findall(r'font-size:\s*[0-9]px', html)
    add_check(checks, 'Readable Font Size', 'pass' if len(small_fonts) < 3 else 'warning',
              'Small fonts', f'{len(small_fonts)} found', 'Use 16px+ base font size', 'Medium', 'Readability')
    
    # 11-15: Mobile Performance
    images = soup.find_all('img')
    lazy_imgs = [i for i in images if i.get('loading') == 'lazy']
    add_check(checks, 'Image Lazy Loading', 'pass' if lazy_imgs or len(images) <= 3 else 'warning',
              'Lazy loaded', f'{len(lazy_imgs)}/{len(images)}', 'Add loading="lazy" for mobile', 'High', 'Mobile Performance')
    
    # Check page weight (HTML size)
    html_size = len(response.content) / 1024
    add_check(checks, 'Page Weight', 'pass' if html_size < 100 else 'warning',
              'HTML size', f'{html_size:.1f} KB', 'Keep HTML under 100KB', 'Medium', 'Mobile Performance')
    
    # Check for AMP
    amp_link = soup.find('link', rel='amphtml')
    add_check(checks, 'AMP Version', 'info',
              'AMP available', 'Yes' if amp_link else 'No', 'Consider AMP for mobile', 'Low', 'Mobile Performance')
    
    # Check for mobile app links
    app_links = soup.find_all('meta', property=re.compile(r'al:(ios|android)'))
    add_check(checks, 'App Deep Links', 'info',
              'App links', f'{len(app_links)} found', 'Add app deep links if applicable', 'Low', 'Mobile Integration')
    
    # Check for tel: links
    tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
    add_check(checks, 'Click-to-Call', 'pass' if tel_links else 'info',
              'Phone links', f'{len(tel_links)} found', 'Add tel: links for mobile', 'Medium', 'Mobile UX')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== PERFORMANCE SEO (18 checks) ==============
def analyze_performance_seo(url, soup, response, load_time):
    checks = []
    html = str(soup)
    
    # 1-5: Core Web Vitals Indicators
    add_check(checks, 'Page Load Time', 'pass' if load_time < 2 else ('warning' if load_time < 4 else 'fail'),
              'Server response time', f'{load_time:.2f}s', 'Optimize to under 2 seconds', 'Critical', 'Core Web Vitals')
    
    html_size = len(response.content) / 1024
    add_check(checks, 'HTML Size', 'pass' if html_size < 100 else ('warning' if html_size < 200 else 'fail'),
              'Document size', f'{html_size:.1f} KB', 'Keep HTML under 100KB', 'High', 'Core Web Vitals')
    
    # CLS indicators - images without dimensions
    images = soup.find_all('img')
    imgs_dims = [i for i in images if i.get('width') and i.get('height')]
    cls_risk = len(images) - len(imgs_dims)
    add_check(checks, 'CLS Prevention', 'pass' if cls_risk == 0 or not images else 'warning',
              'Images with dimensions', f'{len(imgs_dims)}/{len(images)}', 'Add width/height to prevent layout shift', 'High', 'Core Web Vitals')
    
    # LCP indicators - large images/videos above fold
    large_media = soup.find_all(['img', 'video'])[:3]  # First 3 are likely above fold
    preload = soup.find_all('link', rel='preload')
    add_check(checks, 'LCP Optimization', 'pass' if preload else 'info',
              'Preload hints', f'{len(preload)} preloads', 'Preload LCP element', 'High', 'Core Web Vitals')
    
    # INP/FID indicators - JavaScript blocking
    js_files = soup.find_all('script', src=True)
    async_defer = [s for s in js_files if s.get('async') or s.get('defer')]
    add_check(checks, 'Non-blocking JS', 'pass' if len(async_defer) >= len(js_files) * 0.5 or not js_files else 'warning',
              'Async/defer scripts', f'{len(async_defer)}/{len(js_files)}', 'Add async/defer to scripts', 'High', 'Core Web Vitals')
    
    # 6-10: Compression & Caching
    encoding = response.headers.get('Content-Encoding', '')
    add_check(checks, 'Compression', 'pass' if encoding in ['gzip', 'br', 'deflate'] else 'warning',
              'Response compression', encoding or 'None', 'Enable gzip/brotli compression', 'High', 'Compression')
    
    cache_control = response.headers.get('Cache-Control', '')
    add_check(checks, 'Cache Headers', 'pass' if cache_control else 'warning',
              'Cache-Control header', cache_control[:50] if cache_control else 'Not set', 'Set cache headers', 'Medium', 'Caching')
    
    etag = response.headers.get('ETag', '')
    add_check(checks, 'ETag Header', 'pass' if etag else 'info',
              'ETag for caching', 'Present' if etag else 'Not set', 'Enable ETag', 'Low', 'Caching')
    
    expires = response.headers.get('Expires', '')
    add_check(checks, 'Expires Header', 'pass' if expires or cache_control else 'info',
              'Expires header', 'Set' if expires else 'Not set', 'Set expiration for static assets', 'Low', 'Caching')
    
    # 11-15: Resource Optimization
    css_files = soup.find_all('link', rel='stylesheet')
    add_check(checks, 'CSS Files Count', 'pass' if len(css_files) <= 5 else 'warning',
              'Stylesheet count', f'{len(css_files)} files', 'Combine CSS files', 'Medium', 'Resources')
    
    add_check(checks, 'JS Files Count', 'pass' if len(js_files) <= 10 else 'warning',
              'Script count', f'{len(js_files)} files', 'Combine/minimize JS files', 'Medium', 'Resources')
    
    inline_styles = soup.find_all(style=True)
    add_check(checks, 'Inline Styles', 'pass' if len(inline_styles) < 20 else 'warning',
              'Inline style attributes', f'{len(inline_styles)} elements', 'Move styles to CSS files', 'Low', 'Resources')
    
    # Resource hints
    preconnect = soup.find_all('link', rel='preconnect')
    add_check(checks, 'Preconnect Hints', 'pass' if preconnect else 'info',
              'Preconnect links', f'{len(preconnect)} hints', 'Add preconnect for third-party domains', 'Medium', 'Resource Hints')
    
    dns_prefetch = soup.find_all('link', rel='dns-prefetch')
    add_check(checks, 'DNS Prefetch', 'pass' if dns_prefetch or preconnect else 'info',
              'DNS prefetch', f'{len(dns_prefetch)} hints', 'Add dns-prefetch hints', 'Low', 'Resource Hints')
    
    # 16-18: Image Optimization
    lazy_imgs = [i for i in images if i.get('loading') == 'lazy']
    add_check(checks, 'Lazy Loading', 'pass' if lazy_imgs or len(images) <= 3 else 'warning',
              'Lazy loaded images', f'{len(lazy_imgs)}/{len(images)}', 'Add loading="lazy"', 'High', 'Images')
    
    srcset_imgs = [i for i in images if i.get('srcset')]
    add_check(checks, 'Responsive Images', 'pass' if srcset_imgs or len(images) <= 2 else 'info',
              'Srcset images', f'{len(srcset_imgs)}/{len(images)}', 'Use srcset for responsive images', 'Medium', 'Images')
    
    # Check for image optimization (WebP)
    webp = [i for i in images if '.webp' in str(i.get('src', ''))]
    add_check(checks, 'WebP Images', 'pass' if webp or not images else 'info',
              'WebP format', f'{len(webp)}/{len(images)}', 'Use WebP for better compression', 'Medium', 'Images')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== SECURITY SEO (12 checks) ==============
def analyze_security_seo(url, soup, response, load_time):
    checks = []
    parsed = urlparse(url)
    html = str(soup)
    
    # 1-4: HTTPS & SSL
    add_check(checks, 'HTTPS Protocol', 'pass' if parsed.scheme == 'https' else 'fail',
              'Secure connection', parsed.scheme.upper(), 'Enable HTTPS', 'Critical', 'HTTPS')
    
    # Check for HTTP links on HTTPS page
    if parsed.scheme == 'https':
        http_links = soup.find_all(href=re.compile(r'^http://'))
        http_src = soup.find_all(src=re.compile(r'^http://'))
        mixed_content = len(http_links) + len(http_src)
        add_check(checks, 'No Mixed Content', 'pass' if mixed_content == 0 else 'warning',
                  'Mixed content', f'{mixed_content} insecure resources', 'Fix mixed content issues', 'High', 'HTTPS')
    else:
        add_check(checks, 'No Mixed Content', 'fail', 'Mixed content', 'Site not on HTTPS', 'Enable HTTPS first', 'High', 'HTTPS')
    
    # Check for secure cookies
    cookies = response.headers.get('Set-Cookie', '')
    secure_cookie = 'Secure' in cookies if cookies else True
    add_check(checks, 'Secure Cookies', 'pass' if secure_cookie else 'warning',
              'Cookie security', 'Secure flag set' if secure_cookie else 'Missing Secure flag', 'Add Secure flag to cookies', 'Medium', 'HTTPS')
    
    # HTTP to HTTPS redirect check (we can only infer this)
    add_check(checks, 'HTTPS Redirect', 'pass' if parsed.scheme == 'https' else 'warning',
              'HTTP redirects to HTTPS', 'Yes' if parsed.scheme == 'https' else 'Unknown', 'Redirect HTTP to HTTPS', 'High', 'HTTPS')
    
    # 5-8: Security Headers
    hsts = response.headers.get('Strict-Transport-Security', '')
    add_check(checks, 'HSTS Header', 'pass' if hsts else 'warning',
              'HTTP Strict Transport Security', 'Enabled' if hsts else 'Not set', 'Enable HSTS header', 'High', 'Security Headers')
    
    xcto = response.headers.get('X-Content-Type-Options', '')
    add_check(checks, 'X-Content-Type-Options', 'pass' if xcto == 'nosniff' else 'warning',
              'MIME sniffing protection', xcto or 'Not set', 'Add X-Content-Type-Options: nosniff', 'Medium', 'Security Headers')
    
    xfo = response.headers.get('X-Frame-Options', '')
    add_check(checks, 'X-Frame-Options', 'pass' if xfo else 'warning',
              'Clickjacking protection', xfo or 'Not set', 'Add X-Frame-Options header', 'Medium', 'Security Headers')
    
    csp = response.headers.get('Content-Security-Policy', '')
    add_check(checks, 'Content-Security-Policy', 'pass' if csp else 'info',
              'CSP header', 'Configured' if csp else 'Not set', 'Implement Content Security Policy', 'Medium', 'Security Headers')
    
    # 9-12: Additional Security
    referrer = response.headers.get('Referrer-Policy', '')
    add_check(checks, 'Referrer-Policy', 'pass' if referrer else 'info',
              'Referrer policy', referrer or 'Not set', 'Set Referrer-Policy header', 'Low', 'Security Headers')
    
    permissions = response.headers.get('Permissions-Policy', '') or response.headers.get('Feature-Policy', '')
    add_check(checks, 'Permissions-Policy', 'pass' if permissions else 'info',
              'Permissions policy', 'Set' if permissions else 'Not set', 'Configure Permissions-Policy', 'Low', 'Security Headers')
    
    # Check for password fields
    password_fields = soup.find_all('input', {'type': 'password'})
    add_check(checks, 'Secure Login Forms', 'pass' if not password_fields or parsed.scheme == 'https' else 'fail',
              'Password fields on HTTPS', f'{len(password_fields)} fields', 'Use HTTPS for login pages', 'Critical', 'Forms')
    
    # Check for external scripts from untrusted sources
    external_scripts = soup.find_all('script', src=re.compile(r'^https?://'))
    trusted_domains = ['google', 'facebook', 'twitter', 'cloudflare', 'jquery', 'bootstrap', 'cdn']
    untrusted = [s for s in external_scripts if not any(t in str(s.get('src', '')) for t in trusted_domains)]
    add_check(checks, 'Trusted Scripts', 'pass' if len(untrusted) < 3 else 'warning',
              'External scripts', f'{len(untrusted)} from unknown sources', 'Review external script sources', 'Medium', 'Scripts')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== SOCIAL SEO (10 checks) ==============
def analyze_social_seo(url, soup, response, load_time):
    checks = []
    
    # 1-5: Open Graph
    og_title = soup.find('meta', property='og:title')
    add_check(checks, 'OG Title', 'pass' if og_title else 'warning',
              'Open Graph title', og_title.get('content', '')[:50] if og_title else 'Not set',
              'Add og:title meta tag', 'High', 'Open Graph')
    
    og_desc = soup.find('meta', property='og:description')
    add_check(checks, 'OG Description', 'pass' if og_desc else 'warning',
              'Open Graph description', 'Set' if og_desc else 'Not set',
              'Add og:description meta tag', 'High', 'Open Graph')
    
    og_image = soup.find('meta', property='og:image')
    add_check(checks, 'OG Image', 'pass' if og_image else 'warning',
              'Open Graph image', 'Set' if og_image else 'Not set',
              'Add og:image (1200x630px recommended)', 'High', 'Open Graph')
    
    og_url = soup.find('meta', property='og:url')
    add_check(checks, 'OG URL', 'pass' if og_url else 'info',
              'Open Graph URL', 'Set' if og_url else 'Not set',
              'Add og:url meta tag', 'Medium', 'Open Graph')
    
    og_type = soup.find('meta', property='og:type')
    add_check(checks, 'OG Type', 'pass' if og_type else 'info',
              'Open Graph type', og_type.get('content', '') if og_type else 'Not set',
              'Add og:type meta tag', 'Low', 'Open Graph')
    
    # 6-8: Twitter Cards
    twitter_card = soup.find('meta', attrs={'name': 'twitter:card'})
    add_check(checks, 'Twitter Card', 'pass' if twitter_card else 'warning',
              'Twitter card type', twitter_card.get('content', '') if twitter_card else 'Not set',
              'Add twitter:card meta tag', 'Medium', 'Twitter')
    
    twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
    add_check(checks, 'Twitter Title', 'pass' if twitter_title or og_title else 'warning',
              'Twitter title', 'Set' if twitter_title else ('Falls back to OG' if og_title else 'Not set'),
              'Add twitter:title or og:title', 'Medium', 'Twitter')
    
    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
    add_check(checks, 'Twitter Image', 'pass' if twitter_image or og_image else 'warning',
              'Twitter image', 'Set' if twitter_image else ('Falls back to OG' if og_image else 'Not set'),
              'Add twitter:image or og:image', 'Medium', 'Twitter')
    
    # 9-10: Social Integration
    social_links = soup.find_all('a', href=re.compile(r'facebook|twitter|linkedin|instagram|youtube|tiktok', re.I))
    add_check(checks, 'Social Profile Links', 'pass' if social_links else 'info',
              'Social media links', f'{len(social_links)} found',
              'Link to social profiles', 'Low', 'Social Integration')
    
    share_buttons = soup.find_all(class_=re.compile(r'share|social', re.I))
    add_check(checks, 'Share Buttons', 'pass' if share_buttons else 'info',
              'Share functionality', f'{len(share_buttons)} found',
              'Add social share buttons', 'Low', 'Social Integration')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== LOCAL SEO (15 checks) ==============
def analyze_local_seo(url, soup, response, load_time):
    checks = []
    text = soup.get_text()
    html = str(soup)
    
    # 1-5: NAP (Name, Address, Phone)
    # Phone number detection
    phone_pattern = re.search(r'\b(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b', text)
    add_check(checks, 'Phone Number', 'pass' if phone_pattern else 'info',
              'Phone displayed', 'Found' if phone_pattern else 'Not found',
              'Display phone number for local SEO', 'High', 'NAP')
    
    # Address detection
    address_pattern = re.search(r'\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln)\b', text, re.I)
    add_check(checks, 'Physical Address', 'pass' if address_pattern else 'info',
              'Address displayed', 'Found' if address_pattern else 'Not found',
              'Display physical address', 'High', 'NAP')
    
    # Email detection
    email_pattern = re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', text)
    add_check(checks, 'Email Address', 'pass' if email_pattern else 'info',
              'Email displayed', 'Found' if email_pattern else 'Not found',
              'Display contact email', 'Medium', 'NAP')
    
    # Click-to-call links
    tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
    add_check(checks, 'Click-to-Call', 'pass' if tel_links else 'info',
              'Tel: links', f'{len(tel_links)} found',
              'Add tel: links for mobile users', 'Medium', 'NAP')
    
    # Mailto links
    mailto_links = soup.find_all('a', href=re.compile(r'^mailto:'))
    add_check(checks, 'Click-to-Email', 'pass' if mailto_links else 'info',
              'Mailto: links', f'{len(mailto_links)} found',
              'Add mailto: links', 'Low', 'NAP')
    
    # 6-10: Local Schema
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    local_schema_types = ['LocalBusiness', 'Organization', 'Store', 'Restaurant', 'Hotel', 'Place']
    has_local_schema = any(any(t in str(j) for t in local_schema_types) for j in json_ld)
    add_check(checks, 'LocalBusiness Schema', 'pass' if has_local_schema else 'warning',
              'Local business markup', 'Found' if has_local_schema else 'Not found',
              'Add LocalBusiness schema', 'High', 'Schema')
    
    # Organization schema
    has_org_schema = any('Organization' in str(j) for j in json_ld)
    add_check(checks, 'Organization Schema', 'pass' if has_org_schema else 'info',
              'Organization markup', 'Found' if has_org_schema else 'Not found',
              'Add Organization schema', 'Medium', 'Schema')
    
    # Contact page schema
    has_contact = 'ContactPoint' in html or 'contactPoint' in html
    add_check(checks, 'ContactPoint Schema', 'pass' if has_contact else 'info',
              'Contact point markup', 'Found' if has_contact else 'Not found',
              'Add ContactPoint schema', 'Medium', 'Schema')
    
    # Opening hours
    has_hours = 'openingHours' in html or 'OpeningHoursSpecification' in html
    add_check(checks, 'Opening Hours Schema', 'pass' if has_hours else 'info',
              'Hours markup', 'Found' if has_hours else 'Not found',
              'Add opening hours schema', 'Medium', 'Schema')
    
    # GeoCoordinates
    has_geo = 'GeoCoordinates' in html or 'geo' in html.lower()
    add_check(checks, 'GeoCoordinates', 'pass' if has_geo else 'info',
              'Location coordinates', 'Found' if has_geo else 'Not found',
              'Add geo coordinates schema', 'Medium', 'Schema')
    
    # 11-15: Local Signals
    # Google Maps embed
    maps_embed = soup.find('iframe', src=re.compile(r'google.*maps|maps\.google', re.I))
    add_check(checks, 'Google Maps Embed', 'pass' if maps_embed else 'info',
              'Map embedded', 'Found' if maps_embed else 'Not found',
              'Embed Google Maps', 'Medium', 'Local Signals')
    
    # Directions link
    directions = soup.find('a', href=re.compile(r'maps\.google|google.*maps.*dir', re.I))
    add_check(checks, 'Directions Link', 'pass' if directions else 'info',
              'Get directions link', 'Found' if directions else 'Not found',
              'Add directions link', 'Low', 'Local Signals')
    
    # Service area mentions
    service_area = any(term in text.lower() for term in ['serving', 'service area', 'we serve', 'locations'])
    add_check(checks, 'Service Area', 'pass' if service_area else 'info',
              'Service area mentioned', 'Found' if service_area else 'Not found',
              'Mention service areas', 'Medium', 'Local Signals')
    
    # Local keywords
    local_terms = ['near me', 'local', 'nearby', 'in your area']
    has_local_terms = any(term in text.lower() for term in local_terms)
    add_check(checks, 'Local Keywords', 'pass' if has_local_terms else 'info',
              'Local terms used', 'Found' if has_local_terms else 'Not found',
              'Include local keywords', 'Low', 'Local Signals')
    
    # Reviews/testimonials
    reviews = any(term in html.lower() for term in ['review', 'testimonial', 'rating', 'stars'])
    add_check(checks, 'Reviews Section', 'pass' if reviews else 'info',
              'Reviews/testimonials', 'Found' if reviews else 'Not found',
              'Display customer reviews', 'High', 'Local Signals')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== GEO/AEO (30 checks) - AI Search Optimization ==============
def analyze_geo_aeo(url, soup, response, load_time):
    """
    Comprehensive AI/LLM optimization checks based on:
    - Google's AI experiences guidelines
    - Answer Engine Optimization (AEO) best practices
    - LLM interpretability research
    - Passage ranking readiness
    """
    checks = []
    html = str(soup)
    text = soup.get_text()
    words = text.split()
    word_count = len(words)
    parsed = urlparse(url)
    
    # ===== 1-6: Structured Data for AI Parsing =====
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    add_check(checks, 'JSON-LD Structured Data', 'pass' if json_ld else 'fail',
              'Schema.org markup for AI', f'{len(json_ld)} blocks',
              'Add JSON-LD schema for AI understanding', 'Critical', 'AI Parsing')
    
    faq_schema = 'FAQPage' in html or '"Question"' in html
    add_check(checks, 'FAQ Schema', 'pass' if faq_schema else 'warning',
              'FAQPage structured data', 'Present' if faq_schema else 'Not found',
              'Add FAQPage schema for AI snippets', 'Critical', 'AI Parsing')
    
    howto_schema = 'HowTo' in html
    add_check(checks, 'HowTo Schema', 'pass' if howto_schema else 'info',
              'Step-by-step schema', 'Present' if howto_schema else 'Not found',
              'Add HowTo schema for instructions', 'High', 'AI Parsing')
    
    # Entity schemas for AI recognition
    entity_schemas = ['Person', 'Organization', 'Product', 'Place', 'Event', 'Article', 'WebPage']
    entities_found = [s for s in entity_schemas if s in html]
    add_check(checks, 'Entity Schema Markup', 'pass' if entities_found else 'warning',
              'Schema.org entities', ', '.join(entities_found) if entities_found else 'None found',
              'Add entity schemas (Person, Organization, Article)', 'High', 'AI Parsing')
    
    # Speakable schema for voice assistants
    speakable = 'speakable' in html.lower()
    add_check(checks, 'Speakable Schema', 'pass' if speakable else 'info',
              'Voice assistant optimization', 'Present' if speakable else 'Not found',
              'Add Speakable schema for voice search', 'Medium', 'AI Parsing')
    
    # sameAs links for entity disambiguation
    sameas = 'sameAs' in html
    add_check(checks, 'Entity sameAs Links', 'pass' if sameas else 'info',
              'Entity disambiguation', 'Present' if sameas else 'Not found',
              'Add sameAs links to Wikipedia/social profiles', 'Medium', 'AI Parsing')
    
    # ===== 7-12: Semantic HTML & Structure =====
    semantic_tags = soup.find_all(['article', 'section', 'aside', 'nav', 'header', 'footer', 'main'])
    add_check(checks, 'Semantic HTML5', 'pass' if len(semantic_tags) >= 3 else 'warning',
              'Semantic structure', f'{len(semantic_tags)} elements',
              'Use semantic HTML for AI comprehension', 'High', 'Semantic Structure')
    
    # Tables for structured data extraction
    tables = soup.find_all('table')
    add_check(checks, 'Data Tables', 'pass' if tables else 'info',
              'Tabular data', f'{len(tables)} tables',
              'Use tables for structured comparisons', 'Medium', 'Semantic Structure')
    
    # Lists for AI extraction
    lists = soup.find_all(['ul', 'ol'])
    add_check(checks, 'Structured Lists', 'pass' if len(lists) >= 2 else 'warning',
              'Lists for AI extraction', f'{len(lists)} lists',
              'Use bullet/numbered lists for key points', 'High', 'Semantic Structure')
    
    # Figure/figcaption for image context
    figures = soup.find_all('figure')
    figcaptions = soup.find_all('figcaption')
    add_check(checks, 'Figure Captions', 'pass' if figcaptions else 'info',
              'Image context for AI', f'{len(figcaptions)} captions',
              'Use figcaption for image descriptions', 'Medium', 'Semantic Structure')
    
    # Definition lists for glossaries
    dl_tags = soup.find_all('dl')
    add_check(checks, 'Definition Lists', 'pass' if dl_tags else 'info',
              'Term definitions', f'{len(dl_tags)} definition lists',
              'Use <dl> for glossary/definitions', 'Low', 'Semantic Structure')
    
    # Blockquotes for citations
    blockquotes = soup.find_all('blockquote')
    add_check(checks, 'Blockquote Citations', 'pass' if blockquotes else 'info',
              'Quoted content', f'{len(blockquotes)} blockquotes',
              'Use blockquote for expert citations', 'Low', 'Semantic Structure')
    
    # ===== 13-18: LLM Interpretability & Content =====
    # Question-answer patterns (critical for AEO)
    questions = re.findall(r'(what|how|why|when|where|who|which|can|does|is|are)\s+[^.?]*\?', text.lower())
    add_check(checks, 'Q&A Patterns', 'pass' if len(questions) >= 2 else 'warning',
              'Question-answer format', f'{len(questions)} questions',
              'Include Q&A format for AI snippets', 'Critical', 'LLM Interpretability')
    
    # Direct definitions (X is defined as...)
    definitions = re.findall(r'\b\w+\s+(?:is|are|means|refers to|defined as|is defined as)\s+[^.]+\.', text)
    add_check(checks, 'Direct Definitions', 'pass' if definitions else 'warning',
              'Clear definitions', f'{len(definitions)} found',
              'Provide direct "X is..." definitions', 'Critical', 'LLM Interpretability')
    
    # Answer-first writing (inverted pyramid)
    paragraphs = soup.find_all('p')
    first_para = paragraphs[0].get_text() if paragraphs else ''
    has_answer_first = any(w in first_para.lower() for w in ['is', 'are', 'means', 'provides', 'helps', 'allows'])
    add_check(checks, 'Answer-First Writing', 'pass' if has_answer_first else 'warning',
              'Inverted pyramid style', 'Key info upfront' if has_answer_first else 'Buried lede',
              'Lead with the answer, not background', 'High', 'LLM Interpretability')
    
    # Self-contained sentences (can be extracted alone)
    sentences = re.split(r'[.!?]+', text)
    pronoun_heavy = sum(1 for s in sentences if s.lower().strip().startswith(('it ', 'this ', 'that ', 'they ')))
    pronoun_ratio = pronoun_heavy / len(sentences) if sentences else 0
    add_check(checks, 'Self-Contained Sentences', 'pass' if pronoun_ratio < 0.2 else 'warning',
              'Extractable sentences', f'{pronoun_ratio*100:.0f}% start with pronouns',
              'Avoid starting sentences with it/this/that', 'High', 'LLM Interpretability')
    
    # Plain language (avoid jargon)
    complex_words = [w for w in words if len(w) > 12]
    complex_ratio = len(complex_words) / word_count if word_count else 0
    add_check(checks, 'Plain Language', 'pass' if complex_ratio < 0.05 else 'warning',
              'Accessible language', f'{complex_ratio*100:.1f}% complex words',
              'Use simple, clear language for AI', 'High', 'LLM Interpretability')
    
    # Conversational tone
    conv_words = ['you', 'your', "you're", 'we', 'our', "we're"]
    conv_count = sum(text.lower().count(' ' + w + ' ') for w in conv_words)
    conv_ratio = conv_count / word_count if word_count else 0
    add_check(checks, 'Conversational Tone', 'pass' if conv_ratio > 0.005 else 'info',
              'Natural language style', f'{conv_ratio*100:.2f}%',
              'Use conversational you/we language', 'Medium', 'LLM Interpretability')
    
    # ===== 19-24: Passage Ranking & Snippet Readiness =====
    # Heading as questions (prompt-aligned)
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    question_headings = [h for h in headings if '?' in h.get_text()]
    add_check(checks, 'Question Headings', 'pass' if question_headings else 'warning',
              'Prompt-aligned headings', f'{len(question_headings)} question headings',
              'Use questions as headings (What is X?)', 'Critical', 'Snippet Readiness')
    
    # Descriptive headings (not generic)
    generic_headings = ['introduction', 'conclusion', 'overview', 'summary', 'more']
    descriptive_h = [h for h in headings if len(h.get_text().split()) >= 3 and h.get_text().lower().strip() not in generic_headings]
    add_check(checks, 'Descriptive Headings', 'pass' if len(descriptive_h) >= len(headings) * 0.5 else 'warning',
              'Context-rich headings', f'{len(descriptive_h)}/{len(headings)} descriptive',
              'Use specific, descriptive headings', 'High', 'Snippet Readiness')
    
    # Short paragraphs (under 100 words for AI parsing)
    long_paras = [p for p in paragraphs if len(p.get_text().split()) > 100]
    add_check(checks, 'Concise Paragraphs', 'pass' if len(long_paras) <= 2 else 'warning',
              'Paragraph length', f'{len(long_paras)} paragraphs over 100 words',
              'Keep paragraphs under 100 words', 'High', 'Snippet Readiness')
    
    # Section granularity (enough H2/H3 for passage ranking)
    h2_count = len(soup.find_all('h2'))
    h3_count = len(soup.find_all('h3'))
    section_ratio = (h2_count + h3_count) / (word_count / 300) if word_count > 300 else 1
    add_check(checks, 'Section Granularity', 'pass' if section_ratio >= 0.8 else 'warning',
              'Heading density', f'{h2_count} H2s, {h3_count} H3s',
              'Add more subheadings for passage ranking', 'High', 'Snippet Readiness')
    
    # Step-by-step content
    steps = re.findall(r'step\s*\d|first,|second,|third,|finally,|next,|then,', text.lower())
    numbered_lists = soup.find_all('ol')
    add_check(checks, 'Step-by-Step Format', 'pass' if steps or numbered_lists else 'info',
              'Sequential instructions', f'{len(steps)} step indicators, {len(numbered_lists)} ordered lists',
              'Structure how-to content with numbered steps', 'Medium', 'Snippet Readiness')
    
    # Examples and specifics
    examples = ['for example', 'such as', 'e.g.', 'for instance', 'like this', 'including', 'specifically']
    example_count = sum(text.lower().count(e) for e in examples)
    add_check(checks, 'Concrete Examples', 'pass' if example_count >= 2 else 'info',
              'Specific examples', f'{example_count} example phrases',
              'Include specific examples for clarity', 'Medium', 'Snippet Readiness')
    
    # ===== 25-30: Trust, Freshness & AI Optimization =====
    # Content timestamps
    time_elements = soup.find_all('time')
    date_meta = soup.find('meta', property='article:modified_time') or soup.find('meta', property='article:published_time')
    add_check(checks, 'Content Timestamps', 'pass' if time_elements or date_meta else 'warning',
              'Freshness signals', f'{len(time_elements)} time elements',
              'Add visible publish/update dates', 'High', 'Trust & Freshness')
    
    # Last-Modified header
    last_modified = response.headers.get('Last-Modified', '')
    add_check(checks, 'Last-Modified Header', 'pass' if last_modified else 'info',
              'HTTP freshness', 'Set' if last_modified else 'Not set',
              'Set Last-Modified header for freshness', 'Medium', 'Trust & Freshness')
    
    # Author attribution (E-E-A-T)
    author_patterns = soup.find_all(class_=re.compile(r'author|bio|byline|written-by', re.I))
    author_schema = 'author' in html.lower() and ('Person' in html or 'name' in html)
    add_check(checks, 'Author Attribution', 'pass' if author_patterns or author_schema else 'warning',
              'E-E-A-T author signals', 'Found' if author_patterns else 'Not found',
              'Add visible author name and bio', 'Critical', 'Trust & Freshness')
    
    # Source citations
    citations = ['according to', 'source:', 'cited', 'reference', 'study shows', 'research', 'data from']
    has_citations = any(c in text.lower() for c in citations)
    external_links = [a for a in soup.find_all('a', href=True) if a['href'].startswith('http') and parsed.netloc not in a['href']]
    add_check(checks, 'Source Citations', 'pass' if has_citations or len(external_links) >= 2 else 'warning',
              'Factual citations', f'{len(external_links)} external links',
              'Cite authoritative sources with links', 'High', 'Trust & Freshness')
    
    # llms.txt file (emerging standard)
    llms_txt = safe_get(f"{parsed.scheme}://{parsed.netloc}/llms.txt")
    add_check(checks, 'LLMs.txt File', 'pass' if llms_txt and llms_txt.status_code == 200 else 'info',
              'AI crawler guidance', 'Found' if llms_txt and llms_txt.status_code == 200 else 'Not found',
              'Add llms.txt for AI crawler permissions', 'Low', 'AI Optimization')
    
    # AI-friendly content length
    add_check(checks, 'AI-Friendly Length', 'pass' if 500 <= word_count <= 3000 else ('warning' if word_count < 300 else 'info'),
              'Content length', f'{word_count} words',
              'Aim for 500-3000 words for AI context windows', 'Medium', 'AI Optimization')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== CITATION GAP ANALYSIS (20 checks) - Google vs AI Visibility ==============
def extract_primary_keyword(soup):
    """Extract the primary keyword/topic from page signals"""
    signals = []
    
    # Title tag (strongest signal)
    title = soup.find('title')
    if title and title.string:
        signals.append(title.string.strip())
    
    # H1 tag
    h1 = soup.find('h1')
    if h1:
        signals.append(h1.get_text().strip())
    
    # Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        signals.append(meta_desc['content'].strip())
    
    # Meta keywords (if present)
    meta_kw = soup.find('meta', attrs={'name': 'keywords'})
    if meta_kw and meta_kw.get('content'):
        signals.append(meta_kw['content'].strip())
    
    # OG title
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        signals.append(og_title['content'].strip())
    
    # Combine and extract most common meaningful words
    all_text = ' '.join(signals).lower()
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                  'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
                  'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
                  'before', 'after', 'above', 'below', 'between', 'and', 'but', 'or',
                  'not', 'no', 'nor', 'so', 'yet', 'both', 'either', 'neither', 'each',
                  'every', 'all', 'any', 'few', 'more', 'most', 'other', 'some', 'such',
                  'than', 'too', 'very', 'just', 'about', 'up', 'out', 'if', 'then',
                  'that', 'this', 'these', 'those', 'it', 'its', 'how', 'what', 'which',
                  'who', 'whom', 'when', 'where', 'why', 'your', 'our', 'my', 'we', 'you',
                  'i', 'me', 'he', 'she', 'they', 'them', 'his', 'her', 'their', 'us', '|', '-', '–'}
    words = re.findall(r'\b[a-z]{3,}\b', all_text)
    meaningful = [w for w in words if w not in stop_words]
    
    # Count frequency
    freq = Counter(meaningful)
    top_words = [w for w, _ in freq.most_common(5)]
    
    return ' '.join(top_words) if top_words else 'unknown topic'


def analyze_citation_gap(url, soup, response, load_time):
    """
    Citation Gap Analysis - Compares Google ranking signals vs AI citation readiness.
    Identifies content that may rank well on Google but isn't structured for AI citation,
    and vice versa. Helps bridge the gap between traditional SEO and AI visibility.
    """
    checks = []
    html = str(soup)
    text = soup.get_text()
    words = text.split()
    word_count = len(words)
    parsed = urlparse(url)
    
    # Extract primary keyword for context
    keyword = extract_primary_keyword(soup)
    
    # ===== 1-5: Google Ranking Signal Strength =====
    # Title tag keyword alignment
    title = soup.find('title')
    title_text = (title.string.strip() if title and title.string else '').lower()
    keyword_words = keyword.split()
    title_kw_match = sum(1 for kw in keyword_words if kw in title_text)
    title_kw_ratio = title_kw_match / len(keyword_words) if keyword_words else 0
    add_check(checks, 'Title Keyword Alignment', 'pass' if title_kw_ratio >= 0.6 else 'warning',
              'Primary keyword in title', f'{title_kw_match}/{len(keyword_words)} keyword terms in title',
              'Include primary keyword in title for Google ranking', 'High', 'Google Signals')
    
    # Meta description keyword presence
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_text = (meta_desc.get('content', '') if meta_desc else '').lower()
    desc_kw_match = sum(1 for kw in keyword_words if kw in desc_text)
    add_check(checks, 'Meta Description Keywords', 'pass' if desc_kw_match >= 1 else 'warning',
              'Keywords in meta description', f'{desc_kw_match} keyword terms found',
              'Include target keywords in meta description', 'High', 'Google Signals')
    
    # H1 keyword alignment
    h1 = soup.find('h1')
    h1_text = (h1.get_text().strip() if h1 else '').lower()
    h1_kw_match = sum(1 for kw in keyword_words if kw in h1_text)
    add_check(checks, 'H1 Keyword Match', 'pass' if h1_kw_match >= 1 else 'warning',
              'Primary keyword in H1', f'{h1_kw_match} keyword terms in H1',
              'Align H1 heading with target keyword', 'High', 'Google Signals')
    
    # Keyword density in body content
    text_lower = text.lower()
    kw_occurrences = sum(text_lower.count(kw) for kw in keyword_words)
    kw_density = (kw_occurrences / word_count * 100) if word_count else 0
    add_check(checks, 'Keyword Density', 'pass' if 1.0 <= kw_density <= 4.0 else ('warning' if kw_density < 1.0 else 'info'),
              'Keyword frequency in content', f'{kw_density:.1f}% density',
              'Aim for 1-3% keyword density for Google', 'Medium', 'Google Signals')
    
    # Backlink-worthy content signals (long-form, data, unique value)
    has_data = len(re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?%?\b', text)) >= 5
    has_depth = word_count >= 1000
    has_lists = len(soup.find_all(['ul', 'ol'])) >= 2
    link_worthy_score = sum([has_data, has_depth, has_lists])
    add_check(checks, 'Link-Worthy Content', 'pass' if link_worthy_score >= 2 else 'warning',
              'Content likely to earn backlinks', f'{link_worthy_score}/3 signals (data, depth, structure)',
              'Create comprehensive content with data and structure', 'High', 'Google Signals')
    
    # ===== 6-10: AI Citation Readiness =====
    # Direct answer format (AI engines prefer concise, extractable answers)
    paragraphs = soup.find_all('p')
    short_answer_paras = [p for p in paragraphs if 20 <= len(p.get_text().split()) <= 50]
    add_check(checks, 'AI-Extractable Answers', 'pass' if len(short_answer_paras) >= 3 else 'warning',
              'Concise answer paragraphs (20-50 words)', f'{len(short_answer_paras)} extractable paragraphs',
              'Write concise paragraphs that AI can directly quote', 'Critical', 'AI Citation Readiness')
    
    # Factual claim density (AI cites factual, verifiable statements)
    factual_patterns = re.findall(
        r'(?:according to|studies show|research indicates|data shows|statistics reveal|'
        r'experts say|evidence suggests|reports indicate|surveys show|analysis reveals|'
        r'findings show|results demonstrate|published in|conducted by)\b',
        text.lower()
    )
    add_check(checks, 'Factual Claim Density', 'pass' if len(factual_patterns) >= 2 else 'warning',
              'Verifiable factual statements', f'{len(factual_patterns)} factual attribution phrases',
              'Include cited facts and data that AI can reference', 'Critical', 'AI Citation Readiness')
    
    # Definition-style content (AI loves "X is Y" patterns)
    definitions = re.findall(r'\b\w+\s+(?:is|are|refers to|means|is defined as|is known as)\s+[^.]{10,}\.', text)
    add_check(checks, 'Definition Patterns', 'pass' if len(definitions) >= 2 else 'warning',
              'Clear "X is Y" definitions', f'{len(definitions)} definition patterns',
              'Include clear definitions that AI can extract and cite', 'High', 'AI Citation Readiness')
    
    # Unique insight score (AI cites original analysis, not rehashed content)
    opinion_markers = ['we found', 'our analysis', 'we recommend', 'in our experience',
                       'we believe', 'our research', 'we discovered', 'our data shows',
                       'based on our', 'we tested', 'our team', 'we observed']
    unique_insights = sum(1 for m in opinion_markers if m in text.lower())
    add_check(checks, 'Original Insights', 'pass' if unique_insights >= 2 else 'warning',
              'First-party analysis and opinions', f'{unique_insights} original insight markers',
              'Add original research, data, or expert opinions AI will cite', 'Critical', 'AI Citation Readiness')
    
    # Structured Q&A format (directly answerable by AI)
    qa_headings = [h for h in soup.find_all(['h2', 'h3', 'h4']) if '?' in h.get_text()]
    faq_schema = 'FAQPage' in html or '"Question"' in html
    add_check(checks, 'Q&A Structure', 'pass' if len(qa_headings) >= 2 or faq_schema else 'warning',
              'Question-answer format for AI', f'{len(qa_headings)} question headings, FAQ schema: {"Yes" if faq_schema else "No"}',
              'Structure content as questions and answers for AI citation', 'High', 'AI Citation Readiness')
    
    # ===== 11-15: Citation Gap Indicators =====
    # Google-strong but AI-weak: good keywords but poor extractability
    google_score = sum([
        title_kw_ratio >= 0.6,
        desc_kw_match >= 1,
        h1_kw_match >= 1,
        1.0 <= kw_density <= 4.0,
        link_worthy_score >= 2
    ])
    ai_score = sum([
        len(short_answer_paras) >= 3,
        len(factual_patterns) >= 2,
        len(definitions) >= 2,
        unique_insights >= 2,
        len(qa_headings) >= 2 or faq_schema
    ])
    
    gap = abs(google_score - ai_score)
    gap_direction = 'Google-heavy' if google_score > ai_score else ('AI-heavy' if ai_score > google_score else 'Balanced')
    add_check(checks, 'Citation Gap Score', 'pass' if gap <= 1 else ('warning' if gap <= 2 else 'fail'),
              'Balance between Google SEO and AI citation', f'Google: {google_score}/5, AI: {ai_score}/5 ({gap_direction})',
              'Balance traditional SEO with AI-friendly content structure', 'Critical', 'Gap Analysis')
    
    # Content freshness signals (AI prefers recent, updated content)
    date_meta = soup.find('meta', property='article:modified_time') or soup.find('meta', property='article:published_time')
    time_elements = soup.find_all('time')
    freshness_words = ['updated', 'latest', '2025', '2026', 'recently', 'new', 'current']
    has_freshness = any(w in text.lower() for w in freshness_words)
    add_check(checks, 'Content Freshness', 'pass' if (date_meta or time_elements) and has_freshness else 'warning',
              'Recency signals for AI preference', f'Date meta: {"Yes" if date_meta else "No"}, Freshness words: {"Yes" if has_freshness else "No"}',
              'Add publish/update dates and current year references', 'High', 'Gap Analysis')
    
    # Source authority signals (AI cites authoritative domains)
    external_links = [a for a in soup.find_all('a', href=True) if a['href'].startswith('http') and parsed.netloc not in a['href']]
    authority_domains = ['wikipedia', 'gov', 'edu', 'nature.com', 'sciencedirect', 'pubmed',
                         'reuters', 'bbc', 'nytimes', 'forbes', 'harvard', 'stanford', 'mit']
    authority_links = [l for l in external_links if any(d in l['href'].lower() for d in authority_domains)]
    add_check(checks, 'Authority Source Links', 'pass' if len(authority_links) >= 1 else 'warning',
              'Links to authoritative sources', f'{len(authority_links)} authority links out of {len(external_links)} external',
              'Link to .gov, .edu, Wikipedia, and research sources for AI trust', 'High', 'Gap Analysis')
    
    # Semantic topic coverage (AI needs comprehensive topic coverage)
    headings = soup.find_all(['h2', 'h3'])
    heading_texts = [h.get_text().lower() for h in headings]
    topic_breadth = len(set(' '.join(heading_texts).split())) if heading_texts else 0
    add_check(checks, 'Topic Coverage Breadth', 'pass' if topic_breadth >= 15 else 'warning',
              'Semantic topic comprehensiveness', f'{topic_breadth} unique terms across {len(headings)} subheadings',
              'Cover subtopics comprehensively so AI sees your page as authoritative', 'High', 'Gap Analysis')
    
    # Competing content format (does page match what AI typically cites?)
    has_summary = any(w in text.lower() for w in ['in summary', 'to summarize', 'key takeaways', 'bottom line', 'conclusion', 'tldr', 'tl;dr'])
    has_intro = any(w in text.lower()[:500] for w in ['this guide', 'this article', 'in this post', 'we will explore', 'you will learn'])
    has_structure = len(headings) >= 3 and len(paragraphs) >= 5
    format_score = sum([has_summary, has_intro, has_structure])
    add_check(checks, 'AI-Preferred Format', 'pass' if format_score >= 2 else 'warning',
              'Content format AI engines prefer to cite', f'{format_score}/3 (intro: {"✓" if has_intro else "✗"}, structure: {"✓" if has_structure else "✗"}, summary: {"✓" if has_summary else "✗"})',
              'Include clear intro, structured body, and summary/takeaways', 'High', 'Gap Analysis')
    
    # ===== 16-20: Bridge Recommendations =====
    # Entity markup for AI knowledge graphs
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    entity_types = ['Person', 'Organization', 'Product', 'Article', 'WebPage', 'HowTo', 'FAQPage']
    entities_found = [e for e in entity_types if any(e in str(j) for j in json_ld)]
    add_check(checks, 'Entity Schema Coverage', 'pass' if len(entities_found) >= 2 else 'warning',
              'Schema types for AI knowledge extraction', f'{len(entities_found)} entity types: {", ".join(entities_found) or "None"}',
              'Add Article, FAQPage, HowTo schemas to help AI understand your content', 'High', 'Bridge Strategy')
    
    # Snippet-optimized paragraphs (40-60 words, starts with topic)
    snippet_ready = [p for p in paragraphs if 30 <= len(p.get_text().split()) <= 60
                     and any(kw in p.get_text().lower() for kw in keyword_words)]
    add_check(checks, 'Snippet-Ready Paragraphs', 'pass' if len(snippet_ready) >= 2 else 'warning',
              'Paragraphs optimized for both featured snippets and AI quotes', f'{len(snippet_ready)} snippet-ready paragraphs',
              'Write 40-60 word paragraphs containing your keyword that can serve as both Google snippets and AI citations', 'Critical', 'Bridge Strategy')
    
    # Comparative/superlative claims (AI cites "best", "most", "top" content)
    comparison_words = ['best', 'top', 'most', 'leading', 'fastest', 'cheapest', 'easiest',
                        'compared to', 'versus', 'vs', 'better than', 'unlike', 'difference between']
    comparisons = sum(1 for w in comparison_words if w in text.lower())
    add_check(checks, 'Comparative Content', 'pass' if comparisons >= 3 else 'info',
              'Comparison and ranking language', f'{comparisons} comparative terms',
              'Include comparisons and rankings that both Google and AI favor', 'Medium', 'Bridge Strategy')
    
    # Internal topic clustering (helps both Google and AI understand site authority)
    internal_links = [a for a in soup.find_all('a', href=True) if parsed.netloc in urljoin(url, a['href'])]
    descriptive_anchors = [a for a in internal_links if len(a.get_text().strip().split()) >= 2
                           and a.get_text().strip().lower() not in ['click here', 'read more', 'learn more', 'here']]
    add_check(checks, 'Topic Cluster Links', 'pass' if len(descriptive_anchors) >= 3 else 'warning',
              'Internal links with descriptive anchors', f'{len(descriptive_anchors)} descriptive internal links',
              'Build topic clusters with descriptive internal links for both Google authority and AI context', 'High', 'Bridge Strategy')
    
    # Overall bridge score
    total_google = google_score
    total_ai = ai_score
    bridge_score = min(total_google, total_ai) / max(max(total_google, total_ai), 1) * 100
    bridge_status = 'pass' if bridge_score >= 70 else ('warning' if bridge_score >= 40 else 'fail')
    add_check(checks, 'Overall Bridge Score', bridge_status,
              'How well content bridges Google SEO and AI citation', f'Bridge: {bridge_score:.0f}% (Google {total_google}/5, AI {total_ai}/5)',
              'Optimize for both Google ranking factors AND AI citation patterns simultaneously', 'Critical', 'Bridge Strategy')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed,
            'keyword': keyword, 'googleScore': google_score, 'aiScore': ai_score, 'gapDirection': gap_direction}


# ============== API ROUTES ==============
@app.route('/')
def serve_index():
    """Redirect to the production frontend — this backend is API-only infrastructure.
    The real homepage lives on S3/CloudFront at www.ai1stseo.com."""
    return redirect('https://www.ai1stseo.com')

@app.route('/analyze')
def serve_analyze():
    return send_from_directory('.', 'analyze.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

@app.route('/api/signup', methods=['POST'])
def signup():
    """User registration via Cognito (direct HTTP - no AWS credentials needed)"""
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return jsonify({'status': 'error', 'message': 'All fields are required'}), 400

    if '@' not in email or '.' not in email:
        return jsonify({'status': 'error', 'message': 'Invalid email address'}), 400

    try:
        result, status_code = cognito_request('SignUp', {
            'ClientId': COGNITO_CLIENT_ID,
            'SecretHash': get_secret_hash(email),
            'Username': email,
            'Password': password,
            'UserAttributes': [
                {'Name': 'email', 'Value': email},
                {'Name': 'name', 'Value': name}
            ]
        })

        if status_code != 200:
            error_type = result.get('__type', '')
            error_msg = result.get('message', 'Signup failed')
            if 'UsernameExistsException' in error_type:
                return jsonify({'status': 'error', 'message': 'Email already registered'}), 400
            if 'InvalidPasswordException' in error_type:
                return jsonify({'status': 'error', 'message': 'Password must be at least 8 characters with uppercase, lowercase, and numbers'}), 400
            if 'InvalidParameterException' in error_type:
                return jsonify({'status': 'error', 'message': error_msg}), 400
            return jsonify({'status': 'error', 'message': error_msg}), 400

        # Send welcome email via SES (best-effort)
        send_welcome_email(email, name)

        return jsonify({
            'status': 'success',
            'message': 'Account created! Check your email for a verification code.'
        })
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/confirm', methods=['POST'])
def confirm_signup():
    """Confirm user signup with verification code (direct HTTP)"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()

    if not email or not code:
        return jsonify({'status': 'error', 'message': 'Email and code required'}), 400

    try:
        result, status_code = cognito_request('ConfirmSignUp', {
            'ClientId': COGNITO_CLIENT_ID,
            'SecretHash': get_secret_hash(email),
            'Username': email,
            'ConfirmationCode': code
        })

        if status_code != 200:
            error_type = result.get('__type', '')
            error_msg = result.get('message', 'Confirmation failed')
            if 'CodeMismatchException' in error_type:
                return jsonify({'status': 'error', 'message': 'Invalid verification code'}), 400
            if 'ExpiredCodeException' in error_type:
                return jsonify({'status': 'error', 'message': 'Code expired. Please request a new one.'}), 400
            return jsonify({'status': 'error', 'message': error_msg}), 400

        return jsonify({'status': 'success', 'message': 'Email verified! You can now sign in.'})
    except Exception as e:
        print(f"Confirm error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/resend-code', methods=['POST'])
def resend_code():
    """Resend verification code (direct HTTP)"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    try:
        result, status_code = cognito_request('ResendConfirmationCode', {
            'ClientId': COGNITO_CLIENT_ID,
            'SecretHash': get_secret_hash(email),
            'Username': email
        })

        if status_code != 200:
            error_msg = result.get('message', 'Failed to resend code')
            return jsonify({'status': 'error', 'message': error_msg}), 400

        return jsonify({'status': 'success', 'message': 'New code sent to your email'})
    except Exception as e:
        print(f"Resend error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """User login via Cognito (direct HTTP)"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'}), 400

    try:
        result, status_code = cognito_request('InitiateAuth', {
            'ClientId': COGNITO_CLIENT_ID,
            'AuthFlow': 'USER_PASSWORD_AUTH',
            'AuthParameters': {
                'USERNAME': email,
                'PASSWORD': password,
                'SECRET_HASH': get_secret_hash(email)
            }
        })

        if status_code != 200:
            error_type = result.get('__type', '')
            if 'NotAuthorizedException' in error_type:
                return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401
            if 'UserNotConfirmedException' in error_type:
                return jsonify({'status': 'error', 'message': 'Please verify your email first'}), 401
            return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401

        auth_result = result.get('AuthenticationResult', {})
        access_token = auth_result.get('AccessToken', '')

        # Get user attributes using the access token
        user_result, user_status = cognito_request('GetUser', {
            'AccessToken': access_token
        })

        user_name = email.split('@')[0]
        if user_status == 200:
            user_attrs = {a['Name']: a['Value'] for a in user_result.get('UserAttributes', [])}
            user_name = user_attrs.get('name', user_name)

        return jsonify({
            'status': 'success',
            'token': access_token,
            'idToken': auth_result.get('IdToken', ''),
            'refreshToken': auth_result.get('RefreshToken', ''),
            'name': user_name,
            'email': email,
            'message': 'Login successful'
        })
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """User logout - invalidate Cognito token (direct HTTP)"""
    data = request.get_json()
    token = data.get('token', '')

    try:
        cognito_request('GlobalSignOut', {
            'AccessToken': token
        })
    except Exception as e:
        print(f"Logout error (token may be expired): {e}")

    return jsonify({'status': 'success', 'message': 'Logged out successfully'})

@app.route('/api/delete-account', methods=['POST'])
def delete_account():
    """Delete user account from Cognito (direct HTTP)"""
    data = request.get_json()
    token = data.get('token', '')

    try:
        result, status_code = cognito_request('DeleteUser', {
            'AccessToken': token
        })

        if status_code != 200:
            return jsonify({'status': 'error', 'message': 'Invalid or expired session'}), 401

        return jsonify({'status': 'success', 'message': 'Account deleted successfully'})
    except Exception as e:
        print(f"Delete account error: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid or expired session'}), 401

@app.route('/api/verify', methods=['POST'])
def verify_token():
    """Verify if Cognito token is valid (direct HTTP)"""
    data = request.get_json()
    token = data.get('token', '')

    try:
        result, status_code = cognito_request('GetUser', {
            'AccessToken': token
        })

        if status_code != 200:
            return jsonify({'status': 'error', 'valid': False}), 401

        user_attrs = {a['Name']: a['Value'] for a in result.get('UserAttributes', [])}

        return jsonify({
            'status': 'success',
            'valid': True,
            'name': user_attrs.get('name', ''),
            'email': user_attrs.get('email', '')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'valid': False}), 401


# ============== ADDITIONAL AUTH FEATURES ==============

def require_auth(f):
    """Decorator to protect routes — expects JSON body with 'token' field"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        data = request.get_json() or {}
        token = data.get('token', '')
        if not token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]
        if not token:
            return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
        result, status_code = cognito_request('GetUser', {'AccessToken': token})
        if status_code != 200:
            return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 401
        user_attrs = {a['Name']: a['Value'] for a in result.get('UserAttributes', [])}
        request.cognito_user = {'username': result.get('Username', ''), 'attributes': user_attrs}
        request.access_token = token
        return f(*args, **kwargs)
    return decorated

@app.route('/api/refresh-token', methods=['POST'])
def refresh_token():
    """Refresh an expired access token using a refresh token (direct HTTP)"""
    data = request.get_json()
    refresh = data.get('refreshToken', '')
    email = data.get('email', '').strip().lower()

    if not refresh or not email:
        return jsonify({'status': 'error', 'message': 'Refresh token and email are required'}), 400

    try:
        result, status_code = cognito_request('InitiateAuth', {
            'ClientId': COGNITO_CLIENT_ID,
            'AuthFlow': 'REFRESH_TOKEN_AUTH',
            'AuthParameters': {
                'REFRESH_TOKEN': refresh,
                'SECRET_HASH': get_secret_hash(email)
            }
        })

        if status_code != 200:
            return jsonify({'status': 'error', 'message': 'Token refresh failed'}), 401

        auth_result = result.get('AuthenticationResult', {})
        return jsonify({
            'status': 'success',
            'token': auth_result.get('AccessToken', ''),
            'idToken': auth_result.get('IdToken', ''),
            'message': 'Token refreshed'
        })
    except Exception as e:
        print(f"Refresh token error: {e}")
        return jsonify({'status': 'error', 'message': 'Token refresh failed'}), 401

@app.route('/api/send-welcome', methods=['POST'])
def send_welcome():
    """Send welcome email — called by frontend after signup confirmation"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    name = data.get('name', '') or email.split('@')[0]

    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    success = send_welcome_email(email, name)
    if success:
        return jsonify({'status': 'success', 'message': 'Welcome email sent'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to send welcome email'}), 500


@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Initiate password reset — sends code to email (direct HTTP)"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        result, status_code = cognito_request('ForgotPassword', {
            'ClientId': COGNITO_CLIENT_ID,
            'SecretHash': get_secret_hash(email),
            'Username': email
        })

        # Always return success to not reveal if email exists
        return jsonify({
            'status': 'success',
            'message': 'If an account exists with this email, a reset code has been sent.'
        })
    except Exception as e:
        print(f"Forgot password error: {e}")
        return jsonify({'status': 'success', 'message': 'If an account exists with this email, a reset code has been sent.'})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    """Complete password reset with the code from email (direct HTTP)"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    new_password = data.get('newPassword', '')

    if not email or not code or not new_password:
        return jsonify({'status': 'error', 'message': 'Email, code, and new password are required'}), 400

    try:
        result, status_code = cognito_request('ConfirmForgotPassword', {
            'ClientId': COGNITO_CLIENT_ID,
            'SecretHash': get_secret_hash(email),
            'Username': email,
            'ConfirmationCode': code,
            'Password': new_password
        })

        if status_code != 200:
            error_type = result.get('__type', '')
            if 'CodeMismatchException' in error_type:
                return jsonify({'status': 'error', 'message': 'Invalid reset code'}), 400
            if 'InvalidPasswordException' in error_type:
                return jsonify({'status': 'error', 'message': 'Password must be at least 8 characters with uppercase, lowercase, and numbers'}), 400
            return jsonify({'status': 'error', 'message': result.get('message', 'Password reset failed')}), 400

        return jsonify({'status': 'success', 'message': 'Password reset successful. You can now log in.'})
    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({'status': 'error', 'message': 'Password reset failed'}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze_url():
    """Main SEO analysis endpoint - 170 checks across 9 categories"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400
        url = data.get('url', '')
        categories = data.get('categories', ['technical', 'onpage', 'content', 'mobile', 'performance', 'security', 'social', 'local', 'geo', 'citationgap'])
    except Exception:
        return jsonify({'error': 'Invalid request'}), 400
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not url.startswith('http'):
        url = 'https://' + url
    
    try:
        response, soup, load_time = fetch_website(url)
        
        results = {'url': url, 'status': 'success', 'categories': {}, 'totalChecks': 0, 'totalPassed': 0}
        
        # Run selected category analyzers
        analyzers = {
            'technical': ('Technical SEO', analyze_technical_seo),
            'onpage': ('On-Page SEO', analyze_onpage_seo),
            'content': ('Content SEO', analyze_content_seo),
            'mobile': ('Mobile SEO', analyze_mobile_seo),
            'performance': ('Performance', analyze_performance_seo),
            'security': ('Security', analyze_security_seo),
            'social': ('Social SEO', analyze_social_seo),
            'local': ('Local SEO', analyze_local_seo),
            'geo': ('GEO/AEO', analyze_geo_aeo),
            'citationgap': ('Citation Gap', analyze_citation_gap)
        }
        
        for cat_key in categories:
            if cat_key in analyzers:
                name, analyzer_func = analyzers[cat_key]
                result = analyzer_func(url, soup, response, load_time)
                results['categories'][cat_key] = result
                results['totalChecks'] += result['total']
                results['totalPassed'] += result['passed']
        
        # Calculate overall score
        if results['categories']:
            scores = [cat['score'] for cat in results['categories'].values()]
            results['overallScore'] = round(sum(scores) / len(scores), 1)
        else:
            results['overallScore'] = 0
        
        return jsonify(results)
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}', 'url': url}), 400
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}', 'url': url}), 500

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'ok', 
        'totalChecks': 200,
        'categories': {
            'technical': 35,
            'onpage': 25,
            'content': 20,
            'mobile': 15,
            'performance': 18,
            'security': 12,
            'social': 10,
            'local': 15,
            'geo': 30,
            'citationgap': 20
        },
        'endpoints': ['/api/analyze', '/api/content-brief', '/api/content-briefs', '/api/content-score', '/api/ai-recommendations', '/api/health', '/api/status']
    })

@app.route('/api/status')
def status_check():
    """Status endpoint for AEO Platform and other frontends to check backend availability."""
    return jsonify({
        'status': 'online',
        'service': 'ai1stseo-backend',
        'version': '1.0.0',
        'endpoints': {
            'aeo_analyze': '/api/aeo/analyze',
            'geo_probe': '/api/geo-probe',
            'ai_recommendations': '/api/ai-recommendations',
            'content_brief': '/api/content-brief',
            'analyze': '/api/analyze',
            'health': '/api/health'
        }
    })

# Ollama LLM Configuration
OLLAMA_URL = 'https://ollama.sageaios.com/api'  # Primary: free Ollama on homelab GPU
OLLAMA_FALLBACK_URL = 'https://api.databi.io/api'  # Fallback

@app.route('/api/ai-recommendations', methods=['POST'])
def get_ai_recommendations():
    """Generate AI-powered SEO recommendations using local LLM"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400
        audit_results = data.get('auditResults', {})
        url = data.get('url', '')
    except Exception:
        return jsonify({'error': 'Invalid request'}), 400
    
    if not audit_results:
        return jsonify({'error': 'Audit results required'}), 400
    
    # Build a summary of failed/warning checks for the LLM
    issues_summary = []
    for cat_key, cat_data in audit_results.get('categories', {}).items():
        cat_issues = [c for c in cat_data.get('checks', []) if c['status'] in ['fail', 'warning']]
        if cat_issues:
            issues_summary.append(f"\n{cat_key.upper()} ({cat_data.get('score', 0):.0f}% score):")
            for issue in cat_issues[:5]:  # Limit to top 5 per category
                issues_summary.append(f"  - {issue['name']}: {issue['value']} (Recommendation: {issue['recommendation']})")
    
    issues_text = '\n'.join(issues_summary)
    
    prompt = f"""You are an expert SEO consultant. Analyze these SEO audit results and provide actionable recommendations.

Website: {url}
Overall Score: {audit_results.get('overallScore', 0):.0f}%
Passed: {audit_results.get('totalPassed', 0)}/{audit_results.get('totalChecks', 0)} checks

ISSUES FOUND:
{issues_text}

Provide a response with:
1. PRIORITY FIXES (top 5 most impactful changes to make immediately)
2. QUICK WINS (easy fixes that can be done in under 30 minutes)
3. CONTENT RECOMMENDATIONS (specific suggestions for improving content for AI/search visibility)
4. TECHNICAL CODE SNIPPETS (provide actual code for the most critical fixes like schema markup, meta tags, etc.)

Be specific and actionable. Include actual code examples where helpful."""

    try:
        llm_response = call_llm(prompt, timeout=120)
        
        if llm_response:
            return jsonify({
                'status': 'success',
                'recommendations': llm_response,
                'model': 'llama3.1'
            })
        else:
            return jsonify({
                'status': 'error',
                'error': 'Could not connect to any AI server.'
            }), 503
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': f'AI recommendation failed: {str(e)}'
        }), 500

def call_llm(prompt, model='qwen3:30b-a3b', timeout=120):
    """Call LLM with fallback: Nova Lite (Bedrock) → Ollama homelab → Ollama fallback"""
    # 1. Try Nova Lite via Bedrock (fast, cheap, always up)
    try:
        from bedrock_helper import invoke_llm
        result = invoke_llm(prompt, max_tokens=2048)
        if result:
            return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Nova Lite failed, falling back to Ollama: {e}")

    # 2. Fall back to Ollama endpoints (free)
    urls = [OLLAMA_URL, OLLAMA_FALLBACK_URL]
    for url in urls:
        try:
            resp = requests.post(
                f"{url}/generate",
                headers={'Content-Type': 'application/json'},
                json={'model': model, 'stream': False, 'prompt': prompt},
                timeout=timeout
            )
            if resp.status_code == 200:
                return resp.json().get('response', '')
        except:
            continue
    return None


# ============== CONTENT BRIEF GENERATOR ==============

def scrape_serp_results(keyword, num_results=5):
    """Scrape Google search results for a keyword and extract page data"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    serp_data = {'results': [], 'paa_questions': []}
    
    try:
        # Search Google
        search_url = f"https://www.google.com/search?q={requests.utils.quote(keyword)}&num={num_results + 5}&hl=en"
        resp = requests.get(search_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return serp_data
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Extract People Also Ask questions
        paa_divs = soup.find_all('div', {'class': 'related-question-pair'})
        if not paa_divs:
            # Alternative PAA selectors
            paa_divs = soup.find_all('div', attrs={'data-q': True})
        for div in paa_divs:
            q = div.get('data-q') or div.get_text(strip=True)
            if q and len(q) > 10:
                serp_data['paa_questions'].append(q)
        
        # Also try extracting from "People also ask" section
        paa_spans = soup.find_all('span', string=re.compile(r'.+\?$'))
        for span in paa_spans:
            text = span.get_text(strip=True)
            if text and len(text) > 15 and text not in serp_data['paa_questions']:
                serp_data['paa_questions'].append(text)
        
        # Extract organic result URLs
        result_links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('/url?q='):
                clean_url = href.split('/url?q=')[1].split('&')[0]
                if clean_url.startswith('http') and 'google.com' not in clean_url:
                    if clean_url not in result_links:
                        result_links.append(clean_url)
        
        # Scrape each result page
        for url in result_links[:num_results]:
            try:
                page_resp = requests.get(url, headers=headers, timeout=8)
                if page_resp.status_code != 200:
                    continue
                page_soup = BeautifulSoup(page_resp.content, 'html.parser')
                
                # Extract title
                title = ''
                title_tag = page_soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                
                # Extract headings
                headings = {'h1': [], 'h2': [], 'h3': []}
                for level in ['h1', 'h2', 'h3']:
                    for h in page_soup.find_all(level):
                        text = h.get_text(strip=True)
                        if text and len(text) > 2:
                            headings[level].append(text)
                
                # Word count
                text = page_soup.get_text()
                word_count = len(text.split())
                
                # Meta description
                meta_desc = ''
                meta = page_soup.find('meta', attrs={'name': 'description'})
                if meta and meta.get('content'):
                    meta_desc = meta['content']
                
                # Schema markup types
                schemas = []
                for script in page_soup.find_all('script', type='application/ld+json'):
                    try:
                        ld = json.loads(script.string)
                        if isinstance(ld, dict) and '@type' in ld:
                            schemas.append(ld['@type'])
                        elif isinstance(ld, list):
                            for item in ld:
                                if isinstance(item, dict) and '@type' in item:
                                    schemas.append(item['@type'])
                    except:
                        pass
                
                serp_data['results'].append({
                    'url': url,
                    'title': title,
                    'meta_description': meta_desc[:200],
                    'headings': headings,
                    'word_count': word_count,
                    'schema_types': schemas
                })
            except:
                continue
    except Exception as e:
        print(f"SERP scrape error: {e}")
    
    return serp_data


def generate_brief_with_llm(keyword, content_type, serp_data):
    """Use LLM to generate a structured content brief from SERP data"""
    
    # Build competitor summary
    competitor_summary = []
    avg_word_count = 0
    all_h2s = []
    
    for i, r in enumerate(serp_data['results'], 1):
        competitor_summary.append(f"Result {i}: {r['title']}")
        competitor_summary.append(f"  URL: {r['url']}")
        competitor_summary.append(f"  Word count: {r['word_count']}")
        competitor_summary.append(f"  H2 headings: {', '.join(r['headings']['h2'][:8])}")
        competitor_summary.append(f"  Schema: {', '.join(r['schema_types']) if r['schema_types'] else 'None'}")
        avg_word_count += r['word_count']
        all_h2s.extend(r['headings']['h2'])
    
    if serp_data['results']:
        avg_word_count = avg_word_count // len(serp_data['results'])
    
    paa_text = '\n'.join(f"- {q}" for q in serp_data['paa_questions'][:10]) if serp_data['paa_questions'] else 'None found'
    
    prompt = f"""You are an expert SEO content strategist. Generate a structured content brief for the following:

TARGET KEYWORD: {keyword}
CONTENT TYPE: {content_type}
AVERAGE COMPETITOR WORD COUNT: {avg_word_count}

TOP GOOGLE RESULTS FOR THIS KEYWORD:
{chr(10).join(competitor_summary)}

PEOPLE ALSO ASK QUESTIONS:
{paa_text}

Generate a JSON content brief with EXACTLY this structure (no markdown, no code blocks, just raw JSON):
{{
  "recommended_title": "SEO-optimized H1 title for this content",
  "target_word_count": {avg_word_count or 1500},
  "headings": [
    {{"level": "h2", "text": "Heading text", "purpose": "Brief description of what this section covers", "word_budget": 200}},
    {{"level": "h3", "text": "Sub-heading text", "purpose": "Brief description", "word_budget": 150}}
  ],
  "questions_to_answer": [
    {{"question": "Question text", "source": "paa or competitor or ai_suggested", "priority": "high or medium or low"}}
  ],
  "keywords": [
    {{"term": "keyword", "type": "primary or secondary or lsi", "placement": "title or h2 or body or faq"}}
  ],
  "schema_recommendations": ["FAQPage", "Article", "HowTo"],
  "content_guidelines": {{
    "tone": "informative/conversational/technical",
    "target_audience": "description of who this content is for",
    "unique_angle": "what makes this content different from competitors",
    "ai_citation_tips": "how to format content to get cited by AI chatbots"
  }}
}}

IMPORTANT: Return ONLY valid JSON. No explanations, no markdown formatting, no code blocks. Just the JSON object."""

    llm_response = call_llm(prompt, timeout=90)
    
    if llm_response:
        # Try to parse the JSON from LLM response
        try:
            # Clean up response - strip markdown code blocks if present
            cleaned = llm_response.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            match = re.search(r'\{[\s\S]*\}', llm_response)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
    
    return None


@app.route('/api/content-brief', methods=['POST'])
def generate_content_brief():
    """Generate an AI-powered content brief from SERP analysis"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400
        keyword = data.get('keyword', '').strip()
        content_type = data.get('content_type', 'blog').strip()
    except Exception:
        return jsonify({'error': 'Invalid request'}), 400
    
    if not keyword:
        return jsonify({'error': 'keyword is required'}), 400
    
    valid_types = ['blog', 'faq', 'landing_page', 'how_to', 'comparison', 'listicle']
    if content_type not in valid_types:
        content_type = 'blog'
    
    try:
        # Step 1: Scrape SERP results
        serp_data = scrape_serp_results(keyword, num_results=5)
        
        # Step 2: Generate brief with LLM
        brief = generate_brief_with_llm(keyword, content_type, serp_data)
        
        # Step 3: Build response
        response_data = {
            'status': 'success',
            'keyword': keyword,
            'content_type': content_type,
            'serp_analysis': {
                'results_analyzed': len(serp_data['results']),
                'avg_word_count': sum(r['word_count'] for r in serp_data['results']) // max(len(serp_data['results']), 1) if serp_data['results'] else 0,
                'paa_questions': serp_data['paa_questions'],
                'competitors': [{
                    'url': r['url'],
                    'title': r['title'],
                    'word_count': r['word_count'],
                    'headings_count': sum(len(r['headings'][h]) for h in ['h1', 'h2', 'h3']),
                    'schema_types': r['schema_types']
                } for r in serp_data['results']]
            }
        }
        
        if brief:
            response_data['brief'] = brief
            response_data['ai_generated'] = True
        else:
            # Fallback: generate a basic brief from SERP data without LLM
            all_h2s = []
            for r in serp_data['results']:
                all_h2s.extend(r['headings']['h2'][:5])
            
            # Deduplicate and pick top headings
            seen = set()
            unique_h2s = []
            for h in all_h2s:
                h_lower = h.lower().strip()
                if h_lower not in seen and len(h_lower) > 5:
                    seen.add(h_lower)
                    unique_h2s.append(h)
            
            avg_wc = response_data['serp_analysis']['avg_word_count'] or 1500
            
            response_data['brief'] = {
                'recommended_title': f"Complete Guide to {keyword.title()}",
                'target_word_count': avg_wc,
                'headings': [{'level': 'h2', 'text': h, 'purpose': 'Competitor-derived section', 'word_budget': avg_wc // max(len(unique_h2s), 5)} for h in unique_h2s[:8]],
                'questions_to_answer': [{'question': q, 'source': 'paa', 'priority': 'high'} for q in serp_data['paa_questions'][:5]],
                'keywords': [{'term': keyword, 'type': 'primary', 'placement': 'title'}],
                'schema_recommendations': ['Article', 'FAQPage'] if serp_data['paa_questions'] else ['Article'],
                'content_guidelines': {
                    'tone': 'informative',
                    'target_audience': f'People searching for {keyword}',
                    'unique_angle': 'Data-driven analysis based on top-ranking content',
                    'ai_citation_tips': 'Use clear definitions, structured data, and direct answers to questions'
                }
            }
            response_data['ai_generated'] = False
            response_data['note'] = 'LLM unavailable — brief generated from SERP data analysis'
        
        # Save brief to database (DynamoDB or RDS)
        try:
            if USE_DYNAMODB:
                from db_dynamo import save_content_brief
            else:
                from db import save_content_brief
            brief_id = save_content_brief(
                keyword=keyword,
                content_type=content_type,
                brief_json=response_data.get('brief', {}),
                serp_competitors=response_data.get('serp_analysis', {}).get('competitors', []),
                keywords=response_data.get('brief', {}).get('keywords', []),
                ai_generated=response_data.get('ai_generated', False)
            )
            response_data['brief_id'] = brief_id
        except Exception as db_err:
            import logging
            logging.getLogger(__name__).warning(f"Failed to save brief to DB: {db_err}")
        
        return jsonify(response_data)
    
    except Exception as e:
        return jsonify({'error': f'Brief generation failed: {str(e)}'}), 500


@app.route('/api/content-briefs', methods=['GET'])
def list_content_briefs():
    """Retrieve past content briefs, optionally filtered by keyword."""
    try:
        if USE_DYNAMODB:
            from db_dynamo import get_content_briefs, get_content_brief_by_id
        else:
            from db import get_content_briefs, get_content_brief_by_id
        brief_id = request.args.get('id')
        if brief_id:
            brief = get_content_brief_by_id(brief_id)
            if not brief:
                return jsonify({'error': 'Brief not found'}), 404
            return jsonify({'status': 'success', 'brief': brief})
        limit = min(int(request.args.get('limit', 20)), 100)
        keyword_filter = request.args.get('keyword', '').strip()
        briefs = get_content_briefs(limit=limit, keyword_filter=keyword_filter)
        return jsonify({'status': 'success', 'briefs': briefs, 'count': len(briefs)})
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve briefs: {str(e)}'}), 500


# ============== CONTENT SCORING ENGINE (Phase 2) ==============
def compute_readability_score(text):
    """Compute readability metrics: Flesch Reading Ease approximation."""
    words = text.split()
    word_count = len(words)
    if word_count < 10:
        return {'score': 0, 'grade': 'N/A', 'avg_sentence_len': 0, 'avg_word_len': 0, 'word_count': word_count}
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.split()) > 2]
    sent_count = max(len(sentences), 1)
    syllable_count = sum(max(1, len(re.findall(r'[aeiouy]+', w.lower()))) for w in words)
    avg_sent_len = word_count / sent_count
    avg_syl = syllable_count / word_count
    flesch = 206.835 - (1.015 * avg_sent_len) - (84.6 * avg_syl)
    flesch = max(0, min(100, flesch))
    if flesch >= 80: grade = 'Easy'
    elif flesch >= 60: grade = 'Standard'
    elif flesch >= 40: grade = 'Moderate'
    elif flesch >= 20: grade = 'Difficult'
    else: grade = 'Very Difficult'
    return {
        'score': round(flesch, 1), 'grade': grade,
        'avg_sentence_len': round(avg_sent_len, 1),
        'avg_word_len': round(sum(len(w) for w in words) / word_count, 1),
        'word_count': word_count, 'sentence_count': sent_count,
    }


def compute_seo_score(url, soup, text):
    """Score on-page SEO factors (0-100)."""
    points = 0
    max_points = 0
    details = []
    def check(name, passed, weight=1):
        nonlocal points, max_points
        max_points += weight
        if passed:
            points += weight
            details.append({'check': name, 'status': 'pass', 'weight': weight})
        else:
            details.append({'check': name, 'status': 'fail', 'weight': weight})
    title = soup.find('title')
    title_text = title.string.strip() if title and title.string else ''
    check('Title tag present', bool(title_text), 2)
    check('Title length 30-60 chars', 30 <= len(title_text) <= 60)
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_text = meta_desc.get('content', '').strip() if meta_desc else ''
    check('Meta description present', bool(desc_text), 2)
    check('Description length 120-160', 120 <= len(desc_text) <= 160)
    h1s = soup.find_all('h1')
    check('Exactly one H1', len(h1s) == 1, 2)
    h2s = soup.find_all('h2')
    check('Has H2 headings', len(h2s) >= 2)
    words = text.split()
    check('Word count 300+', len(words) >= 300, 2)
    check('Word count 1000+', len(words) >= 1000)
    images = soup.find_all('img')
    imgs_with_alt = [i for i in images if i.get('alt')]
    check('Images have alt text', len(imgs_with_alt) == len(images) or not images)
    parsed = urlparse(url)
    internal_links = [a for a in soup.find_all('a', href=True) if parsed.netloc in urljoin(url, a.get('href', ''))]
    check('3+ internal links', len(internal_links) >= 3)
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    check('Has structured data', bool(json_ld))
    canonical = soup.find('link', {'rel': 'canonical'})
    check('Has canonical tag', bool(canonical))
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    check('Has viewport meta', bool(viewport))
    score = round((points / max_points) * 100) if max_points else 0
    return {'score': score, 'points': points, 'max_points': max_points, 'details': details}


def compute_aeo_score(soup, text):
    """Score AI Engine Optimization readiness (0-100)."""
    points = 0
    max_points = 0
    details = []
    def check(name, passed, weight=1):
        nonlocal points, max_points
        max_points += weight
        if passed:
            points += weight
            details.append({'check': name, 'status': 'pass', 'weight': weight})
        else:
            details.append({'check': name, 'status': 'fail', 'weight': weight})
    has_definition = bool(re.search(r'\b(is a|refers to|is defined as|means that)\b', text.lower()))
    check('Contains direct definitions', has_definition, 2)
    questions = text.count('?')
    check('Has Q&A content (3+ questions)', questions >= 3, 2)
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    has_faq_schema = any('faq' in str(s).lower() for s in json_ld)
    check('Has FAQ schema', has_faq_schema, 2)
    check('Has any structured data', bool(json_ld))
    list_items = soup.find_all('li')
    check('Has lists (5+ items)', len(list_items) >= 5)
    tables = soup.find_all('table')
    check('Has data tables', bool(tables))
    h2s = soup.find_all('h2')
    h3s = soup.find_all('h3')
    check('Good heading structure (3+ H2s)', len(h2s) >= 3)
    check('Has sub-headings (H3s)', bool(h3s))
    numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?%?\b', text)
    check('Contains statistics/data (5+)', len(numbers) >= 5)
    has_citations = bool(re.search(r'(according to|source:|study|research shows|data from)', text.lower()))
    check('Cites sources/research', has_citations)
    has_date = bool(re.search(r'(202[4-6]|updated|as of|last modified)', text.lower()))
    check('Has freshness signals', has_date)
    paragraphs = soup.find_all('p')
    long_paras = [p for p in paragraphs if len(p.get_text().split()) > 100]
    check('No overly long paragraphs', len(long_paras) <= 2)
    score = round((points / max_points) * 100) if max_points else 0
    return {'score': score, 'points': points, 'max_points': max_points, 'details': details}


@app.route('/api/content-score', methods=['POST'])
def content_score():
    """Content Scoring Engine — computes SEO score, AEO score, and readability for any URL."""
    data = request.get_json()
    url = (data or {}).get('url', '').strip()
    if not url:
        return jsonify({'error': 'url is required'}), 400
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        start_time = time.time()
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        load_time = time.time() - start_time
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        readability = compute_readability_score(text)
        seo = compute_seo_score(url, soup, text)
        aeo = compute_aeo_score(soup, text)
        overall = round(seo['score'] * 0.4 + aeo['score'] * 0.35 + readability['score'] * 0.25)
        return jsonify({
            'status': 'success', 'url': url, 'overall_score': overall,
            'seo': seo, 'aeo': aeo, 'readability': readability,
            'load_time': round(load_time, 2),
            'scored_at': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Scoring failed: {str(e)}'}), 500


@app.route('/api/geo-probe', methods=['POST'])
def geo_probe():
    """GEO Monitoring Engine — multi-provider, direct AI calls."""
    from geo_probe_service import geo_probe as _geo_probe

    data = request.get_json() or {}
    brand = (data.get('brand_name') or data.get('brand') or '').strip()
    keyword = (data.get('keyword') or '').strip()
    provider = (data.get('provider') or data.get('ai_model') or 'nova').strip().lower()

    if not brand or not keyword:
        return jsonify({'error': 'brand_name and keyword are required'}), 400

    try:
        result = _geo_probe(brand, keyword, ai_model=provider)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'GEO probe failed: {str(e)}'}), 500


@app.route('/api/geo-probe/models', methods=['GET'])
def geo_probe_models():
    """List available AI providers for GEO probing."""
    from geo_probe_service import available_models
    return jsonify({'models': available_models()})


@app.route('/api/geo-probe/batch', methods=['POST'])
def geo_probe_batch():
    """GEO/AEO batch analysis — multi-provider, direct AI calls."""
    from geo_probe_service import geo_probe_batch as _batch

    data = request.get_json() or {}
    brand = (data.get('brand_name') or data.get('brand') or '').strip()
    keywords = data.get('keywords') or []
    provider = (data.get('provider') or data.get('ai_model') or 'nova').strip().lower()

    if not brand:
        return jsonify({'error': 'brand_name is required'}), 400
    if not keywords or not isinstance(keywords, list):
        return jsonify({'error': 'keywords must be a non-empty list'}), 400
    if len(keywords) > 20:
        return jsonify({'error': 'Maximum 20 keywords per batch'}), 400

    try:
        return jsonify(_batch(brand, keywords, ai_model=provider))
    except Exception as e:
        return jsonify({'error': f'Batch probe failed: {str(e)}'}), 500


@app.route('/api/geo-probe/history', methods=['GET'])
def geo_probe_history():
    """Return probe history — batch summaries + individual probes from RDS."""
    from geo_probe_service import get_history, get_stored_history
    brand = request.args.get('brand')
    ai_model = request.args.get('ai_model')
    limit = int(request.args.get('limit', 50))
    try:
        batch = get_history()
    except Exception as e:
        batch = []
        app.logger.error("Failed to load batch history: %s", e)
    try:
        stored = get_stored_history(limit=limit, brand=brand, ai_model=ai_model)
    except Exception as e:
        stored = []
        app.logger.error("Failed to load stored history: %s", e)
    return jsonify({
        'batch_history': batch,
        'stored_results': stored,
        'db_status': 'ok' if (batch or stored) else 'empty_or_unreachable',
    })


@app.route('/api/geo-probe/schedule', methods=['POST'])
def geo_probe_schedule():
    """Register a scheduled monitoring job (placeholder)."""
    from geo_probe_service import schedule_probe
    data = request.get_json() or {}
    brand = (data.get('brand_name') or '').strip()
    keywords = data.get('keywords') or []
    provider = (data.get('provider') or 'nova').strip()
    interval = int(data.get('interval_minutes', 60))
    if not brand or not keywords:
        return jsonify({'error': 'brand_name and keywords are required'}), 400
    job = schedule_probe(brand, keywords, ai_model=provider, interval_minutes=interval)
    return jsonify(job)


@app.route('/api/geo-probe/schedule', methods=['GET'])
def geo_probe_schedule_list():
    """List registered scheduled jobs."""
    from geo_probe_service import get_scheduled_jobs
    return jsonify({'jobs': get_scheduled_jobs()})


@app.route('/api/geo-probe/compare', methods=['POST'])
def geo_probe_compare():
    """Compare brand visibility across ALL available AI providers simultaneously."""
    from geo_probe_service import geo_probe_compare as _compare
    data = request.get_json() or {}
    brand = (data.get('brand_name') or data.get('brand') or '').strip()
    keyword = (data.get('keyword') or '').strip()
    if not brand or not keyword:
        return jsonify({'error': 'brand_name and keyword are required'}), 400
    try:
        return jsonify(_compare(brand, keyword))
    except Exception as e:
        return jsonify({'error': f'Compare failed: {str(e)}'}), 500


@app.route('/api/geo-probe/site', methods=['POST'])
def geo_probe_site():
    """Detect if a website/URL is mentioned in AI output for a keyword."""
    from geo_probe_service import geo_probe_site as _site
    data = request.get_json() or {}
    site_url = (data.get('site_url') or data.get('url') or '').strip()
    keyword = (data.get('keyword') or '').strip()
    provider = (data.get('provider') or 'nova').strip().lower()
    if not site_url or not keyword:
        return jsonify({'error': 'site_url and keyword are required'}), 400
    try:
        return jsonify(_site(site_url, keyword, ai_model=provider))
    except Exception as e:
        return jsonify({'error': f'Site probe failed: {str(e)}'}), 500


@app.route('/api/geo-probe/trend', methods=['GET'])
def geo_probe_trend():
    """Get visibility trend for a brand over time."""
    from geo_probe_service import get_visibility_trend
    brand = request.args.get('brand', '').strip()
    limit = int(request.args.get('limit', 30))
    if not brand:
        return jsonify({'error': 'brand query param is required'}), 400
    return jsonify(get_visibility_trend(brand, limit=limit))


@app.route('/api/brand/resolve', methods=['POST'])
def brand_resolve():
    """Resolve brand name <-> domain, suggest keywords."""
    from brand_resolver import resolve_brand
    data = request.get_json() or {}
    brand = (data.get('brand') or data.get('brand_name') or '').strip() or None
    url = (data.get('url') or data.get('site_url') or '').strip() or None
    if not brand and not url:
        return jsonify({'error': 'Provide brand or url'}), 400
    try:
        return jsonify(resolve_brand(brand=brand, url=url))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/citation-probe', methods=['POST'])
def ai_citation_probe():
    """
    AI Citation Probe — calls Bedrock/Ollama directly.

    Request:
        { "keyword": "best project management tools 2025",
          "brand_name": "Notion" }

    Response:
        { keyword, ai_model, brand_present, citation_context,
          confidence, cited_sources, timestamp }
    """
    from geo_probe_service import geo_probe as _geo_probe

    data = request.get_json() or {}
    keyword = (data.get('keyword') or '').strip()
    brand = (data.get('brand_name') or data.get('brand') or '').strip()

    if not keyword:
        return jsonify({'error': 'keyword is required'}), 400
    if not brand:
        return jsonify({'error': 'brand_name is required'}), 400

    try:
        result = _geo_probe(brand, keyword)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Citation probe failed: {str(e)}'}), 500


@app.route('/api/ai/geo-monitor', methods=['POST'])
def ai_geo_monitor():
    """
    GEO Monitor — query all available AI models in parallel for a keyword.

    Request:
        {
          "keyword":   "best CRM software 2025",  (required)
          "brand":     "HubSpot",                 (optional — tracked in scoring)
          "providers": ["claude", "openai"]        (optional — defaults to all)
        }

    Response:
        {
          "keyword": "...",
          "brand": "...",
          "models": {
            "claude":  { cited probe result },
            "openai":  { cited probe result },
            "gemini":  { unavailable or result }
          },
          "geo_score": 67,
          "score_breakdown": { ... },
          "timestamp": "..."
        }
    """
    from llm_service import geo_monitor

    data = request.get_json() or {}
    keyword   = (data.get('keyword') or '').strip()
    brand     = (data.get('brand') or '').strip() or None
    providers = data.get('providers') or None

    if not keyword:
        return jsonify({'error': 'keyword is required'}), 400

    if providers is not None and not isinstance(providers, list):
        return jsonify({'error': 'providers must be a list'}), 400

    try:
        result = geo_monitor(keyword, brand=brand, providers=providers)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'GEO monitor failed: {str(e)}'}), 500


@app.route('/resources/AI1STSEO-UML-DIAGRAMS.md')
def serve_uml_diagrams():
    return send_from_directory('.', 'AI1STSEO-UML-DIAGRAMS.md', mimetype='text/markdown')


# ============== AEO OPTIMIZER ==============

@app.route('/api/aeo/analyze', methods=['POST'])
def aeo_analyze():
    """AEO analysis — scan a URL for AI engine optimization issues."""
    from aeo_optimizer import analyze_aeo

    data = request.get_json() or {}
    url = (data.get('url') or '').strip()
    brand = (data.get('brand_name') or '').strip() or None

    if not url:
        return jsonify({'error': 'url is required'}), 400

    try:
        result = analyze_aeo(url, brand_name=brand)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'AEO analysis failed: {str(e)}'}), 500


# ============== AI RANKING RECOMMENDATIONS ==============

@app.route('/api/ai/ranking-recommendations', methods=['POST'])
def ai_ranking_recommendations():
    """
    AI ranking recommendations for a URL + brand.

    Request: { "url": "https://...", "brand_name": "Nike", "keywords": ["running shoes"] }
    """
    from ai_ranking_service import get_ranking_recommendations
    from geo_probe_service import geo_probe_batch as _batch

    data = request.get_json() or {}
    url = (data.get('url') or '').strip()
    brand = (data.get('brand_name') or '').strip()
    keywords = data.get('keywords') or []

    if not url or not brand:
        return jsonify({'error': 'url and brand_name are required'}), 400

    # Optionally run GEO probes for the keywords to feed into recommendations
    geo_results = []
    if keywords:
        try:
            batch = _batch(brand, keywords[:5])
            geo_results = batch.get('results', [])
        except Exception:
            pass  # Recommendations still work without probe data

    try:
        result = get_ranking_recommendations(url, brand, geo_results=geo_results)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Ranking analysis failed: {str(e)}'}), 500


# ============== CONTENT GENERATION PIPELINE ==============

@app.route('/api/content/generate', methods=['POST'])
def content_generate():
    """
    Generate AI-optimized content.

    Request: {
        "brand_name": "Notion",
        "content_type": "faq|comparison|meta_description|feature_snippet",
        "topic": "project management tools",
        "competitors": ["Asana", "Monday"],  (for comparison type)
        "count": 5                            (for faq type)
    }
    """
    from content_generator import generate_content

    data = request.get_json() or {}
    brand = (data.get('brand_name') or '').strip()
    content_type = (data.get('content_type') or '').strip()
    topic = (data.get('topic') or '').strip()
    competitors = data.get('competitors') or []
    count = data.get('count', 5)

    if not brand or not content_type:
        return jsonify({'error': 'brand_name and content_type are required'}), 400

    try:
        result = generate_content(brand, content_type, topic=topic,
                                   competitors=competitors, count=count)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Content generation failed: {str(e)}'}), 500


# ============== AI SEO CHATBOT ==============

@app.route('/api/chatbot/session', methods=['POST'])
def chatbot_create_session():
    """Create a new chatbot session."""
    from ai_chatbot import create_session
    return jsonify(create_session())


@app.route('/api/chatbot/chat', methods=['POST'])
def chatbot_chat():
    """
    Send a message to the AI SEO chatbot.

    Request: { "session_id": "abc123", "message": "How do I optimize for ChatGPT?" }
    Auto-creates session if session_id is new.
    """
    from ai_chatbot import chat

    data = request.get_json() or {}
    session_id = (data.get('session_id') or '').strip()
    message = (data.get('message') or '').strip()

    if not message:
        return jsonify({'error': 'message is required'}), 400
    if not session_id:
        session_id = str(__import__('uuid').uuid4())[:12]

    try:
        result = chat(session_id, message)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Chatbot failed: {str(e)}'}), 500


@app.route('/api/chatbot/history/<session_id>', methods=['GET'])
def chatbot_history(session_id):
    """Get chat history for a session."""
    from ai_chatbot import get_session_history
    return jsonify(get_session_history(session_id))


@app.route('/api/chatbot/sessions', methods=['GET'])
def chatbot_sessions():
    """List active chatbot sessions."""
    from ai_chatbot import list_sessions
    return jsonify({'sessions': list_sessions()})


# ============== LLM MULTI-PROVIDER ==============

@app.route('/api/llm/providers', methods=['GET'])
def llm_providers():
    """List available LLM providers."""
    from llm_service import _available_providers, PROVIDERS
    available = _available_providers()
    return jsonify({
        'providers': [
            {'name': name, 'model': PROVIDERS[name]['default_model'],
             'available': name in available}
            for name in PROVIDERS
        ],
        'available_count': len(available),
    })


@app.route('/api/llm/citation-probe', methods=['POST'])
def llm_citation_probe():
    """
    Multi-provider citation probe.

    Request: { "keyword": "best CRM tools", "provider": "claude" }
    """
    from llm_service import citation_probe

    data = request.get_json() or {}
    keyword = (data.get('keyword') or '').strip()
    provider = (data.get('provider') or 'claude').strip()

    if not keyword:
        return jsonify({'error': 'keyword is required'}), 400

    try:
        result = citation_probe(keyword, provider=provider)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Citation probe failed: {str(e)}'}), 500

# ── GEO Scanner Agent Orchestrator ────────────────────────────────────────────

@app.route('/api/geo-scanner/scan', methods=['POST'])
@app.route('/api/geo-scanner/scan', methods=['POST'])
def geo_scanner_scan():
    """Run a full GEO Scanner Agent scan — orchestrates all scanner agents."""
    from geo_scanner_agent import run_full_scan
    data = request.get_json() or {}
    brand = (data.get('brand_name') or data.get('brand') or '').strip()
    if not brand:
        return jsonify({'error': 'brand_name is required'}), 400

    try:
        result = run_full_scan(
            brand_name=brand,
            url=data.get('url'),
            keywords=data.get('keywords', []),
            provider=data.get('provider', 'nova'),
            scanners=data.get('scanners'),
        )

        # Persist full scan result to geo-scans table for history
        try:
            from dynamo.geo_repository import GEORepository
            repo = GEORepository()
            repo.save_scan(brand, {
                'geo_score': result.get('overall_score', 0),
                'grade': _score_to_grade(result.get('overall_score', 0)),
                'metrics': {
                    'scanners_run': result.get('scanners_run', []),
                    'elapsed_seconds': result.get('elapsed_seconds', 0),
                },
                'suggestions': result.get('recommendations', []),
                'missing': [],
                'verdict': result.get('executive_summary', ''),
            })
        except Exception as e:
            app.logger.warning("Failed to persist GEO scan to history: %s", e)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'GEO scan failed: {str(e)}'}), 500


def _score_to_grade(score):
    if score >= 90: return 'A+'
    if score >= 80: return 'A'
    if score >= 70: return 'B'
    if score >= 60: return 'C'
    if score >= 50: return 'D'
    return 'F'


@app.route('/api/geo-scanner/history', methods=['GET'])
def geo_scanner_history():
    """GET /api/geo-scanner/history — retrieve past GEO scanner scan results."""
    brand = request.args.get('brand', request.args.get('brand_name', ''))
    limit = int(request.args.get('limit', 20))
    if not brand:
        return jsonify({'error': 'brand query param is required'}), 400
    try:
        from dynamo.geo_repository import GEORepository
        repo = GEORepository()
        scans = repo.get_scans(brand, limit=limit)
        return jsonify({'brand': brand, 'scans': scans, 'count': len(scans)})
    except Exception as e:
        return jsonify({'brand': brand, 'scans': [], 'error': str(e)})


@app.route('/api/geo-scanner/agents', methods=['GET'])
def geo_scanner_agents():
    """List available scanner agents."""
    from geo_scanner_agent import get_available_scanners
    return jsonify({'agents': get_available_scanners()})


# ── Feature 1: AI Answer Fingerprinting ───────────────────────────────────────

@app.route('/api/geo/fingerprint', methods=['POST'])
def geo_fingerprint_save():
    """Save a response fingerprint and detect changes."""
    from answer_fingerprint import save_fingerprint
    data = request.get_json() or {}
    brand = (data.get('brand_name') or '').strip()
    keyword = (data.get('keyword') or '').strip()
    ai_model = (data.get('ai_model') or 'nova').strip()
    response_text = (data.get('response_text') or '').strip()
    if not brand or not keyword or not response_text:
        return jsonify({'error': 'brand_name, keyword, and response_text are required'}), 400
    try:
        result = save_fingerprint(brand, keyword, ai_model, response_text,
                                   probe_id=data.get('probe_id'))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Fingerprint save failed: {str(e)}'}), 500


@app.route('/api/geo/fingerprint/<brand_name>/history', methods=['GET'])
def geo_fingerprint_history(brand_name):
    """Get the last N fingerprints for a brand with diff summaries."""
    from answer_fingerprint import get_fingerprint_history
    keyword = request.args.get('keyword')
    ai_model = request.args.get('ai_model')
    limit = int(request.args.get('limit', 10))
    try:
        history = get_fingerprint_history(brand_name, keyword=keyword,
                                           ai_model=ai_model, limit=limit)
        return jsonify({'brand_name': brand_name, 'history': history, 'count': len(history)})
    except Exception as e:
        return jsonify({'error': f'History fetch failed: {str(e)}'}), 500


# ── Feature 2: AI Model Disagreement Detector ─────────────────────────────────

@app.route('/api/geo/model-comparison', methods=['POST'])
def geo_model_comparison():
    """Compare how different AI models respond to the same brand/keyword query."""
    from model_comparison import probe_all_models
    data = request.get_json() or {}
    brand = (data.get('brand_name') or '').strip()
    keyword = (data.get('keyword') or '').strip()
    if not brand or not keyword:
        return jsonify({'error': 'brand_name and keyword are required'}), 400
    try:
        result = probe_all_models(brand, keyword)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Model comparison failed: {str(e)}'}), 500


@app.route('/api/geo/model-comparison/history', methods=['GET'])
def geo_model_comparison_history():
    """Get past model comparison results."""
    from model_comparison import get_comparison_history
    brand = request.args.get('brand_name')
    limit = int(request.args.get('limit', 10))
    try:
        history = get_comparison_history(brand_name=brand, limit=limit)
        return jsonify({'history': history, 'count': len(history)})
    except Exception as e:
        return jsonify({'error': f'History fetch failed: {str(e)}'}), 500


# ── Feature 3: Multi-Language GEO Probing ─────────────────────────────────────

@app.route('/api/geo/scan/languages', methods=['POST'])
def geo_multilang_scan():
    """Run GEO probes across multiple languages."""
    from multilang_probe import probe_multilang
    data = request.get_json() or {}
    brand = (data.get('brand_name') or '').strip()
    keyword = (data.get('keyword') or '').strip()
    languages = data.get('languages', ['en'])
    provider = data.get('provider', 'nova')
    if not brand or not keyword:
        return jsonify({'error': 'brand_name and keyword are required'}), 400
    if len(languages) > 10:
        return jsonify({'error': 'Maximum 10 languages per scan'}), 400
    try:
        result = probe_multilang(brand, keyword, languages=languages, provider=provider)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Multi-language scan failed: {str(e)}'}), 500


# ── Feature 5: AI Share of Voice ──────────────────────────────────────────────

@app.route('/api/geo/share-of-voice', methods=['POST'])
def geo_share_of_voice():
    """Calculate AI Share of Voice: brand vs competitors across keywords."""
    from share_of_voice import calculate_sov
    data = request.get_json() or {}
    brand = (data.get('brand') or data.get('brand_name') or '').strip()
    competitors = [c.strip() for c in (data.get('competitors') or []) if c.strip()]
    keywords = [k.strip() for k in (data.get('keywords') or []) if k.strip()]
    provider = data.get('provider', 'nova')
    if not brand:
        return jsonify({'error': 'brand is required'}), 400
    if not keywords:
        return jsonify({'error': 'At least one keyword is required'}), 400
    if not competitors:
        return jsonify({'error': 'At least one competitor is required'}), 400
    try:
        result = calculate_sov(brand, competitors[:5], keywords[:10], provider=provider)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'SOV calculation failed: {str(e)}'}), 500


@app.route('/api/geo/share-of-voice/<brand_name>/latest', methods=['GET'])
def geo_sov_latest(brand_name):
    """Get the latest SOV scan for a brand."""
    from share_of_voice import get_sov_latest
    result = get_sov_latest(brand_name)
    if not result:
        return jsonify({'error': 'No SOV data found for this brand', 'brand': brand_name}), 404
    return jsonify(result)


# ── Feature 6: Prompt Injection Simulator ─────────────────────────────────────

@app.route('/api/geo/prompt-simulator', methods=['POST'])
def geo_prompt_simulator():
    """Run prompt simulation: 15 prompt variations to test brand visibility."""
    from prompt_simulator import run_simulation
    data = request.get_json() or {}
    brand = (data.get('brand') or data.get('brand_name') or '').strip()
    keyword = (data.get('keyword') or '').strip()
    provider = data.get('provider', 'nova')
    if not brand or not keyword:
        return jsonify({'error': 'brand and keyword are required'}), 400
    try:
        result = run_simulation(brand, keyword, provider=provider)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Prompt simulation failed: {str(e)}'}), 500


@app.route('/api/geo/prompt-simulator/<brand_name>/history', methods=['GET'])
def geo_prompt_simulator_history(brand_name):
    """Get past prompt simulation results."""
    from prompt_simulator import get_simulation_history
    limit = int(request.args.get('limit', 5))
    history = get_simulation_history(brand_name, limit=limit)
    return jsonify({'brand': brand_name, 'history': history, 'count': len(history)})


# ── RDS Data Persistence Endpoints ────────────────────────────────────────────

@app.route('/api/data/geo-probes', methods=['GET'])
def data_geo_probes_get():
    """GET /api/data/geo-probes — retrieve GEO probe history."""
    if USE_DYNAMODB:
        from db_dynamo import get_probes
    else:
        from db import get_probes
    brand = request.args.get('brand')
    ai_model = request.args.get('ai_model')
    limit = int(request.args.get('limit', 50))
    try:
        probes = get_probes(limit=limit, brand=brand, ai_model=ai_model)
        return jsonify({'probes': probes, 'count': len(probes)})
    except Exception as e:
        return jsonify({'probes': [], 'count': 0, 'error': str(e)})


@app.route('/api/data/geo-probes', methods=['POST'])
def data_geo_probes():
    """POST /api/data/geo-probes — persist GEO probe results."""
    if USE_DYNAMODB:
        from db_dynamo import insert_probe
    else:
        from db import insert_probe
    data = request.get_json() or {}
    keyword = (data.get('keyword') or '').strip()
    brand = (data.get('brand') or data.get('brand_name') or '').strip()
    ai_model = (data.get('ai_model') or data.get('provider') or 'nova').strip()

    if not keyword or not brand:
        return jsonify({'error': 'keyword and brand are required'}), 400

    try:
        probe_id = insert_probe(
            keyword=keyword,
            brand=brand,
            ai_model=ai_model,
            cited=data.get('cited', False),
            citation_context=data.get('citation_context', ''),
            confidence=data.get('confidence', 0.0),
            response_snippet=data.get('response_snippet', ''),
            sentiment=data.get('sentiment', 'neutral'),
        )
        return jsonify({'status': 'saved', 'probe_id': probe_id})
    except Exception as e:
        return jsonify({'error': f'Failed to save probe: {str(e)}'}), 500


@app.route('/api/data/ai-visibility', methods=['GET'])
def data_ai_visibility_get():
    """GET /api/data/ai-visibility — retrieve visibility history."""
    if USE_DYNAMODB:
        from db_dynamo import get_visibility_history
    else:
        from db import get_visibility_history
    brand = request.args.get('brand')
    limit = int(request.args.get('limit', 20))
    try:
        history = get_visibility_history(limit=limit, brand=brand)
        return jsonify({'history': history, 'count': len(history)})
    except Exception as e:
        return jsonify({'history': [], 'count': 0, 'error': str(e)})


@app.route('/api/data/ai-visibility/trend', methods=['GET'])
def data_ai_visibility_trend():
    """GET /api/data/ai-visibility/trend — daily probe trend for a brand."""
    if USE_DYNAMODB:
        from db_dynamo import get_probe_trend
    else:
        from db import get_probe_trend
    brand = request.args.get('brand', '')
    limit = int(request.args.get('limit', 30))
    if not brand:
        return jsonify({'error': 'brand query param is required'}), 400
    try:
        trend = get_probe_trend(brand, limit=limit)
        return jsonify({'brand': brand, 'trend': trend, 'count': len(trend)})
    except Exception as e:
        return jsonify({'brand': brand, 'trend': [], 'error': str(e)})


@app.route('/api/data/ai-visibility', methods=['POST'])
def data_ai_visibility():
    """POST /api/data/ai-visibility — persist batch visibility results."""
    if USE_DYNAMODB:
        from db_dynamo import insert_visibility_batch
    else:
        from db import insert_visibility_batch
    data = request.get_json() or {}
    brand = (data.get('brand') or data.get('brand_name') or '').strip()
    ai_model = (data.get('ai_model') or data.get('provider') or 'nova').strip()

    if not brand:
        return jsonify({'error': 'brand is required'}), 400

    try:
        batch_id = insert_visibility_batch(
            brand=brand,
            ai_model=ai_model,
            keyword=data.get('keyword', ''),
            geo_score=data.get('geo_score', 0),
            cited_count=data.get('cited_count', 0),
            total_prompts=data.get('total_prompts', 0),
            batch_results=json.dumps(data.get('batch_results', [])),
        )
        return jsonify({'status': 'saved', 'batch_id': batch_id})
    except Exception as e:
        return jsonify({'error': f'Failed to save visibility batch: {str(e)}'}), 500


# ── GEO Scanner Dashboard Page ───────────────────────────────────────────────

@app.route('/geo-scanner')
def serve_geo_scanner():
    """Serve the GEO Scanner Agent dashboard."""
    return send_from_directory('.', 'geo-scanner.html')


@app.route('/audit/')
@app.route('/audit/<path:url>')
def serve_audit(url=None):
    return send_from_directory('.', 'audit.html')

@app.route('/geo-test')
def serve_geo_test():
    return send_from_directory('.', 'geo-test.html')

@app.route('/dev1-dashboard')
def serve_dev1_dashboard():
    return send_from_directory('.', 'dev1-dashboard.html')

@app.route('/dashboard')
def serve_dashboard_redirect():
    """Short alias — /dashboard redirects to /dev1-dashboard"""
    return send_from_directory('.', 'dev1-dashboard.html')

@app.route('/admin')
def serve_admin():
    """Admin dashboard — overview, users, usage, AI costs, errors, health."""
    return send_from_directory('.', 'admin.html')


@app.route('/directory')
def serve_directory():
    """AI Business Directory — Top 10 dentists in Ottawa."""
    return render_template('directory_category.html')


@app.route('/directory-listing.html')
@app.route('/directory-listing')
def serve_directory_listing():
    """AI Business Directory — individual listing detail page."""
    return render_template('directory_listing.html')


@app.route('/directory-compare.html')
@app.route('/directory-compare')
def serve_directory_compare():
    """AI Business Directory — compare two businesses side by side."""
    return render_template('directory_compare.html')


# ── Root-level AI crawler files (proxy to directory module) ───────────────────

@app.route('/llms.txt')
def serve_root_llms_txt():
    """Serve llms.txt at root level for AI crawlers."""
    from flask import Response
    try:
        from directory.routes import _get_backend
        from directory.seo_files import generate_llms_txt
        backend = _get_backend()
        listings = backend.get_all_listings(limit=200)
        categories = backend.get_categories()
        content = generate_llms_txt(listings, categories)
        return Response(content, mimetype='text/plain; charset=utf-8')
    except Exception as e:
        return Response(f'# Error: {e}', mimetype='text/plain'), 500


@app.route('/sitemap-ai.xml')
def serve_root_sitemap_ai():
    """Serve sitemap-ai.xml at root level for AI crawlers."""
    from flask import Response
    try:
        from directory.routes import _get_backend
        from directory.seo_files import generate_sitemap_ai_xml
        backend = _get_backend()
        listings = backend.get_all_listings(limit=500)
        categories = backend.get_categories()
        content = generate_sitemap_ai_xml(listings, categories)
        return Response(content, mimetype='application/xml; charset=utf-8')
    except Exception as e:
        return Response(f'<!-- Error: {e} -->', mimetype='application/xml'), 500


# ── Month 1 Research API ──────────────────────────────────────────────────────

@app.route('/api/month1/keyword-universe', methods=['POST'])
def month1_keyword_universe():
    """Generate 200 categorised natural-language queries."""
    from month1_api import api_keyword_universe
    data = request.get_json() or {}
    result, status = api_keyword_universe(data)
    return jsonify(result), status

@app.route('/api/month1/benchmark', methods=['POST'])
def month1_benchmark():
    """Run benchmark research — returns job_id for async polling."""
    from month1_api import api_benchmark
    data = request.get_json() or {}
    result, status = api_benchmark(data)
    return jsonify(result), status

@app.route('/api/month1/provider-behaviour', methods=['POST'])
def month1_provider_behaviour():
    """Analyze provider behaviour — returns job_id for async polling."""
    from month1_api import api_provider_behaviour
    data = request.get_json() or {}
    result, status = api_provider_behaviour(data)
    return jsonify(result), status

@app.route('/api/month1/answer-taxonomy', methods=['POST'])
def month1_answer_taxonomy():
    """Build answer format taxonomy from empirical data."""
    from month1_api import api_answer_taxonomy
    data = request.get_json() or {}
    result, status = api_answer_taxonomy(data)
    return jsonify(result), status

@app.route('/api/month1/geo-baseline', methods=['POST'])
def month1_geo_baseline():
    """Generate Month 1 GEO baseline — returns job_id for async polling."""
    from month1_api import api_geo_baseline
    data = request.get_json() or {}
    result, status = api_geo_baseline(data)
    return jsonify(result), status

@app.route('/api/month1/monitoring/activate', methods=['POST'])
def month1_monitoring_activate():
    """Activate scheduled monitoring jobs."""
    from month1_api import api_monitoring_activate
    data = request.get_json() or {}
    result, status = api_monitoring_activate(data)
    return jsonify(result), status

@app.route('/api/month1/eeat-register', methods=['POST'])
def month1_eeat_register():
    """Build E-E-A-T gap register from page audits."""
    from month1_api import api_eeat_register
    data = request.get_json() or {}
    result, status = api_eeat_register(data)
    return jsonify(result), status

@app.route('/api/month1/technical-debt', methods=['POST'])
def month1_technical_debt():
    """Run 236-check audit and build technical debt register."""
    from month1_api import api_technical_debt
    data = request.get_json() or {}
    result, status = api_technical_debt(data)
    return jsonify(result), status

@app.route('/api/month1/run-all', methods=['POST'])
def month1_run_all():
    """Run all 8 Month 1 deliverables — returns job_id for async polling."""
    from month1_api import api_run_all
    data = request.get_json() or {}
    result, status = api_run_all(data)
    return jsonify(result), status

@app.route('/api/month1/job/<job_id>', methods=['GET'])
def month1_job_status(job_id):
    """Poll async job status."""
    from month1_api import api_job_status
    result, status = api_job_status(job_id)
    return jsonify(result), status

@app.route('/api/month1/results', methods=['GET'])
def month1_results():
    """Get latest Month 1 results."""
    from month1_api import api_latest_results
    deliverable = request.args.get('deliverable')
    result, status = api_latest_results(deliverable=deliverable)
    return jsonify(result), status

@app.route('/api/month1/results/<deliverable>', methods=['GET'])
def month1_results_by_type(deliverable):
    """Get latest results for a specific deliverable."""
    from month1_api import api_latest_results
    result, status = api_latest_results(deliverable=deliverable)
    return jsonify(result), status


@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('assets/'):
        return send_from_directory('.', path)
    # Don't serve index.html for unknown paths — the real frontend is on S3/CloudFront
    return jsonify({'error': 'Not found', 'message': 'This is the API backend. Visit https://www.ai1stseo.com for the website.'}), 404

if __name__ == '__main__':
    os.environ.setdefault('FLASK_SKIP_DOTENV', '1')
    app.run(host='0.0.0.0', port=5001, debug=False, load_dotenv=False)

# === Lambda handler (Mangum) ===
if IS_LAMBDA:
    try:
        from mangum import Mangum
        from mangum.adapter import Mangum as _M
        import asyncio
        import io as _io

        class _FlaskAsgi:
            """Minimal WSGI-to-ASGI adapter for Flask on Lambda."""
            def __init__(self, wsgi_app):
                self.wsgi_app = wsgi_app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "lifespan":
                    while True:
                        message = await receive()
                        if message["type"] == "lifespan.startup":
                            await send({"type": "lifespan.startup.complete"})
                        elif message["type"] == "lifespan.shutdown":
                            await send({"type": "lifespan.shutdown.complete"})
                            return
                        else:
                            return
                elif scope["type"] == "http":
                    await self._handle_http(scope, receive, send)

            async def _handle_http(self, scope, receive, send):
                body_parts = []
                while True:
                    message = await receive()
                    body_parts.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
                body = b"".join(body_parts)

                headers = dict(scope.get("headers", []))
                environ = {
                    "REQUEST_METHOD": scope["method"],
                    "SCRIPT_NAME": "",
                    "PATH_INFO": scope["path"],
                    "QUERY_STRING": scope.get("query_string", b"").decode("utf-8"),
                    "SERVER_NAME": headers.get(b"host", b"localhost").decode("utf-8").split(":")[0],
                    "SERVER_PORT": str(scope.get("server", ("", 80))[1]) if scope.get("server") else "80",
                    "SERVER_PROTOCOL": "HTTP/{}".format(scope.get("http_version", "1.1")),
                    "wsgi.version": (1, 0),
                    "wsgi.url_scheme": scope.get("scheme", "https"),
                    "wsgi.input": _io.BytesIO(body),
                    "wsgi.errors": _io.BytesIO(),
                    "wsgi.multithread": False,
                    "wsgi.multiprocess": False,
                    "wsgi.run_once": False,
                    "CONTENT_LENGTH": str(len(body)),
                }
                for hdr_name, hdr_val in scope.get("headers", []):
                    name = hdr_name.decode("utf-8").lower()
                    val = hdr_val.decode("utf-8")
                    if name == "content-type":
                        environ["CONTENT_TYPE"] = val
                    else:
                        key = "HTTP_{}".format(name.upper().replace("-", "_"))
                        environ[key] = val

                response_headers = []
                status_code = [500]

                def start_response(status, headers, exc_info=None):
                    status_code[0] = int(status.split(" ", 1)[0])
                    response_headers.clear()
                    response_headers.extend(headers)

                output = self.wsgi_app(environ, start_response)
                body_out = b"".join(output)
                if hasattr(output, "close"):
                    output.close()

                await send({
                    "type": "http.response.start",
                    "status": status_code[0],
                    "headers": [(k.lower().encode(), v.encode()) for k, v in response_headers],
                })
                await send({
                    "type": "http.response.body",
                    "body": body_out,
                })

        _mangum_handler = Mangum(_FlaskAsgi(app), lifespan="off")

        def handler(event, context):
            """Route EventBridge scheduled events to aggregation, everything else to Mangum."""
            if event.get("source") == "aws.events" or event.get("detail-type") == "Scheduled Event":
                try:
                    from admin_aggregation import aggregate_daily_metrics
                    result = aggregate_daily_metrics()
                    print("Admin metrics aggregated: {}".format(result))
                    return {"statusCode": 200, "body": str(result)}
                except Exception as e:
                    return {"statusCode": 500, "body": str(e)}
            return _mangum_handler(event, context)
    except ImportError:
        pass
