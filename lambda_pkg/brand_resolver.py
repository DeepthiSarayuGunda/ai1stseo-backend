"""
brand_resolver.py
Resolves brand names to domains and vice versa.
Caches results in memory with TTL.
"""

import logging
import re
import time
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ── In-memory cache with TTL ─────────────────────────────────────────────────
_cache = {}  # key -> {"result": ..., "ts": float}
CACHE_TTL = 3600  # 1 hour


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL:
        return entry["result"]
    return None


def _cache_set(key: str, result):
    _cache[key] = {"result": result, "ts": time.time()}


# ── Domain resolution from brand name ────────────────────────────────────────

# Common brand -> domain mappings (fast path, no network needed)
KNOWN_BRANDS = {
    "google": "google.com",
    "amazon": "amazon.com",
    "apple": "apple.com",
    "microsoft": "microsoft.com",
    "facebook": "facebook.com",
    "meta": "meta.com",
    "netflix": "netflix.com",
    "twitter": "twitter.com",
    "x": "x.com",
    "linkedin": "linkedin.com",
    "github": "github.com",
    "shopify": "shopify.com",
    "wordpress": "wordpress.com",
    "notion": "notion.so",
    "slack": "slack.com",
    "zoom": "zoom.us",
    "stripe": "stripe.com",
    "hubspot": "hubspot.com",
    "salesforce": "salesforce.com",
    "mailchimp": "mailchimp.com",
    "semrush": "semrush.com",
    "ahrefs": "ahrefs.com",
    "moz": "moz.com",
}


def _guess_domains(brand: str) -> list[str]:
    """Generate likely domain candidates from a brand name."""
    slug = re.sub(r"[^a-z0-9]", "", brand.lower())
    return [
        f"{slug}.com",
        f"{slug}.io",
        f"{slug}.co",
        f"{slug}.org",
        f"{slug}.net",
        f"{slug}.ai",
    ]


def _check_domain(domain: str, timeout: int = 4) -> bool:
    """Check if a domain resolves to a live website."""
    for scheme in ("https://", "http://"):
        try:
            r = requests.head(
                f"{scheme}{domain}",
                timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; BrandResolver/1.0)"},
            )
            if r.status_code < 500:
                return True
        except Exception:
            continue
    return False


def _extract_brand_from_domain(domain: str) -> str:
    """Extract a likely brand name from a domain."""
    # Remove www. and TLD
    clean = domain.replace("www.", "")
    parts = clean.split(".")
    name = parts[0] if parts else clean
    # Title-case it
    return name.capitalize()


def _suggest_keywords(brand: str, domain: str = None) -> list[str]:
    """Generate suggested keywords based on brand name."""
    b = brand.lower()
    suggestions = [
        f"best {b} alternatives",
        f"{b} review",
        f"is {b} worth it",
        f"{b} vs competitors",
        f"top tools like {b}",
        f"{b} pricing",
        f"what is {b}",
        f"{b} features",
    ]
    return suggestions


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_brand(brand: str = None, url: str = None) -> dict:
    """
    Resolve brand <-> domain.

    Cases:
      1. brand only  -> find domain
      2. url only    -> extract brand
      3. both        -> validate consistency
    """
    result = {
        "brand": None,
        "domain": None,
        "url": None,
        "suggested_keywords": [],
        "alternatives": [],
        "source": None,
        "consistent": None,
    }

    # ── Case 2 & 3: URL provided ─────────────────────────────────────────
    if url:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        domain = (parsed.netloc or parsed.path).replace("www.", "")
        result["domain"] = domain
        result["url"] = f"https://{domain}"

        if not brand:
            # Case 2: URL only -> extract brand
            # Check reverse lookup in known brands
            for b, d in KNOWN_BRANDS.items():
                if d == domain or domain.endswith(d):
                    result["brand"] = b.capitalize()
                    result["source"] = "known_brands"
                    break
            if not result["brand"]:
                result["brand"] = _extract_brand_from_domain(domain)
                result["source"] = "extracted_from_url"
        else:
            # Case 3: both provided -> validate
            result["brand"] = brand.strip()
            slug = re.sub(r"[^a-z0-9]", "", brand.lower())
            domain_slug = domain.split(".")[0].lower()
            result["consistent"] = slug == domain_slug or slug in domain_slug or domain_slug in slug
            result["source"] = "user_provided_both"

    # ── Case 1: brand only ───────────────────────────────────────────────
    elif brand:
        brand = brand.strip()
        result["brand"] = brand
        cache_key = f"brand:{brand.lower()}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        # Check known brands first
        known = KNOWN_BRANDS.get(brand.lower())
        if known:
            result["domain"] = known
            result["url"] = f"https://{known}"
            result["source"] = "known_brands"
        else:
            # Try guessed domains
            candidates = _guess_domains(brand)
            verified = []
            for d in candidates:
                if _check_domain(d):
                    verified.append(d)
                    if not result["domain"]:
                        result["domain"] = d
                        result["url"] = f"https://{d}"
                        result["source"] = "domain_probe"
                if len(verified) >= 3:
                    break

            if len(verified) > 1:
                result["alternatives"] = [
                    {"domain": d, "url": f"https://{d}"} for d in verified
                ]

            if not result["domain"]:
                result["source"] = "unresolved"

        _cache_set(cache_key, result)
    else:
        return {"error": "Provide at least brand or url"}

    # Add keyword suggestions
    if result["brand"]:
        result["suggested_keywords"] = _suggest_keywords(
            result["brand"], result.get("domain")
        )

    return result
