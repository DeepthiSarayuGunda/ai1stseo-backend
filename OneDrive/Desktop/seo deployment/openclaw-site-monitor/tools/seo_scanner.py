"""
SEO Scanner Tool for OpenClaw
Comprehensive 216+ SEO checks across 9 categories
Combines quick monitoring scan with deep analysis from main backend
Based on SEMrush, Moz, Ahrefs, and industry best practices
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
import time
import json
from typing import TypedDict


class ScanResult(TypedDict):
    url: str
    score: int
    critical_issues: list[str]
    warnings: list[str]
    recommendations: list[dict]
    load_time: float
    timestamp: str


class DetailedScanResult(TypedDict):
    url: str
    score: int
    critical_issues: list[str]
    warnings: list[str]
    recommendations: list[dict]
    load_time: float
    timestamp: str
    categories: dict
    totalChecks: int
    totalPassed: int
    overallScore: float


# ============== HELPER FUNCTIONS ==============

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

    canonical_href = canonical.get('href', '') if canonical else ''
    is_self_canonical = url in canonical_href or canonical_href in url
    add_check(checks, 'Self-Referencing Canonical', 'pass' if is_self_canonical or not canonical else 'warning',
              'Canonical points to self', 'Yes' if is_self_canonical else 'No',
              'Use self-referencing canonical', 'Medium', 'Crawlability')

    hreflang = soup.find_all('link', {'hreflang': True})
    add_check(checks, 'Hreflang Tags', 'pass' if hreflang else 'info',
              'International targeting', f'{len(hreflang)} tags', 'Add for multi-language sites', 'Medium', 'Crawlability')

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

    params = parsed.query
    param_count = len(params.split('&')) if params else 0
    add_check(checks, 'URL Parameters', 'pass' if param_count <= 2 else 'warning',
              'Query parameters', f'{param_count} parameters', 'Minimize URL parameters', 'Medium', 'URL Structure')

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

    empty_links = [l for l in all_links if not l.get('href', '').strip() or l.get('href', '') == '#']
    add_check(checks, 'Valid Link Hrefs', 'pass' if len(empty_links) < 3 else 'warning',
              'Empty/placeholder links', f'{len(empty_links)} found', 'Fix empty href attributes', 'Medium', 'Internal Linking')

    nofollow_internal = [l for l in internal if 'nofollow' in str(l.get('rel', []))]
    add_check(checks, 'Internal Nofollow', 'pass' if not nofollow_internal else 'warning',
              'Nofollow on internal links', f'{len(nofollow_internal)} found', 'Remove nofollow from internal links', 'Medium', 'Internal Linking')

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

    webp_imgs = [i for i in images if '.webp' in str(i.get('src', ''))]
    add_check(checks, 'Modern Image Formats', 'pass' if webp_imgs or not images else 'info',
              'WebP images', f'{len(webp_imgs)} WebP', 'Consider WebP format', 'Low', 'Images')

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

    sentences = re.split(r'[.!?]+', text)
    sent_count = len([s for s in sentences if len(s.split()) > 3])
    avg_sentence_len = word_count / sent_count if sent_count else 0
    add_check(checks, 'Sentence Length', 'pass' if 10 <= avg_sentence_len <= 20 else 'warning',
              'Average sentence length', f'{avg_sentence_len:.1f} words', 'Aim for 15-20 words per sentence', 'Medium', 'Content Quality')

    unique_words = len(set(w.lower() for w in words if len(w) > 3))
    ratio = unique_words / word_count if word_count else 0
    add_check(checks, 'Vocabulary Diversity', 'pass' if ratio > 0.3 else 'warning',
              'Unique words ratio', f'{ratio*100:.0f}% unique', 'Use varied vocabulary', 'Low', 'Content Quality')

    questions = text.count('?')
    add_check(checks, 'Engaging Questions', 'pass' if questions >= 1 else 'info',
              'Questions in content', f'{questions} questions', 'Include questions for engagement', 'Low', 'Content Quality')

    numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?%?\b', text)
    add_check(checks, 'Data & Statistics', 'pass' if len(numbers) >= 3 else 'info',
              'Numerical data', f'{len(numbers)} data points', 'Include statistics for credibility', 'Medium', 'Content Quality')

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

    nofollow_ext = [l for l in external if 'nofollow' in str(l.get('rel', []))]
    add_check(checks, 'External Nofollow', 'info',
              'Nofollow external links', f'{len(nofollow_ext)}/{len(external)}', 'Consider nofollow for untrusted links', 'Low', 'Linking')

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

    about_link = soup.find('a', href=re.compile(r'about|contact|team', re.I))
    add_check(checks, 'Trust Pages Linked', 'pass' if about_link else 'info',
              'About/Contact links', 'Found' if about_link else 'Not found', 'Link to About/Contact pages', 'Medium', 'E-E-A-T')

    citations = any(p in text.lower() for p in ['according to', 'source:', 'study shows', 'research', 'cited'])
    add_check(checks, 'Source Citations', 'pass' if citations else 'info',
              'Citations present', 'Found' if citations else 'Not found', 'Cite authoritative sources', 'Medium', 'E-E-A-T')

    expertise = any(p in text.lower() for p in ['years of experience', 'certified', 'expert', 'professional', 'specialist'])
    add_check(checks, 'Expertise Signals', 'pass' if expertise else 'info',
              'Expertise indicators', 'Found' if expertise else 'Not found', 'Demonstrate expertise', 'Medium', 'E-E-A-T')

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

    no_scale = 'user-scalable=no' in viewport_content or 'maximum-scale=1' in viewport_content
    add_check(checks, 'Zoom Enabled', 'pass' if not no_scale else 'warning',
              'User can zoom', 'Yes' if not no_scale else 'Disabled', 'Allow user zooming for accessibility', 'Medium', 'Viewport')

    media_queries = '@media' in html
    add_check(checks, 'Media Queries', 'pass' if media_queries else 'warning',
              'Responsive CSS', 'Found' if media_queries else 'Not found', 'Use CSS media queries', 'High', 'Responsiveness')

    # 6-10: Touch & Mobile UX
    buttons = soup.find_all(['button', 'a'])
    small_targets = [b for b in buttons if b.get('style') and ('font-size: 1' in b.get('style', '') or 'padding: 0' in b.get('style', ''))]
    add_check(checks, 'Touch Targets', 'pass' if len(small_targets) < len(buttons) * 0.1 else 'warning',
              'Touch-friendly buttons', f'{len(buttons) - len(small_targets)}/{len(buttons)}', 'Use 48px minimum touch targets', 'Medium', 'Touch UX')

    flash = soup.find_all(['object', 'embed'])
    flash_content = [f for f in flash if 'flash' in str(f).lower() or 'swf' in str(f).lower()]
    add_check(checks, 'No Flash Content', 'pass' if not flash_content else 'fail',
              'Flash elements', f'{len(flash_content)} found', 'Remove Flash content', 'Critical', 'Mobile Compatibility')

    frames = soup.find_all(['frame', 'frameset'])
    add_check(checks, 'No Frames', 'pass' if not frames else 'fail',
              'Frame elements', f'{len(frames)} found', 'Remove frames', 'High', 'Mobile Compatibility')

    fixed_width = re.findall(r'width:\s*\d{4,}px', html)
    add_check(checks, 'No Fixed Width', 'pass' if not fixed_width else 'warning',
              'Fixed width elements', f'{len(fixed_width)} found', 'Use responsive widths', 'Medium', 'Responsiveness')

    small_fonts = re.findall(r'font-size:\s*[0-9]px', html)
    add_check(checks, 'Readable Font Size', 'pass' if len(small_fonts) < 3 else 'warning',
              'Small fonts', f'{len(small_fonts)} found', 'Use 16px+ base font size', 'Medium', 'Readability')

    # 11-15: Mobile Performance
    images = soup.find_all('img')
    lazy_imgs = [i for i in images if i.get('loading') == 'lazy']
    add_check(checks, 'Image Lazy Loading', 'pass' if lazy_imgs or len(images) <= 3 else 'warning',
              'Lazy loaded', f'{len(lazy_imgs)}/{len(images)}', 'Add loading="lazy" for mobile', 'High', 'Mobile Performance')

    html_size = len(response.content) / 1024
    add_check(checks, 'Page Weight', 'pass' if html_size < 100 else 'warning',
              'HTML size', f'{html_size:.1f} KB', 'Keep HTML under 100KB', 'Medium', 'Mobile Performance')

    amp_link = soup.find('link', rel='amphtml')
    add_check(checks, 'AMP Version', 'info',
              'AMP available', 'Yes' if amp_link else 'No', 'Consider AMP for mobile', 'Low', 'Mobile Performance')

    app_links = soup.find_all('meta', property=re.compile(r'al:(ios|android)'))
    add_check(checks, 'App Deep Links', 'info',
              'App links', f'{len(app_links)} found', 'Add app deep links if applicable', 'Low', 'Mobile Integration')

    tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
    add_check(checks, 'Click-to-Call', 'pass' if tel_links else 'info',
              'Phone links', f'{len(tel_links)} found', 'Add click-to-call for mobile', 'Medium', 'Mobile Integration')

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

    images = soup.find_all('img')
    imgs_dims = [i for i in images if i.get('width') and i.get('height')]
    cls_risk = len(images) - len(imgs_dims)
    add_check(checks, 'CLS Prevention', 'pass' if cls_risk == 0 or not images else 'warning',
              'Images with dimensions', f'{len(imgs_dims)}/{len(images)}', 'Add width/height to prevent layout shift', 'High', 'Core Web Vitals')

    preload = soup.find_all('link', rel='preload')
    add_check(checks, 'LCP Optimization', 'pass' if preload else 'info',
              'Preload hints', f'{len(preload)} preloads', 'Preload LCP element', 'High', 'Core Web Vitals')

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

    if parsed.scheme == 'https':
        http_links = soup.find_all(href=re.compile(r'^http://'))
        http_src = soup.find_all(src=re.compile(r'^http://'))
        mixed_content = len(http_links) + len(http_src)
        add_check(checks, 'No Mixed Content', 'pass' if mixed_content == 0 else 'warning',
                  'Mixed content', f'{mixed_content} insecure resources', 'Fix mixed content issues', 'High', 'HTTPS')
    else:
        add_check(checks, 'No Mixed Content', 'fail', 'Mixed content', 'Site not on HTTPS', 'Enable HTTPS first', 'High', 'HTTPS')

    cookies = response.headers.get('Set-Cookie', '')
    secure_cookie = 'Secure' in cookies if cookies else True
    add_check(checks, 'Secure Cookies', 'pass' if secure_cookie else 'warning',
              'Cookie security', 'Secure flag set' if secure_cookie else 'Missing Secure flag', 'Add Secure flag to cookies', 'Medium', 'HTTPS')

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

    password_fields = soup.find_all('input', {'type': 'password'})
    add_check(checks, 'Secure Login Forms', 'pass' if not password_fields or parsed.scheme == 'https' else 'fail',
              'Password fields on HTTPS', f'{len(password_fields)} fields', 'Use HTTPS for login pages', 'Critical', 'Forms')

    external_scripts = soup.find_all('script', src=re.compile(r'^https?://'))
    trusted_domains = ['google', 'facebook', 'twitter', 'cloudflare', 'jquery', 'bootstrap', 'cdn']
    untrusted = [s for s in external_scripts if not any(t in str(s.get('src', '')) for t in trusted_domains)]
    add_check(checks, 'Trusted Scripts', 'pass' if len(untrusted) < 3 else 'warning',
              'External scripts', f'{len(untrusted)} from unknown sources', 'Review external script sources', 'Medium', 'Scripts')

    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== SOCIAL SEO (25 checks) ==============
def analyze_social_seo(url, soup, response, load_time):
    checks = []
    html = str(soup)
    parsed = urlparse(url)

    # 1-10: Open Graph
    og_title = soup.find('meta', property='og:title')
    og_title_content = og_title.get('content', '') if og_title else ''
    add_check(checks, 'OG Title', 'pass' if og_title else 'fail',
              'Open Graph title', og_title_content[:50] or 'Missing',
              'Add og:title for social sharing', 'Critical', 'Open Graph')

    add_check(checks, 'OG Title Length', 'pass' if 40 <= len(og_title_content) <= 60 else 'warning',
              'Title character count', f'{len(og_title_content)} chars',
              'Optimize to 40-60 characters', 'Medium', 'Open Graph')

    og_desc = soup.find('meta', property='og:description')
    og_desc_content = og_desc.get('content', '') if og_desc else ''
    add_check(checks, 'OG Description', 'pass' if og_desc else 'fail',
              'Open Graph description', 'Set' if og_desc else 'Missing',
              'Add og:description for social previews', 'Critical', 'Open Graph')

    add_check(checks, 'OG Description Length', 'pass' if 100 <= len(og_desc_content) <= 200 else 'warning',
              'Description length', f'{len(og_desc_content)} chars',
              'Optimize to 100-200 characters', 'Medium', 'Open Graph')

    og_image = soup.find('meta', property='og:image')
    og_image_url = og_image.get('content', '') if og_image else ''
    add_check(checks, 'OG Image', 'pass' if og_image else 'fail',
              'Open Graph image', 'Set' if og_image else 'Missing',
              'Add og:image (1200x630px recommended)', 'Critical', 'Open Graph')

    og_image_absolute = og_image_url.startswith('http') if og_image_url else False
    add_check(checks, 'OG Image Absolute URL', 'pass' if og_image_absolute or not og_image else 'warning',
              'Image URL format', 'Absolute' if og_image_absolute else 'Relative/Missing',
              'Use absolute URL for og:image', 'High', 'Open Graph')

    og_url = soup.find('meta', property='og:url')
    add_check(checks, 'OG URL', 'pass' if og_url else 'warning',
              'Canonical social URL', 'Set' if og_url else 'Not set',
              'Add og:url to prevent duplicate share tracking', 'Medium', 'Open Graph')

    og_type = soup.find('meta', property='og:type')
    og_type_content = og_type.get('content', '') if og_type else ''
    valid_types = ['website', 'article', 'product', 'profile', 'video.other', 'music.song']
    add_check(checks, 'OG Type', 'pass' if og_type_content in valid_types else ('warning' if og_type else 'info'),
              'Content type', og_type_content or 'Not set',
              'Set og:type for rich previews', 'Medium', 'Open Graph')

    og_site_name = soup.find('meta', property='og:site_name')
    add_check(checks, 'OG Site Name', 'pass' if og_site_name else 'info',
              'Brand name in shares', og_site_name.get('content', '')[:30] if og_site_name else 'Not set',
              'Add og:site_name for brand visibility', 'Low', 'Open Graph')

    og_locale = soup.find('meta', property='og:locale')
    add_check(checks, 'OG Locale', 'pass' if og_locale else 'info',
              'Language/region', og_locale.get('content', '') if og_locale else 'Not set',
              'Add og:locale for international targeting', 'Low', 'Open Graph')

    # 11-15: Twitter/X Cards
    twitter_card = soup.find('meta', attrs={'name': 'twitter:card'})
    twitter_card_type = twitter_card.get('content', '') if twitter_card else ''
    valid_cards = ['summary', 'summary_large_image', 'player', 'app']
    add_check(checks, 'Twitter Card Type', 'pass' if twitter_card_type in valid_cards else 'warning',
              'Card format', twitter_card_type or 'Not set',
              'Add twitter:card (use summary_large_image for best engagement)', 'High', 'Twitter/X')

    twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
    add_check(checks, 'Twitter Title', 'pass' if twitter_title or og_title else 'warning',
              'X/Twitter title', 'Set' if twitter_title else ('Falls back to OG' if og_title else 'Missing'),
              'Add twitter:title or ensure og:title exists', 'Medium', 'Twitter/X')

    twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
    add_check(checks, 'Twitter Description', 'pass' if twitter_desc or og_desc else 'warning',
              'X/Twitter description', 'Set' if twitter_desc else ('Falls back to OG' if og_desc else 'Missing'),
              'Add twitter:description for custom X previews', 'Medium', 'Twitter/X')

    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
    add_check(checks, 'Twitter Image', 'pass' if twitter_image or og_image else 'warning',
              'X/Twitter image', 'Set' if twitter_image else ('Falls back to OG' if og_image else 'Missing'),
              'Add twitter:image (1200x675px for summary_large_image)', 'High', 'Twitter/X')

    twitter_site = soup.find('meta', attrs={'name': 'twitter:site'})
    add_check(checks, 'Twitter Site Handle', 'pass' if twitter_site else 'info',
              'Brand X handle', twitter_site.get('content', '') if twitter_site else 'Not set',
              'Add twitter:site (@handle) for brand attribution', 'Low', 'Twitter/X')

    # 16-18: LinkedIn
    article_author = soup.find('meta', property='article:author')
    add_check(checks, 'Article Author', 'pass' if article_author else 'info',
              'Content author', 'Set' if article_author else 'Not set',
              'Add article:author for LinkedIn attribution', 'Low', 'LinkedIn')

    article_published = soup.find('meta', property='article:published_time')
    add_check(checks, 'Article Published Time', 'pass' if article_published else 'info',
              'Publish date', 'Set' if article_published else 'Not set',
              'Add article:published_time for freshness signals', 'Low', 'LinkedIn')

    add_check(checks, 'LinkedIn Image Optimization', 'pass' if og_image else 'warning',
              'LinkedIn preview image', 'OG image set' if og_image else 'Missing',
              'Use 1200x627px image for optimal LinkedIn display', 'Medium', 'LinkedIn')

    # 19-21: Social Schema
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    has_sameas = any('sameAs' in str(j) for j in json_ld)
    add_check(checks, 'SameAs Schema', 'pass' if has_sameas else 'warning',
              'Social profile schema', 'Found' if has_sameas else 'Not found',
              'Add sameAs schema linking to social profiles', 'High', 'Social Schema')

    has_org_social = any('"@type"' in str(j) and ('Organization' in str(j) or 'Person' in str(j)) for j in json_ld)
    add_check(checks, 'Organization Social Schema', 'pass' if has_org_social else 'info',
              'Entity social markup', 'Found' if has_org_social else 'Not found',
              'Add Organization schema with sameAs for AI entity recognition', 'Medium', 'Social Schema')

    # 22-25: Social Integration & Engagement
    social_platforms = {
        'facebook': r'facebook\.com', 'twitter': r'twitter\.com|x\.com',
        'linkedin': r'linkedin\.com', 'instagram': r'instagram\.com',
        'youtube': r'youtube\.com', 'tiktok': r'tiktok\.com', 'pinterest': r'pinterest\.com'
    }
    social_links = []
    for platform, pattern in social_platforms.items():
        links = soup.find_all('a', href=re.compile(pattern, re.I))
        if links:
            social_links.extend([(platform, l) for l in links])
    platforms_found = list(set([s[0] for s in social_links]))
    add_check(checks, 'Social Profile Links', 'pass' if len(platforms_found) >= 3 else ('warning' if platforms_found else 'info'),
              'Linked platforms', f'{len(platforms_found)} platforms: {", ".join(platforms_found[:4])}' if platforms_found else 'None found',
              'Link to at least 3 social profiles', 'Medium', 'Social Integration')

    share_patterns = ['share', 'social-share', 'sharing', 'addthis', 'sharethis', 'shareaholic']
    share_buttons = soup.find_all(class_=re.compile('|'.join(share_patterns), re.I))
    share_links = soup.find_all('a', href=re.compile(r'share|intent/tweet|sharer\.php', re.I))
    total_share = len(share_buttons) + len(share_links)
    add_check(checks, 'Share Buttons', 'pass' if total_share > 0 else 'info',
              'Social sharing', f'{total_share} share elements found',
              'Add share buttons to increase content distribution', 'Medium', 'Social Integration')

    social_proof = any(term in html.lower() for term in ['followers', 'likes', 'shares', 'social proof', 'follow us'])
    add_check(checks, 'Social Proof Signals', 'pass' if social_proof else 'info',
              'Social credibility', 'Found' if social_proof else 'Not found',
              'Display follower counts or social proof', 'Low', 'Social Integration')

    whatsapp_link = soup.find('a', href=re.compile(r'wa\.me|whatsapp|api\.whatsapp', re.I))
    add_check(checks, 'WhatsApp Integration', 'pass' if whatsapp_link else 'info',
              'Messaging share', 'Found' if whatsapp_link else 'Not found',
              'Add WhatsApp share/contact for mobile engagement', 'Low', 'Social Integration')

    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== LOCAL SEO (35 checks) ==============
def analyze_local_seo(url, soup, response, load_time):
    checks = []
    text = soup.get_text()
    html = str(soup)
    parsed = urlparse(url)

    # 1-8: NAP (Name, Address, Phone)
    phone_patterns = [
        r'\b(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b',
        r'\b(\d{3}[-.\s]?\d{4})\b',
        r'\b(\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9})\b'
    ]
    phone_found = any(re.search(p, text) for p in phone_patterns)
    add_check(checks, 'Phone Number Visible', 'pass' if phone_found else 'warning',
              'Phone displayed on page', 'Found' if phone_found else 'Not found',
              'Display phone number prominently for local trust', 'High', 'NAP')

    tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
    add_check(checks, 'Click-to-Call Links', 'pass' if tel_links else 'warning',
              'Tel: links for mobile', f'{len(tel_links)} found',
              'Add tel: links - 88% of local mobile searches lead to calls', 'Critical', 'NAP')

    address_patterns = [
        r'\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct|place|pl)\b',
        r'\b(?:suite|ste|unit|apt|#)\s*\d+\b',
        r'\b[A-Z][a-z]+,\s*[A-Z]{2}\s+\d{5}\b'
    ]
    address_found = any(re.search(p, text, re.I) for p in address_patterns)
    add_check(checks, 'Physical Address', 'pass' if address_found else 'info',
              'Street address displayed', 'Found' if address_found else 'Not found',
              'Display full address for local businesses', 'High', 'NAP')

    zip_pattern = re.search(r'\b\d{5}(?:-\d{4})?\b|\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b', text)
    add_check(checks, 'ZIP/Postal Code', 'pass' if zip_pattern else 'info',
              'Postal code visible', 'Found' if zip_pattern else 'Not found',
              'Include ZIP code for geo-targeting', 'Medium', 'NAP')

    email_pattern = re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', text)
    add_check(checks, 'Contact Email', 'pass' if email_pattern else 'info',
              'Email displayed', 'Found' if email_pattern else 'Not found',
              'Display contact email for trust signals', 'Medium', 'NAP')

    mailto_links = soup.find_all('a', href=re.compile(r'^mailto:'))
    add_check(checks, 'Click-to-Email Links', 'pass' if mailto_links else 'info',
              'Mailto: links', f'{len(mailto_links)} found',
              'Add mailto: links for easy contact', 'Low', 'NAP')

    footer = soup.find('footer') or soup.find(class_=re.compile(r'footer', re.I))
    footer_text = footer.get_text() if footer else ''
    nap_in_footer = phone_found and (re.search(r'\b\d+\s+\w+', footer_text) if footer_text else False)
    add_check(checks, 'NAP in Footer', 'pass' if nap_in_footer else 'info',
              'Contact info in footer', 'Found' if nap_in_footer else 'Not found',
              'Place NAP in footer for site-wide consistency', 'Medium', 'NAP')

    hours_patterns = ['hours', 'open', 'closed', 'monday', 'tuesday', 'am', 'pm', '24/7', '24 hours']
    has_hours = any(term in text.lower() for term in hours_patterns)
    add_check(checks, 'Business Hours', 'pass' if has_hours else 'info',
              'Operating hours displayed', 'Found' if has_hours else 'Not found',
              'Display business hours for local search intent', 'High', 'NAP')

    # 9-17: LocalBusiness Schema
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    json_ld_content = ' '.join([str(j) for j in json_ld])

    local_schema_types = ['LocalBusiness', 'Store', 'Restaurant', 'Hotel', 'MedicalBusiness',
                          'LegalService', 'FinancialService', 'RealEstateAgent', 'AutoDealer',
                          'HomeAndConstructionBusiness', 'SportsActivityLocation']
    has_local_schema = any(t in json_ld_content for t in local_schema_types)
    add_check(checks, 'LocalBusiness Schema', 'pass' if has_local_schema else 'fail',
              'Local business markup', 'Found' if has_local_schema else 'Missing',
              'Add LocalBusiness schema - top ranking factor for Map Pack', 'Critical', 'Schema')

    has_org_schema = 'Organization' in json_ld_content or 'Corporation' in json_ld_content
    add_check(checks, 'Organization Schema', 'pass' if has_org_schema or has_local_schema else 'warning',
              'Organization markup', 'Found' if has_org_schema else 'Not found',
              'Add Organization schema for entity recognition', 'High', 'Schema')

    has_address_schema = 'PostalAddress' in json_ld_content or 'address' in json_ld_content
    add_check(checks, 'Address Schema', 'pass' if has_address_schema else 'warning',
              'Structured address', 'Found' if has_address_schema else 'Not found',
              'Add PostalAddress schema for NAP consistency', 'High', 'Schema')

    has_geo = 'GeoCoordinates' in json_ld_content or '"latitude"' in json_ld_content or '"geo"' in json_ld_content
    add_check(checks, 'GeoCoordinates Schema', 'pass' if has_geo else 'warning',
              'Location coordinates', 'Found' if has_geo else 'Not found',
              'Add geo coordinates for precise map placement', 'High', 'Schema')

    has_hours_schema = 'openingHours' in json_ld_content or 'OpeningHoursSpecification' in json_ld_content
    add_check(checks, 'Opening Hours Schema', 'pass' if has_hours_schema else 'info',
              'Hours in schema', 'Found' if has_hours_schema else 'Not found',
              'Add openingHours schema for rich results', 'Medium', 'Schema')

    has_contact_schema = 'ContactPoint' in json_ld_content or 'contactPoint' in json_ld_content
    add_check(checks, 'ContactPoint Schema', 'pass' if has_contact_schema else 'info',
              'Contact schema', 'Found' if has_contact_schema else 'Not found',
              'Add ContactPoint schema with phone/email', 'Medium', 'Schema')

    has_price_range = 'priceRange' in json_ld_content
    add_check(checks, 'Price Range Schema', 'pass' if has_price_range else 'info',
              'Price indicator', 'Found' if has_price_range else 'Not found',
              'Add priceRange for search filters', 'Low', 'Schema')

    has_rating_schema = 'AggregateRating' in json_ld_content or 'aggregateRating' in json_ld_content
    add_check(checks, 'Rating Schema', 'pass' if has_rating_schema else 'info',
              'Review rating markup', 'Found' if has_rating_schema else 'Not found',
              'Add AggregateRating schema for star ratings in search', 'High', 'Schema')

    # 18-24: Local Signals & Trust
    maps_embed = soup.find('iframe', src=re.compile(r'google.*maps|maps\.google', re.I))
    add_check(checks, 'Google Maps Embed', 'pass' if maps_embed else 'info',
              'Map embedded', 'Found' if maps_embed else 'Not found',
              'Embed Google Maps for location verification', 'Medium', 'Local Signals')

    directions = soup.find('a', href=re.compile(r'maps\.google|google.*maps.*dir|directions', re.I))
    add_check(checks, 'Get Directions Link', 'pass' if directions else 'info',
              'Directions link', 'Found' if directions else 'Not found',
              'Add "Get Directions" link', 'Low', 'Local Signals')

    service_area_terms = ['serving', 'service area', 'we serve', 'locations', 'coverage area',
                          'available in', 'servicing', 'proudly serving']
    has_service_area = any(term in text.lower() for term in service_area_terms)
    add_check(checks, 'Service Area Mentions', 'pass' if has_service_area else 'info',
              'Service coverage', 'Found' if has_service_area else 'Not found',
              'Mention service areas/cities for geo-relevance', 'Medium', 'Local Signals')

    local_terms = ['near me', 'local', 'nearby', 'in your area', 'neighborhood', 'community']
    has_local_terms = any(term in text.lower() for term in local_terms)
    add_check(checks, 'Local Keywords', 'pass' if has_local_terms else 'info',
              'Local terms used', 'Found' if has_local_terms else 'Not found',
              'Include local/geo keywords naturally', 'Medium', 'Local Signals')

    review_terms = ['review', 'testimonial', 'rating', 'stars', 'customer feedback', 'what our customers say']
    has_reviews = any(term in html.lower() for term in review_terms)
    add_check(checks, 'Reviews Section', 'pass' if has_reviews else 'warning',
              'Customer reviews', 'Found' if has_reviews else 'Not found',
              'Display reviews - 4.5+ stars get 94% more clicks', 'High', 'Local Signals')

    trust_terms = ['certified', 'licensed', 'insured', 'bonded', 'accredited', 'bbb', 'member of',
                   'association', 'award', 'years in business', 'established', 'since']
    has_trust = any(term in text.lower() for term in trust_terms)
    add_check(checks, 'Trust Signals', 'pass' if has_trust else 'info',
              'Credibility indicators', 'Found' if has_trust else 'Not found',
              'Display certifications, awards, years in business', 'Medium', 'Local Signals')

    community_terms = ['community', 'local event', 'sponsor', 'charity', 'give back', 'neighborhood']
    has_community = any(term in text.lower() for term in community_terms)
    add_check(checks, 'Community Involvement', 'pass' if has_community else 'info',
              'Local engagement', 'Found' if has_community else 'Not found',
              'Mention community involvement for local authority', 'Low', 'Local Signals')

    # 25-30: Citation & Directory Signals
    directory_patterns = ['yelp.com', 'yellowpages', 'bbb.org', 'angieslist', 'homeadvisor',
                          'thumbtack', 'houzz', 'tripadvisor', 'healthgrades', 'avvo']
    directory_links = soup.find_all('a', href=re.compile('|'.join(directory_patterns), re.I))
    add_check(checks, 'Directory Profile Links', 'pass' if directory_links else 'info',
              'Citation links', f'{len(directory_links)} found',
              'Link to your profiles on major directories', 'Low', 'Citations')

    platform_mentions = ['google reviews', 'yelp', 'facebook reviews', 'trustpilot', 'g2']
    has_platform_proof = any(term in text.lower() for term in platform_mentions)
    add_check(checks, 'Review Platform Mentions', 'pass' if has_platform_proof else 'info',
              'Platform social proof', 'Found' if has_platform_proof else 'Not found',
              'Reference reviews from Google, Yelp, etc.', 'Medium', 'Citations')

    # 31-35: AI/Voice Search Local Optimization
    faq_patterns = ['faq', 'frequently asked', 'common questions', 'q&a', 'questions']
    has_faq = any(term in text.lower() for term in faq_patterns) or 'FAQPage' in json_ld_content
    add_check(checks, 'Local FAQ Content', 'pass' if has_faq else 'info',
              'FAQ section', 'Found' if has_faq else 'Not found',
              'Add FAQ for voice search queries', 'Medium', 'AI/Voice')

    question_words = text.lower().count('where') + text.lower().count('when') + text.lower().count('how to get')
    add_check(checks, 'Conversational Content', 'pass' if question_words >= 2 else 'info',
              'Question-based content', f'{question_words} question phrases',
              'Include conversational phrases for AI/voice search', 'Medium', 'AI/Voice')

    has_sameas = 'sameAs' in json_ld_content
    add_check(checks, 'SameAs Local Links', 'pass' if has_sameas else 'warning',
              'Entity connections', 'Found' if has_sameas else 'Not found',
              'Add sameAs linking to GBP, directories for AI entity recognition', 'High', 'AI/Voice')

    has_area_served = 'areaServed' in json_ld_content or 'serviceArea' in json_ld_content
    add_check(checks, 'Area Served Schema', 'pass' if has_area_served else 'info',
              'Service area markup', 'Found' if has_area_served else 'Not found',
              'Add areaServed schema for service-area businesses', 'Medium', 'AI/Voice')

    viewport = soup.find('meta', attrs={'name': 'viewport'})
    add_check(checks, 'Mobile-First Local', 'pass' if viewport else 'fail',
              'Mobile optimization', 'Viewport set' if viewport else 'Missing',
              'Mobile-first is critical - 76% of local searches are mobile', 'Critical', 'AI/Voice')

    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== GEO/AEO (60 checks) - AI Search Optimization ==============
def analyze_geo_aeo(url, soup, response, load_time):
    checks = []
    html = str(soup)
    text = soup.get_text()
    words = text.split()
    word_count = len(words)
    parsed = urlparse(url)

    # 1-6: Structured Data for AI Parsing
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

    entity_schemas = ['Person', 'Organization', 'Product', 'Place', 'Event', 'Article', 'WebPage']
    entities_found = [s for s in entity_schemas if s in html]
    add_check(checks, 'Entity Schema Markup', 'pass' if entities_found else 'warning',
              'Schema.org entities', ', '.join(entities_found) if entities_found else 'None found',
              'Add entity schemas (Person, Organization, Article)', 'High', 'AI Parsing')

    speakable = 'speakable' in html.lower()
    add_check(checks, 'Speakable Schema', 'pass' if speakable else 'info',
              'Voice assistant optimization', 'Present' if speakable else 'Not found',
              'Add Speakable schema for voice search', 'Medium', 'AI Parsing')

    sameas = 'sameAs' in html
    add_check(checks, 'Entity sameAs Links', 'pass' if sameas else 'info',
              'Entity disambiguation', 'Present' if sameas else 'Not found',
              'Add sameAs links to Wikipedia/social profiles', 'Medium', 'AI Parsing')

    # 7-12: Semantic HTML & Structure
    semantic_tags = soup.find_all(['article', 'section', 'aside', 'nav', 'header', 'footer', 'main'])
    add_check(checks, 'Semantic HTML5', 'pass' if len(semantic_tags) >= 3 else 'warning',
              'Semantic structure', f'{len(semantic_tags)} elements',
              'Use semantic HTML for AI comprehension', 'High', 'Semantic Structure')

    tables = soup.find_all('table')
    add_check(checks, 'Data Tables', 'pass' if tables else 'info',
              'Tabular data', f'{len(tables)} tables',
              'Use tables for structured comparisons', 'Medium', 'Semantic Structure')

    lists = soup.find_all(['ul', 'ol'])
    add_check(checks, 'Structured Lists', 'pass' if len(lists) >= 2 else 'warning',
              'Lists for AI extraction', f'{len(lists)} lists',
              'Use bullet/numbered lists for key points', 'High', 'Semantic Structure')

    figcaptions = soup.find_all('figcaption')
    add_check(checks, 'Figure Captions', 'pass' if figcaptions else 'info',
              'Image context for AI', f'{len(figcaptions)} captions',
              'Use figcaption for image descriptions', 'Medium', 'Semantic Structure')

    dl_tags = soup.find_all('dl')
    add_check(checks, 'Definition Lists', 'pass' if dl_tags else 'info',
              'Term definitions', f'{len(dl_tags)} definition lists',
              'Use <dl> for glossary/definitions', 'Low', 'Semantic Structure')

    blockquotes = soup.find_all('blockquote')
    add_check(checks, 'Blockquote Citations', 'pass' if blockquotes else 'info',
              'Quoted content', f'{len(blockquotes)} blockquotes',
              'Use blockquote for expert citations', 'Low', 'Semantic Structure')

    # 13-18: LLM Interpretability & Content
    questions = re.findall(r'(what|how|why|when|where|who|which|can|does|is|are)\s+[^.?]*\?', text.lower())
    add_check(checks, 'Q&A Patterns', 'pass' if len(questions) >= 2 else 'warning',
              'Question-answer format', f'{len(questions)} questions',
              'Include Q&A format for AI snippets', 'Critical', 'LLM Interpretability')

    definitions = re.findall(r'\b\w+\s+(?:is|are|means|refers to|defined as|is defined as)\s+[^.]+\.', text)
    add_check(checks, 'Direct Definitions', 'pass' if definitions else 'warning',
              'Clear definitions', f'{len(definitions)} found',
              'Provide direct "X is..." definitions', 'Critical', 'LLM Interpretability')

    paragraphs = soup.find_all('p')
    first_para = paragraphs[0].get_text() if paragraphs else ''
    has_answer_first = any(w in first_para.lower() for w in ['is', 'are', 'means', 'provides', 'helps', 'allows'])
    add_check(checks, 'Answer-First Writing', 'pass' if has_answer_first else 'warning',
              'Inverted pyramid style', 'Key info upfront' if has_answer_first else 'Buried lede',
              'Lead with the answer, not background', 'High', 'LLM Interpretability')

    sentences = re.split(r'[.!?]+', text)
    pronoun_heavy = sum(1 for s in sentences if s.lower().strip().startswith(('it ', 'this ', 'that ', 'they ')))
    pronoun_ratio = pronoun_heavy / len(sentences) if sentences else 0
    add_check(checks, 'Self-Contained Sentences', 'pass' if pronoun_ratio < 0.2 else 'warning',
              'Extractable sentences', f'{pronoun_ratio*100:.0f}% start with pronouns',
              'Avoid starting sentences with it/this/that', 'High', 'LLM Interpretability')

    complex_words = [w for w in words if len(w) > 12]
    complex_ratio = len(complex_words) / word_count if word_count else 0
    add_check(checks, 'Plain Language', 'pass' if complex_ratio < 0.05 else 'warning',
              'Accessible language', f'{complex_ratio*100:.1f}% complex words',
              'Use simple, clear language for AI', 'High', 'LLM Interpretability')

    conv_words = ['you', 'your', "you're", 'we', 'our', "we're"]
    conv_count = sum(text.lower().count(' ' + w + ' ') for w in conv_words)
    conv_ratio = conv_count / word_count if word_count else 0
    add_check(checks, 'Conversational Tone', 'pass' if conv_ratio > 0.005 else 'info',
              'Natural language style', f'{conv_ratio*100:.2f}%',
              'Use conversational you/we language', 'Medium', 'LLM Interpretability')

    # 19-24: Passage Ranking & Snippet Readiness
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    question_headings = [h for h in headings if '?' in h.get_text()]
    add_check(checks, 'Question Headings', 'pass' if question_headings else 'warning',
              'Prompt-aligned headings', f'{len(question_headings)} question headings',
              'Use questions as headings (What is X?)', 'Critical', 'Snippet Readiness')

    generic_headings = ['introduction', 'conclusion', 'overview', 'summary', 'more']
    descriptive_h = [h for h in headings if len(h.get_text().split()) >= 3 and h.get_text().lower().strip() not in generic_headings]
    add_check(checks, 'Descriptive Headings', 'pass' if len(descriptive_h) >= len(headings) * 0.5 else 'warning',
              'Context-rich headings', f'{len(descriptive_h)}/{len(headings)} descriptive',
              'Use specific, descriptive headings', 'High', 'Snippet Readiness')

    long_paras = [p for p in paragraphs if len(p.get_text().split()) > 100]
    add_check(checks, 'Concise Paragraphs', 'pass' if len(long_paras) <= 2 else 'warning',
              'Paragraph length', f'{len(long_paras)} paragraphs over 100 words',
              'Keep paragraphs under 100 words', 'High', 'Snippet Readiness')

    h2_count = len(soup.find_all('h2'))
    h3_count = len(soup.find_all('h3'))
    section_ratio = (h2_count + h3_count) / (word_count / 300) if word_count > 300 else 1
    add_check(checks, 'Section Granularity', 'pass' if section_ratio >= 0.8 else 'warning',
              'Heading density', f'{h2_count} H2s, {h3_count} H3s',
              'Add more subheadings for passage ranking', 'High', 'Snippet Readiness')

    steps = re.findall(r'step\s*\d|first,|second,|third,|finally,|next,|then,', text.lower())
    numbered_lists = soup.find_all('ol')
    add_check(checks, 'Step-by-Step Format', 'pass' if steps or numbered_lists else 'info',
              'Sequential instructions', f'{len(steps)} step indicators, {len(numbered_lists)} ordered lists',
              'Structure how-to content with numbered steps', 'Medium', 'Snippet Readiness')

    examples = ['for example', 'such as', 'e.g.', 'for instance', 'like this', 'including', 'specifically']
    example_count = sum(text.lower().count(e) for e in examples)
    add_check(checks, 'Concrete Examples', 'pass' if example_count >= 2 else 'info',
              'Specific examples', f'{example_count} example phrases',
              'Include specific examples for clarity', 'Medium', 'Snippet Readiness')

    # 25-30: Trust, Freshness & AI Optimization
    time_elements = soup.find_all('time')
    date_meta = soup.find('meta', property='article:modified_time') or soup.find('meta', property='article:published_time')
    add_check(checks, 'Content Timestamps', 'pass' if time_elements or date_meta else 'warning',
              'Freshness signals', f'{len(time_elements)} time elements',
              'Add visible publish/update dates', 'High', 'Trust & Freshness')

    last_modified = response.headers.get('Last-Modified', '')
    add_check(checks, 'Last-Modified Header', 'pass' if last_modified else 'info',
              'HTTP freshness', 'Set' if last_modified else 'Not set',
              'Set Last-Modified header for freshness', 'Medium', 'Trust & Freshness')

    author_patterns = soup.find_all(class_=re.compile(r'author|bio|byline|written-by', re.I))
    author_schema = 'author' in html.lower() and ('Person' in html or 'name' in html)
    add_check(checks, 'Author Attribution', 'pass' if author_patterns or author_schema else 'warning',
              'E-E-A-T author signals', 'Found' if author_patterns else 'Not found',
              'Add visible author name and bio', 'Critical', 'Trust & Freshness')

    citations = ['according to', 'source:', 'cited', 'reference', 'study shows', 'research', 'data from']
    has_citations = any(c in text.lower() for c in citations)
    external_links = [a for a in soup.find_all('a', href=True) if a['href'].startswith('http') and parsed.netloc not in a['href']]
    add_check(checks, 'Source Citations', 'pass' if has_citations or len(external_links) >= 2 else 'warning',
              'Factual citations', f'{len(external_links)} external links',
              'Cite authoritative sources with links', 'High', 'Trust & Freshness')

    llms_txt = safe_get(f"{parsed.scheme}://{parsed.netloc}/llms.txt")
    add_check(checks, 'LLMs.txt File', 'pass' if llms_txt and llms_txt.status_code == 200 else 'info',
              'AI crawler guidance', 'Found' if llms_txt and llms_txt.status_code == 200 else 'Not found',
              'Add llms.txt for AI crawler permissions', 'Low', 'AI Optimization')

    add_check(checks, 'AI-Friendly Length', 'pass' if 500 <= word_count <= 3000 else ('warning' if word_count < 300 else 'info'),
              'Content length', f'{word_count} words',
              'Aim for 500-3000 words for AI context windows', 'Medium', 'AI Optimization')

    # 31-37: AI Crawlability & Bot Permissions
    robots_resp = safe_get(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    robots_text = robots_resp.text if robots_resp and robots_resp.status_code == 200 else ''

    gptbot_blocked = 'user-agent: gptbot' in robots_text.lower() and 'disallow: /' in robots_text.lower()
    add_check(checks, 'GPTBot Access', 'pass' if robots_text and not gptbot_blocked else ('warning' if gptbot_blocked else 'info'),
              'OpenAI GPTBot crawler', 'Blocked' if gptbot_blocked else ('Allowed' if robots_text else 'No robots.txt'),
              'Review GPTBot access — blocking prevents AI Overview citations', 'High', 'AI Crawlability')

    google_ai_blocked = any(x in robots_text.lower() for x in ['user-agent: google-extended', 'user-agent: googleother'])
    google_ai_disallow = google_ai_blocked and 'disallow: /' in robots_text.lower()
    add_check(checks, 'Google AI Crawler', 'pass' if robots_text and not google_ai_disallow else ('warning' if google_ai_disallow else 'info'),
              'Google-Extended/GoogleOther', 'Blocked' if google_ai_disallow else ('Allowed' if robots_text else 'No robots.txt'),
              'Google-Extended controls AI training; blocking may reduce AI Overview visibility', 'High', 'AI Crawlability')

    claudebot_blocked = 'user-agent: claudebot' in robots_text.lower() or 'user-agent: anthropic' in robots_text.lower()
    add_check(checks, 'ClaudeBot Access', 'pass' if robots_text and not claudebot_blocked else ('warning' if claudebot_blocked else 'info'),
              'Anthropic ClaudeBot', 'Blocked' if claudebot_blocked else ('Allowed' if robots_text else 'No robots.txt'),
              'ClaudeBot crawls for Anthropic AI — allow for broader AI discoverability', 'Medium', 'AI Crawlability')

    llms_full = safe_get(f"{parsed.scheme}://{parsed.netloc}/llms-full.txt")
    add_check(checks, 'LLMs-Full.txt', 'pass' if llms_full and llms_full.status_code == 200 else 'info',
              'Extended AI content file', 'Found' if llms_full and llms_full.status_code == 200 else 'Not found',
              'Add llms-full.txt with detailed site content for LLM ingestion', 'Low', 'AI Crawlability')

    sitemap_resp = safe_get(f"{parsed.scheme}://{parsed.netloc}/sitemap.xml")
    add_check(checks, 'Sitemap for AI Discovery', 'pass' if sitemap_resp and sitemap_resp.status_code == 200 else 'warning',
              'XML sitemap accessible', 'Found' if sitemap_resp and sitemap_resp.status_code == 200 else 'Not found',
              'Sitemap helps AI crawlers discover and index all content', 'High', 'AI Crawlability')

    meta_robots = soup.find('meta', {'name': 'robots'})
    robots_content = meta_robots.get('content', '').lower() if meta_robots else ''
    noai_directives = any(d in robots_content for d in ['noai', 'noimageai', 'nosnippet'])
    add_check(checks, 'AI Meta Directives', 'pass' if not noai_directives else 'warning',
              'AI-restrictive meta tags', 'Restricted' if noai_directives else 'No restrictions',
              'noai/nosnippet meta tags prevent AI from using your content', 'High', 'AI Crawlability')

    # 38-42: Knowledge Graph & Entity Authority
    json_ld_text = ' '.join([j.string or '' for j in json_ld])
    has_main_entity = 'mainEntity' in json_ld_text or 'mainEntityOfPage' in json_ld_text
    add_check(checks, 'Main Entity Declaration', 'pass' if has_main_entity else 'warning',
              'mainEntityOfPage schema', 'Declared' if has_main_entity else 'Missing',
              'Add mainEntityOfPage to help AI identify the primary topic', 'High', 'Knowledge Graph')

    breadcrumb_schema = 'BreadcrumbList' in html
    add_check(checks, 'Breadcrumb Schema', 'pass' if breadcrumb_schema else 'info',
              'Navigation hierarchy for AI', 'Present' if breadcrumb_schema else 'Not found',
              'Add BreadcrumbList schema for AI content hierarchy', 'Medium', 'Knowledge Graph')

    comparison_terms = ['vs', 'versus', 'compared to', 'comparison', 'difference between', 'pros and cons', 'advantages', 'disadvantages']
    comparison_count = sum(text.lower().count(t) for t in comparison_terms)
    has_comparison_table = any(t for t in tables if any(ct in t.get_text().lower() for ct in ['vs', 'feature', 'comparison', 'pro', 'con']))
    add_check(checks, 'Comparison Content', 'pass' if comparison_count >= 2 or has_comparison_table else 'info',
              'Structured comparisons', f'{comparison_count} comparison phrases',
              'Add comparison tables — highly cited by AI answer engines', 'Medium', 'Knowledge Graph')

    content_types = 0
    if paragraphs: content_types += 1
    if lists: content_types += 1
    if tables: content_types += 1
    if blockquotes: content_types += 1
    if soup.find_all('code') or soup.find_all('pre'): content_types += 1
    if soup.find_all(['img', 'video', 'audio']): content_types += 1
    add_check(checks, 'Content Format Diversity', 'pass' if content_types >= 4 else ('warning' if content_types >= 2 else 'fail'),
              'Mixed content formats', f'{content_types}/6 types',
              'Use diverse formats — AI extracts from tables, lists, and code blocks more reliably', 'High', 'Knowledge Graph')

    internal_links = [a for a in soup.find_all('a', href=True) if parsed.netloc in urljoin(url, a.get('href', '')) and a.get_text().strip()]
    descriptive_internal = [a for a in internal_links if len(a.get_text().split()) >= 2]
    add_check(checks, 'Topic Cluster Links', 'pass' if len(descriptive_internal) >= 3 else 'warning',
              'Topical internal linking', f'{len(descriptive_internal)} descriptive internal links',
              'Build topic clusters with descriptive anchor text for AI entity mapping', 'High', 'Knowledge Graph')

    # 43-45: Publishing Readiness
    cite_elements = soup.find_all('cite')
    ref_links = [a for a in external_links if any(d in a.get('href', '') for d in ['.gov', '.edu', '.org', 'wikipedia', 'scholar.google'])]
    add_check(checks, 'Authority Citations', 'pass' if cite_elements or len(ref_links) >= 1 else 'warning',
              'Authoritative source references', f'{len(cite_elements)} cite tags, {len(ref_links)} authority links',
              'Link to .gov/.edu/.org sources — AI engines weight authoritative citations heavily', 'High', 'Knowledge Graph')

    wp_api_link = soup.find('link', rel='https://api.w.org/')
    wp_json_head = response.headers.get('Link', '')
    has_wp_api = wp_api_link is not None or 'api.w.org' in wp_json_head
    add_check(checks, 'CMS API Discoverability', 'pass' if has_wp_api else 'info',
              'REST API link header', 'WordPress API detected' if has_wp_api else 'No CMS API found',
              'CMS REST API enables automated content publishing and AEO workflows', 'Low', 'Publishing Readiness')

    has_article_schema = 'Article' in html or 'BlogPosting' in html or 'NewsArticle' in html
    add_check(checks, 'Article Schema', 'pass' if has_article_schema else 'warning',
              'Article/BlogPosting markup', 'Present' if has_article_schema else 'Missing',
              'Add Article schema with author, datePublished, dateModified', 'High', 'Publishing Readiness')

    has_excerpt = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    has_slug = len(parsed.path.strip('/').split('/')) >= 1 and parsed.path != '/'
    has_categories = soup.find(class_=re.compile(r'category|tag|topic', re.I)) or 'articleSection' in html
    pipeline_score = sum([bool(has_excerpt), bool(has_slug), bool(has_categories), bool(json_ld), bool(has_article_schema)])
    add_check(checks, 'AEO Pipeline Readiness', 'pass' if pipeline_score >= 4 else ('warning' if pipeline_score >= 2 else 'fail'),
              'Automated optimization signals', f'{pipeline_score}/5',
              'Ensure content has excerpt, clean slug, categories, and schema for AEO automation', 'High', 'Publishing Readiness')

    # 46-50: Prompt Visibility & AI Answer Readiness
    best_patterns = re.findall(r'\b(?:best|top|leading|recommended)\s+\d*\s*\w+', text.lower())
    has_listicle_format = bool(best_patterns) and len(lists) >= 1
    add_check(checks, 'Prompt-Aligned Listicle Content', 'pass' if has_listicle_format else 'info',
              'Best/top list patterns', '{} pattern(s){}'.format(len(best_patterns), ", with lists" if has_listicle_format else ""),
              'Add "best/top X" sections with ranked lists — #1 AI prompt archetype', 'High', 'Prompt Visibility')

    vs_patterns = re.findall(r'\b\w+\s+(?:vs\.?|versus|compared to|or)\s+\w+', text.lower())
    has_comparison_structure = bool(vs_patterns) or has_comparison_table
    add_check(checks, 'Comparison Query Readiness', 'pass' if has_comparison_structure else 'info',
              'X vs Y patterns', '{} pattern(s){}'.format(len(vs_patterns), ", table present" if has_comparison_table else ""),
              'Add comparison tables with side-by-side features/pricing — #2 AI prompt type', 'High', 'Prompt Visibility')

    howto_patterns = re.findall(r'\b(?:how to|step[- ]by[- ]step|guide to|tutorial)\b', text.lower())
    add_check(checks, 'How-To Query Readiness', 'pass' if len(howto_patterns) >= 2 else 'info',
              'Tutorial patterns', '{} how-to pattern(s)'.format(len(howto_patterns)),
              'Add step-by-step guides with numbered steps — #3 AI prompt type', 'Medium', 'Prompt Visibility')

    pricing_patterns = re.findall(r'\$\d+|\bpric(?:e|ing)\b|\bfree\b|\bcost\b|\bplan\b|\btier\b', text.lower())
    has_pricing_table = any(t for t in tables if any(p in t.get_text().lower() for p in ['price', 'cost', 'plan', 'free', 'month', 'year', '$']))
    add_check(checks, 'Pricing & Specs Transparency', 'pass' if len(pricing_patterns) >= 3 or has_pricing_table else 'info',
              'Pricing/cost signals', '{} signal(s){}'.format(len(pricing_patterns), ", pricing table" if has_pricing_table else ""),
              'Add pricing tables — AI heavily cites transparent pricing for commercial queries', 'Medium', 'Prompt Visibility')

    first_para_words = len(first_para.split()) if first_para else 0
    intro_is_concise = 20 <= first_para_words <= 60
    add_check(checks, 'AI Overview Intro Block', 'pass' if intro_is_concise and has_answer_first else 'warning',
              'Intro optimization', '{} words, {}'.format(first_para_words, "answer-first" if has_answer_first else "no answer-first"),
              'Write 20-60 word intro with answer upfront — highest-impact AI Overview pattern', 'Critical', 'Prompt Visibility')

    # 51-55: Citation Worthiness & Evidence Signals
    stat_patterns = re.findall(r'\d+(?:\.\d+)?%|\d+(?:,\d{3})+|\d+x\b', text)
    add_check(checks, 'Original Data & Statistics', 'pass' if len(stat_patterns) >= 3 else 'warning',
              'Data points', '{} statistic(s)'.format(len(stat_patterns)),
              'Include specific data/percentages — content with data is cited 2-3x more', 'High', 'Citation Worthiness')

    evidence_words = ['methodology', 'method', 'approach', 'framework', 'benchmark', 'measured', 'tested', 'analyzed', 'evaluated', 'results show', 'findings', 'data shows', 'evidence']
    evidence_count = sum(1 for w in evidence_words if w in text.lower())
    add_check(checks, 'Methodology & Evidence Language', 'pass' if evidence_count >= 3 else 'info',
              'Evidence signals', '{}/13 signal(s)'.format(evidence_count),
              'Use methodology language — "results show," "data indicates," "findings suggest"', 'Medium', 'Citation Worthiness')

    negation_claims = re.findall(r'\b(?:never|always|impossible|guaranteed|100%|every single)\b', text.lower())
    add_check(checks, 'Claim Consistency & Safety', 'pass' if len(negation_claims) <= 2 else 'warning',
              'Absolute claims', '{} absolute claim(s)'.format(len(negation_claims)),
              'Replace "always/never/guaranteed" with hedged language to reduce contradiction risk', 'Medium', 'Citation Worthiness')

    freshness_words = ['updated', 'latest', 'current', '2026', '2025', 'new', 'recently', 'this year', 'this month']
    freshness_count = sum(1 for w in freshness_words if w in text.lower())
    add_check(checks, 'Content Freshness Signals', 'pass' if freshness_count >= 2 else 'warning',
              'Freshness language', '{} signal(s)'.format(freshness_count),
              'Add "Updated [Month Year]" and current year references in visible content', 'High', 'Citation Worthiness')

    has_summary_section = bool(re.search(r'(?:summary|key takeaway|tl;?dr|in brief|bottom line|conclusion)', text.lower()))
    has_deep_content = word_count >= 800
    used_cited_score = sum([has_summary_section, has_deep_content, bool(json_ld), len(external_links) >= 2, bool(has_article_schema)])
    add_check(checks, 'Used-vs-Cited Readiness', 'pass' if used_cited_score >= 4 else ('warning' if used_cited_score >= 2 else 'fail'),
              'Source + citation potential', '{}/5 signals'.format(used_cited_score),
              'Add summary section + depth + schema to maximize both AI usage and explicit citation', 'High', 'Citation Worthiness')

    # 56-60: Brand Entity & Trust Stack
    org_schema = 'Organization' in html or 'Corporation' in html
    brand_mentions = text.lower().count(parsed.netloc.replace('www.', '').split('.')[0])
    add_check(checks, 'Brand Entity Definition', 'pass' if org_schema and brand_mentions >= 2 else 'warning',
              'Brand entity signals', '{} mention(s), {}'.format(brand_mentions, "Org schema" if org_schema else "no Org schema"),
              'Add Organization schema + consistent brand mentions for AI entity recognition', 'High', 'Brand & Trust')

    trust_words = ['case study', 'testimonial', 'review', 'client', 'customer', 'success story', 'results', 'roi', 'certified', 'award', 'recognized']
    trust_count = sum(1 for w in trust_words if w in text.lower())
    add_check(checks, 'Trust Stack Signals', 'pass' if trust_count >= 3 else 'info',
              'Social proof', '{} trust signal(s)'.format(trust_count),
              'Add case studies, testimonials, certifications for AI credibility', 'Medium', 'Brand & Trust')

    value_words = ['unique', 'only', 'first', 'exclusive', 'proprietary', 'patent', 'unlike', 'different from', 'our approach', 'we built']
    value_count = sum(1 for w in value_words if w in text.lower())
    add_check(checks, 'Unique Value Proposition', 'pass' if value_count >= 2 else 'info',
              'Differentiation signals', '{} signal(s)'.format(value_count),
              'State what makes you different — AI cites unique perspectives over commodity info', 'Medium', 'Brand & Trust')

    main_content = soup.find('main') or soup.find('article')
    content_to_chrome_ratio = word_count / max(len(html), 1) * 100
    add_check(checks, 'Content-to-Chrome Ratio', 'pass' if main_content and content_to_chrome_ratio > 15 else 'warning',
              'Content extractability', '{:.1f}%, {}'.format(content_to_chrome_ratio, "main/article wrapper" if main_content else "no wrapper"),
              'Wrap content in <main>/<article> — AI extracts from semantic containers first', 'High', 'Brand & Trust')

    has_tldr = bool(re.search(r'(?:tl;?dr|key takeaway|summary|in brief|at a glance|quick answer)', text.lower()))
    has_detailed = word_count >= 500
    add_check(checks, 'Summary + Depth Pattern', 'pass' if has_tldr and has_detailed else ('warning' if has_detailed else 'fail'),
              'TL;DR + depth', '{}, {} words'.format("Summary found" if has_tldr else "No summary", word_count),
              'Add Key Takeaways/TL;DR section — AI extracts summary, depth builds citation trust', 'High', 'Brand & Trust')

    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== MAIN SCAN FUNCTIONS ==============

def scan_site(url: str, timeout: int = 15) -> ScanResult:
    """
    OpenClaw Tool: Quick scan a website for SEO issues.
    Preserves original output format for backward compatibility.
    Now powered by the full 216-check engine under the hood.
    """
    try:
        # Run the deep scan
        deep = deep_scan_site(url, timeout=timeout)

        # Convert deep results back to the simple ScanResult format
        critical_issues = []
        warnings = []
        recommendations = []

        for cat_key, cat_data in deep.get('categories', {}).items():
            for check in cat_data.get('checks', []):
                if check['status'] == 'fail':
                    critical_issues.append(f"[{cat_key.upper()}] {check['name']}: {check['value']}")
                    recommendations.append({
                        "issue": check['name'],
                        "action": check['recommendation'],
                        "priority": check['impact'],
                        "impact": check['description']
                    })
                elif check['status'] == 'warning':
                    warnings.append(f"[{cat_key.upper()}] {check['name']}: {check['value']}")
                    recommendations.append({
                        "issue": check['name'],
                        "action": check['recommendation'],
                        "priority": check['impact'],
                        "impact": check['description']
                    })

        return ScanResult(
            url=url,
            score=round(deep.get('overallScore', 0)),
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations,
            load_time=deep.get('load_time', 0),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    except requests.RequestException as e:
        return ScanResult(
            url=url, score=0,
            critical_issues=[f"Site unreachable: {str(e)}"],
            warnings=[], recommendations=[{
                "issue": "Site unreachable",
                "action": "Check server status, DNS settings, and firewall rules",
                "priority": "Critical", "impact": "Site is completely inaccessible"
            }],
            load_time=0, timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ")
        )


def deep_scan_site(url: str, timeout: int = 15, categories: list = None) -> DetailedScanResult:
    """
    Full 216-check deep scan across all 9 categories.
    Returns detailed results with per-category breakdowns.
    """
    if not url.startswith('http'):
        url = 'https://' + url

    headers = {'User-Agent': 'Mozilla/5.0 (compatible; SEOMonitor/2.0)'}
    start_time = time.time()
    response = requests.get(url, headers=headers, timeout=timeout)
    load_time = time.time() - start_time
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    if categories is None:
        categories = ['technical', 'onpage', 'content', 'mobile', 'performance', 'security', 'social', 'local', 'geo']

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

    results_categories = {}
    total_checks = 0
    total_passed = 0

    for cat_key in categories:
        if cat_key in analyzers:
            name, analyzer_func = analyzers[cat_key]
            result = analyzer_func(url, soup, response, load_time)
            results_categories[cat_key] = result
            total_checks += result['total']
            total_passed += result['passed']

    scores = [cat['score'] for cat in results_categories.values()]
    overall_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Build simple issue lists for backward compat
    critical_issues = []
    warnings_list = []
    recommendations = []
    for cat_key, cat_data in results_categories.items():
        for check in cat_data.get('checks', []):
            if check['status'] == 'fail':
                critical_issues.append(f"[{cat_key.upper()}] {check['name']}: {check['value']}")
                recommendations.append({"issue": check['name'], "action": check['recommendation'],
                                        "priority": check['impact'], "impact": check['description']})
            elif check['status'] == 'warning':
                warnings_list.append(f"[{cat_key.upper()}] {check['name']}: {check['value']}")

    return {
        'url': url,
        'score': round(overall_score),
        'critical_issues': critical_issues,
        'warnings': warnings_list,
        'recommendations': recommendations,
        'load_time': round(load_time, 2),
        'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        'categories': results_categories,
        'totalChecks': total_checks,
        'totalPassed': total_passed,
        'overallScore': overall_score
    }


# OpenClaw tool registration
TOOL_SCHEMA = {
    "name": "seo_scanner",
    "description": "Comprehensive 216-check SEO scanner across 9 categories including GEO/AEO",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Website URL to scan"},
            "timeout": {"type": "integer", "default": 15},
            "deep": {"type": "boolean", "default": False, "description": "Return detailed per-category results"}
        },
        "required": ["url"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "score": {"type": "integer"},
            "critical_issues": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "load_time": {"type": "number"},
            "timestamp": {"type": "string"},
            "categories": {"type": "object"},
            "totalChecks": {"type": "integer"},
            "totalPassed": {"type": "integer"},
            "overallScore": {"type": "number"}
        }
    }
}
