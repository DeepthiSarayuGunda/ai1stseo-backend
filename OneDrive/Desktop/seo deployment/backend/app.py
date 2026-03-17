"""
SEO Analyzer Backend - Flask API
216 Comprehensive SEO Checks across 9 categories
Enhanced GEO/AEO (45 checks) with AI Crawlability, Knowledge Graph, and Publishing Readiness
Enhanced Local SEO (30 checks) and Social SEO (24 checks) based on 2026 best practices
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
CORS(app)

# Register auth blueprint (Cognito + Secrets Manager)
from auth import auth_bp
app.register_blueprint(auth_bp)

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
                   'value': str(value)[:500], 'recommendation': rec, 
                   'impact': impact, 'category': cat or 'General'})


# ============== TECHNICAL SEO (35 checks) ==============
def analyze_technical_seo(url, soup, response, load_time):
    checks = []
    parsed = urlparse(url)
    html = str(soup)
    
    # 1-7: Crawlability
    robots = safe_get(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    add_check(checks, 'Robots.txt', 'pass' if robots and robots.status_code == 200 else 'warning',
              'Checks whether a robots.txt file exists at the site root. This file tells search engine crawlers which pages or sections they can or cannot access, helping you control crawl budget and prevent indexing of private areas',
              'Found' if robots and robots.status_code == 200 else 'Not found',
              'Create a robots.txt file in your site root. Include directives like "User-agent: *" and "Disallow: /private/" to control crawler access. Also add a Sitemap directive pointing to your XML sitemap URL', 'High', 'Crawlability')
    
    meta_robots = soup.find('meta', {'name': 'robots'})
    robots_content = meta_robots.get('content', '').lower() if meta_robots else ''
    add_check(checks, 'Meta Robots', 'pass' if 'noindex' not in robots_content else 'fail',
              'Checks the meta robots tag to see if this page is allowed to be indexed by search engines. A "noindex" directive tells Google and other engines to exclude this page from search results entirely',
              robots_content or 'Not set (indexable by default)',
              'If this page should appear in search results, remove the "noindex" directive from the meta robots tag. If intentionally hidden, this is expected. Check: <meta name="robots" content="index, follow">', 'Critical', 'Crawlability')
    
    sitemap = safe_get(f"{parsed.scheme}://{parsed.netloc}/sitemap.xml")
    add_check(checks, 'XML Sitemap', 'pass' if sitemap and sitemap.status_code == 200 else 'warning',
              'Checks for an XML sitemap at /sitemap.xml. Sitemaps help search engines discover all your pages faster and understand your site structure, especially important for large sites or new pages that lack inbound links',
              'Found' if sitemap and sitemap.status_code == 200 else 'Not found',
              'Create an XML sitemap listing all important pages with their last-modified dates and priority. Submit it to Google Search Console and Bing Webmaster Tools. Most CMS platforms (WordPress, Shopify) generate these automatically', 'High', 'Crawlability')
    
    canonical = soup.find('link', {'rel': 'canonical'})
    add_check(checks, 'Canonical URL', 'pass' if canonical else 'warning',
              'Checks for a canonical tag that tells search engines which version of a page is the "official" one. This prevents duplicate content issues when the same page is accessible via multiple URLs (e.g., with/without www, with tracking parameters)',
              canonical.get('href', '')[:100] if canonical else 'Not set',
              'Add a <link rel="canonical" href="https://yoursite.com/page"> tag in the <head> section. This consolidates ranking signals to one URL and prevents search engines from splitting authority across duplicate pages', 'High', 'Crawlability')
    
    # Check if canonical is self-referencing
    canonical_href = canonical.get('href', '') if canonical else ''
    is_self_canonical = url in canonical_href or canonical_href in url
    add_check(checks, 'Self-Referencing Canonical', 'pass' if is_self_canonical or not canonical else 'warning',
              'Verifies the canonical tag points back to this page itself. A self-referencing canonical is best practice — it explicitly tells search engines this is the preferred URL, even if no duplicates exist',
              'Yes (self-referencing)' if is_self_canonical else 'No — points to a different URL',
              'Set the canonical URL to match the current page URL exactly. If it points elsewhere, search engines may treat this page as a duplicate and consolidate ranking signals to the other URL instead', 'Medium', 'Crawlability')
    
    hreflang = soup.find_all('link', {'hreflang': True})
    add_check(checks, 'Hreflang Tags', 'pass' if hreflang else 'info',
              'Checks for hreflang tags that tell search engines which language and regional version of a page to show to users in different countries. Essential for multilingual or multi-regional sites to avoid duplicate content across languages',
              f'{len(hreflang)} hreflang tags found', 'Add hreflang tags if your site serves content in multiple languages or targets different countries. Format: <link rel="alternate" hreflang="es" href="https://yoursite.com/es/page">. Include an x-default for the fallback version', 'Medium', 'Crawlability')
    
    # Check for noindex in X-Robots-Tag header
    x_robots = response.headers.get('X-Robots-Tag', '')
    add_check(checks, 'X-Robots-Tag', 'pass' if 'noindex' not in x_robots.lower() else 'fail',
              'Checks the X-Robots-Tag HTTP header for indexing directives. This header-level directive works like the meta robots tag but is set at the server level, often used for non-HTML files like PDFs. A "noindex" here will block the page from search results',
              x_robots or 'Not set (no restrictions)',
              'Remove the "noindex" directive from the X-Robots-Tag HTTP header in your server configuration (Nginx, Apache, or CDN settings) if this page should be indexed. This overrides any meta tag settings', 'High', 'Crawlability')
    
    # 8-14: Security
    add_check(checks, 'HTTPS', 'pass' if parsed.scheme == 'https' else 'fail',
              'Checks whether the site uses HTTPS (SSL/TLS encryption). HTTPS is a confirmed Google ranking factor and is essential for user trust, data security, and browser compatibility. Sites without HTTPS show "Not Secure" warnings in Chrome',
              parsed.scheme.upper(), 'Install an SSL certificate and redirect all HTTP traffic to HTTPS. Free certificates are available from Let\'s Encrypt. Most hosting providers offer one-click SSL setup', 'Critical', 'Security')
    
    hsts = response.headers.get('Strict-Transport-Security', '')
    add_check(checks, 'HSTS Header', 'pass' if hsts else 'warning',
              'Checks for the Strict-Transport-Security header, which tells browsers to always use HTTPS for your site. This prevents downgrade attacks and cookie hijacking by ensuring the browser never makes an insecure HTTP request after the first visit',
              'Enabled' if hsts else 'Not set',
              'Add the header: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload. This tells browsers to enforce HTTPS for one year. Consider submitting to the HSTS preload list at hstspreload.org', 'Medium', 'Security')
    
    xcto = response.headers.get('X-Content-Type-Options', '')
    add_check(checks, 'X-Content-Type-Options', 'pass' if xcto else 'warning',
              'Checks for the X-Content-Type-Options header that prevents browsers from MIME-sniffing a response away from the declared content type. Without this, attackers could trick the browser into executing malicious files disguised as harmless content types',
              xcto or 'Not set',
              'Add the header: X-Content-Type-Options: nosniff. This is a simple one-line server configuration change that prevents MIME type confusion attacks', 'Medium', 'Security')
    
    xfo = response.headers.get('X-Frame-Options', '')
    add_check(checks, 'X-Frame-Options', 'pass' if xfo else 'warning',
              'Checks for the X-Frame-Options header that prevents your site from being embedded in iframes on other domains. Without this protection, attackers can overlay invisible frames on your site to trick users into clicking malicious elements (clickjacking)',
              xfo or 'Not set',
              'Add the header: X-Frame-Options: SAMEORIGIN (allows framing only from your own domain) or DENY (blocks all framing). This protects against clickjacking attacks', 'Medium', 'Security')
    
    csp = response.headers.get('Content-Security-Policy', '')
    add_check(checks, 'Content-Security-Policy', 'pass' if csp else 'info',
              'Checks for a Content Security Policy header that controls which resources (scripts, styles, images) the browser is allowed to load. CSP is one of the strongest defenses against cross-site scripting (XSS) and data injection attacks',
              'Configured' if csp else 'Not set',
              'Implement a CSP header that whitelists trusted sources. Start with a report-only mode to identify issues: Content-Security-Policy-Report-Only: default-src \'self\'. Gradually tighten the policy as you identify all legitimate resource sources', 'Medium', 'Security')
    
    mixed = len(soup.find_all(src=re.compile(r'^http://')))
    add_check(checks, 'No Mixed Content', 'pass' if mixed == 0 else 'warning',
              'Checks whether all resources (images, scripts, stylesheets) are loaded over HTTPS. Mixed content occurs when an HTTPS page loads resources over insecure HTTP, which triggers browser warnings and can break page functionality',
              f'{mixed} insecure resources found' if mixed > 0 else 'All resources loaded securely over HTTPS',
              'Update all resource URLs from http:// to https://. Use protocol-relative URLs (//example.com/file.js) or absolute HTTPS URLs. Check images, scripts, stylesheets, fonts, and iframes', 'High', 'Security')
    
    # Check for password fields on HTTP
    password_fields = soup.find_all('input', {'type': 'password'})
    add_check(checks, 'Secure Password Fields', 'pass' if parsed.scheme == 'https' or not password_fields else 'fail',
              'Checks that any password input fields are served over HTTPS. Transmitting passwords over unencrypted HTTP exposes user credentials to interception. Browsers now display prominent warnings on HTTP pages with password fields',
              f'{len(password_fields)} password fields found' + (' — served securely over HTTPS' if parsed.scheme == 'https' else ' — WARNING: served over insecure HTTP'),
              'Ensure all pages with login forms or password fields are served exclusively over HTTPS. Redirect any HTTP versions to HTTPS immediately', 'Critical', 'Security')
    
    # 15-23: URL Structure
    add_check(checks, 'URL Length', 'pass' if len(url) < 75 else 'warning',
              'Measures the total character count of the URL. Shorter URLs are easier for users to read, share, and remember. Google has indicated that URLs under 75 characters tend to perform better in search results and are fully displayed in SERPs',
              f'{len(url)} characters', 'Shorten the URL by removing unnecessary words, parameters, or directory levels. Focus on including only the target keyword and essential path segments. Aim for under 75 characters total', 'Medium', 'URL Structure')
    
    add_check(checks, 'URL Lowercase', 'pass' if url == url.lower() else 'warning',
              'Checks whether the URL uses only lowercase characters. Mixed-case URLs can create duplicate content issues since some servers treat /Page and /page as different URLs, splitting ranking signals between them',
              'All lowercase' if url == url.lower() else 'Contains uppercase characters — may cause duplicate content issues',
              'Configure your server to redirect uppercase URLs to their lowercase equivalents using 301 redirects. In Nginx: rewrite ^(.*)$ $scheme://$host$lowercase_uri redirect;', 'Medium', 'URL Structure')
    
    add_check(checks, 'URL Hyphens', 'pass' if '_' not in parsed.path else 'warning',
              'Checks whether the URL uses hyphens (-) instead of underscores (_) as word separators. Google treats hyphens as word separators but treats underscores as word joiners, meaning "seo-tips" is read as two words but "seo_tips" is read as one',
              'Uses hyphens (correct)' if '_' not in parsed.path else 'Contains underscores — Google reads these as word joiners, not separators',
              'Replace underscores with hyphens in all URLs. Set up 301 redirects from old underscore URLs to new hyphenated versions to preserve any existing link equity', 'Medium', 'URL Structure')
    
    depth = len([p for p in parsed.path.split('/') if p])
    add_check(checks, 'URL Depth', 'pass' if depth <= 3 else 'warning',
              'Counts the number of directory levels in the URL path. Pages buried deep in the site hierarchy (4+ levels) receive less crawl priority and link equity. Flatter URL structures help search engines discover and rank content more efficiently',
              f'{depth} directory levels deep',
              'Restructure deep URLs to be within 3 levels of the root. Example: change /blog/2024/category/subcategory/post to /blog/post-title. Flatter structures improve both crawlability and user navigation', 'Medium', 'URL Structure')
    
    # Check for URL parameters
    params = parsed.query
    param_count = len(params.split('&')) if params else 0
    add_check(checks, 'URL Parameters', 'pass' if param_count <= 2 else 'warning',
              'Counts query string parameters (?key=value) in the URL. Excessive parameters create crawl bloat, as search engines may treat each parameter combination as a separate page. This wastes crawl budget and dilutes ranking signals',
              f'{param_count} parameters found',
              'Minimize URL parameters by using clean URL paths instead. For tracking, use UTM parameters only for campaign links (not internal navigation). Configure Google Search Console to indicate which parameters to ignore', 'Medium', 'URL Structure')
    
    # Check for special characters in URL
    special_chars = re.findall(r'[^a-zA-Z0-9\-\_\/\.\:]', parsed.path)
    add_check(checks, 'Clean URL', 'pass' if not special_chars else 'warning',
              'Checks for special characters (spaces, accents, symbols) in the URL path. Clean URLs with only alphanumeric characters, hyphens, and slashes are more reliable across browsers, easier to share, and less likely to cause encoding issues in links',
              f'{len(special_chars)} special characters found' if special_chars else 'URL is clean — no special characters',
              'Remove or replace special characters with hyphens. URL-encode any necessary characters. Avoid spaces (which become %20), accents, and symbols like &, =, +, or # in URL paths', 'Medium', 'URL Structure')
    
    # 24-30: Internal Linking
    all_links = soup.find_all('a', href=True)
    internal = [l for l in all_links if parsed.netloc in urljoin(url, l.get('href', ''))]
    add_check(checks, 'Internal Links', 'pass' if len(internal) >= 3 else 'warning',
              'Counts links pointing to other pages on the same domain. Internal links distribute page authority (link equity) throughout your site, help search engines discover content, and guide users to related pages. Pages with few internal links are harder to rank',
              f'{len(internal)} internal links found',
              'Add 3-10 contextual internal links per page pointing to related content. Use descriptive anchor text that includes target keywords. Prioritize linking to your most important pages (pillar content, service pages)', 'High', 'Internal Linking')
    
    external = [l for l in all_links if l.get('href', '').startswith('http') and parsed.netloc not in l.get('href', '')]
    add_check(checks, 'External Links', 'pass' if external else 'info',
              'Counts outbound links to other domains. Linking to authoritative external sources signals to search engines that your content is well-researched and trustworthy. It also provides additional value to users by connecting them to supporting information',
              f'{len(external)} external links found',
              'Include 2-5 outbound links to authoritative, relevant sources (industry publications, research papers, official documentation). This builds topical trust and demonstrates E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)', 'Medium', 'Internal Linking')
    
    # Check for broken link indicators (empty hrefs)
    empty_links = [l for l in all_links if not l.get('href', '').strip() or l.get('href', '') == '#']
    add_check(checks, 'Valid Link Hrefs', 'pass' if len(empty_links) < 3 else 'warning',
              'Checks for links with empty or placeholder href attributes (href="" or href="#"). These create poor user experience, waste crawl budget, and can cause unexpected page reloads or scroll-to-top behavior',
              f'{len(empty_links)} empty/placeholder links found',
              'Replace empty href attributes with actual destination URLs. If a link is meant as a button, use a <button> element instead. Remove any href="#" links that serve no navigation purpose', 'Medium', 'Internal Linking')
    
    # Check for nofollow on internal links
    nofollow_internal = [l for l in internal if 'nofollow' in str(l.get('rel', []))]
    add_check(checks, 'Internal Nofollow', 'pass' if not nofollow_internal else 'warning',
              'Checks for rel="nofollow" on internal links. Adding nofollow to your own internal links wastes link equity — it tells search engines not to pass ranking value to your own pages, which hurts your site\'s overall SEO performance',
              f'{len(nofollow_internal)} internal links with nofollow' if nofollow_internal else 'No internal links have nofollow (correct)',
              'Remove rel="nofollow" from all internal links. Nofollow should only be used on external links to untrusted or user-generated content, paid links, or login/registration pages', 'Medium', 'Internal Linking')
    
    # Check anchor text quality
    generic_anchors = ['click here', 'read more', 'learn more', 'here', 'link']
    generic_links = [l for l in all_links if l.get_text().strip().lower() in generic_anchors]
    add_check(checks, 'Descriptive Anchors', 'pass' if len(generic_links) <= 2 else 'warning',
              'Checks for generic anchor text like "click here" or "read more." Descriptive anchor text helps search engines understand what the linked page is about and improves accessibility for screen reader users who navigate by link text',
              f'{len(generic_links)} links with generic anchor text (e.g., "click here", "read more")',
              'Replace generic anchor text with descriptive phrases that include relevant keywords. Instead of "click here to learn about SEO," use "learn about our SEO audit process." This helps both search engines and users understand link destinations', 'Medium', 'Internal Linking')
    
    # 31-35: Structured Data & Technical
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    add_check(checks, 'Schema.org JSON-LD', 'pass' if json_ld else 'warning',
              'Checks for JSON-LD structured data markup. Schema.org markup helps search engines understand your content\'s meaning and context, enabling rich results (star ratings, FAQs, breadcrumbs, product info) that significantly increase click-through rates in search results',
              f'{len(json_ld)} JSON-LD blocks found',
              'Add JSON-LD structured data in a <script type="application/ld+json"> tag. Start with Organization, WebSite, and BreadcrumbList schemas. For content pages, add Article or BlogPosting. Use Google\'s Rich Results Test to validate: search.google.com/test/rich-results', 'High', 'Structured Data')
    
    microdata = soup.find_all(attrs={'itemtype': True})
    add_check(checks, 'Microdata', 'pass' if microdata or json_ld else 'info',
              'Checks for HTML microdata attributes (itemtype, itemprop). Microdata is an older format for structured data embedded directly in HTML elements. While JSON-LD is now preferred by Google, microdata still works and can complement JSON-LD markup',
              f'{len(microdata)} microdata items found',
              'If you already have JSON-LD, microdata is optional. If not, consider adding JSON-LD instead as it\'s easier to maintain (separate from HTML) and is Google\'s recommended format', 'Low', 'Structured Data')
    
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    add_check(checks, 'Viewport Meta', 'pass' if viewport else 'fail',
              'Checks for the viewport meta tag that controls how the page scales on mobile devices. Without this tag, mobile browsers render the page at desktop width and scale it down, making text unreadable and buttons untappable. This is a core mobile-friendliness requirement',
              viewport.get('content', '')[:80] if viewport else 'Not set — page will not render correctly on mobile devices',
              'Add this tag in your <head>: <meta name="viewport" content="width=device-width, initial-scale=1.0">. This ensures the page adapts to the device screen width', 'Critical', 'Technical')
    
    doctype = '<!doctype' in html.lower()[:100]
    add_check(checks, 'DOCTYPE Declaration', 'pass' if doctype else 'warning',
              'Checks for an HTML DOCTYPE declaration at the top of the page. The DOCTYPE tells browsers which version of HTML to use for rendering. Without it, browsers enter "quirks mode" which can cause inconsistent layout and styling across different browsers',
              'Present (standards mode)' if doctype else 'Missing — browser may use quirks mode',
              'Add <!DOCTYPE html> as the very first line of your HTML document, before the <html> tag. This triggers standards mode rendering in all modern browsers', 'Medium', 'Technical')
    
    charset = soup.find('meta', charset=True) or soup.find('meta', {'http-equiv': 'Content-Type'})
    add_check(checks, 'Character Encoding', 'pass' if charset else 'warning',
              'Checks for a character encoding declaration (usually UTF-8). This tells browsers how to interpret the bytes in your HTML file as text characters. Without it, special characters, accents, and non-Latin scripts may display as garbled text',
              'UTF-8 declared' if charset else 'Not set — may cause character display issues',
              'Add <meta charset="UTF-8"> as the first element inside your <head> tag. UTF-8 supports virtually all characters and symbols from every language and is the universal standard', 'High', 'Technical')
    
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
              'Checks for a <title> tag in the page head. The title tag is the single most important on-page SEO element — it appears as the clickable headline in search results and browser tabs. Pages without titles are nearly impossible to rank',
              title_text[:80] + '...' if len(title_text) > 80 else title_text or 'Missing — no title tag found',
              'Add a unique, descriptive <title> tag that includes your primary keyword near the beginning. Format: "Primary Keyword - Secondary Keyword | Brand Name". Every page on your site should have a unique title', 'Critical', 'Title & Meta')
    
    add_check(checks, 'Title Length', 'pass' if 30 <= len(title_text) <= 60 else 'warning',
              'Measures the character count of your title tag. Google typically displays 50-60 characters in search results. Titles that are too short miss keyword opportunities, while titles that are too long get truncated with "..." which reduces click-through rates',
              f'{len(title_text)} characters (optimal range: 50-60)',
              'Rewrite the title to be 50-60 characters. Front-load your most important keyword. Include a compelling reason to click. Example: "SEO Audit Tool - Free 200+ Point Website Analysis | AISEO"', 'High', 'Title & Meta')
    
    # Check for duplicate words in title
    title_words = title_text.lower().split()
    unique_title_words = set(title_words)
    add_check(checks, 'Title Uniqueness', 'pass' if len(unique_title_words) >= len(title_words) * 0.7 else 'warning',
              'Checks for repeated words in the title tag. Keyword stuffing in titles (repeating the same word multiple times) looks spammy to both users and search engines, and can trigger ranking penalties',
              f'{len(unique_title_words)} unique words out of {len(title_words)} total',
              'Remove repeated words from the title. Each word should add meaning. Instead of "SEO SEO Tools - Best SEO Software," use "SEO Tools - Professional Website Analysis Software"', 'Medium', 'Title & Meta')
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_text = meta_desc.get('content', '').strip() if meta_desc else ''
    add_check(checks, 'Meta Description', 'pass' if desc_text else 'fail',
              'Checks for a meta description tag. While not a direct ranking factor, the meta description appears as the snippet text below your title in search results. A compelling description significantly increases click-through rate, which indirectly boosts rankings',
              desc_text[:100] + '...' if len(desc_text) > 100 else desc_text or 'Missing — Google will auto-generate a snippet from page content',
              'Write a unique meta description that summarizes the page content, includes target keywords naturally, and contains a call-to-action. Include your value proposition to entice clicks from search results', 'High', 'Title & Meta')
    
    add_check(checks, 'Description Length', 'pass' if 120 <= len(desc_text) <= 160 else 'warning',
              'Measures the character count of your meta description. Google displays approximately 155-160 characters on desktop and 120 characters on mobile. Descriptions that are too short waste valuable SERP real estate, while too-long ones get truncated',
              f'{len(desc_text)} characters (optimal range: 120-160)',
              'Rewrite the meta description to be 120-160 characters. Use the full space to communicate value. Include a call-to-action like "Learn more," "Get started," or "Try free." Make it read like ad copy that compels clicks', 'High', 'Title & Meta')
    
    meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
    add_check(checks, 'Meta Keywords', 'info',
              'Checks for the meta keywords tag. Google has officially confirmed they ignore this tag for ranking purposes since 2009. However, some other search engines (Yandex, Baidu) may still consider it. Its presence is neither helpful nor harmful for Google SEO',
              'Present' if meta_keywords else 'Not set (this is fine — Google ignores meta keywords)',
              'The meta keywords tag is deprecated for Google SEO. Focus your keyword optimization efforts on title tags, headings, content, and meta descriptions instead. No action needed here', 'Low', 'Title & Meta')
    
    html_tag = soup.find('html')
    lang = html_tag.get('lang', '') if html_tag else ''
    add_check(checks, 'Language Attribute', 'pass' if lang else 'warning',
              'Checks for a lang attribute on the <html> tag. This tells search engines and screen readers what language the page content is in, improving accessibility and helping search engines serve the right version to users in different regions',
              f'Language set to: {lang}' if lang else 'Not set — search engines must guess the page language',
              'Add a lang attribute to your <html> tag: <html lang="en"> for English, <html lang="es"> for Spanish, etc. This is a simple change that improves both SEO and accessibility compliance', 'Medium', 'Title & Meta')
    
    favicon = soup.find('link', rel=re.compile(r'icon', re.I))
    add_check(checks, 'Favicon', 'pass' if favicon else 'warning',
              'Checks for a favicon (the small icon shown in browser tabs, bookmarks, and search results). While not a direct ranking factor, favicons improve brand recognition and user trust. Google displays favicons next to search results on mobile',
              'Favicon found' if favicon else 'No favicon detected',
              'Add a favicon in multiple sizes. At minimum: <link rel="icon" type="image/png" href="/favicon.png">. For best results, include a 32x32 .ico file and a 180x180 apple-touch-icon for mobile devices', 'Low', 'Title & Meta')
    
    # 9-15: Headings
    h1_tags = soup.find_all('h1')
    add_check(checks, 'H1 Tag', 'pass' if len(h1_tags) == 1 else ('fail' if not h1_tags else 'warning'),
              'Checks for exactly one H1 heading tag on the page. The H1 is the main heading that tells search engines and users what the page is about. Having zero H1s means no clear topic signal; having multiple H1s dilutes the page focus and confuses hierarchy',
              f'{len(h1_tags)} H1 tag(s) found' + (' (should be exactly 1)' if len(h1_tags) != 1 else ' (correct)'),
              'Use exactly one H1 tag per page containing your primary keyword. The H1 should clearly describe the page topic and be different from the title tag. Place it at the top of the main content area', 'Critical', 'Headings')
    
    h1_text = h1_tags[0].get_text().strip() if h1_tags else ''
    add_check(checks, 'H1 Content', 'pass' if len(h1_text) >= 10 else 'warning',
              'Evaluates the content quality of the H1 tag. An H1 that is too short or empty fails to communicate the page topic to search engines. The H1 should be descriptive enough to stand alone as a summary of what the page covers',
              f'H1 text: "{h1_text[:60]}..." ({len(h1_text)} chars)' if len(h1_text) > 60 else f'H1 text: "{h1_text}" ({len(h1_text)} chars)' if h1_text else 'H1 is empty or missing',
              'Write a descriptive H1 of 20-70 characters that includes your primary keyword naturally. It should clearly tell visitors what they will find on this page. Avoid generic H1s like "Welcome" or "Home"', 'High', 'Headings')
    
    h2_tags = soup.find_all('h2')
    add_check(checks, 'H2 Tags', 'pass' if 2 <= len(h2_tags) <= 10 else 'warning',
              'Counts H2 subheading tags that break content into logical sections. H2s help search engines understand content structure and enable featured snippet eligibility. They also improve readability by creating scannable sections for users',
              f'{len(h2_tags)} H2 tags found',
              'Use 2-8 H2 tags to organize your content into clear sections. Include secondary keywords and related terms in H2s. Think of H2s as chapter titles — each should introduce a distinct subtopic of the page', 'High', 'Headings')
    
    h3_tags = soup.find_all('h3')
    add_check(checks, 'H3 Tags', 'pass' if h3_tags else 'info',
              'Checks for H3 subheading tags that provide additional content hierarchy under H2 sections. H3s signal detailed content depth to search engines and help organize complex topics into digestible subsections',
              f'{len(h3_tags)} H3 tags found',
              'Use H3 tags to break down H2 sections into more specific subtopics. This creates a clear content outline that search engines can use to understand topic depth and potentially generate featured snippets', 'Low', 'Headings')
    
    all_headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    empty_h = [h for h in all_headings if not h.get_text().strip()]
    add_check(checks, 'No Empty Headings', 'pass' if not empty_h else 'warning',
              'Checks for heading tags (H1-H6) that contain no text. Empty headings create confusing document structure for search engines and screen readers, and suggest incomplete or poorly structured content',
              f'{len(empty_h)} empty heading tags found' if empty_h else 'All headings contain text (correct)',
              'Either add descriptive text to empty headings or remove them entirely. If a heading is used purely for styling, replace it with a styled <div> or <span> instead — headings should always convey content structure', 'Medium', 'Headings')
    
    # Check heading hierarchy
    heading_order = [int(h.name[1]) for h in all_headings]
    hierarchy_ok = all(heading_order[i] <= heading_order[i-1] + 1 for i in range(1, len(heading_order))) if heading_order else True
    add_check(checks, 'Heading Hierarchy', 'pass' if hierarchy_ok else 'warning',
              'Verifies that headings follow a logical order without skipping levels (e.g., H1 → H2 → H3, not H1 → H3). Proper hierarchy helps search engines understand content relationships and is required for accessibility compliance (WCAG)',
              'Heading order is correct (no skipped levels)' if hierarchy_ok else 'Heading levels are skipped — e.g., jumping from H1 to H3 without an H2',
              'Restructure headings to follow sequential order: H1 → H2 → H3 → H4. Never skip a level. If you need smaller text, use CSS styling on the correct heading level rather than jumping to a lower heading number', 'Medium', 'Headings')
    
    # 16-21: Images
    images = soup.find_all('img')
    imgs_alt = [i for i in images if i.get('alt')]
    add_check(checks, 'Image Alt Text', 'pass' if len(imgs_alt) == len(images) or not images else 'warning',
              'Checks whether all images have alt attributes. Alt text describes images to search engines (which cannot "see" images) and to visually impaired users using screen readers. Images without alt text are invisible to search engines and inaccessible to blind users',
              f'{len(imgs_alt)} of {len(images)} images have alt text',
              'Add descriptive alt text to every image that conveys meaning. Describe what the image shows in 5-15 words. Include relevant keywords naturally. For decorative images, use alt="" (empty alt). Example: alt="SEO audit dashboard showing website health score"', 'High', 'Images')
    
    imgs_dims = [i for i in images if i.get('width') and i.get('height')]
    add_check(checks, 'Image Dimensions', 'pass' if len(imgs_dims) == len(images) or not images else 'warning',
              'Checks whether images have explicit width and height attributes. Without dimensions, the browser does not know how much space to reserve, causing layout shifts as images load (Cumulative Layout Shift — a Core Web Vital that affects rankings)',
              f'{len(imgs_dims)} of {len(images)} images have width/height specified',
              'Add width and height attributes to all <img> tags matching the image\'s intrinsic dimensions. This prevents layout shift (CLS). Example: <img src="photo.jpg" width="800" height="600" alt="...">. CSS can still make them responsive', 'Medium', 'Images')
    
    lazy_imgs = [i for i in images if i.get('loading') == 'lazy']
    add_check(checks, 'Lazy Loading', 'pass' if lazy_imgs or len(images) <= 3 else 'warning',
              'Checks for loading="lazy" on images below the fold. Lazy loading defers loading of off-screen images until the user scrolls near them, significantly improving initial page load time and reducing bandwidth usage on mobile devices',
              f'{len(lazy_imgs)} of {len(images)} images use lazy loading',
              'Add loading="lazy" to all images that are not visible in the initial viewport (below the fold). Do NOT lazy-load the hero image or LCP element — those should load immediately. Example: <img src="photo.jpg" loading="lazy" alt="...">', 'Medium', 'Images')
    
    srcset = [i for i in images if i.get('srcset')]
    add_check(checks, 'Responsive Images', 'pass' if srcset or len(images) <= 2 else 'info',
              'Checks for srcset attributes that serve different image sizes based on the user\'s screen size. Without responsive images, mobile users download full-size desktop images, wasting bandwidth and slowing page load',
              f'{len(srcset)} of {len(images)} images use srcset for responsive delivery',
              'Add srcset to serve appropriately sized images: <img srcset="small.jpg 400w, medium.jpg 800w, large.jpg 1200w" sizes="(max-width: 600px) 400px, 800px" src="medium.jpg" alt="...">. This can reduce image payload by 50-70% on mobile', 'Medium', 'Images')
    
    # Check for large images without optimization hints
    webp_imgs = [i for i in images if '.webp' in str(i.get('src', ''))]
    add_check(checks, 'Modern Image Formats', 'pass' if webp_imgs or not images else 'info',
              'Checks whether images use modern formats like WebP or AVIF. These formats provide 25-50% better compression than JPEG/PNG with equivalent visual quality, significantly reducing page weight and improving load times',
              f'{len(webp_imgs)} of {len(images)} images use WebP format',
              'Convert images to WebP format using tools like Squoosh, ImageMagick, or your CDN\'s auto-conversion feature. Use <picture> element for fallback: <picture><source srcset="image.webp" type="image/webp"><img src="image.jpg" alt="..."></picture>', 'Low', 'Images')
    
    # Empty alt vs missing alt
    empty_alt = [i for i in images if i.get('alt') == '']
    add_check(checks, 'Meaningful Alt Text', 'pass' if len(empty_alt) <= len(images) * 0.2 else 'warning',
              'Distinguishes between images with descriptive alt text vs empty alt="" attributes. Empty alt is correct for decorative images (icons, spacers), but content images need descriptive text. Too many empty alts suggest missing descriptions on important images',
              f'{len(images) - len(empty_alt)} of {len(images)} images have non-empty alt text',
              'Review images with empty alt="" attributes. If the image conveys information or content, add a descriptive alt. Only use empty alt for purely decorative images (backgrounds, dividers, icons that have adjacent text labels)', 'Medium', 'Images')
    
    # 22-25: Content Structure
    paragraphs = soup.find_all('p')
    add_check(checks, 'Paragraph Count', 'pass' if len(paragraphs) >= 3 else 'warning',
              'Counts paragraph elements on the page. Well-structured content uses multiple paragraphs to break information into digestible chunks. Pages with few paragraphs often indicate thin content or content that is difficult to read',
              f'{len(paragraphs)} paragraphs found',
              'Break your content into short, focused paragraphs of 2-4 sentences each. Each paragraph should cover one idea. Use transition words to connect paragraphs. This improves readability scores and time-on-page metrics', 'Medium', 'Content Structure')
    
    lists = soup.find_all(['ul', 'ol'])
    add_check(checks, 'List Usage', 'pass' if lists else 'info',
              'Checks for ordered (<ol>) and unordered (<ul>) lists. Lists make content scannable, improve user experience, and are frequently used by Google for featured snippets. Content with lists tends to have higher engagement and lower bounce rates',
              f'{len(lists)} lists found on the page',
              'Add bulleted or numbered lists where appropriate — steps, features, benefits, comparisons. Lists are prime candidates for featured snippet extraction. Use <ol> for sequential steps and <ul> for non-ordered items', 'Low', 'Content Structure')
    
    word_count = len(text.split())
    add_check(checks, 'Word Count', 'pass' if word_count >= 300 else 'warning',
              'Measures the total word count of visible page content. Search engines use content length as a quality signal — pages with fewer than 300 words are often considered "thin content" and struggle to rank for competitive keywords',
              f'{word_count} words on the page',
              'Aim for at least 300 words for basic pages and 1,000-2,000 words for content targeting competitive keywords. Focus on quality over quantity — every sentence should add value. Longer content naturally covers more related keywords and topics', 'Medium', 'Content Structure')
    
    # Check for thin content
    add_check(checks, 'Content Depth', 'pass' if word_count >= 500 else ('warning' if word_count >= 200 else 'fail'),
              'Evaluates whether the page has enough substantive content to thoroughly cover its topic. Google\'s Helpful Content system rewards pages that demonstrate depth, expertise, and comprehensive coverage of a subject',
              'Comprehensive content depth' if word_count >= 500 else f'Thin content — only {word_count} words. May struggle to rank',
              'Expand the content to thoroughly cover the topic. Add sections addressing common questions, provide examples, include data/statistics, and cover related subtopics. Use tools like "People Also Ask" in Google to find questions to answer', 'High', 'Content Structure')
    
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
              'Measures total word count as a content depth indicator. Studies consistently show that longer, comprehensive content ranks higher for competitive keywords. Pages under 300 words are flagged as thin content by Google\'s quality algorithms',
              f'{word_count} words (target: 1,000+ for competitive topics)',
              'Expand content to at least 1,000 words for pages targeting competitive keywords. Cover the topic comprehensively by addressing related questions, providing examples, and including supporting data. Use "People Also Ask" for content ideas', 'High', 'Content Quality')
    
    paragraphs = soup.find_all('p')
    para_count = len([p for p in paragraphs if len(p.get_text().strip()) > 20])
    add_check(checks, 'Paragraph Structure', 'pass' if para_count >= 5 else 'warning',
              'Counts substantial paragraphs (20+ characters) that form the body of the content. Well-structured content with multiple focused paragraphs signals depth and quality to search engines, and keeps readers engaged longer',
              f'{para_count} substantial paragraphs found',
              'Break content into 5+ focused paragraphs of 2-4 sentences each. Each paragraph should cover one distinct point. Short paragraphs improve readability, especially on mobile where long text blocks are overwhelming', 'Medium', 'Content Quality')
    
    # Readability - Flesch-like simple check
    sentences = re.split(r'[.!?]+', text)
    sent_count = len([s for s in sentences if len(s.split()) > 3])
    avg_sentence_len = word_count / sent_count if sent_count else 0
    add_check(checks, 'Sentence Length', 'pass' if 10 <= avg_sentence_len <= 20 else 'warning',
              'Calculates average words per sentence as a readability indicator. Content with sentences averaging 15-20 words is easiest to read. Very long sentences (25+) reduce comprehension, while very short ones can feel choppy and lack depth',
              f'Average sentence length: {avg_sentence_len:.1f} words (optimal: 15-20)',
              'Aim for an average of 15-20 words per sentence. Mix short punchy sentences with longer explanatory ones for rhythm. Break up sentences over 25 words. Use tools like Hemingway Editor to identify overly complex sentences', 'Medium', 'Content Quality')
    
    # Vocabulary diversity
    unique_words = len(set(w.lower() for w in words if len(w) > 3))
    ratio = unique_words / word_count if word_count else 0
    add_check(checks, 'Vocabulary Diversity', 'pass' if ratio > 0.3 else 'warning',
              'Measures the ratio of unique words to total words. Higher vocabulary diversity indicates richer, more natural content. Low diversity suggests repetitive writing or keyword stuffing, which search engines may penalize',
              f'{ratio*100:.0f}% unique vocabulary (target: 30%+)',
              'Use synonyms, related terms, and varied phrasing instead of repeating the same words. This also helps with semantic SEO — Google understands topic relevance through word variety, not just exact keyword matches', 'Low', 'Content Quality')
    
    # Questions for engagement
    questions = text.count('?')
    add_check(checks, 'Engaging Questions', 'pass' if questions >= 1 else 'info',
              'Counts question marks in the content. Questions increase reader engagement, create a conversational tone, and align with how people search (especially voice search). Content with questions is more likely to be selected for featured snippets',
              f'{questions} questions found in content',
              'Include 2-5 questions throughout your content, especially in headings. Use questions that match search queries: "What is...?", "How do you...?", "Why does...?". Answer each question directly in the following paragraph', 'Low', 'Content Quality')
    
    # Statistics and data
    numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?%?\b', text)
    add_check(checks, 'Data & Statistics', 'pass' if len(numbers) >= 3 else 'info',
              'Counts numerical data points in the content. Statistics, percentages, and specific numbers add credibility and authority to content. Data-driven content is more likely to be cited by other sites and referenced by AI systems',
              f'{len(numbers)} numerical data points found',
              'Include specific statistics, percentages, dates, and measurements to support your claims. Cite sources for data points. Example: "SEO drives 53% of all website traffic" is more compelling than "SEO drives a lot of traffic"', 'Medium', 'Content Quality')
    
    # Bold/emphasis usage
    bold = soup.find_all(['strong', 'b', 'em'])
    add_check(checks, 'Text Emphasis', 'pass' if bold else 'info',
              'Checks for <strong>, <b>, and <em> tags that highlight key information. Text emphasis helps readers scan content quickly and signals to search engines which phrases are most important on the page',
              f'{len(bold)} emphasized text elements found',
              'Use <strong> tags to highlight key phrases, important statistics, and critical takeaways. This helps both skimming readers and search engines identify the most important content. Avoid over-emphasizing — 3-5 bold phrases per 500 words is ideal', 'Low', 'Content Quality')
    
    # 8-13: Linking
    all_links = soup.find_all('a', href=True)
    internal = [l for l in all_links if parsed.netloc in urljoin(url, l.get('href', ''))]
    add_check(checks, 'Internal Links', 'pass' if 3 <= len(internal) <= 100 else 'warning',
              'Counts internal links that connect to other pages on your domain. Internal linking is one of the most powerful and underused SEO tactics — it distributes page authority, helps search engines discover content, and keeps users engaged longer on your site',
              f'{len(internal)} internal links found (optimal: 3-10 per page)',
              'Add 3-10 contextual internal links per page. Link to related blog posts, service pages, and pillar content using descriptive anchor text. Create a hub-and-spoke model where pillar pages link to cluster content and vice versa', 'High', 'Linking')
    
    external = [l for l in all_links if l.get('href', '').startswith('http') and parsed.netloc not in l.get('href', '')]
    add_check(checks, 'External Links', 'pass' if external else 'info',
              'Counts outbound links to external domains. Linking to authoritative sources demonstrates research quality and builds topical trust. Google\'s guidelines explicitly state that linking to relevant, high-quality external resources is a positive signal',
              f'{len(external)} external links found',
              'Include 2-5 outbound links to authoritative sources (research papers, industry publications, official documentation). This signals E-E-A-T and provides additional value to readers. Avoid linking to competitors\' commercial pages', 'Medium', 'Linking')
    
    link_density = len(all_links) / (word_count / 100) if word_count else 0
    add_check(checks, 'Link Density', 'pass' if 1 <= link_density <= 10 else 'warning',
              'Calculates the ratio of links per 100 words of content. Too few links means missed opportunities for internal linking and citations. Too many links (over 10 per 100 words) can appear spammy and dilute the value passed to each linked page',
              f'{link_density:.1f} links per 100 words (optimal: 1-5)',
              'Maintain 1-5 links per 100 words of content. If link density is too high, remove low-value or redundant links. If too low, add contextual internal links to related content and external citations to authoritative sources', 'Medium', 'Linking')
    
    # Nofollow on external
    nofollow_ext = [l for l in external if 'nofollow' in str(l.get('rel', []))]
    add_check(checks, 'External Nofollow', 'info',
              'Checks how many external links use rel="nofollow." Nofollow tells search engines not to pass ranking value through the link. Use it for paid links, user-generated content, and untrusted sources. Trusted editorial links should generally be followed',
              f'{len(nofollow_ext)} of {len(external)} external links have nofollow',
              'Apply rel="nofollow" to paid/sponsored links and user-generated content. For editorial links to trusted sources (Wikipedia, government sites, research papers), leave them as followed links to build topical trust', 'Low', 'Linking')
    
    # Check for affiliate/sponsored links
    sponsored = [l for l in all_links if 'sponsored' in str(l.get('rel', [])) or 'ugc' in str(l.get('rel', []))]
    add_check(checks, 'Link Qualification', 'pass' if not external or sponsored or nofollow_ext else 'info',
              'Checks for proper use of rel="sponsored" and rel="ugc" attributes. Google requires these labels on paid/affiliate links (sponsored) and user-generated content links (ugc). Failure to properly label paid links can result in manual penalties',
              f'{len(sponsored)} links properly labeled as sponsored/ugc',
              'Label all paid, affiliate, or sponsored links with rel="sponsored". Label links from user comments, forums, or reviews with rel="ugc". This is a Google requirement — unlabeled paid links violate their guidelines', 'Low', 'Linking')
    
    # 14-20: E-E-A-T Signals
    author = any(p in str(soup).lower() for p in ['author', 'written by', 'posted by', 'byline'])
    add_check(checks, 'Author Attribution', 'pass' if author else 'warning',
              'Checks for author information on the page. Google\'s E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) framework heavily weighs author credibility. Pages with clear author attribution rank better, especially for YMYL (Your Money Your Life) topics',
              'Author attribution found on page' if author else 'No author information detected',
              'Add a visible author name and bio to content pages. Include credentials, experience, and links to the author\'s social profiles or other published work. Use Person schema markup to help search engines connect content to the author entity', 'High', 'E-E-A-T')
    
    date_shown = any(p in str(soup).lower() for p in ['updated', 'published', 'modified', 'date'])
    add_check(checks, 'Content Date', 'pass' if date_shown else 'warning',
              'Checks for visible publish or last-updated dates. Content freshness is a ranking factor — Google prefers recently updated content for time-sensitive queries. Showing dates also builds user trust and helps readers assess information relevance',
              'Date information found on page' if date_shown else 'No publish/update date detected',
              'Display both the original publish date and last-updated date on content pages. Use <time> HTML elements and datePublished/dateModified in schema markup. Regularly update content and reflect the new date to signal freshness', 'Medium', 'E-E-A-T')
    
    # About/Contact pages linked
    about_link = soup.find('a', href=re.compile(r'about|contact|team', re.I))
    add_check(checks, 'Trust Pages Linked', 'pass' if about_link else 'info',
              'Checks for links to About, Contact, or Team pages. These "trust pages" are critical E-E-A-T signals — they prove there are real people behind the website. Google\'s Search Quality Rater Guidelines specifically look for accessible contact and about information',
              'Links to About/Contact/Team pages found' if about_link else 'No links to trust pages detected',
              'Add visible links to your About, Contact, and Team pages in the header, footer, or sidebar navigation. These pages should include real names, photos, credentials, physical address (if applicable), and multiple contact methods', 'Medium', 'E-E-A-T')
    
    # Citations/Sources
    citations = any(p in text.lower() for p in ['according to', 'source:', 'study shows', 'research', 'cited'])
    add_check(checks, 'Source Citations', 'pass' if citations else 'info',
              'Checks for citation language indicating the content references external sources or research. Citing authoritative sources demonstrates thorough research, builds credibility, and aligns with Google\'s emphasis on well-sourced, factual content',
              'Source citations or research references found' if citations else 'No citation language detected in content',
              'Reference authoritative sources throughout your content using phrases like "According to [Source]..." or "Research from [Institution] shows...". Link to the original sources. This is especially important for YMYL topics (health, finance, legal)', 'Medium', 'E-E-A-T')
    
    # Expertise indicators
    expertise = any(p in text.lower() for p in ['years of experience', 'certified', 'expert', 'professional', 'specialist'])
    add_check(checks, 'Expertise Signals', 'pass' if expertise else 'info',
              'Checks for language that demonstrates professional expertise and credentials. Google\'s E-E-A-T framework rewards content that clearly shows the author or organization has relevant qualifications and hands-on experience with the topic',
              'Expertise indicators found (credentials, experience, certifications)' if expertise else 'No explicit expertise signals detected',
              'Include credentials, certifications, years of experience, and professional affiliations in author bios and about pages. Use language that demonstrates first-hand experience: "In my 10 years as an SEO consultant..." rather than generic advice', 'Medium', 'E-E-A-T')
    
    # Contact information
    contact_info = re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', text) or re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text)
    add_check(checks, 'Contact Information', 'pass' if contact_info else 'info',
              'Checks for visible contact information (email addresses, phone numbers) on the page. Accessible contact details are a strong trust signal — they show the business is real and reachable. Google\'s quality raters specifically check for this on YMYL sites',
              'Contact information (email or phone) found on page' if contact_info else 'No contact information detected on this page',
              'Display at least one contact method (email, phone, contact form) on every page, ideally in the header or footer. For local businesses, include full NAP (Name, Address, Phone). Use tel: links for phone numbers and mailto: for emails', 'Medium', 'E-E-A-T')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== MOBILE SEO (15 checks) ==============
def analyze_mobile_seo(url, soup, response, load_time):
    checks = []
    html = str(soup)
    
    # 1-5: Viewport & Responsiveness
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    add_check(checks, 'Viewport Meta Tag', 'pass' if viewport else 'fail',
              'Checks for the viewport meta tag that controls page scaling on mobile devices. Since Google uses mobile-first indexing, this tag is essential — without it, your page renders at desktop width on phones, making it unusable and hurting mobile rankings',
              viewport.get('content', '')[:80] if viewport else 'Missing — page will not display correctly on mobile devices',
              'Add <meta name="viewport" content="width=device-width, initial-scale=1.0"> in your <head> tag. This is the single most important mobile optimization and is required for Google\'s mobile-first indexing', 'Critical', 'Viewport')
    
    viewport_content = viewport.get('content', '') if viewport else ''
    has_width = 'width=' in viewport_content
    add_check(checks, 'Viewport Width', 'pass' if has_width else 'fail',
              'Verifies the viewport tag includes a width directive. The width=device-width setting tells the browser to match the page width to the device screen width, which is the foundation of responsive design',
              'width=device-width is set (correct)' if has_width else 'No width directive — page will not adapt to screen size',
              'Ensure your viewport tag includes width=device-width. Without this, the browser defaults to a virtual viewport of ~980px, causing horizontal scrolling on mobile devices', 'Critical', 'Viewport')
    
    has_scale = 'initial-scale' in viewport_content
    add_check(checks, 'Initial Scale', 'pass' if has_scale else 'warning',
              'Checks for initial-scale=1 in the viewport tag. This sets the initial zoom level when the page first loads. Without it, some mobile browsers may zoom in or out unexpectedly, creating a poor first impression',
              'initial-scale is set' if has_scale else 'initial-scale not specified — browser will choose default zoom',
              'Add initial-scale=1 to your viewport tag: <meta name="viewport" content="width=device-width, initial-scale=1.0">. This ensures the page loads at 100% zoom on all devices', 'High', 'Viewport')
    
    # Check for user-scalable=no (bad for accessibility)
    no_scale = 'user-scalable=no' in viewport_content or 'maximum-scale=1' in viewport_content
    add_check(checks, 'Zoom Enabled', 'pass' if not no_scale else 'warning',
              'Checks whether users can pinch-to-zoom on the page. Disabling zoom (user-scalable=no or maximum-scale=1) is an accessibility violation — visually impaired users rely on zoom to read content. This also fails WCAG 2.1 Success Criterion 1.4.4',
              'Zoom is enabled (accessible)' if not no_scale else 'Zoom is disabled — this is an accessibility violation',
              'Remove user-scalable=no and maximum-scale=1 from your viewport tag. Users must be able to zoom to at least 200% for accessibility compliance. Your responsive design should handle zoom gracefully', 'Medium', 'Viewport')
    
    # Check for responsive CSS
    media_queries = '@media' in html
    add_check(checks, 'Media Queries', 'pass' if media_queries else 'warning',
              'Checks for CSS @media queries that adapt the layout to different screen sizes. Media queries are the core mechanism of responsive web design, allowing you to adjust layouts, font sizes, and element visibility based on device width',
              'CSS media queries found (responsive design detected)' if media_queries else 'No media queries found — layout may not adapt to different screen sizes',
              'Implement CSS media queries for key breakpoints: @media (max-width: 768px) for tablets, @media (max-width: 480px) for phones. Adjust grid layouts, font sizes, padding, and navigation for each breakpoint', 'High', 'Responsiveness')
    
    # 6-10: Touch & Mobile UX
    buttons = soup.find_all(['button', 'a'])
    small_targets = [b for b in buttons if b.get('style') and ('font-size: 1' in b.get('style', '') or 'padding: 0' in b.get('style', ''))]
    add_check(checks, 'Touch Targets', 'pass' if len(small_targets) < len(buttons) * 0.1 else 'warning',
              'Checks for adequately sized touch targets (buttons, links). Google requires a minimum 48x48px touch target size. Small targets cause accidental taps, frustrate users, and are flagged as mobile usability issues in Google Search Console',
              f'{len(buttons) - len(small_targets)} of {len(buttons)} interactive elements appear touch-friendly',
              'Ensure all buttons and links have a minimum size of 48x48 CSS pixels with at least 8px spacing between targets. Use padding to increase tap area without changing visual size. Test with Chrome DevTools mobile emulator', 'Medium', 'Touch UX')
    
    flash = soup.find_all(['object', 'embed'])
    flash_content = [f for f in flash if 'flash' in str(f).lower() or 'swf' in str(f).lower()]
    add_check(checks, 'No Flash Content', 'pass' if not flash_content else 'fail',
              'Checks for Flash (SWF) content that is completely unsupported on mobile devices. Flash was discontinued in 2020 and no modern browser supports it. Any Flash content is invisible to all mobile users and most desktop users',
              f'{len(flash_content)} Flash elements found' if flash_content else 'No Flash content (correct — Flash is obsolete)',
              'Replace all Flash content with HTML5, CSS3, and JavaScript alternatives. Use <video> for video, CSS animations for effects, and JavaScript for interactivity. Flash content is completely invisible to modern browsers', 'Critical', 'Mobile Compatibility')
    
    frames = soup.find_all(['frame', 'frameset'])
    add_check(checks, 'No Frames', 'pass' if not frames else 'fail',
              'Checks for HTML frames/framesets which are obsolete and poorly supported on mobile devices. Frames break mobile navigation, prevent proper indexing by search engines, and create accessibility barriers',
              f'{len(frames)} frame elements found' if frames else 'No frames (correct — frames are obsolete)',
              'Replace framesets with modern CSS layouts (flexbox, grid) and use iframes only when necessary (e.g., embedding maps or videos). Frames have been deprecated since HTML5', 'High', 'Mobile Compatibility')
    
    fixed_width = re.findall(r'width:\s*\d{4,}px', html)
    add_check(checks, 'No Fixed Width', 'pass' if not fixed_width else 'warning',
              'Checks for CSS elements with fixed widths of 1000px or more. Fixed-width elements wider than the mobile viewport cause horizontal scrolling, which is a major mobile usability issue flagged by Google Search Console',
              f'{len(fixed_width)} elements with fixed widths over 1000px' if fixed_width else 'No oversized fixed-width elements found',
              'Replace fixed pixel widths with responsive units: use max-width: 100%, width: 100%, or percentage-based widths. For containers, use max-width instead of width to allow shrinking on smaller screens', 'Medium', 'Responsiveness')
    
    small_fonts = re.findall(r'font-size:\s*[0-9]px', html)
    add_check(checks, 'Readable Font Size', 'pass' if len(small_fonts) < 3 else 'warning',
              'Checks for font sizes under 10px which are unreadable on mobile devices without zooming. Google recommends a base font size of 16px for body text on mobile. Small fonts are flagged as mobile usability issues in Search Console',
              f'{len(small_fonts)} elements with very small font sizes (under 10px)' if small_fonts else 'All font sizes appear readable',
              'Set your base body font size to 16px minimum. Use relative units (rem, em) instead of pixels so text scales properly. Ensure all text is readable without zooming on a 320px-wide screen', 'Medium', 'Readability')
    
    # 11-15: Mobile Performance
    images = soup.find_all('img')
    lazy_imgs = [i for i in images if i.get('loading') == 'lazy']
    add_check(checks, 'Image Lazy Loading', 'pass' if lazy_imgs or len(images) <= 3 else 'warning',
              'Checks for loading="lazy" on images, which is critical for mobile performance. Mobile users often have slower connections and data limits. Lazy loading defers off-screen images, reducing initial page weight by 40-60% on image-heavy pages',
              f'{len(lazy_imgs)} of {len(images)} images use lazy loading',
              'Add loading="lazy" to all images below the fold. Do NOT lazy-load the first visible image (LCP element). This is a native browser feature requiring no JavaScript: <img src="photo.jpg" loading="lazy" alt="...">', 'High', 'Mobile Performance')
    
    html_size = len(response.content) / 1024
    add_check(checks, 'Page Weight', 'pass' if html_size < 100 else 'warning',
              'Measures the HTML document size in kilobytes. On mobile networks (3G/4G), every kilobyte matters. Pages over 100KB of HTML take noticeably longer to parse and render, especially on lower-end mobile devices with limited processing power',
              f'{html_size:.1f} KB HTML document size (target: under 100KB)',
              'Reduce HTML size by removing inline styles, unnecessary comments, whitespace, and unused code. Minify HTML in production. Consider server-side rendering optimizations and removing redundant wrapper elements', 'Medium', 'Mobile Performance')
    
    amp_link = soup.find('link', rel='amphtml')
    add_check(checks, 'AMP Version', 'info',
              'Checks for an AMP (Accelerated Mobile Pages) version of the page. AMP pages load near-instantly on mobile by using a stripped-down HTML framework. While AMP is no longer required for Top Stories, it still provides performance benefits for content-heavy sites',
              'AMP version available' if amp_link else 'No AMP version detected',
              'AMP is optional but can improve mobile performance for news and content sites. If implemented, ensure the AMP version has equivalent content to the canonical page. Google no longer requires AMP for Top Stories carousel placement', 'Low', 'Mobile Performance')
    
    # Check for mobile app links
    app_links = soup.find_all('meta', property=re.compile(r'al:(ios|android)'))
    add_check(checks, 'App Deep Links', 'info',
              'Checks for App Links meta tags that connect web pages to corresponding screens in iOS/Android apps. Deep linking improves user experience by opening content directly in the app when installed, and helps with app indexing in search results',
              f'{len(app_links)} app deep link meta tags found',
              'If you have a mobile app, add App Links meta tags: <meta property="al:ios:url" content="myapp://page"> and <meta property="al:android:url" content="myapp://page">. This enables seamless web-to-app transitions', 'Low', 'Mobile Integration')
    
    # Check for tel: links
    tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
    add_check(checks, 'Click-to-Call', 'pass' if tel_links else 'info',
              'Checks for tel: links that allow mobile users to call with a single tap. Studies show 88% of local mobile searches result in a call or visit within 24 hours. Click-to-call links remove friction and are essential for businesses that take phone calls',
              f'{len(tel_links)} click-to-call links found',
              'Add tel: links for all phone numbers: <a href="tel:+15551234567">Call (555) 123-4567</a>. Place them prominently in the header, contact section, and footer. On mobile, these trigger the phone dialer directly', 'Medium', 'Mobile UX')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== PERFORMANCE SEO (18 checks) ==============
def analyze_performance_seo(url, soup, response, load_time):
    checks = []
    html = str(soup)
    
    # 1-5: Core Web Vitals Indicators
    add_check(checks, 'Page Load Time', 'pass' if load_time < 2 else ('warning' if load_time < 4 else 'fail'),
              'Measures the server response time (Time to First Byte). This is a Core Web Vital indicator — Google uses page speed as a ranking factor. Pages loading in under 2 seconds provide good user experience; over 4 seconds causes 25% of users to abandon the page',
              f'{load_time:.2f} seconds (target: under 2s, critical threshold: 4s)',
              'Optimize server response time by enabling caching, using a CDN, optimizing database queries, and upgrading hosting. Consider server-side rendering (SSR) or static site generation (SSG) for content pages. Use tools like WebPageTest for detailed analysis', 'Critical', 'Core Web Vitals')
    
    html_size = len(response.content) / 1024
    add_check(checks, 'HTML Size', 'pass' if html_size < 100 else ('warning' if html_size < 200 else 'fail'),
              'Measures the raw HTML document size. Large HTML files take longer to download and parse, directly impacting First Contentful Paint (FCP) and Largest Contentful Paint (LCP). This is especially impactful on mobile networks',
              f'{html_size:.1f} KB (target: under 100KB, warning: over 200KB)',
              'Reduce HTML size by minifying output, removing inline CSS/JS, eliminating unnecessary comments and whitespace, and using server-side compression. Consider code-splitting for single-page applications', 'High', 'Core Web Vitals')
    
    # CLS indicators - images without dimensions
    images = soup.find_all('img')
    imgs_dims = [i for i in images if i.get('width') and i.get('height')]
    cls_risk = len(images) - len(imgs_dims)
    add_check(checks, 'CLS Prevention', 'pass' if cls_risk == 0 or not images else 'warning',
              'Checks for images with explicit width/height attributes to prevent Cumulative Layout Shift (CLS). CLS is a Core Web Vital — when images load without reserved space, page content jumps around, frustrating users and hurting rankings',
              f'{len(imgs_dims)} of {len(images)} images have dimensions set. {cls_risk} images risk causing layout shift' if images else 'No images found',
              'Add width and height attributes to all <img> tags. The browser uses these to reserve space before the image loads, preventing layout shift. CSS can still make images responsive with max-width: 100%; height: auto;', 'High', 'Core Web Vitals')
    
    # LCP indicators
    large_media = soup.find_all(['img', 'video'])[:3]
    preload = soup.find_all('link', rel='preload')
    add_check(checks, 'LCP Optimization', 'pass' if preload else 'info',
              'Checks for <link rel="preload"> hints that tell the browser to prioritize loading critical resources. Preloading the Largest Contentful Paint (LCP) element (usually the hero image or main heading font) can improve LCP by 200-500ms',
              f'{len(preload)} preload hints found',
              'Identify your LCP element (usually the hero image or largest text block) and preload it: <link rel="preload" as="image" href="hero.webp">. Also preload critical fonts and above-the-fold CSS. Use Chrome DevTools Performance tab to identify the LCP element', 'High', 'Core Web Vitals')
    
    # INP/FID indicators
    js_files = soup.find_all('script', src=True)
    async_defer = [s for s in js_files if s.get('async') or s.get('defer')]
    add_check(checks, 'Non-blocking JS', 'pass' if len(async_defer) >= len(js_files) * 0.5 or not js_files else 'warning',
              'Checks whether JavaScript files use async or defer attributes. Render-blocking scripts prevent the page from displaying until they finish downloading and executing, directly impacting Interaction to Next Paint (INP) and First Input Delay (FID)',
              f'{len(async_defer)} of {len(js_files)} scripts use async/defer (non-blocking)',
              'Add async or defer to all non-critical scripts. Use defer for scripts that depend on DOM: <script src="app.js" defer>. Use async for independent scripts like analytics: <script src="analytics.js" async>. Move critical JS inline in <head>', 'High', 'Core Web Vitals')
    
    # 6-10: Compression & Caching
    encoding = response.headers.get('Content-Encoding', '')
    add_check(checks, 'Compression', 'pass' if encoding in ['gzip', 'br', 'deflate'] else 'warning',
              'Checks whether the server compresses responses using gzip or Brotli. Compression typically reduces transfer size by 60-80%, dramatically improving load times. Brotli (br) offers 15-20% better compression than gzip for text content',
              f'Compression: {encoding}' if encoding else 'No compression detected — responses are sent uncompressed',
              'Enable Brotli (preferred) or gzip compression on your server. In Nginx: gzip on; gzip_types text/html text/css application/javascript; In Apache: AddOutputFilterByType DEFLATE text/html text/css application/javascript', 'High', 'Compression')
    
    cache_control = response.headers.get('Cache-Control', '')
    add_check(checks, 'Cache Headers', 'pass' if cache_control else 'warning',
              'Checks for Cache-Control headers that tell browsers how long to store resources locally. Proper caching means returning visitors load pages instantly from their local cache instead of re-downloading everything from the server',
              f'Cache-Control: {cache_control[:80]}' if cache_control else 'No Cache-Control header — browser will re-download resources on every visit',
              'Set Cache-Control headers: for static assets (CSS, JS, images) use max-age=31536000 (1 year) with versioned filenames. For HTML pages use max-age=3600 or no-cache with ETag for freshness validation', 'Medium', 'Caching')
    
    etag = response.headers.get('ETag', '')
    add_check(checks, 'ETag Header', 'pass' if etag else 'info',
              'Checks for ETag headers that enable efficient cache validation. When a cached resource expires, the browser sends the ETag back to the server — if the resource has not changed, the server responds with 304 Not Modified (no download needed)',
              'ETag header present (enables efficient cache revalidation)' if etag else 'No ETag header set',
              'Enable ETag headers on your server for cache validation. ETags work with Cache-Control to minimize unnecessary downloads. Most web servers (Nginx, Apache) generate ETags automatically — ensure they are not disabled', 'Low', 'Caching')
    
    expires = response.headers.get('Expires', '')
    add_check(checks, 'Expires Header', 'pass' if expires or cache_control else 'info',
              'Checks for the Expires header that sets an absolute expiration date for cached resources. While Cache-Control max-age is preferred (relative time), Expires provides backward compatibility with older HTTP/1.0 clients and CDN edge servers',
              'Expires header set' if expires else ('Cache-Control is set (Expires not needed)' if cache_control else 'No expiration headers — resources are not cached'),
              'If not using Cache-Control, set Expires headers for static assets. Cache-Control max-age takes precedence when both are present. For most setups, Cache-Control alone is sufficient', 'Low', 'Caching')
    
    # 11-15: Resource Optimization
    css_files = soup.find_all('link', rel='stylesheet')
    add_check(checks, 'CSS Files Count', 'pass' if len(css_files) <= 5 else 'warning',
              'Counts external CSS stylesheet files. Each CSS file requires a separate HTTP request, and stylesheets are render-blocking by default — the browser cannot display the page until all CSS is downloaded and parsed. Fewer files means faster rendering',
              f'{len(css_files)} external CSS files (target: 5 or fewer)',
              'Combine multiple CSS files into one or two bundles. Inline critical above-the-fold CSS in the <head> and load the rest asynchronously. Use CSS minification to reduce file sizes. Consider using a build tool like Webpack or Vite', 'Medium', 'Resources')
    
    add_check(checks, 'JS Files Count', 'pass' if len(js_files) <= 10 else 'warning',
              'Counts external JavaScript files. Each script file adds an HTTP request and potential render-blocking time. Excessive scripts increase page weight, slow down parsing, and can cause JavaScript execution bottlenecks on mobile devices',
              f'{len(js_files)} external JavaScript files (target: 10 or fewer)',
              'Bundle JavaScript files using a module bundler (Webpack, Rollup, Vite). Remove unused libraries. Use code-splitting to load only the JavaScript needed for the current page. Defer non-critical scripts with the defer attribute', 'Medium', 'Resources')
    
    inline_styles = soup.find_all(style=True)
    add_check(checks, 'Inline Styles', 'pass' if len(inline_styles) < 20 else 'warning',
              'Counts elements with inline style attributes. Excessive inline styles increase HTML size, cannot be cached separately, and make maintenance difficult. They also prevent Content Security Policy (CSP) from blocking injected styles',
              f'{len(inline_styles)} elements with inline styles (target: under 20)',
              'Move inline styles to external CSS files or <style> blocks. This enables browser caching, reduces HTML size, and improves maintainability. Exception: critical above-the-fold styles can be inlined in <head> for performance', 'Low', 'Resources')
    
    preconnect = soup.find_all('link', rel='preconnect')
    add_check(checks, 'Preconnect Hints', 'pass' if preconnect else 'info',
              'Checks for <link rel="preconnect"> tags that establish early connections to important third-party domains. Preconnect saves 100-300ms per domain by completing DNS lookup, TCP handshake, and TLS negotiation before the resource is actually needed',
              f'{len(preconnect)} preconnect hints found',
              'Add preconnect for your most important third-party domains (fonts, CDN, analytics): <link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>. Limit to 4-6 domains — too many preconnects waste resources', 'Medium', 'Resource Hints')
    
    dns_prefetch = soup.find_all('link', rel='dns-prefetch')
    add_check(checks, 'DNS Prefetch', 'pass' if dns_prefetch or preconnect else 'info',
              'Checks for <link rel="dns-prefetch"> tags that resolve domain names before they are needed. DNS resolution typically takes 20-120ms per domain. Prefetching eliminates this delay for third-party resources loaded later in the page',
              f'{len(dns_prefetch)} dns-prefetch hints found',
              'Add dns-prefetch for third-party domains used on the page: <link rel="dns-prefetch" href="//cdn.example.com">. This is lighter than preconnect and suitable for domains where you are less certain the connection will be used', 'Low', 'Resource Hints')
    
    # 16-18: Image Optimization
    lazy_imgs = [i for i in images if i.get('loading') == 'lazy']
    add_check(checks, 'Lazy Loading', 'pass' if lazy_imgs or len(images) <= 3 else 'warning',
              'Checks for native lazy loading on images. Images are typically the heaviest resources on a page. Lazy loading defers downloading off-screen images until the user scrolls near them, reducing initial page weight and improving LCP',
              f'{len(lazy_imgs)} of {len(images)} images use lazy loading',
              'Add loading="lazy" to all below-the-fold images. Do NOT lazy-load the LCP image (hero/banner). Native lazy loading requires no JavaScript: <img src="photo.jpg" loading="lazy" alt="...">. This alone can reduce initial page weight by 40-60%', 'High', 'Images')
    
    srcset_imgs = [i for i in images if i.get('srcset')]
    add_check(checks, 'Responsive Images', 'pass' if srcset_imgs or len(images) <= 2 else 'info',
              'Checks for srcset attributes that serve appropriately sized images based on device screen size. Without responsive images, mobile users download full-resolution desktop images — often 3-5x larger than needed, wasting bandwidth and slowing load times',
              f'{len(srcset_imgs)} of {len(images)} images use srcset',
              'Generate multiple image sizes and use srcset: <img srcset="small.jpg 400w, medium.jpg 800w, large.jpg 1200w" sizes="(max-width: 600px) 400px, 800px" src="medium.jpg">. Many CDNs and CMS platforms can auto-generate responsive variants', 'Medium', 'Images')
    
    webp = [i for i in images if '.webp' in str(i.get('src', ''))]
    add_check(checks, 'WebP Images', 'pass' if webp or not images else 'info',
              'Checks for WebP image format usage. WebP provides 25-35% smaller file sizes than JPEG and 26% smaller than PNG at equivalent quality. Supported by all modern browsers, WebP is the recommended format for web images in 2026',
              f'{len(webp)} of {len(images)} images use WebP format',
              'Convert images to WebP using tools like Squoosh, cwebp, or your CDN\'s auto-conversion. Use <picture> for fallback: <picture><source srcset="img.webp" type="image/webp"><img src="img.jpg"></picture>. Consider AVIF for even better compression', 'Medium', 'Images')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== SECURITY SEO (12 checks) ==============
def analyze_security_seo(url, soup, response, load_time):
    checks = []
    parsed = urlparse(url)
    html = str(soup)
    
    # 1-4: HTTPS & SSL
    add_check(checks, 'HTTPS Protocol', 'pass' if parsed.scheme == 'https' else 'fail',
              'Checks whether the site uses HTTPS (TLS/SSL encryption) for all connections. HTTPS is a confirmed Google ranking factor and protects user data in transit. Without it, browsers display "Not Secure" warnings that destroy user trust.',
              f'Protocol: {parsed.scheme.upper()} — {"Encrypted connection verified" if parsed.scheme == "https" else "WARNING: Unencrypted HTTP detected"}',
              'Enable HTTPS immediately: 1) Get a free SSL certificate from Let\'s Encrypt (certbot). 2) Configure your web server to serve over port 443. 3) Set up automatic certificate renewal. 4) Update all internal links to use https://.',
              'Critical', 'HTTPS')
    
    # Check for HTTP links on HTTPS page
    if parsed.scheme == 'https':
        http_links = soup.find_all(href=re.compile(r'^http://'))
        http_src = soup.find_all(src=re.compile(r'^http://'))
        mixed_content = len(http_links) + len(http_src)
        add_check(checks, 'No Mixed Content', 'pass' if mixed_content == 0 else 'warning',
                  'Detects insecure HTTP resources (images, scripts, stylesheets) loaded on an HTTPS page. Mixed content triggers browser warnings, breaks the padlock icon, and can expose users to man-in-the-middle attacks.',
                  f'{mixed_content} insecure HTTP resources found on this HTTPS page — {"Clean: no mixed content detected" if mixed_content == 0 else "These resources are loaded over unencrypted HTTP"}',
                  'Fix all mixed content: 1) Search your HTML/CSS for http:// URLs and change them to https:// or protocol-relative //. 2) Update any hardcoded asset URLs in your CMS. 3) Use Content-Security-Policy: upgrade-insecure-requests as a safety net. 4) Test with browser DevTools > Console for remaining warnings.',
                  'High', 'HTTPS')
    else:
        add_check(checks, 'No Mixed Content', 'fail',
                  'Cannot check for mixed content because the site itself is not served over HTTPS. Mixed content analysis requires an HTTPS base page to detect insecure sub-resources.',
                  'Site not on HTTPS — mixed content check not applicable until HTTPS is enabled',
                  'Enable HTTPS first, then re-run this audit to check for mixed content issues.',
                  'High', 'HTTPS')
    
    # Check for secure cookies
    cookies = response.headers.get('Set-Cookie', '')
    secure_cookie = 'Secure' in cookies if cookies else True
    add_check(checks, 'Secure Cookies', 'pass' if secure_cookie else 'warning',
              'Verifies that cookies include the Secure flag, which ensures they are only sent over HTTPS connections. Without this flag, cookies (including session tokens) can be intercepted on insecure networks, enabling session hijacking attacks.',
              f'{"Secure flag detected on cookies — cookies only transmitted over HTTPS" if secure_cookie else "WARNING: Cookies missing Secure flag — vulnerable to interception on HTTP connections"}',
              'Add the Secure flag to all cookies: 1) In your server config, set cookie attributes to include Secure and HttpOnly. 2) Also add SameSite=Lax or SameSite=Strict to prevent CSRF. 3) For session cookies, use: Set-Cookie: session=abc123; Secure; HttpOnly; SameSite=Lax.',
              'Medium', 'HTTPS')
    
    # HTTP to HTTPS redirect check
    add_check(checks, 'HTTPS Redirect', 'pass' if parsed.scheme == 'https' else 'warning',
              'Checks whether HTTP requests are automatically redirected to HTTPS using a 301 permanent redirect. Without this redirect, users who type your domain without https:// will land on an insecure version, and search engines may index duplicate HTTP/HTTPS pages.',
              f'{"Site accessed via HTTPS — redirect likely in place" if parsed.scheme == "https" else "Site accessed via HTTP — no automatic HTTPS redirect detected"}',
              'Set up a 301 redirect from HTTP to HTTPS: 1) In Nginx: add "return 301 https://$server_name$request_uri;" in the port 80 server block. 2) In Apache: use RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]. 3) Test by visiting http://yoursite.com and confirming it redirects.',
              'High', 'HTTPS')
    
    # 5-8: Security Headers
    hsts = response.headers.get('Strict-Transport-Security', '')
    add_check(checks, 'HSTS Header', 'pass' if hsts else 'warning',
              'Checks for the Strict-Transport-Security (HSTS) header, which tells browsers to always use HTTPS for your domain. Once set, browsers will refuse to connect over HTTP even if a user types http://. This prevents SSL-stripping attacks and protocol downgrade attacks.',
              f'{"HSTS enabled: " + hsts[:100] if hsts else "HSTS header not set — browsers will still allow HTTP connections"}',
              'Enable HSTS: 1) Add header: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload. 2) Start with a short max-age (300) to test, then increase to 31536000 (1 year). 3) Once stable, submit to hstspreload.org for browser preload list inclusion.',
              'High', 'Security Headers')
    
    xcto = response.headers.get('X-Content-Type-Options', '')
    add_check(checks, 'X-Content-Type-Options', 'pass' if xcto == 'nosniff' else 'warning',
              'Checks for the X-Content-Type-Options: nosniff header, which prevents browsers from MIME-sniffing a response away from the declared Content-Type. Without it, browsers may interpret files as executable scripts, enabling XSS attacks through uploaded files.',
              f'{"Protected: X-Content-Type-Options set to nosniff" if xcto == "nosniff" else "Missing or incorrect — value is: " + (xcto or "not set")}',
              'Add this header to your server config: 1) Nginx: add_header X-Content-Type-Options "nosniff" always; 2) Apache: Header always set X-Content-Type-Options "nosniff". 3) This is a simple, zero-risk header — add it immediately.',
              'Medium', 'Security Headers')
    
    xfo = response.headers.get('X-Frame-Options', '')
    add_check(checks, 'X-Frame-Options', 'pass' if xfo else 'warning',
              'Checks for the X-Frame-Options header, which prevents your site from being embedded in iframes on other domains. Without it, attackers can overlay your site in a hidden iframe to trick users into clicking malicious elements (clickjacking).',
              f'{"Clickjacking protection active: " + xfo if xfo else "X-Frame-Options not set — site can be embedded in iframes on any domain"}',
              'Add clickjacking protection: 1) Nginx: add_header X-Frame-Options "SAMEORIGIN" always; 2) Use SAMEORIGIN to allow your own iframes, or DENY to block all framing. 3) For modern browsers, also use CSP frame-ancestors directive as a more flexible alternative.',
              'Medium', 'Security Headers')
    
    csp = response.headers.get('Content-Security-Policy', '')
    add_check(checks, 'Content-Security-Policy', 'pass' if csp else 'info',
              'Checks for a Content-Security-Policy (CSP) header, which controls which resources (scripts, styles, images) the browser is allowed to load. CSP is the most powerful defense against XSS attacks, as it prevents unauthorized script execution even if an attacker injects code.',
              f'{"CSP configured: " + csp[:150] if csp else "No Content-Security-Policy header detected — no restrictions on resource loading"}',
              'Implement CSP gradually: 1) Start with Content-Security-Policy-Report-Only to monitor without breaking anything. 2) Begin with: default-src \'self\'; script-src \'self\'; style-src \'self\' \'unsafe-inline\'. 3) Review violation reports and whitelist legitimate sources. 4) Switch from Report-Only to enforcing once stable.',
              'Medium', 'Security Headers')
    
    # 9-12: Additional Security
    referrer = response.headers.get('Referrer-Policy', '')
    add_check(checks, 'Referrer-Policy', 'pass' if referrer else 'info',
              'Checks for the Referrer-Policy header, which controls how much URL information is sent to other sites when users click links. Without it, full URLs (including query parameters with sensitive data) may leak to third-party sites via the Referer header.',
              f'{"Referrer-Policy set: " + referrer if referrer else "No Referrer-Policy header — full URLs may be sent to external sites"}',
              'Set a Referrer-Policy: 1) Recommended: strict-origin-when-cross-origin (sends origin only to cross-origin, full URL to same-origin). 2) For maximum privacy: no-referrer. 3) Add via server config: add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
              'Low', 'Security Headers')
    
    permissions = response.headers.get('Permissions-Policy', '') or response.headers.get('Feature-Policy', '')
    add_check(checks, 'Permissions-Policy', 'pass' if permissions else 'info',
              'Checks for the Permissions-Policy header (formerly Feature-Policy), which controls which browser features (camera, microphone, geolocation, payment) your site and embedded iframes can access. This limits the attack surface if third-party scripts are compromised.',
              f'{"Permissions-Policy configured: " + (permissions[:120] if permissions else "") if permissions else "No Permissions-Policy header — all browser features available to scripts and iframes"}',
              'Configure Permissions-Policy: 1) Disable features you don\'t use: Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(). 2) Allow only for your origin if needed: camera=(self). 3) Add via Nginx: add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;',
              'Low', 'Security Headers')
    
    # Check for password fields
    password_fields = soup.find_all('input', {'type': 'password'})
    add_check(checks, 'Secure Login Forms', 'pass' if not password_fields or parsed.scheme == 'https' else 'fail',
              'Checks whether any login forms with password fields are served over HTTPS. Transmitting passwords over unencrypted HTTP exposes credentials to anyone monitoring the network. This is a critical security vulnerability that can lead to account compromise.',
              f'{len(password_fields)} password field(s) found — {"all served securely over HTTPS" if parsed.scheme == "https" else "WARNING: served over insecure HTTP — credentials exposed in plaintext"}',
              'Secure all login forms immediately: 1) Enable HTTPS site-wide (see HTTPS Protocol check above). 2) Ensure login pages specifically use https:// in form action URLs. 3) Add HSTS to prevent any HTTP fallback. 4) Consider adding autocomplete="current-password" for password manager support.',
              'Critical', 'Forms')
    
    # Check for external scripts from untrusted sources
    external_scripts = soup.find_all('script', src=re.compile(r'^https?://'))
    trusted_domains = ['google', 'facebook', 'twitter', 'cloudflare', 'jquery', 'bootstrap', 'cdn']
    untrusted = [s for s in external_scripts if not any(t in str(s.get('src', '')) for t in trusted_domains)]
    add_check(checks, 'Trusted Scripts', 'pass' if len(untrusted) < 3 else 'warning',
              'Analyzes external JavaScript sources loaded on the page and flags scripts from unrecognized domains. Third-party scripts have full access to your page DOM and user data. Compromised or malicious scripts can steal credentials, inject ads, or redirect users.',
              f'{len(external_scripts)} external scripts total, {len(untrusted)} from unrecognized sources{" — " + ", ".join([s.get("src", "")[:60] for s in untrusted[:3]]) if untrusted else ""}',
              'Review all external scripts: 1) Audit each script source — remove any you don\'t recognize or no longer need. 2) Add Subresource Integrity (SRI) hashes: <script src="..." integrity="sha384-..." crossorigin="anonymous">. 3) Use CSP to whitelist only approved script sources. 4) Consider self-hosting critical third-party scripts.',
              'Medium', 'Scripts')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== SOCIAL SEO (25 checks) ==============
def analyze_social_seo(url, soup, response, load_time):
    """
    Enhanced Social SEO analysis based on 2026 best practices:
    - Open Graph optimization for Facebook, LinkedIn, WhatsApp
    - Twitter/X Cards for maximum engagement
    - Social schema markup (sameAs)
    - Platform-specific image requirements
    - Social proof and engagement signals
    """
    checks = []
    html = str(soup)
    parsed = urlparse(url)
    
    # ===== 1-8: Open Graph Core Tags =====
    og_title = soup.find('meta', property='og:title')
    og_title_content = og_title.get('content', '') if og_title else ''
    add_check(checks, 'OG Title', 'pass' if og_title else 'fail',
              'Checks for the og:title meta tag, which controls the headline displayed when your page is shared on Facebook, LinkedIn, WhatsApp, and other platforms. Without it, platforms auto-generate a title from your page content, often producing ugly or misleading previews that reduce click-through rates.',
              f'{"Found: " + (og_title_content[:80] + "..." if len(og_title_content) > 80 else og_title_content) if og_title else "MISSING — social shares will use auto-generated title"}',
              'Add <meta property="og:title" content="Your Compelling Title"> in the <head>. 1) Keep it 40-60 characters for full display. 2) Front-load your primary keyword. 3) Make it different from your <title> tag if needed — og:title can be more engaging/clickable.',
              'Critical', 'Open Graph')
    
    # OG Title length optimization (40-60 chars ideal)
    add_check(checks, 'OG Title Length', 'pass' if 40 <= len(og_title_content) <= 60 else 'warning',
              'Evaluates whether the og:title length falls within the optimal 40-60 character range. Titles under 40 characters waste valuable preview space, while titles over 60 characters get truncated on most platforms, cutting off your message mid-sentence.',
              f'{len(og_title_content)} characters — {"within optimal 40-60 range" if 40 <= len(og_title_content) <= 60 else ("too short, wasting preview space" if len(og_title_content) < 40 else "may be truncated on some platforms")}',
              'Optimize to 40-60 characters: 1) Facebook truncates at ~88 chars but shows best at 40-60. 2) LinkedIn truncates at ~70 chars. 3) WhatsApp shows even fewer. 4) Test your preview at metatags.io or opengraph.xyz.',
              'Medium', 'Open Graph')
    
    og_desc = soup.find('meta', property='og:description')
    og_desc_content = og_desc.get('content', '') if og_desc else ''
    add_check(checks, 'OG Description', 'pass' if og_desc else 'fail',
              'Checks for the og:description meta tag, which provides the preview text shown below the title when your page is shared on social media. This is your chance to write compelling copy that convinces people to click through from their social feed.',
              f'{"Found: " + (og_desc_content[:100] + "..." if len(og_desc_content) > 100 else og_desc_content) if og_desc else "MISSING — platforms will auto-extract text, often poorly"}',
              'Add <meta property="og:description" content="...">. 1) Write 100-200 characters of compelling preview text. 2) Include a call-to-action. 3) Don\'t just copy your meta description — tailor it for social engagement.',
              'Critical', 'Open Graph')
    
    # OG Description length (155-200 chars ideal)
    add_check(checks, 'OG Description Length', 'pass' if 100 <= len(og_desc_content) <= 200 else 'warning',
              'Evaluates whether the og:description length is optimized for social platform display. Descriptions under 100 characters look sparse in previews, while those over 200 characters get cut off, potentially losing your call-to-action.',
              f'{len(og_desc_content)} characters — {"within optimal 100-200 range" if 100 <= len(og_desc_content) <= 200 else ("too short for impactful preview" if len(og_desc_content) < 100 else "may be truncated on some platforms")}',
              'Optimize to 100-200 characters: 1) Facebook shows ~300 chars but 100-200 is the sweet spot. 2) LinkedIn shows ~100 chars in feed. 3) Include value proposition + CTA within first 100 chars.',
              'Medium', 'Open Graph')
    
    og_image = soup.find('meta', property='og:image')
    og_image_url = og_image.get('content', '') if og_image else ''
    add_check(checks, 'OG Image', 'pass' if og_image else 'fail',
              'Checks for the og:image meta tag, which sets the preview image displayed in social shares. Posts with images get 2-3x more engagement than text-only posts. Without og:image, platforms either show no image or grab a random one from your page.',
              f'{"Found: " + (og_image_url[:100] + "..." if len(og_image_url) > 100 else og_image_url) if og_image else "MISSING — social shares will have no image or a random one"}',
              'Add <meta property="og:image" content="https://yoursite.com/image.jpg">. 1) Use 1200x630px for Facebook/LinkedIn (1.91:1 ratio). 2) Keep file size under 8MB. 3) Use JPG or PNG format. 4) Use an absolute URL starting with https://.',
              'Critical', 'Open Graph')
    
    # Check if OG image is absolute URL
    og_image_absolute = og_image_url.startswith('http') if og_image_url else False
    add_check(checks, 'OG Image Absolute URL', 'pass' if og_image_absolute or not og_image else 'warning',
              'Verifies that the og:image URL is absolute (starts with https://). Social platforms fetch images from external servers and cannot resolve relative paths like /images/og.jpg. A relative URL means your image will never display in social previews.',
              f'{"Absolute URL — platforms can fetch this image" if og_image_absolute else "Relative or missing URL — social platforms cannot resolve this path"}',
              'Use a full absolute URL: 1) Change from /images/og.jpg to https://yoursite.com/images/og.jpg. 2) Ensure the URL is accessible without authentication. 3) Test by pasting the image URL directly in a browser.',
              'High', 'Open Graph')
    
    og_url = soup.find('meta', property='og:url')
    add_check(checks, 'OG URL', 'pass' if og_url else 'warning',
              'Checks for the og:url meta tag, which tells social platforms the canonical URL for this content. Without it, shares from different URL variations (with/without www, query params, etc.) are tracked separately, splitting your engagement metrics.',
              f'{"Set: " + (og_url.get("content", "")[:80] if og_url else "") if og_url else "Not set — share counts may be split across URL variations"}',
              'Add <meta property="og:url" content="https://yoursite.com/page">. 1) Use the same URL as your canonical tag. 2) Don\'t include query parameters or tracking codes. 3) This consolidates all share counts to one URL.',
              'Medium', 'Open Graph')
    
    og_type = soup.find('meta', property='og:type')
    og_type_content = og_type.get('content', '') if og_type else ''
    valid_types = ['website', 'article', 'product', 'profile', 'video.other', 'music.song']
    add_check(checks, 'OG Type', 'pass' if og_type_content in valid_types else ('warning' if og_type else 'info'),
              'Checks for the og:type meta tag, which tells platforms what kind of content this is. Different types unlock different preview formats — "article" shows author and publish date, "product" can show price, "video" enables inline playback.',
              f'{"Type: " + og_type_content if og_type_content else "Not set — defaults to website type"}',
              'Set og:type based on your content: 1) Use "website" for homepages. 2) Use "article" for blog posts (enables article:author, article:published_time). 3) Use "product" for product pages. 4) Add as: <meta property="og:type" content="website">.',
              'Medium', 'Open Graph')
    
    # ===== 9-10: OG Advanced Tags =====
    og_site_name = soup.find('meta', property='og:site_name')
    add_check(checks, 'OG Site Name', 'pass' if og_site_name else 'info',
              'Checks for the og:site_name meta tag, which displays your brand name alongside the page title in social previews. This helps users identify the source of shared content and builds brand recognition across social platforms.',
              f'{"Brand: " + og_site_name.get("content", "")[:50] if og_site_name else "Not set — shared content won\'t show your brand name"}',
              'Add <meta property="og:site_name" content="Your Brand Name">. This appears as small text above or below the title in social previews, reinforcing brand identity with every share.',
              'Low', 'Open Graph')
    
    og_locale = soup.find('meta', property='og:locale')
    add_check(checks, 'OG Locale', 'pass' if og_locale else 'info',
              'Checks for the og:locale meta tag, which specifies the language and region of your content (e.g., en_US, fr_FR). This helps social platforms serve your content to the right audience and is essential for multilingual sites targeting different markets.',
              f'{"Locale: " + og_locale.get("content", "") if og_locale else "Not set — defaults to en_US on most platforms"}',
              'Add <meta property="og:locale" content="en_US">. For multilingual sites, also add og:locale:alternate for each additional language to enable proper content targeting.',
              'Low', 'Open Graph')
    
    # ===== 11-15: Twitter/X Cards =====
    twitter_card = soup.find('meta', attrs={'name': 'twitter:card'})
    twitter_card_type = twitter_card.get('content', '') if twitter_card else ''
    valid_cards = ['summary', 'summary_large_image', 'player', 'app']
    add_check(checks, 'Twitter Card Type', 'pass' if twitter_card_type in valid_cards else 'warning',
              'Checks for the twitter:card meta tag, which controls how your page appears when shared on X (Twitter). The "summary_large_image" type displays a large preview image that dominates the feed, getting significantly more engagement than the small "summary" card.',
              f'{"Card type: " + twitter_card_type + (" — large image preview enabled" if twitter_card_type == "summary_large_image" else "") if twitter_card_type else "Not set — X will use a minimal text-only preview"}',
              'Add <meta name="twitter:card" content="summary_large_image">. 1) summary_large_image: large image above title (best for engagement). 2) summary: small square image beside title. 3) player: for video/audio embeds. 4) app: for mobile app promotion.',
              'High', 'Twitter/X')
    
    twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
    add_check(checks, 'Twitter Title', 'pass' if twitter_title or og_title else 'warning',
              'Checks for a twitter:title meta tag or og:title fallback. X/Twitter uses twitter:title first, then falls back to og:title. Having a dedicated twitter:title lets you customize the headline specifically for X\'s audience and character constraints.',
              f'{"Dedicated twitter:title set" if twitter_title else ("Falls back to og:title" if og_title else "MISSING — no title for X/Twitter previews")}',
              'Add <meta name="twitter:title" content="Your X-Optimized Title">. Keep it under 70 characters. If you don\'t need a separate title for X, ensure og:title is set as a fallback.',
              'Medium', 'Twitter/X')
    
    twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
    add_check(checks, 'Twitter Description', 'pass' if twitter_desc or og_desc else 'warning',
              'Checks for a twitter:description meta tag or og:description fallback. This text appears below the title in X/Twitter card previews. A compelling description increases click-through from the X feed.',
              f'{"Dedicated twitter:description set" if twitter_desc else ("Falls back to og:description" if og_desc else "MISSING — no description for X/Twitter previews")}',
              'Add <meta name="twitter:description" content="...">. Keep it under 200 characters. Write it as a hook that makes X users want to click through.',
              'Medium', 'Twitter/X')
    
    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
    add_check(checks, 'Twitter Image', 'pass' if twitter_image or og_image else 'warning',
              'Checks for a twitter:image meta tag or og:image fallback. X/Twitter has specific image requirements — summary_large_image needs 1200x675px (16:9 ratio). Using the wrong size results in cropped or distorted previews.',
              f'{"Dedicated twitter:image set" if twitter_image else ("Falls back to og:image" if og_image else "MISSING — no image for X/Twitter cards")}',
              'Add <meta name="twitter:image" content="https://yoursite.com/twitter-image.jpg">. 1) Use 1200x675px for summary_large_image. 2) Use 144x144px minimum for summary. 3) Max file size: 5MB. 4) Must be absolute URL.',
              'High', 'Twitter/X')
    
    twitter_site = soup.find('meta', attrs={'name': 'twitter:site'})
    add_check(checks, 'Twitter Site Handle', 'pass' if twitter_site else 'info',
              'Checks for the twitter:site meta tag, which attributes the card to your brand\'s X/Twitter account. When set, your @handle appears in the card footer, driving followers to your profile and building brand authority on the platform.',
              f'{"Handle: " + twitter_site.get("content", "") if twitter_site else "Not set — cards won\'t show your @handle"}',
              'Add <meta name="twitter:site" content="@YourHandle">. This links every shared card back to your X profile, increasing brand visibility and follower growth.',
              'Low', 'Twitter/X')
    
    # ===== 16-18: LinkedIn Specific =====
    article_author = soup.find('meta', property='article:author')
    add_check(checks, 'Article Author', 'pass' if article_author else 'info',
              'Checks for the article:author meta tag, which LinkedIn uses to attribute content to a specific author. On LinkedIn, author attribution increases credibility and engagement, especially for thought leadership and B2B content.',
              f'{"Author set: " + article_author.get("content", "")[:60] if article_author else "Not set — LinkedIn shares won\'t show author attribution"}',
              'Add <meta property="article:author" content="https://yoursite.com/about/author-name"> or a Facebook profile URL. This is especially valuable for B2B content shared on LinkedIn.',
              'Low', 'LinkedIn')
    
    article_published = soup.find('meta', property='article:published_time')
    add_check(checks, 'Article Published Time', 'pass' if article_published else 'info',
              'Checks for the article:published_time meta tag, which signals content freshness on social platforms. LinkedIn and Facebook display this date in article previews, and users are more likely to engage with recently published content.',
              f'{"Published: " + article_published.get("content", "")[:30] if article_published else "Not set — no publish date shown in social previews"}',
              'Add <meta property="article:published_time" content="2026-03-17T10:00:00Z">. Use ISO 8601 format. Also add article:modified_time to show content is actively maintained.',
              'Low', 'LinkedIn')
    
    add_check(checks, 'LinkedIn Image Optimization', 'pass' if og_image else 'warning',
              'Checks whether an og:image is set for LinkedIn feed display. LinkedIn uses og:image for both feed posts and article previews. The optimal size is 1200x627px (1.91:1 ratio). Without an image, LinkedIn shares appear as plain text links with minimal engagement.',
              f'{"OG image available for LinkedIn previews" if og_image else "MISSING — LinkedIn shares will appear as plain text links"}',
              'Ensure og:image is set with a 1200x627px image for LinkedIn. 1) Use high-contrast, branded images. 2) Include text overlay with your headline for visual impact. 3) Test at linkedin.com/post-inspector.',
              'Medium', 'LinkedIn')
    
    # ===== 19-21: Social Schema Markup (sameAs) =====
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    has_sameas = any('sameAs' in str(j) for j in json_ld)
    add_check(checks, 'SameAs Schema', 'pass' if has_sameas else 'warning',
              'Checks for sameAs schema markup that links your website to your social media profiles. This is a critical E-E-A-T signal — it helps Google and AI systems connect your brand entity across platforms, strengthening your knowledge graph presence and authority.',
              f'{"sameAs schema found — social profiles linked in structured data" if has_sameas else "No sameAs schema — search engines can\'t connect your social profiles to your site entity"}',
              'Add sameAs to your Organization JSON-LD: "sameAs": ["https://facebook.com/yourbusiness", "https://twitter.com/yourbusiness", "https://linkedin.com/company/yourbusiness"]. Include all active social profiles.',
              'High', 'Social Schema')
    
    has_org_social = any('"@type"' in str(j) and ('Organization' in str(j) or 'Person' in str(j)) for j in json_ld)
    add_check(checks, 'Organization Social Schema', 'pass' if has_org_social else 'info',
              'Checks for Organization or Person schema that includes social profile information. This structured data helps AI systems and search engines build a complete entity profile for your brand, improving your chances of appearing in knowledge panels and AI-generated answers.',
              f'{"Organization/Person schema with social context found" if has_org_social else "No Organization/Person schema detected — AI systems have limited entity information"}',
              'Add Organization schema with social links: 1) Include @type: Organization with name, url, logo, and sameAs array. 2) For personal brands, use @type: Person with name, jobTitle, and sameAs. 3) This directly feeds Google\'s Knowledge Graph.',
              'Medium', 'Social Schema')
    
    # ===== 22-25: Social Integration & Engagement =====
    social_platforms = {
        'facebook': r'facebook\.com',
        'twitter': r'twitter\.com|x\.com',
        'linkedin': r'linkedin\.com',
        'instagram': r'instagram\.com',
        'youtube': r'youtube\.com',
        'tiktok': r'tiktok\.com',
        'pinterest': r'pinterest\.com'
    }
    social_links = []
    for platform, pattern in social_platforms.items():
        links = soup.find_all('a', href=re.compile(pattern, re.I))
        if links:
            social_links.extend([(platform, l) for l in links])
    
    platforms_found = list(set([s[0] for s in social_links]))
    add_check(checks, 'Social Profile Links', 'pass' if len(platforms_found) >= 3 else ('warning' if platforms_found else 'info'),
              'Scans the page for links to major social media platforms (Facebook, X/Twitter, LinkedIn, Instagram, YouTube, TikTok, Pinterest). Having visible social links builds trust, enables cross-platform discovery, and signals to search engines that your brand has an active online presence.',
              f'{len(platforms_found)} platform(s) linked: {", ".join(platforms_found[:5]) if platforms_found else "none found"} — {"good cross-platform presence" if len(platforms_found) >= 3 else "consider adding more social profile links"}',
              'Link to at least 3 social profiles: 1) Add social icons in your header or footer. 2) Use recognizable platform icons with proper aria-labels for accessibility. 3) Ensure links open in new tabs (target="_blank" rel="noopener"). 4) Prioritize platforms where your audience is most active.',
              'Medium', 'Social Integration')
    
    # Share buttons detection
    share_patterns = ['share', 'social-share', 'sharing', 'addthis', 'sharethis', 'shareaholic']
    share_buttons = soup.find_all(class_=re.compile('|'.join(share_patterns), re.I))
    share_links = soup.find_all('a', href=re.compile(r'share|intent/tweet|sharer\.php', re.I))
    total_share = len(share_buttons) + len(share_links)
    add_check(checks, 'Share Buttons', 'pass' if total_share > 0 else 'info',
              'Detects social sharing buttons or share intent links on the page. Share buttons make it effortless for visitors to distribute your content across their networks, amplifying reach organically. Pages with share buttons get shared 7x more than those without.',
              f'{total_share} share element(s) detected — {"sharing functionality available" if total_share > 0 else "no share buttons found"}',
              'Add share buttons to your content: 1) Use native share URLs (no heavy third-party scripts needed): Facebook: https://www.facebook.com/sharer/sharer.php?u=URL, X: https://twitter.com/intent/tweet?url=URL&text=TITLE. 2) Place them above and below long content. 3) Consider the Web Share API for mobile.',
              'Medium', 'Social Integration')
    
    # Social proof signals
    social_proof = any(term in html.lower() for term in ['followers', 'likes', 'shares', 'social proof', 'follow us'])
    add_check(checks, 'Social Proof Signals', 'pass' if social_proof else 'info',
              'Scans for social proof elements like follower counts, share counts, or "follow us" calls-to-action. Social proof leverages the psychological principle that people trust what others endorse. Displaying engagement metrics builds credibility and encourages further interaction.',
              f'{"Social proof elements detected on page" if social_proof else "No social proof signals found — consider adding follower counts or engagement metrics"}',
              'Display social proof: 1) Show follower/subscriber counts if impressive. 2) Display share counts on popular content. 3) Add "Join X,000+ subscribers" to email signups. 4) Embed social media feeds showing real engagement.',
              'Low', 'Social Integration')
    
    # WhatsApp/Messaging optimization
    whatsapp_link = soup.find('a', href=re.compile(r'wa\.me|whatsapp|api\.whatsapp', re.I))
    add_check(checks, 'WhatsApp Integration', 'pass' if whatsapp_link else 'info',
              'Checks for WhatsApp contact or share links. WhatsApp has 2+ billion users and is the primary communication channel in many markets. A WhatsApp link enables instant customer contact on mobile and is especially valuable for local businesses and e-commerce.',
              f'{"WhatsApp link found — mobile messaging enabled" if whatsapp_link else "No WhatsApp integration — missing a major mobile engagement channel"}',
              'Add WhatsApp integration: 1) Contact link: <a href="https://wa.me/1234567890">Chat on WhatsApp</a>. 2) Share link: https://wa.me/?text=Check+this+out:+URL. 3) Add a floating WhatsApp button for mobile users. 4) Pre-fill messages with your business context.',
              'Low', 'Social Integration')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== LOCAL SEO (35 checks) ==============
def analyze_local_seo(url, soup, response, load_time):
    """
    Enhanced Local SEO analysis based on 2026 ranking factors:
    - NAP consistency and visibility
    - LocalBusiness schema markup
    - Google Business Profile alignment signals
    - Citation and directory signals
    - Local trust and authority indicators
    - AI/Voice search local optimization
    """
    checks = []
    text = soup.get_text()
    html = str(soup)
    parsed = urlparse(url)
    
    # ===== 1-8: NAP (Name, Address, Phone) Consistency =====
    phone_patterns = [
        r'\b(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b',
        r'\b(\d{3}[-.\s]?\d{4})\b',
        r'\b(\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9})\b'
    ]
    phone_found = any(re.search(p, text) for p in phone_patterns)
    add_check(checks, 'Phone Number Visible', 'pass' if phone_found else 'warning',
              'Scans the page for a visible phone number in common formats (US, international). For local businesses, a prominently displayed phone number is a top trust signal. Google uses phone numbers to verify NAP consistency across the web and match your site to your Google Business Profile.',
              f'{"Phone number detected on page — local trust signal present" if phone_found else "No phone number found — missing a critical local SEO trust signal"}',
              'Display your phone number prominently: 1) Add it to the header and footer of every page. 2) Use consistent formatting across your entire web presence. 3) Match it exactly to your Google Business Profile listing. 4) Use the same number on all directory listings.',
              'High', 'NAP')
    
    tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
    add_check(checks, 'Click-to-Call Links', 'pass' if tel_links else 'warning',
              'Checks for tel: links that enable one-tap calling on mobile devices. 88% of local mobile searches result in a call or visit within 24 hours. Without click-to-call links, mobile users must manually copy and dial your number, creating friction that loses leads.',
              f'{len(tel_links)} click-to-call link(s) found — {"mobile users can tap to call" if tel_links else "mobile users cannot tap to call"}',
              'Add click-to-call links: 1) Wrap phone numbers in <a href="tel:+16135551234">(613) 555-1234</a>. 2) Include the country code with + prefix. 3) Add to header, footer, and contact sections. 4) Style as a visible button on mobile for maximum conversions.',
              'Critical', 'NAP')
    
    address_patterns = [
        r'\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct|place|pl)\b',
        r'\b(?:suite|ste|unit|apt|#)\s*\d+\b',
        r'\b[A-Z][a-z]+,\s*[A-Z]{2}\s+\d{5}\b'
    ]
    address_found = any(re.search(p, text, re.I) for p in address_patterns)
    add_check(checks, 'Physical Address', 'pass' if address_found else 'info',
              'Scans for a physical street address on the page. For local businesses, displaying your full address is essential for NAP consistency — the #1 local SEO ranking factor. Google cross-references your website address with your Google Business Profile and directory listings.',
              f'{"Street address detected on page" if address_found else "No street address pattern found — acceptable for service-area businesses, critical for storefront businesses"}',
              'Display your full address: 1) Include street, city, state/province, and postal code. 2) Match it character-for-character with your Google Business Profile. 3) Use Schema.org PostalAddress markup. 4) For service-area businesses, display your service region instead.',
              'High', 'NAP')
    
    zip_pattern = re.search(r'\b\d{5}(?:-\d{4})?\b|\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b', text)
    add_check(checks, 'ZIP/Postal Code', 'pass' if zip_pattern else 'info',
              'Checks for a visible ZIP or postal code on the page. Postal codes are used by search engines for precise geo-targeting and help match your business to "near me" searches. They also validate your address data across citation sources.',
              f'{"Postal/ZIP code found on page" if zip_pattern else "No postal code detected — reduces geo-targeting precision"}',
              'Include your postal/ZIP code: 1) Display it as part of your full address. 2) Ensure it matches your Google Business Profile exactly. 3) For Canadian businesses, use the A1A 1A1 format consistently.',
              'Medium', 'NAP')
    
    email_pattern = re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', text)
    add_check(checks, 'Contact Email', 'pass' if email_pattern else 'info',
              'Scans for a visible email address on the page. A displayed email address adds to your contact information completeness and provides an alternative communication channel. It also contributes to trust signals that search engines use to evaluate business legitimacy.',
              f'{"Email address found on page" if email_pattern else "No email address detected — consider adding a contact email"}',
              'Display a professional contact email: 1) Use a domain-based email (info@yourbusiness.com) rather than Gmail/Yahoo. 2) Add it to your contact page and footer. 3) Also add a mailto: link for easy clicking.',
              'Medium', 'NAP')
    
    mailto_links = soup.find_all('a', href=re.compile(r'^mailto:'))
    add_check(checks, 'Click-to-Email Links', 'pass' if mailto_links else 'info',
              'Checks for mailto: links that open the user\'s email client with your address pre-filled. Like click-to-call, this removes friction from the contact process and improves conversion rates, especially on mobile devices.',
              f'{len(mailto_links)} mailto link(s) found — {"users can click to email" if mailto_links else "users must manually copy your email address"}',
              'Add mailto links: 1) Wrap email addresses in <a href="mailto:info@yourbusiness.com">info@yourbusiness.com</a>. 2) Optionally pre-fill subject: mailto:info@yourbusiness.com?subject=Inquiry. 3) Add to contact page and footer.',
              'Low', 'NAP')
    
    footer = soup.find('footer') or soup.find(class_=re.compile(r'footer', re.I))
    footer_text = footer.get_text() if footer else ''
    nap_in_footer = phone_found and (re.search(r'\b\d+\s+\w+', footer_text) if footer_text else False)
    add_check(checks, 'NAP in Footer', 'pass' if nap_in_footer else 'info',
              'Checks whether your Name, Address, and Phone (NAP) information appears in the page footer. Footer NAP ensures your contact information is visible on every page of your site, providing consistent local signals that search engines use to verify your business identity.',
              f'{"NAP information detected in footer — site-wide consistency" if nap_in_footer else "NAP not found in footer — contact info may not be visible on all pages"}',
              'Place full NAP in your footer: 1) Include business name, full address, and phone number. 2) Wrap in Schema.org LocalBusiness markup. 3) This ensures every page on your site reinforces your local presence. 4) Keep formatting identical to your Google Business Profile.',
              'Medium', 'NAP')
    
    hours_patterns = ['hours', 'open', 'closed', 'monday', 'tuesday', 'am', 'pm', '24/7', '24 hours']
    has_hours = any(term in text.lower() for term in hours_patterns)
    add_check(checks, 'Business Hours', 'pass' if has_hours else 'info',
              'Scans for business hours or schedule-related content on the page. Displaying operating hours is critical for local search intent — users searching locally often need to know if you\'re open now. Google also uses this data for the "Open now" filter in Maps results.',
              f'{"Business hours or schedule information detected" if has_hours else "No business hours found — users can\'t tell when you\'re open"}',
              'Display your business hours: 1) List hours for each day of the week. 2) Include holiday hours and special schedules. 3) Add OpeningHoursSpecification schema markup. 4) Keep hours updated — incorrect hours lead to negative reviews.',
              'High', 'NAP')
    
    # ===== 9-17: LocalBusiness Schema Markup =====
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    json_ld_content = ' '.join([str(j) for j in json_ld])
    
    local_schema_types = ['LocalBusiness', 'Store', 'Restaurant', 'Hotel', 'MedicalBusiness', 
                          'LegalService', 'FinancialService', 'RealEstateAgent', 'AutoDealer',
                          'HomeAndConstructionBusiness', 'SportsActivityLocation']
    has_local_schema = any(t in json_ld_content for t in local_schema_types)
    add_check(checks, 'LocalBusiness Schema', 'pass' if has_local_schema else 'fail',
              'Checks for LocalBusiness (or subtype) schema markup in JSON-LD. This is the single most important structured data for local SEO — it directly feeds Google\'s Map Pack results and enables rich local search features like hours, ratings, and directions.',
              f'{"LocalBusiness schema detected — eligible for Map Pack rich results" if has_local_schema else "MISSING LocalBusiness schema — severely limits Map Pack visibility"}',
              'Add LocalBusiness JSON-LD schema: 1) Choose the most specific subtype (Restaurant, LegalService, MedicalBusiness, etc.). 2) Include name, address, phone, geo coordinates, hours, and priceRange. 3) Validate at search.google.com/test/rich-results.',
              'Critical', 'Schema')
    
    # Organization schema
    has_org_schema = 'Organization' in json_ld_content or 'Corporation' in json_ld_content
    add_check(checks, 'Organization Schema', 'pass' if has_org_schema or has_local_schema else 'warning',
              'Checks for Organization or Corporation schema markup. This establishes your business as a recognized entity in Google\'s Knowledge Graph, enabling knowledge panels and improving how AI systems understand and reference your brand.',
              f'{"Organization/Corporation schema found — entity recognition enabled" if has_org_schema else ("LocalBusiness schema serves as organization entity" if has_local_schema else "No organization entity schema — limited Knowledge Graph presence")}',
              'Add Organization schema: 1) Include name, url, logo, description, and sameAs (social profiles). 2) If you already have LocalBusiness schema, it inherits from Organization. 3) Add contactPoint for customer service details.',
              'High', 'Schema')
    
    # Address in schema
    has_address_schema = 'PostalAddress' in json_ld_content or 'address' in json_ld_content
    add_check(checks, 'Address Schema', 'pass' if has_address_schema else 'warning',
              'Checks for PostalAddress schema within your structured data. Structured address data ensures search engines parse your location correctly — street, city, state, postal code, and country as separate fields rather than guessing from unstructured text.',
              f'{"PostalAddress schema found — address is machine-readable" if has_address_schema else "No structured address — search engines must guess your location from page text"}',
              'Add PostalAddress schema: 1) Include streetAddress, addressLocality (city), addressRegion (state/province), postalCode, and addressCountry. 2) Match every field exactly to your Google Business Profile.',
              'High', 'Schema')
    
    # GeoCoordinates
    has_geo = 'GeoCoordinates' in json_ld_content or '"latitude"' in json_ld_content or '"geo"' in json_ld_content
    add_check(checks, 'GeoCoordinates Schema', 'pass' if has_geo else 'warning',
              'Checks for GeoCoordinates (latitude/longitude) in your structured data. Precise coordinates enable exact map placement and improve "near me" search matching. Without coordinates, search engines must geocode your address, which can be inaccurate.',
              f'{"GeoCoordinates found — precise map placement enabled" if has_geo else "No geo coordinates — map placement relies on address geocoding (less precise)"}',
              'Add GeoCoordinates to your LocalBusiness schema: "geo": {"@type": "GeoCoordinates", "latitude": 45.4215, "longitude": -75.6972}. Get exact coordinates from Google Maps by right-clicking your location.',
              'High', 'Schema')
    
    # Opening hours schema
    has_hours_schema = 'openingHours' in json_ld_content or 'OpeningHoursSpecification' in json_ld_content
    add_check(checks, 'Opening Hours Schema', 'pass' if has_hours_schema else 'info',
              'Checks for openingHours or OpeningHoursSpecification in structured data. Schema-based hours enable the "Open now" badge in search results and Google Maps, which significantly increases click-through rates for local searches.',
              f'{"Opening hours in schema — eligible for Open now badge" if has_hours_schema else "No hours in schema — missing Open now badge opportunity"}',
              'Add opening hours to schema: 1) Simple: "openingHours": "Mo-Fr 09:00-17:00". 2) Detailed: use OpeningHoursSpecification with dayOfWeek, opens, and closes. 3) Include special hours for holidays.',
              'Medium', 'Schema')
    
    # Contact point schema
    has_contact_schema = 'ContactPoint' in json_ld_content or 'contactPoint' in json_ld_content
    add_check(checks, 'ContactPoint Schema', 'pass' if has_contact_schema else 'info',
              'Checks for ContactPoint schema, which provides structured contact information including phone type (customer service, sales, support), available languages, and contact options. This helps search engines display the right contact method for user intent.',
              f'{"ContactPoint schema found — structured contact info available" if has_contact_schema else "No ContactPoint schema — contact details not structured for search engines"}',
              'Add ContactPoint schema: "contactPoint": {"@type": "ContactPoint", "telephone": "+1-613-555-1234", "contactType": "customer service", "availableLanguage": "English"}.',
              'Medium', 'Schema')
    
    # Price range
    has_price_range = 'priceRange' in json_ld_content
    add_check(checks, 'Price Range Schema', 'pass' if has_price_range else 'info',
              'Checks for priceRange in your LocalBusiness schema. Price range indicators ($, $$, $$$) appear in Google search results and Maps, helping users filter businesses by budget and pre-qualifying visitors to improve conversion rates.',
              f'{"Price range set in schema — visible in search filters" if has_price_range else "No price range — business won\'t appear in price-filtered searches"}',
              'Add priceRange to your LocalBusiness schema: "priceRange": "$$". Use $ (budget), $$ (moderate), $$$ (upscale), or $$$$ (luxury).',
              'Low', 'Schema')
    
    # Aggregate rating schema
    has_rating_schema = 'AggregateRating' in json_ld_content or 'aggregateRating' in json_ld_content
    add_check(checks, 'Rating Schema', 'pass' if has_rating_schema else 'info',
              'Checks for AggregateRating schema, which enables star ratings to appear directly in search results. Listings with star ratings get up to 35% higher click-through rates. This is one of the most visually impactful rich result types available.',
              f'{"AggregateRating schema found — star ratings can appear in search results" if has_rating_schema else "No rating schema — missing star ratings in search results"}',
              'Add AggregateRating schema: "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.8", "reviewCount": "127"}. Only use real review data — Google penalizes fake ratings.',
              'High', 'Schema')
    
    # ===== 18-24: Local Signals & Trust =====
    # Google Maps embed
    maps_embed = soup.find('iframe', src=re.compile(r'google.*maps|maps\.google', re.I))
    add_check(checks, 'Google Maps Embed', 'pass' if maps_embed else 'info',
              'Checks for an embedded Google Maps iframe on the page. An embedded map verifies your physical location to search engines and provides convenience to users. It also signals to Google that your business has a real, verifiable location.',
              f'{"Google Maps embed found — location visually verified" if maps_embed else "No Google Maps embed — consider adding one to your contact or about page"}',
              'Embed Google Maps: 1) Go to Google Maps, search your business, click Share > Embed. 2) Add the iframe to your contact page. 3) Include a "Get Directions" link alongside it. 4) Use loading="lazy" to avoid impacting page speed.',
              'Medium', 'Local Signals')
    
    directions = soup.find('a', href=re.compile(r'maps\.google|google.*maps.*dir|directions', re.I))
    add_check(checks, 'Get Directions Link', 'pass' if directions else 'info',
              'Checks for a "Get Directions" link that opens Google Maps navigation to your business. This is a strong local intent signal and provides immediate utility to mobile users who are ready to visit your location.',
              f'{"Directions link found — users can navigate to your location" if directions else "No directions link — mobile users can\'t easily navigate to you"}',
              'Add a directions link: <a href="https://www.google.com/maps/dir/?api=1&destination=Your+Business+Name+City" target="_blank">Get Directions</a>. Place it near your address and map embed.',
              'Low', 'Local Signals')
    
    # Service area mentions
    service_area_terms = ['serving', 'service area', 'we serve', 'locations', 'coverage area', 
                          'available in', 'servicing', 'proudly serving']
    has_service_area = any(term in text.lower() for term in service_area_terms)
    add_check(checks, 'Service Area Mentioned', 'pass' if has_service_area else 'info',
              'Scans for service area or coverage mentions on the page. Explicitly stating which cities, neighborhoods, or regions you serve helps search engines match your business to location-specific queries and "near me" searches in those areas.',
              f'{"Service area/coverage language found on page" if has_service_area else "No service area mentions — search engines can\'t determine your coverage region"}',
              'Mention your service areas naturally: 1) Add a "Service Areas" section listing cities/neighborhoods you serve. 2) Create location-specific landing pages for each major area. 3) Include service area in your LocalBusiness schema with areaServed.',
              'Medium', 'Local Signals')
    
    local_terms = ['near me', 'local', 'nearby', 'in your area', 'neighborhood', 'community']
    has_local_terms = any(term in text.lower() for term in local_terms)
    add_check(checks, 'Local Keywords', 'pass' if has_local_terms else 'info',
              'Scans for local-intent keywords like "near me," "local," and "nearby" in your content. These terms align your page with the way users actually search for local businesses. Google processes billions of "near me" searches monthly.',
              f'{"Local-intent keywords found in content" if has_local_terms else "No local keywords detected — content may not match local search intent"}',
              'Include local keywords naturally: 1) Use "[service] near me" and "[service] in [city]" in headings and content. 2) Mention your neighborhood and surrounding areas. 3) Don\'t keyword-stuff — write naturally for local users.',
              'Medium', 'Local Signals')
    
    review_terms = ['review', 'testimonial', 'rating', 'stars', 'customer feedback', 'what our customers say']
    has_reviews = any(term in html.lower() for term in review_terms)
    add_check(checks, 'Reviews Section', 'pass' if has_reviews else 'warning',
              'Checks for a reviews or testimonials section on the page. Customer reviews are the #2 local ranking factor after Google Business Profile signals. Businesses with 4.5+ star ratings get 94% more clicks than those with lower ratings.',
              f'{"Reviews/testimonials section detected" if has_reviews else "No reviews section found — missing a top local ranking signal"}',
              'Add a reviews section: 1) Display your best Google/Yelp reviews on your site. 2) Add Review schema markup for star ratings in search results. 3) Include reviewer name and date for authenticity. 4) Actively request reviews from satisfied customers.',
              'High', 'Local Signals')
    
    trust_terms = ['certified', 'licensed', 'insured', 'bonded', 'accredited', 'bbb', 'member of', 
                   'association', 'award', 'years in business', 'established', 'since']
    has_trust = any(term in text.lower() for term in trust_terms)
    add_check(checks, 'Trust Signals', 'pass' if has_trust else 'info',
              'Scans for trust and credibility indicators like certifications, licenses, awards, BBB accreditation, and years in business. These signals build confidence with both users and search engines, contributing to E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness).',
              f'{"Trust/credibility signals found on page" if has_trust else "No trust signals detected — consider adding certifications, awards, or years of experience"}',
              'Display trust signals prominently: 1) Show certification badges and license numbers. 2) Mention years in business ("Serving Ottawa since 2010"). 3) Display BBB rating or industry association memberships. 4) Add award badges with dates.',
              'Medium', 'Local Signals')
    
    community_terms = ['community', 'local event', 'sponsor', 'charity', 'give back', 'neighborhood']
    has_community = any(term in text.lower() for term in community_terms)
    add_check(checks, 'Community Involvement', 'pass' if has_community else 'info',
              'Scans for community engagement signals like sponsorships, local events, charity work, and neighborhood involvement. Community content builds local authority and generates natural backlinks from local organizations, events, and news outlets.',
              f'{"Community involvement content found" if has_community else "No community engagement signals — consider highlighting local involvement"}',
              'Showcase community involvement: 1) Create a page about your community partnerships. 2) Sponsor local events and link to them. 3) Write blog posts about local topics. 4) This generates natural local backlinks and builds authority.',
              'Low', 'Local Signals')
    
    # ===== 25-30: Citation & Directory Signals =====
    # Links to major directories
    directory_patterns = ['yelp.com', 'yellowpages', 'bbb.org', 'angieslist', 'homeadvisor', 
                          'thumbtack', 'houzz', 'tripadvisor', 'healthgrades', 'avvo']
    directory_links = soup.find_all('a', href=re.compile('|'.join(directory_patterns), re.I))
    add_check(checks, 'Directory Profile Links', 'pass' if directory_links else 'info',
              'Scans for links to major business directories (Yelp, BBB, Yellow Pages, TripAdvisor, etc.). Linking to your directory profiles from your website helps search engines verify your business across multiple sources and strengthens your citation network.',
              f'{len(directory_links)} directory link(s) found — {"citation network connected" if directory_links else "no directory profile links detected"}',
              'Link to your directory profiles: 1) Claim and optimize profiles on Yelp, BBB, Yellow Pages, and industry-specific directories. 2) Add links to these profiles from your website footer or "Find Us" page. 3) Ensure NAP is identical across all directories.',
              'Low', 'Citations')
    
    platform_mentions = ['google reviews', 'yelp', 'facebook reviews', 'trustpilot', 'g2']
    has_platform_proof = any(term in text.lower() for term in platform_mentions)
    add_check(checks, 'Review Platform Mentions', 'pass' if has_platform_proof else 'info',
              'Checks for mentions of review platforms (Google Reviews, Yelp, Trustpilot, etc.) on your page. Referencing your presence on these platforms signals to users and search engines that your business has been reviewed and validated by real customers.',
              f'{"Review platform references found — social proof from external platforms" if has_platform_proof else "No review platform mentions — consider referencing your Google/Yelp ratings"}',
              'Reference your review platforms: 1) Display "Rated 4.8/5 on Google Reviews" with a link. 2) Embed review widgets from Google, Yelp, or Trustpilot. 3) Add review platform badges to build trust.',
              'Medium', 'Citations')
    
    # ===== 31-35: AI/Voice Search Local Optimization =====
    # FAQ for voice search
    faq_patterns = ['faq', 'frequently asked', 'common questions', 'q&a', 'questions']
    has_faq = any(term in text.lower() for term in faq_patterns) or 'FAQPage' in json_ld_content
    add_check(checks, 'Local FAQ Content', 'pass' if has_faq else 'info',
              'Checks for FAQ content or FAQPage schema, which is critical for voice search optimization. Voice assistants answer "Where is...," "What time does... open," and "How do I get to..." queries by extracting FAQ content. Local FAQs directly target these high-intent voice searches.',
              f'{"FAQ content or FAQPage schema found — voice search optimized" if has_faq else "No FAQ content — missing voice search optimization opportunity"}',
              'Add a local FAQ section: 1) Answer common questions: "Where are you located?", "What are your hours?", "Do you offer free parking?". 2) Add FAQPage schema markup. 3) Use natural, conversational language that matches voice queries.',
              'Medium', 'AI/Voice')
    
    question_words = text.lower().count('where') + text.lower().count('when') + text.lower().count('how to get')
    add_check(checks, 'Conversational Content', 'pass' if question_words >= 2 else 'info',
              'Counts question-based phrases (where, when, how to get) that match how people speak to voice assistants and AI chatbots. Conversational content aligns with natural language queries, making your page more likely to be cited by AI answer engines.',
              f'{question_words} conversational question phrase(s) found — {"good alignment with voice/AI queries" if question_words >= 2 else "consider adding more question-based content"}',
              'Include conversational phrases: 1) Write content that answers "Where can I find...", "When is... open", "How do I get to...". 2) Use question-and-answer format. 3) Write at a natural reading level (8th-10th grade).',
              'Medium', 'AI/Voice')
    
    has_sameas = 'sameAs' in json_ld_content
    add_check(checks, 'SameAs Local Links', 'pass' if has_sameas else 'warning',
              'Checks for sameAs schema linking your website to your Google Business Profile, directory listings, and social profiles. This is how AI systems connect your website entity to your business entity across the web, enabling accurate citations in AI-generated answers.',
              f'{"sameAs schema found — entity connections established for AI recognition" if has_sameas else "No sameAs schema — AI systems can\'t connect your site to your business listings"}',
              'Add sameAs to your LocalBusiness schema: "sameAs": ["https://www.google.com/maps/place/...", "https://www.yelp.com/biz/...", "https://facebook.com/..."]. Include your GBP URL, directory profiles, and social accounts.',
              'High', 'AI/Voice')
    
    has_area_served = 'areaServed' in json_ld_content or 'serviceArea' in json_ld_content
    add_check(checks, 'Area Served Schema', 'pass' if has_area_served else 'info',
              'Checks for areaServed or serviceArea schema, which explicitly tells search engines and AI systems which geographic areas your business covers. This is especially important for service-area businesses that don\'t have a storefront customers visit.',
              f'{"areaServed/serviceArea schema found — service coverage defined" if has_area_served else "No area served schema — search engines must infer your coverage area"}',
              'Add areaServed to your schema: "areaServed": [{"@type": "City", "name": "Ottawa"}, {"@type": "City", "name": "Gatineau"}]. Use City, State, or GeoCircle types to define your coverage.',
              'Medium', 'AI/Voice')
    
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    add_check(checks, 'Mobile-First Local', 'pass' if viewport else 'fail',
              'Checks for a viewport meta tag, which is the foundation of mobile responsiveness. 76% of local searches happen on mobile devices, and Google uses mobile-first indexing. Without a viewport tag, your site renders at desktop width on phones, destroying the mobile experience.',
              f'{"Viewport meta tag set — mobile rendering enabled" if viewport else "MISSING viewport tag — site is not mobile-friendly, severely impacting local search visibility"}',
              'Add the viewport meta tag: <meta name="viewport" content="width=device-width, initial-scale=1.0">. 1) This is the minimum requirement for mobile-friendliness. 2) Test at search.google.com/test/mobile-friendly. 3) Ensure tap targets are at least 48x48px.',
              'Critical', 'AI/Voice')
    
    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}


# ============== GEO/AEO (45 checks) - AI Search Optimization ==============

def analyze_geo_aeo(url, soup, response, load_time):
    """
    Comprehensive AI/LLM optimization checks (45 checks) based on:
    - Google's AI experiences guidelines & AI Overviews
    - Answer Engine Optimization (AEO) best practices
    - LLM interpretability research & passage ranking readiness
    - AI crawler permissions & llms.txt emerging standard
    - WordPress REST API publishing readiness signals
    - E-E-A-T authority signals for AI citation
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
              'Checks for JSON-LD structured data (Schema.org markup), which is the primary way AI systems and search engines understand your content programmatically. Without it, AI must infer meaning from unstructured HTML, leading to less accurate citations and missed rich result opportunities.',
              f'{len(json_ld)} JSON-LD block(s) found — {"structured data available for AI parsing" if json_ld else "no structured data — AI systems have limited understanding of your content"}',
              'Add JSON-LD schema: 1) Start with Organization/WebPage schema on every page. 2) Add Article schema for blog posts. 3) Add FAQPage for Q&A content. 4) Use Google\'s Rich Results Test to validate. 5) Place in <script type="application/ld+json"> tags.',
              'Critical', 'AI Parsing')

    faq_schema = 'FAQPage' in html or '"Question"' in html
    add_check(checks, 'FAQ Schema', 'pass' if faq_schema else 'warning',
              'Checks for FAQPage schema markup, which is one of the most AI-cited structured data types. AI answer engines like ChatGPT, Perplexity, and Google AI Overviews directly extract FAQ content for their responses. This is your highest-impact AEO optimization.',
              f'{"FAQPage schema detected — content is directly extractable by AI answer engines" if faq_schema else "No FAQ schema — missing the most AI-cited structured data type"}',
              'Add FAQPage schema: 1) Identify your top 5-10 customer questions. 2) Write clear, concise answers (2-3 sentences each). 3) Wrap in FAQPage JSON-LD with Question/Answer pairs. 4) Also display the Q&A visually on the page.',
              'Critical', 'AI Parsing')

    howto_schema = 'HowTo' in html
    add_check(checks, 'HowTo Schema', 'pass' if howto_schema else 'info',
              'Checks for HowTo schema markup, which structures step-by-step instructions for AI consumption. HowTo content is heavily featured in Google AI Overviews and voice assistant responses. It enables rich results with numbered steps and images.',
              f'{"HowTo schema detected — step-by-step content is AI-readable" if howto_schema else "No HowTo schema — instructional content not structured for AI extraction"}',
              'Add HowTo schema for instructional content: 1) Break processes into numbered steps with name and text. 2) Include estimatedCost, totalTime, and supply if applicable. 3) Add images per step for rich results.',
              'High', 'AI Parsing')

    entity_schemas = ['Person', 'Organization', 'Product', 'Place', 'Event', 'Article', 'WebPage']
    entities_found = [s for s in entity_schemas if s in html]
    add_check(checks, 'Entity Schema Markup', 'pass' if entities_found else 'warning',
              'Checks for entity-type schemas (Person, Organization, Product, Article, etc.) that help AI systems build knowledge graphs about your content. Entity markup is how your brand, products, and people become recognized entities in AI systems.',
              f'Entities found: {", ".join(entities_found) if entities_found else "None"} — {"AI can identify key entities on this page" if entities_found else "no entity schemas — AI systems can\'t identify what this page is about"}',
              'Add entity schemas: 1) Organization for your business. 2) Person for team members/authors. 3) Article/BlogPosting for content. 4) Product for offerings. 5) Each entity should have name, description, and sameAs links.',
              'High', 'AI Parsing')

    speakable = 'speakable' in html.lower()
    add_check(checks, 'Speakable Schema', 'pass' if speakable else 'info',
              'Checks for Speakable schema, which tells voice assistants (Google Assistant, Alexa, Siri) which sections of your page are best suited for text-to-speech reading. This is key for voice search optimization and audio content delivery.',
              f'{"Speakable schema found — voice assistants know which content to read aloud" if speakable else "No Speakable schema — voice assistants must guess which content to read"}',
              'Add Speakable schema: 1) Use cssSelector to point to your summary and key takeaways sections. 2) Keep speakable content concise (2-3 sentences). 3) Write in a natural, conversational tone suitable for audio.',
              'Medium', 'AI Parsing')

    sameas = 'sameAs' in html
    add_check(checks, 'Entity sameAs Links', 'pass' if sameas else 'info',
              'Checks for sameAs links in your structured data, which connect your entity to authoritative external profiles (Wikipedia, Wikidata, social media, directories). This is how AI systems disambiguate your brand from others with similar names and build accurate knowledge graph entries.',
              f'{"sameAs links found — entity disambiguation enabled for AI systems" if sameas else "No sameAs links — AI systems may confuse your entity with others"}',
              'Add sameAs to your Organization schema: 1) Link to your Wikipedia page (if you have one). 2) Link to Wikidata entry. 3) Include all social media profile URLs. 4) Add industry directory profile URLs.',
              'Medium', 'AI Parsing')

    # ===== 7-12: Semantic HTML & Structure =====
    semantic_tags = soup.find_all(['article', 'section', 'aside', 'nav', 'header', 'footer', 'main'])
    add_check(checks, 'Semantic HTML5', 'pass' if len(semantic_tags) >= 3 else 'warning',
              'Counts semantic HTML5 elements (article, section, aside, nav, header, footer, main) that give AI systems structural context about your content. Semantic HTML helps AI distinguish navigation from content, sidebars from main text, and articles from page chrome.',
              f'{len(semantic_tags)} semantic element(s) found — {"good structural context for AI" if len(semantic_tags) >= 3 else "limited semantic structure — AI must guess content boundaries"}',
              'Use semantic HTML5 elements: 1) Wrap main content in <main> and <article>. 2) Use <section> for distinct content blocks. 3) Use <aside> for supplementary content. 4) Use <nav> for navigation. 5) This helps AI extract the right content.',
              'High', 'Semantic Structure')

    tables = soup.find_all('table')
    add_check(checks, 'Data Tables', 'pass' if tables else 'info',
              'Checks for HTML tables, which AI systems extract more reliably than prose for structured comparisons, pricing, specifications, and feature lists. Tables are one of the most commonly cited content formats in AI-generated answers.',
              f'{len(tables)} table(s) found — {"structured data available for AI extraction" if tables else "no tables — consider adding comparison or specification tables"}',
              'Add data tables for structured information: 1) Use tables for feature comparisons, pricing tiers, and specifications. 2) Include <thead> with clear column headers. 3) Use <caption> to describe the table. 4) AI systems extract table data with high accuracy.',
              'Medium', 'Semantic Structure')

    lists = soup.find_all(['ul', 'ol'])
    add_check(checks, 'Structured Lists', 'pass' if len(lists) >= 2 else 'warning',
              'Counts ordered and unordered lists on the page. Lists are the second most AI-extractable content format after tables. AI answer engines frequently cite bulleted and numbered lists because they provide concise, scannable information.',
              f'{len(lists)} list(s) found — {"good list usage for AI extraction" if len(lists) >= 2 else "few lists — AI prefers content structured as bullet points and numbered steps"}',
              'Use lists for key information: 1) Use <ul> for feature lists, benefits, and requirements. 2) Use <ol> for step-by-step processes and rankings. 3) Keep list items concise (1-2 sentences each). 4) AI extracts lists more accurately than long paragraphs.',
              'High', 'Semantic Structure')

    figures = soup.find_all('figure')
    figcaptions = soup.find_all('figcaption')
    add_check(checks, 'Figure Captions', 'pass' if figcaptions else 'info',
              'Checks for <figure> and <figcaption> elements that provide context for images and diagrams. AI systems use figcaptions to understand what images represent, enabling more accurate multimodal content analysis and image search optimization.',
              f'{len(figcaptions)} figcaption(s) found — {"images have contextual descriptions for AI" if figcaptions else "no figcaptions — AI has limited understanding of your images"}',
              'Use figure/figcaption for images: 1) Wrap images in <figure> tags. 2) Add <figcaption> with descriptive text explaining what the image shows. 3) This is more semantically meaningful than alt text alone for AI systems.',
              'Medium', 'Semantic Structure')

    dl_tags = soup.find_all('dl')
    add_check(checks, 'Definition Lists', 'pass' if dl_tags else 'info',
              'Checks for definition lists (<dl>/<dt>/<dd>), which are the semantic HTML way to present term-definition pairs. AI systems can directly extract definitions from <dl> elements, making them ideal for glossaries, FAQs, and technical terminology.',
              f'{len(dl_tags)} definition list(s) found — {"term-definition pairs available for AI extraction" if dl_tags else "no definition lists — consider using <dl> for glossary terms"}',
              'Use definition lists for terminology: 1) Wrap glossary terms in <dl><dt>Term</dt><dd>Definition</dd></dl>. 2) Ideal for industry jargon, product features, and FAQ-style content. 3) AI systems extract these with high precision.',
              'Low', 'Semantic Structure')

    blockquotes = soup.find_all('blockquote')
    add_check(checks, 'Blockquote Citations', 'pass' if blockquotes else 'info',
              'Checks for <blockquote> elements used for expert quotes and citations. AI systems recognize blockquotes as authoritative third-party statements, which strengthens E-E-A-T signals and provides citable expert opinions for AI-generated answers.',
              f'{len(blockquotes)} blockquote(s) found — {"expert citations available for AI to reference" if blockquotes else "no blockquotes — consider adding expert quotes for authority"}',
              'Use blockquotes for expert citations: 1) Wrap expert quotes in <blockquote> with <cite> for attribution. 2) Include the expert\'s name and credentials. 3) AI systems use these as authoritative supporting evidence in answers.',
              'Low', 'Semantic Structure')

    # ===== 13-18: LLM Interpretability & Content =====
    questions = re.findall(r'(what|how|why|when|where|who|which|can|does|is|are)\s+[^.?]*\?', text.lower())
    add_check(checks, 'Q&A Patterns', 'pass' if len(questions) >= 2 else 'warning',
              'Counts question-and-answer patterns in your content. Q&A format is the most AI-cited content structure because it directly matches how users query AI systems. Pages with clear Q&A patterns are 3x more likely to be cited in AI-generated answers.',
              f'{len(questions)} Q&A pattern(s) found — {"strong alignment with AI query patterns" if len(questions) >= 2 else "few Q&A patterns — AI systems prefer explicit question-answer format"}',
              'Add Q&A patterns: 1) Use questions as subheadings (H2/H3). 2) Answer immediately in the first sentence after the heading. 3) Target "People Also Ask" questions from Google. 4) Match the exact phrasing users type into AI chatbots.',
              'Critical', 'LLM Interpretability')

    definitions = re.findall(r'\b\w+\s+(?:is|are|means|refers to|defined as|is defined as)\s+[^.]+\.', text)
    add_check(checks, 'Direct Definitions', 'pass' if definitions else 'warning',
              'Scans for direct definition patterns ("X is...", "X means...", "X refers to..."). These are the most extractable content patterns for AI systems. When an AI needs to define a concept, it looks for these exact sentence structures.',
              f'{len(definitions)} definition pattern(s) found — {"clear definitions available for AI extraction" if definitions else "no direct definitions — AI systems can\'t easily extract concept explanations"}',
              'Write direct definitions: 1) Start key paragraphs with "X is [definition]." 2) Use "refers to," "means," and "is defined as" patterns. 3) Keep definitions to 1-2 sentences. 4) Place them near the top of relevant sections.',
              'Critical', 'LLM Interpretability')

    paragraphs = soup.find_all('p')
    first_para = paragraphs[0].get_text() if paragraphs else ''
    has_answer_first = any(w in first_para.lower() for w in ['is', 'are', 'means', 'provides', 'helps', 'allows'])
    add_check(checks, 'Answer-First Writing', 'pass' if has_answer_first else 'warning',
              'Checks whether your content leads with the answer (inverted pyramid style) rather than building up to it. AI systems extract the first relevant sentence they find. If your answer is buried after paragraphs of context, AI will cite a competitor who answers first.',
              f'{"First paragraph contains answer-first language — key information is upfront" if has_answer_first else "First paragraph may bury the lede — consider leading with your main point"}',
              'Write answer-first: 1) Start each section with the key takeaway. 2) Follow with supporting details and examples. 3) Think "if AI only reads the first sentence, does it get the answer?" 4) This is the inverted pyramid style used in journalism.',
              'High', 'LLM Interpretability')

    sentences = re.split(r'[.!?]+', text)
    pronoun_heavy = sum(1 for s in sentences if s.lower().strip().startswith(('it ', 'this ', 'that ', 'they ')))
    pronoun_ratio = pronoun_heavy / len(sentences) if sentences else 0
    add_check(checks, 'Self-Contained Sentences', 'pass' if pronoun_ratio < 0.2 else 'warning',
              'Measures how many sentences start with pronouns (it, this, that, they) that require context from previous sentences to understand. AI systems extract individual passages — if a sentence starts with "It" or "This," the extracted passage is meaningless without its predecessor.',
              f'{pronoun_ratio*100:.0f}% of sentences start with pronouns — {"good: most sentences are self-contained and extractable" if pronoun_ratio < 0.2 else "high pronoun usage — many sentences lose meaning when extracted individually"}',
              'Write self-contained sentences: 1) Replace "It is important..." with "SEO auditing is important..." 2) Replace "This helps..." with "Schema markup helps..." 3) Each sentence should make sense if read in isolation by an AI system.',
              'High', 'LLM Interpretability')

    complex_words = [w for w in words if len(w) > 12]
    complex_ratio = len(complex_words) / word_count if word_count else 0
    add_check(checks, 'Plain Language', 'pass' if complex_ratio < 0.05 else 'warning',
              'Measures the ratio of complex words (13+ characters) in your content. AI systems trained on diverse text perform better with clear, accessible language. Content written at an 8th-10th grade reading level gets cited more frequently by AI answer engines.',
              f'{complex_ratio*100:.1f}% complex words — {"accessible reading level for broad AI citation" if complex_ratio < 0.05 else "high complexity — may reduce AI citation frequency"}',
              'Simplify your language: 1) Replace jargon with plain alternatives where possible. 2) Target 8th-10th grade reading level. 3) Use short sentences (15-20 words average). 4) Explain technical terms when you must use them.',
              'High', 'LLM Interpretability')

    conv_words = ['you', 'your', "you're", 'we', 'our', "we're"]
    conv_count = sum(text.lower().count(' ' + w + ' ') for w in conv_words)
    conv_ratio = conv_count / word_count if word_count else 0
    add_check(checks, 'Conversational Tone', 'pass' if conv_ratio > 0.005 else 'info',
              'Measures the use of conversational pronouns (you, your, we, our) that create a natural, engaging tone. AI systems increasingly favor content that reads naturally and conversationally, as it better matches how users phrase their queries.',
              f'Conversational pronoun ratio: {conv_ratio*100:.2f}% — {"natural, engaging tone detected" if conv_ratio > 0.005 else "formal tone — consider adding more you/your/we language"}',
              'Add conversational elements: 1) Address the reader directly with "you" and "your." 2) Use "we" to include your brand perspective. 3) Write as if explaining to a colleague, not writing a textbook.',
              'Medium', 'LLM Interpretability')

    # ===== 19-24: Passage Ranking & Snippet Readiness =====
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    question_headings = [h for h in headings if '?' in h.get_text()]
    add_check(checks, 'Question Headings', 'pass' if question_headings else 'warning',
              'Counts headings that are phrased as questions (containing "?"). Question headings directly match how users query AI systems and search engines. Google\'s passage ranking algorithm specifically looks for headings that match search queries.',
              f'{len(question_headings)} question heading(s) — {"headings align with AI query patterns" if question_headings else "no question headings — consider rephrasing headings as questions users would ask"}',
              'Use questions as headings: 1) "What is SEO?" instead of "SEO Overview." 2) "How do I improve page speed?" instead of "Page Speed." 3) Match exact phrases from Google\'s "People Also Ask" boxes. 4) AI systems match these directly to user queries.',
              'Critical', 'Snippet Readiness')

    generic_headings = ['introduction', 'conclusion', 'overview', 'summary', 'more']
    descriptive_h = [h for h in headings if len(h.get_text().split()) >= 3 and h.get_text().lower().strip() not in generic_headings]
    add_check(checks, 'Descriptive Headings', 'pass' if len(descriptive_h) >= len(headings) * 0.5 else 'warning',
              'Evaluates whether headings are descriptive (3+ words, not generic like "Introduction" or "Summary"). Descriptive headings help AI systems understand section content without reading the full text, improving passage ranking accuracy.',
              f'{len(descriptive_h)}/{len(headings)} headings are descriptive — {"good heading specificity" if len(descriptive_h) >= len(headings) * 0.5 else "too many generic headings — AI can\'t determine section content from headings alone"}',
              'Write descriptive headings: 1) Replace "Overview" with "Complete Guide to Technical SEO Auditing." 2) Include key terms in every heading. 3) Each heading should tell the reader (and AI) exactly what the section covers.',
              'High', 'Snippet Readiness')

    long_paras = [p for p in paragraphs if len(p.get_text().split()) > 100]
    add_check(checks, 'Concise Paragraphs', 'pass' if len(long_paras) <= 2 else 'warning',
              'Counts paragraphs exceeding 100 words. AI systems extract content at the passage level (typically 1-3 sentences). Long paragraphs force AI to extract more text than needed, diluting the answer. Short, focused paragraphs get cited more accurately.',
              f'{len(long_paras)} paragraph(s) over 100 words — {"content is well-segmented for AI extraction" if len(long_paras) <= 2 else "long paragraphs reduce AI extraction accuracy — break them up"}',
              'Keep paragraphs concise: 1) Limit to 3-5 sentences (50-80 words). 2) One idea per paragraph. 3) Use line breaks between distinct points. 4) AI passage ranking works best with focused, self-contained paragraphs.',
              'High', 'Snippet Readiness')

    h2_count = len(soup.find_all('h2'))
    h3_count = len(soup.find_all('h3'))
    section_ratio = (h2_count + h3_count) / (word_count / 300) if word_count > 300 else 1
    add_check(checks, 'Section Granularity', 'pass' if section_ratio >= 0.8 else 'warning',
              'Measures heading density relative to content length. Google\'s passage ranking indexes individual sections, not whole pages. More granular sections (one heading per ~300 words) give AI more precise passages to cite.',
              f'{h2_count} H2s, {h3_count} H3s for {word_count} words — {"good section granularity for passage ranking" if section_ratio >= 0.8 else "sections are too long — add more subheadings for better passage ranking"}',
              'Increase section granularity: 1) Add an H2 or H3 every 200-300 words. 2) Each section should cover one specific subtopic. 3) Use H2 for main topics, H3 for subtopics. 4) This creates more citable passages for AI.',
              'High', 'Snippet Readiness')

    steps = re.findall(r'step\s*\d|first,|second,|third,|finally,|next,|then,', text.lower())
    numbered_lists = soup.find_all('ol')
    add_check(checks, 'Step-by-Step Format', 'pass' if steps or numbered_lists else 'info',
              'Detects step-by-step instructional patterns (numbered lists, "Step 1," "First/Second/Third" sequences). Step-by-step content is heavily featured in AI Overviews and voice assistant responses because it provides clear, actionable guidance.',
              f'{len(steps)} step indicator(s), {len(numbered_lists)} ordered list(s) — {"instructional content structured for AI" if steps or numbered_lists else "no step-by-step format — consider structuring how-to content with numbered steps"}',
              'Structure instructions as steps: 1) Use <ol> for numbered sequences. 2) Start each step with an action verb. 3) Keep steps concise (1-2 sentences). 4) Add HowTo schema for rich results.',
              'Medium', 'Snippet Readiness')

    examples = ['for example', 'such as', 'e.g.', 'for instance', 'like this', 'including', 'specifically']
    example_count = sum(text.lower().count(e) for e in examples)
    add_check(checks, 'Concrete Examples', 'pass' if example_count >= 2 else 'info',
              'Counts concrete example indicators ("for example," "such as," "e.g.") in your content. AI systems prefer content with specific examples because they make abstract concepts concrete and verifiable, increasing citation confidence.',
              f'{example_count} example phrase(s) — {"good use of concrete examples" if example_count >= 2 else "few examples — AI prefers content with specific, concrete illustrations"}',
              'Add concrete examples: 1) Follow every concept with "For example..." or "Such as..." 2) Use real numbers, names, and scenarios. 3) Include code snippets for technical content. 4) Examples make your content more citable and trustworthy.',
              'Medium', 'Snippet Readiness')

    # ===== 25-30: Trust, Freshness & AI Optimization =====
    time_elements = soup.find_all('time')
    date_meta = soup.find('meta', property='article:modified_time') or soup.find('meta', property='article:published_time')
    add_check(checks, 'Content Timestamps', 'pass' if time_elements or date_meta else 'warning',
              'Checks for visible timestamps (<time> elements) or article date meta tags. Content freshness is a critical AI citation factor — AI systems prefer recently updated content and display dates to users. Undated content is perceived as potentially stale.',
              f'{len(time_elements)} <time> element(s), {"article date meta tag found" if date_meta else "no article date meta"} — {"freshness signals present" if time_elements or date_meta else "no date signals — AI may deprioritize undated content"}',
              'Add content timestamps: 1) Use <time datetime="2026-03-17">March 17, 2026</time> for visible dates. 2) Add article:published_time and article:modified_time meta tags. 3) Update the modified date whenever you revise content.',
              'High', 'Trust & Freshness')

    last_modified = response.headers.get('Last-Modified', '')
    add_check(checks, 'Last-Modified Header', 'pass' if last_modified else 'info',
              'Checks for the Last-Modified HTTP header, which tells crawlers when the page content was last changed. AI crawlers use this to prioritize re-crawling recently updated content and to assess freshness without downloading the full page.',
              f'{"Last-Modified: " + last_modified if last_modified else "No Last-Modified header — crawlers can\'t determine content freshness from HTTP headers"}',
              'Set the Last-Modified header: 1) Most web servers set this automatically for static files. 2) For dynamic pages, set it programmatically based on content update time. 3) Also set ETag for efficient conditional requests.',
              'Medium', 'Trust & Freshness')

    author_patterns = soup.find_all(class_=re.compile(r'author|bio|byline|written-by', re.I))
    author_schema = 'author' in html.lower() and ('Person' in html or 'name' in html)
    add_check(checks, 'Author Attribution', 'pass' if author_patterns or author_schema else 'warning',
              'Checks for visible author attribution (bylines, author bios) or author schema markup. Author attribution is a core E-E-A-T signal — Google and AI systems use it to evaluate content credibility. Content with named, credentialed authors ranks higher in AI citations.',
              f'{"Author attribution found — E-E-A-T author signals present" if author_patterns else ("Author schema detected" if author_schema else "No author attribution — content lacks E-E-A-T author signals")}',
              'Add author attribution: 1) Display author name and photo on every article. 2) Link to an author bio page with credentials. 3) Add Person schema with name, jobTitle, and sameAs links. 4) Include "Reviewed by [Expert]" for YMYL content.',
              'Critical', 'Trust & Freshness')

    citations = ['according to', 'source:', 'cited', 'reference', 'study shows', 'research', 'data from']
    has_citations = any(c in text.lower() for c in citations)
    external_links = [a for a in soup.find_all('a', href=True) if a['href'].startswith('http') and parsed.netloc not in a['href']]
    add_check(checks, 'Source Citations', 'pass' if has_citations or len(external_links) >= 2 else 'warning',
              'Checks for source citations and external reference links. AI systems evaluate content trustworthiness by checking whether claims are supported by external sources. Well-cited content is more likely to be selected for AI-generated answers.',
              f'{len(external_links)} external link(s), {"citation language found" if has_citations else "no citation language"} — {"content is well-sourced" if has_citations or len(external_links) >= 2 else "few sources — AI may question content reliability"}',
              'Cite your sources: 1) Link to authoritative sources (.gov, .edu, research papers). 2) Use "According to [Source]..." attribution. 3) Include a references/sources section. 4) AI systems weight well-cited content more heavily.',
              'High', 'Trust & Freshness')

    llms_txt = safe_get(f"{parsed.scheme}://{parsed.netloc}/llms.txt")
    add_check(checks, 'LLMs.txt File', 'pass' if llms_txt and llms_txt.status_code == 200 else 'info',
              'Checks for an llms.txt file at your site root, an emerging standard that provides AI crawlers with a structured summary of your site content, purpose, and preferred citation format. Think of it as robots.txt but specifically for AI systems.',
              f'{"llms.txt found — AI crawlers have structured guidance for your site" if llms_txt and llms_txt.status_code == 200 else "No llms.txt — consider adding one as the standard matures"}',
              'Create an llms.txt file: 1) Place at yoursite.com/llms.txt. 2) Include site name, description, key pages, and preferred citation format. 3) This is an emerging standard — early adoption signals AI-readiness.',
              'Low', 'AI Optimization')

    add_check(checks, 'AI-Friendly Length', 'pass' if 500 <= word_count <= 3000 else ('warning' if word_count < 300 else 'info'),
              'Evaluates whether content length falls within the optimal range for AI context windows (500-3000 words). Too short and there\'s insufficient context for AI to cite. Too long and key information gets diluted. The sweet spot provides comprehensive coverage without overwhelming AI extraction.',
              f'{word_count} words — {"within optimal AI context window range" if 500 <= word_count <= 3000 else ("too short for comprehensive AI citation" if word_count < 500 else "very long — key points may be diluted for AI extraction")}',
              'Optimize content length: 1) Aim for 500-3000 words for most pages. 2) For competitive topics, 1500-2500 words performs best. 3) If longer, use clear sections so AI can extract relevant passages. 4) Quality and structure matter more than raw word count.',
              'Medium', 'AI Optimization')

    # ===== 31-37: AI Crawlability & Bot Permissions =====
    robots_resp = safe_get(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    robots_text = robots_resp.text if robots_resp and robots_resp.status_code == 200 else ''

    gptbot_blocked = 'user-agent: gptbot' in robots_text.lower() and 'disallow: /' in robots_text.lower()
    add_check(checks, 'GPTBot Access', 'pass' if robots_text and not gptbot_blocked else ('warning' if gptbot_blocked else 'info'),
              'Checks whether OpenAI\'s GPTBot crawler is allowed or blocked in robots.txt. GPTBot crawls content for ChatGPT and OpenAI\'s search features. Blocking it prevents your content from being cited in ChatGPT responses and OpenAI-powered search results.',
              f'{"GPTBot BLOCKED in robots.txt — your content cannot be cited by ChatGPT" if gptbot_blocked else ("GPTBot allowed — content eligible for ChatGPT citations" if robots_text else "No robots.txt found — GPTBot defaults to allowed")}',
              'Review GPTBot access: 1) To allow: ensure no "User-agent: GPTBot / Disallow: /" in robots.txt. 2) To allow selectively: Disallow specific paths only. 3) Blocking GPTBot means zero visibility in ChatGPT and OpenAI search.',
              'High', 'AI Crawlability')

    google_ai_blocked = any(x in robots_text.lower() for x in ['user-agent: google-extended', 'user-agent: googleother'])
    google_ai_disallow = google_ai_blocked and 'disallow: /' in robots_text.lower()
    add_check(checks, 'Google AI Crawler', 'pass' if robots_text and not google_ai_disallow else ('warning' if google_ai_disallow else 'info'),
              'Checks whether Google-Extended and GoogleOther crawlers are allowed. Google-Extended controls whether your content is used for AI training and Gemini responses. GoogleOther handles additional AI-related crawling. Blocking these may reduce your visibility in Google AI Overviews.',
              f'{"Google AI crawlers BLOCKED — may reduce AI Overview visibility" if google_ai_disallow else ("Google AI crawlers allowed — content eligible for AI Overviews" if robots_text else "No robots.txt — Google AI crawlers default to allowed")}',
              'Review Google AI crawler access: 1) Google-Extended controls AI training data usage. 2) Blocking it may reduce AI Overview citations. 3) GoogleOther handles supplementary AI crawling. 4) Consider allowing both for maximum AI visibility.',
              'High', 'AI Crawlability')

    claudebot_blocked = 'user-agent: claudebot' in robots_text.lower() or 'user-agent: anthropic' in robots_text.lower()
    add_check(checks, 'ClaudeBot Access', 'pass' if robots_text and not claudebot_blocked else ('warning' if claudebot_blocked else 'info'),
              'Checks whether Anthropic\'s ClaudeBot crawler is allowed in robots.txt. ClaudeBot crawls content for Claude AI, which powers many enterprise AI applications and search integrations. Blocking it limits your reach in the growing Claude ecosystem.',
              f'{"ClaudeBot BLOCKED — content excluded from Claude AI citations" if claudebot_blocked else ("ClaudeBot allowed — content eligible for Claude AI citations" if robots_text else "No robots.txt — ClaudeBot defaults to allowed")}',
              'Review ClaudeBot access: 1) Allow for broader AI discoverability. 2) ClaudeBot respects robots.txt directives. 3) Anthropic\'s Claude powers many enterprise search and analysis tools.',
              'Medium', 'AI Crawlability')

    llms_full = safe_get(f"{parsed.scheme}://{parsed.netloc}/llms-full.txt")
    add_check(checks, 'LLMs-Full.txt', 'pass' if llms_full and llms_full.status_code == 200 else 'info',
              'Checks for an llms-full.txt file, the extended version of llms.txt that provides comprehensive site content in a format optimized for LLM ingestion. This file gives AI systems a complete, structured view of your site content beyond what crawling alone provides.',
              f'{"llms-full.txt found — comprehensive content available for AI ingestion" if llms_full and llms_full.status_code == 200 else "No llms-full.txt — AI systems rely on standard crawling only"}',
              'Create llms-full.txt: 1) Include detailed content from your key pages. 2) Structure with clear sections and headings. 3) This is an emerging standard — early adoption gives you an edge in AI discoverability.',
              'Low', 'AI Crawlability')

    sitemap_resp = safe_get(f"{parsed.scheme}://{parsed.netloc}/sitemap.xml")
    add_check(checks, 'Sitemap for AI Discovery', 'pass' if sitemap_resp and sitemap_resp.status_code == 200 else 'warning',
              'Checks for an accessible XML sitemap, which helps AI crawlers discover and index all your content efficiently. Without a sitemap, AI crawlers must follow links to find pages, potentially missing important content that isn\'t well-linked.',
              f'{"XML sitemap found — AI crawlers can discover all content" if sitemap_resp and sitemap_resp.status_code == 200 else "No sitemap found — AI crawlers may miss pages that aren\'t well-linked"}',
              'Create and submit an XML sitemap: 1) Include all important pages with lastmod dates. 2) Submit to Google Search Console and Bing Webmaster Tools. 3) Reference it in robots.txt: Sitemap: https://yoursite.com/sitemap.xml.',
              'High', 'AI Crawlability')

    meta_robots = soup.find('meta', {'name': 'robots'})
    robots_content = meta_robots.get('content', '').lower() if meta_robots else ''
    noai_directives = any(d in robots_content for d in ['noai', 'noimageai', 'nosnippet'])
    add_check(checks, 'AI Meta Directives', 'pass' if not noai_directives else 'warning',
              'Checks for AI-restrictive meta robot directives (noai, noimageai, nosnippet) that prevent AI systems from using your content. The nosnippet directive prevents Google from showing any text snippet, including in AI Overviews. noai is an emerging directive to block AI usage entirely.',
              f'{"AI-restrictive directives found: " + robots_content + " — content restricted from AI use" if noai_directives else "No AI restrictions — content available for AI citation and snippets"}',
              'Review AI meta directives: 1) Remove nosnippet if you want AI Overview visibility. 2) noai blocks AI from using your content entirely. 3) noimageai blocks AI from using your images. 4) Only use these if you specifically want to opt out of AI.',
              'High', 'AI Crawlability')

    # ===== 38-42: Knowledge Graph & Entity Authority =====
    json_ld_text = ' '.join([j.string or '' for j in json_ld])
    has_main_entity = 'mainEntity' in json_ld_text or 'mainEntityOfPage' in json_ld_text
    add_check(checks, 'Main Entity Declaration', 'pass' if has_main_entity else 'warning',
              'Checks for mainEntityOfPage or mainEntity in your schema, which explicitly tells AI systems what the primary topic of this page is. Without it, AI must infer the main topic from content analysis, which can be inaccurate for pages covering multiple subjects.',
              f'{"mainEntity/mainEntityOfPage declared — AI knows the primary topic" if has_main_entity else "No main entity declared — AI must infer the page\'s primary topic"}',
              'Add mainEntityOfPage to your schema: 1) For articles: "mainEntityOfPage": {"@type": "WebPage", "@id": "https://yoursite.com/page"}. 2) For FAQ pages: set mainEntity to the FAQPage. 3) This anchors AI understanding of your page\'s purpose.',
              'High', 'Knowledge Graph')

    breadcrumb_schema = 'BreadcrumbList' in html
    add_check(checks, 'Breadcrumb Schema', 'pass' if breadcrumb_schema else 'info',
              'Checks for BreadcrumbList schema, which maps your site\'s content hierarchy for AI systems. Breadcrumbs help AI understand how pages relate to each other and where content sits in your topic structure, improving topical authority signals.',
              f'{"BreadcrumbList schema found — site hierarchy mapped for AI" if breadcrumb_schema else "No breadcrumb schema — AI can\'t see your content hierarchy"}',
              'Add BreadcrumbList schema: 1) Map the path from homepage to current page. 2) Include name and URL for each level. 3) Also display visual breadcrumbs for users. 4) This enables breadcrumb rich results in Google.',
              'Medium', 'Knowledge Graph')

    comparison_terms = ['vs', 'versus', 'compared to', 'comparison', 'difference between', 'pros and cons', 'advantages', 'disadvantages']
    comparison_count = sum(text.lower().count(t) for t in comparison_terms)
    has_comparison_table = any(t for t in tables if any(ct in t.get_text().lower() for ct in ['vs', 'feature', 'comparison', 'pro', 'con']))
    add_check(checks, 'Comparison Content', 'pass' if comparison_count >= 2 or has_comparison_table else 'info',
              'Detects comparison content (vs, pros/cons, difference between) and comparison tables. Comparison queries are among the most common AI search patterns ("X vs Y," "pros and cons of X"). Pages with structured comparisons are heavily cited by AI answer engines.',
              f'{comparison_count} comparison phrase(s){", comparison table found" if has_comparison_table else ""} — {"strong comparison content for AI citation" if comparison_count >= 2 or has_comparison_table else "no comparison content — consider adding vs/pros-cons sections"}',
              'Add comparison content: 1) Create "X vs Y" sections for related topics. 2) Use comparison tables with clear columns. 3) Include "Pros and Cons" sections. 4) These directly match high-volume AI query patterns.',
              'Medium', 'Knowledge Graph')

    content_types = 0
    if paragraphs: content_types += 1
    if lists: content_types += 1
    if tables: content_types += 1
    if blockquotes: content_types += 1
    if soup.find_all('code') or soup.find_all('pre'): content_types += 1
    if soup.find_all(['img', 'video', 'audio']): content_types += 1
    add_check(checks, 'Content Format Diversity', 'pass' if content_types >= 4 else ('warning' if content_types >= 2 else 'fail'),
              'Counts the variety of content formats on the page (text, lists, tables, quotes, code, media). AI systems extract different types of information from different formats — tables for data, lists for steps, code for implementations. Format diversity increases citation opportunities.',
              f'{content_types}/6 content types (text, lists, tables, quotes, code, media) — {"rich format diversity for AI extraction" if content_types >= 4 else "limited formats — AI has fewer extraction opportunities"}',
              'Diversify content formats: 1) Add tables for structured data. 2) Use lists for key points. 3) Include code blocks for technical content. 4) Add images with figcaptions. 5) Use blockquotes for expert opinions. 6) Each format creates a new AI citation opportunity.',
              'High', 'Knowledge Graph')

    internal_links = [a for a in soup.find_all('a', href=True) if parsed.netloc in urljoin(url, a.get('href', '')) and a.get_text().strip()]
    descriptive_internal = [a for a in internal_links if len(a.get_text().split()) >= 2]
    add_check(checks, 'Topic Cluster Links', 'pass' if len(descriptive_internal) >= 3 else 'warning',
              'Counts internal links with descriptive anchor text (2+ words). Topic clusters connected by descriptive internal links help AI systems map your topical authority. AI uses link context to understand entity relationships and content depth.',
              f'{len(descriptive_internal)} descriptive internal link(s) — {"strong topic cluster signals for AI" if len(descriptive_internal) >= 3 else "weak internal linking — AI can\'t map your topical authority"}',
              'Build topic clusters: 1) Link related pages with descriptive anchor text ("learn about technical SEO" not "click here"). 2) Create pillar pages that link to cluster content. 3) Each cluster page should link back to the pillar. 4) This builds topical authority for AI.',
              'High', 'Knowledge Graph')

    cite_elements = soup.find_all('cite')
    ref_links = [a for a in external_links if any(d in a.get('href', '') for d in ['.gov', '.edu', '.org', 'wikipedia', 'scholar.google'])]
    add_check(checks, 'Authority Citations', 'pass' if cite_elements or len(ref_links) >= 1 else 'warning',
              'Checks for <cite> elements and links to authoritative domains (.gov, .edu, .org, Wikipedia, Google Scholar). AI answer engines heavily weight content that references authoritative sources, as it signals factual reliability and research depth.',
              f'{len(cite_elements)} <cite> tag(s), {len(ref_links)} authority link(s) — {"authoritative sourcing detected" if cite_elements or len(ref_links) >= 1 else "no authority citations — AI may question content reliability"}',
              'Add authority citations: 1) Link to .gov, .edu, and .org sources. 2) Reference peer-reviewed research via Google Scholar. 3) Use <cite> tags for formal citations. 4) AI engines weight these sources heavily when selecting content to cite.',
              'High', 'Knowledge Graph')

    # ===== 43-45: WordPress & CMS Publishing Readiness =====
    wp_api_link = soup.find('link', rel='https://api.w.org/')
    wp_json_head = response.headers.get('Link', '')
    has_wp_api = wp_api_link is not None or 'api.w.org' in wp_json_head
    add_check(checks, 'CMS API Discoverability', 'pass' if has_wp_api else 'info',
              'Checks for WordPress REST API or CMS API discoverability headers. A discoverable CMS API enables automated content publishing workflows, including AI-assisted content optimization pipelines that can programmatically update schema, meta tags, and content structure.',
              f'{"CMS REST API detected — automated publishing workflows possible" if has_wp_api else "No CMS API detected — manual content updates only"}',
              'If using WordPress: the REST API is enabled by default. For other CMS platforms, ensure API endpoints are discoverable via Link headers. This enables AEO automation tools to optimize content programmatically.',
              'Low', 'Publishing Readiness')

    has_article_schema = 'Article' in html or 'BlogPosting' in html or 'NewsArticle' in html
    add_check(checks, 'Article Schema', 'pass' if has_article_schema else 'warning',
              'Checks for Article, BlogPosting, or NewsArticle schema markup. Article schema provides AI systems with structured metadata about your content including author, publish date, modified date, and headline — all critical signals for AI freshness evaluation and citation.',
              f'{"Article/BlogPosting schema found — content metadata structured for AI" if has_article_schema else "No article schema — AI lacks structured content metadata"}',
              'Add Article schema: 1) Use BlogPosting for blog content, NewsArticle for news. 2) Include author (Person), datePublished, dateModified, headline, and image. 3) This is essential for Google Discover and AI Overview eligibility.',
              'High', 'Publishing Readiness')

    has_excerpt = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    has_slug = len(parsed.path.strip('/').split('/')) >= 1 and parsed.path != '/'
    has_categories = soup.find(class_=re.compile(r'category|tag|topic', re.I)) or 'articleSection' in html
    pipeline_score = sum([bool(has_excerpt), bool(has_slug), bool(has_categories), bool(json_ld), bool(has_article_schema)])
    add_check(checks, 'AEO Pipeline Readiness', 'pass' if pipeline_score >= 4 else ('warning' if pipeline_score >= 2 else 'fail'),
              'Evaluates 5 signals that indicate your content is ready for automated AEO optimization: excerpt/description, clean URL slug, category/topic classification, JSON-LD schema, and article type markup. Higher scores mean AI optimization tools can work more effectively with your content.',
              f'{pipeline_score}/5 AEO signals (excerpt, slug, categories, schema, article type) — {"content is well-structured for AEO automation" if pipeline_score >= 4 else "missing key signals for automated AEO optimization"}',
              'Improve AEO pipeline readiness: 1) Add meta description (excerpt). 2) Use clean, descriptive URL slugs. 3) Categorize content with visible tags/categories. 4) Add JSON-LD schema. 5) Use Article/BlogPosting type. All 5 enable automated optimization.',
              'High', 'Publishing Readiness')

    passed = sum(1 for c in checks if c['status'] == 'pass')
    return {'score': round((passed / len(checks)) * 100, 1), 'checks': checks, 'total': len(checks), 'passed': passed}




# ============== API ROUTES ==============
@app.route('/')
def serve_index():
    return send_from_directory('..', 'index.html')

@app.route('/analyze')
def serve_analyze():
    return send_from_directory('..', 'analyze.html')

@app.route('/guides')
def serve_guides():
    return send_from_directory('..', 'guides.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('../assets', filename)

@app.route('/api/analyze', methods=['POST'])
def analyze_url():
    """Main SEO analysis endpoint - 216 checks across 9 categories"""
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
        'totalChecks': 216,
        'categories': {
            'technical': 30,
            'onpage': 24,
            'content': 18,
            'mobile': 15,
            'performance': 17,
            'security': 13,
            'social': 24,
            'local': 30,
            'geo': 45
        }
    })

# Ollama LLM Configuration
OLLAMA_URL = 'https://api.databi.io/api'  # Reverse proxy to local Ollama server

@app.route('/api/ai-recommendations', methods=['POST'])
def get_ai_recommendations():
    """Generate AI-powered SEO recommendations using local LLM with full audit context"""
    data = request.get_json()
    audit_results = data.get('auditResults', {})
    url = data.get('url', '')
    
    if not audit_results:
        return jsonify({'error': 'Audit results required'}), 400
    
    # Build comprehensive audit summary - include ALL checks for full context
    # Llama 3.1 supports 128K context, so we can send much more data
    
    full_audit_summary = []
    critical_issues = []
    high_issues = []
    medium_issues = []
    low_issues = []
    passing_checks = []
    
    for cat_key, cat_data in audit_results.get('categories', {}).items():
        cat_name = cat_data.get('name', cat_key.upper())
        cat_score = cat_data.get('score', 0)
        cat_total = cat_data.get('total', 0)
        cat_passed = cat_data.get('passed', 0)
        
        full_audit_summary.append(f"\n### {cat_name} ({cat_score:.0f}% - {cat_passed}/{cat_total} passed)")
        
        for check in cat_data.get('checks', []):
            check_name = check.get('name', 'Unknown')
            check_status = check.get('status', 'unknown')
            check_value = check.get('value', '')
            check_rec = check.get('recommendation', '')
            check_impact = check.get('impact', 'Medium')
            check_category = check.get('category', '')
            
            check_line = f"  [{check_status.upper()}] {check_name}: {check_value}"
            if check_status in ['fail', 'warning']:
                check_line += f" → {check_rec} (Impact: {check_impact})"
                
                # Categorize by impact for prioritization
                issue_entry = {
                    'category': cat_name,
                    'subcategory': check_category,
                    'name': check_name,
                    'value': check_value,
                    'recommendation': check_rec,
                    'impact': check_impact,
                    'status': check_status
                }
                
                if check_impact == 'Critical':
                    critical_issues.append(issue_entry)
                elif check_impact == 'High':
                    high_issues.append(issue_entry)
                elif check_impact == 'Medium':
                    medium_issues.append(issue_entry)
                else:
                    low_issues.append(issue_entry)
            else:
                passing_checks.append(f"{cat_name} > {check_name}")
            
            full_audit_summary.append(check_line)
    
    # Build prioritized issues section
    prioritized_issues = []
    
    if critical_issues:
        prioritized_issues.append("\n🚨 CRITICAL ISSUES (Fix Immediately):")
        for issue in critical_issues:
            prioritized_issues.append(f"  • [{issue['category']}] {issue['name']}: {issue['value']}")
            prioritized_issues.append(f"    Fix: {issue['recommendation']}")
    
    if high_issues:
        prioritized_issues.append("\n⚠️ HIGH PRIORITY ISSUES:")
        for issue in high_issues:
            prioritized_issues.append(f"  • [{issue['category']}] {issue['name']}: {issue['value']}")
            prioritized_issues.append(f"    Fix: {issue['recommendation']}")
    
    if medium_issues:
        prioritized_issues.append("\n📋 MEDIUM PRIORITY ISSUES:")
        for issue in medium_issues[:15]:  # Limit medium to top 15
            prioritized_issues.append(f"  • [{issue['category']}] {issue['name']}: {issue['value']}")
            prioritized_issues.append(f"    Fix: {issue['recommendation']}")
    
    if low_issues:
        prioritized_issues.append("\n📝 LOW PRIORITY (Nice to Have):")
        for issue in low_issues[:10]:  # Limit low to top 10
            prioritized_issues.append(f"  • [{issue['category']}] {issue['name']}")
    
    full_audit_text = '\n'.join(full_audit_summary)
    prioritized_text = '\n'.join(prioritized_issues)
    
    # Count issues by severity
    total_critical = len(critical_issues)
    total_high = len(high_issues)
    total_medium = len(medium_issues)
    total_low = len(low_issues)
    total_passing = len(passing_checks)
    
    # Build dynamic category scores summary
    category_scores = []
    for cat_key, cat_data in audit_results.get('categories', {}).items():
        cat_name = cat_data.get('name', cat_key)
        cat_score = cat_data.get('score', 0)
        cat_passed = cat_data.get('passed', 0)
        cat_total = cat_data.get('total', 0)
        category_scores.append(f"  • {cat_name}: {cat_score:.0f}% ({cat_passed}/{cat_total} passed)")
    
    category_scores_text = '\n'.join(category_scores)
    
    prompt = f"""You are an expert SEO consultant with deep knowledge of all aspects of search engine optimization. Analyze this comprehensive SEO audit and provide detailed, actionable recommendations for each category.

## WEBSITE AUDIT SUMMARY
**URL:** {url}
**Overall Score:** {audit_results.get('overallScore', 0):.0f}%
**Total Checks:** {audit_results.get('totalChecks', 0)}
**Passed:** {audit_results.get('totalPassed', 0)}
**Issues Found:** {total_critical} Critical, {total_high} High, {total_medium} Medium, {total_low} Low

## CATEGORY BREAKDOWN
{category_scores_text}

## PRIORITIZED ISSUES BY SEVERITY
{prioritized_text}

## COMPLETE AUDIT RESULTS BY CATEGORY
{full_audit_text}

## WHAT'S WORKING WELL ({total_passing} checks passing)
{', '.join(passing_checks[:30])}{'...' if len(passing_checks) > 30 else ''}

---

Based on this comprehensive audit, provide a detailed response with the following sections. For each section, analyze the relevant audit results and provide specific, actionable recommendations with code examples where applicable.

## 1. EXECUTIVE SUMMARY
Brief overview of the site's SEO health, strongest areas, and most critical issues needing immediate attention. Include a priority ranking of which categories need the most work.

## 2. CRITICAL FIXES (Do These First)
For each critical/high severity issue found in the audit:
- What's wrong and why it matters for rankings/visibility
- Step-by-step fix instructions
- Actual code snippets where applicable

## 3. QUICK WINS (Under 30 Minutes Each)
Easy fixes from any category that will improve scores quickly with minimal effort.

---

## 4. TECHNICAL SEO RECOMMENDATIONS
Based on the Technical SEO audit results, provide fixes for:
- Crawlability issues (robots.txt, sitemap, canonical tags)
- Security headers (HTTPS, HSTS, CSP, X-Frame-Options)
- URL structure optimization
- Internal linking improvements
- Structured data implementation
Include specific code snippets for robots.txt, .htaccess, or server configuration.

## 5. ON-PAGE SEO RECOMMENDATIONS
Based on the On-Page SEO audit results, provide fixes for:
- Title tag and meta description optimization
- Heading hierarchy (H1, H2, H3 structure)
- Image optimization (alt text, dimensions, lazy loading)
- Content structure improvements
Include example title tags and meta descriptions tailored to the site.

## 6. CONTENT SEO RECOMMENDATIONS
Based on the Content SEO audit results, provide fixes for:
- Content length and depth improvements
- Readability and engagement optimization
- E-E-A-T signals (expertise, experience, authority, trust)
- Internal and external linking strategy
Include content outline suggestions and E-E-A-T improvement tactics.

## 7. MOBILE SEO RECOMMENDATIONS
Based on the Mobile SEO audit results, provide fixes for:
- Viewport and responsive design issues
- Touch target sizing
- Mobile page speed optimization
- Mobile-specific UX improvements
Include CSS media query examples and mobile optimization code.

## 8. PERFORMANCE RECOMMENDATIONS
Based on the Performance audit results, provide fixes for:
- Page load time optimization
- Core Web Vitals (LCP, FID, CLS)
- Resource optimization (images, scripts, CSS)
- Caching and compression
Include specific performance optimization code and configurations.

## 9. SECURITY RECOMMENDATIONS
Based on the Security audit results, provide fixes for:
- SSL/HTTPS implementation
- Security headers configuration
- Mixed content issues
- Form and data protection
Include complete security header configurations for Apache/Nginx.

## 10. LOCAL SEO RECOMMENDATIONS
Based on the Local SEO audit results (35 checks), provide fixes for:
- NAP (Name, Address, Phone) consistency and visibility
- LocalBusiness schema markup implementation
- Google Business Profile optimization signals
- Local trust signals and reviews
- Citation and directory optimization
- Voice/AI search local optimization
Include complete LocalBusiness JSON-LD schema tailored to the business.

## 11. SOCIAL SEO RECOMMENDATIONS
Based on the Social SEO audit results (25 checks), provide fixes for:
- Open Graph meta tags (og:title, og:description, og:image)
- Twitter/X Card implementation
- LinkedIn optimization
- SameAs schema for social profiles
- Social sharing integration
Include complete Open Graph and Twitter Card meta tag code.

## 12. AI/GEO OPTIMIZATION (Generative Engine Optimization)
Based on the GEO/AEO audit results (45 checks across 8 subcategories), provide fixes for:
- Structured data for AI parsing (JSON-LD, FAQ schema, HowTo, Speakable)
- Content formatting for LLM comprehension (Q&A patterns, definitions, answer-first writing)
- Answer Engine Optimization (featured snippets, PAA, passage ranking)
- AI citation optimization (self-contained sentences, plain language, examples)
- AI Crawlability (GPTBot, Google-Extended, ClaudeBot permissions in robots.txt)
- llms.txt and llms-full.txt implementation for AI crawler guidance
- Knowledge Graph readiness (mainEntityOfPage, BreadcrumbList, topic clusters)
- Content format diversity (tables, lists, code blocks, comparisons)
- CMS/WordPress publishing readiness (Article schema, REST API, AEO pipeline signals)
Include FAQ schema, AI-optimized structured data, and robots.txt AI bot configuration.

---

## 13. COMPLETE CODE SNIPPETS
Provide ready-to-implement code blocks for all major fixes:

### A. Schema.org JSON-LD (combine all relevant types)
```json
// Complete schema markup for this site
```

### B. Meta Tags (head section)
```html
<!-- Complete meta tag block including OG, Twitter, etc. -->
```

### C. Security Headers
```apache
# Apache .htaccess or Nginx config
```

### D. Robots.txt Template
```
# Optimized robots.txt
```

## 14. 90-DAY ACTION PLAN
Prioritized implementation roadmap:

**Week 1-2 (Critical):** [List specific tasks]
**Week 3-4 (High Priority):** [List specific tasks]
**Month 2 (Medium Priority):** [List specific tasks]
**Month 3 (Optimization):** [List specific tasks]

---

Be extremely specific and actionable. Every recommendation should include exact steps the website owner can implement immediately. Provide actual code, not placeholders. Reference specific issues found in the audit by name."""

    try:
        llm_response = requests.post(
            f"{OLLAMA_URL}/generate",
            headers={'Content-Type': 'application/json'},
            json={
                'model': 'llama3.1:latest',
                'stream': False,
                'prompt': prompt,
                'options': {
                    'num_ctx': 65536,  # Maximize context window for comprehensive analysis
                    'num_predict': 8192,  # Allow much longer responses for all categories
                    'temperature': 0.7  # Balanced creativity/accuracy
                }
            },
            timeout=300  # 5 minutes for comprehensive multi-category analysis
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
    print("📊 Total Checks: 216 across 9 categories")
    print("   - Technical SEO: 30 checks")
    print("   - On-Page SEO: 24 checks")
    print("   - Content SEO: 18 checks")
    print("   - Mobile SEO: 15 checks")
    print("   - Performance: 17 checks")
    print("   - Security: 13 checks")
    print("   - Social SEO: 24 checks (Enhanced)")
    print("   - Local SEO: 30 checks (Enhanced)")
    print("   - GEO/AEO: 45 checks (AI Crawlability + Knowledge Graph + Publishing Readiness)")
    print("📍 http://localhost:5000")
    app.run(debug=True, port=5000)
