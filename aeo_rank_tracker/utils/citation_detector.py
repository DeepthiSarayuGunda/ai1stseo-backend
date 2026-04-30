"""
Citation detection for AEO Rank Tracker.
Detects if a brand/domain is mentioned in LLM responses.
"""

import re


def detect_citation(response_text: str, brand_name: str, target_domain: str) -> dict:
    """Detect if brand or domain appears in the LLM response.

    Returns:
        dict with keys: found (bool), match_type (str), matches (list[str])
    """
    text_lower = response_text.lower()
    matches = []
    match_type = None

    # Check brand name (exact word boundary match)
    brand_lower = brand_name.lower()
    if brand_lower in text_lower:
        matches.append(f"brand:{brand_name}")
        match_type = "brand_mention"

    # Check domain (strip protocol/www)
    domain_clean = target_domain.lower().replace("https://", "").replace("http://", "").replace("www.", "")
    if domain_clean in text_lower:
        matches.append(f"domain:{target_domain}")
        match_type = match_type or "domain_mention"
        if match_type == "brand_mention":
            match_type = "brand_and_domain"

    # Check for URL patterns containing the domain
    url_pattern = re.compile(
        rf'https?://(?:www\.)?{re.escape(domain_clean)}[^\s]*', re.IGNORECASE
    )
    url_matches = url_pattern.findall(response_text)
    if url_matches:
        matches.extend([f"url:{u}" for u in url_matches[:3]])
        if not match_type:
            match_type = "url_citation"

    return {
        "found": len(matches) > 0,
        "match_type": match_type,
        "matches": matches,
    }


def detect_citation_simple(response_text: str, brand_name: str, target_domain: str) -> bool:
    """Simple boolean check — is the brand/domain cited?"""
    return detect_citation(response_text, brand_name, target_domain)["found"]
