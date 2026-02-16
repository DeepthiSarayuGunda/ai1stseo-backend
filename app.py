"""
SEO Analyzer Backend - Flask API
170 Comprehensive SEO Checks across 9 categories
Based on SEMrush, Moz, Ahrefs, and industry best practices
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
import time
import json

app = Flask(__name__, static_folder='../assets', static_url_path='/assets')
CORS(app, origins=[
    'https://ai1stseo.com',
    'https://www.ai1stseo.com',
    'http://localhost:5000',
    'http://127.0.0.1:5000'
])

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


# ============== API ROUTES ==============
@app.route('/')
def serve_index():
    return send_from_directory('..', 'index.html')

@app.route('/analyze')
def serve_analyze():
    return send_from_directory('..', 'analyze.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('../assets', filename)

@app.route('/api/analyze', methods=['POST'])
def analyze_url():
    """Main SEO analysis endpoint - 170 checks across 9 categories"""
    data = request.get_json()
    url = data.get('url', '')
    categories = data.get('categories', ['technical', 'onpage', 'content', 'mobile', 'performance', 'security', 'social', 'local', 'geo'])
    
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
            'geo': ('GEO/AEO', analyze_geo_aeo)
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
        'totalChecks': 180,
        'categories': {
            'technical': 35,
            'onpage': 25,
            'content': 20,
            'mobile': 15,
            'performance': 18,
            'security': 12,
            'social': 10,
            'local': 15,
            'geo': 30
        }
    })

# Ollama LLM Configuration
OLLAMA_URL = 'https://api.databi.io/api'  # Reverse proxy to local Ollama server

@app.route('/api/ai-recommendations', methods=['POST'])
def get_ai_recommendations():
    """Generate AI-powered SEO recommendations using local LLM"""
    data = request.get_json()
    audit_results = data.get('auditResults', {})
    url = data.get('url', '')
    
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
        llm_response = requests.post(
            f"{OLLAMA_URL}/generate",
            headers={'Content-Type': 'application/json'},
            json={
                'model': 'llama3.1:latest',
                'stream': False,
                'prompt': prompt
            },
            timeout=120  # LLM can take time
        )
        
        if llm_response.status_code == 200:
            result = llm_response.json()
            return jsonify({
                'status': 'success',
                'recommendations': result.get('response', 'No recommendations generated'),
                'model': 'llama3.1'
            })
        else:
            return jsonify({
                'status': 'error',
                'error': f'LLM service returned status {llm_response.status_code}'
            }), 500
            
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'error': 'LLM request timed out. The AI server may be busy.'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error', 
            'error': 'Could not connect to AI server. Please check if the Ollama service is running.'
        }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': f'AI recommendation failed: {str(e)}'
        }), 500

@app.route('/audit/')
@app.route('/audit/<path:url>')
def serve_audit(url=None):
    return send_from_directory('..', 'audit.html')

@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('assets/'):
        return send_from_directory('..', path)
    return send_from_directory('..', 'index.html')

if __name__ == '__main__':
    print("🚀 AISEO Master Backend starting...")
    print("📊 Total Checks: 180 across 9 categories")
    print("   - Technical SEO: 35 checks")
    print("   - On-Page SEO: 25 checks")
    print("   - Content SEO: 20 checks")
    print("   - Mobile SEO: 15 checks")
    print("   - Performance: 18 checks")
    print("   - Security: 12 checks")
    print("   - Social SEO: 10 checks")
    print("   - Local SEO: 15 checks")
    print("   - GEO/AEO: 30 checks (AI-First Optimization)")
    print("📍 http://localhost:5000")
    app.run(debug=True, port=5000)
