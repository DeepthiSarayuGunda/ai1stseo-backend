"""
growth/lead_magnet.py
Lead Magnet Registry — static metadata store for Phase 1.

Stores lead magnet definitions as a Python list of dicts.
Provides lookup and validation functions. No database, no external deps.

Integration points:
  - growth/growth_api.py calls get_lead_magnets() and get_lead_magnet_by_slug()
  - growth/analytics_tracker.py logs lead_magnet_downloaded / lead_magnet_clicked events
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static registry — add new lead magnets here
# ---------------------------------------------------------------------------

_LEAD_MAGNETS: list[dict] = [
    {
        "id": "lm-001",
        "slug": "seo-starter-checklist",
        "title": "SEO Starter Checklist",
        "description": "A 20-point checklist to launch your first SEO campaign.",
        "download_url": "https://assets.ai1stseo.com/lead-magnets/seo-starter-checklist.pdf",
    },
]

_REQUIRED_FIELDS = ("id", "slug", "title", "description", "download_url")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_lead_magnet(entry: dict) -> bool:
    """Validate a single lead magnet entry.

    Checks: all required fields non-empty strings, download_url starts with https://.
    """
    for field in _REQUIRED_FIELDS:
        val = entry.get(field)
        if not val or not isinstance(val, str) or not val.strip():
            return False
    if not entry["download_url"].startswith("https://"):
        return False
    return True


def _check_unique_ids(magnets: list[dict]) -> list[dict]:
    """Filter out entries with duplicate IDs, keeping the first occurrence."""
    seen = set()
    result = []
    for m in magnets:
        mid = m.get("id", "")
        if mid in seen:
            logger.warning("Duplicate lead magnet id=%s — skipping", mid)
            continue
        seen.add(mid)
        result.append(m)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_lead_magnets() -> list[dict]:
    """Return all valid lead magnet entries from the registry."""
    unique = _check_unique_ids(_LEAD_MAGNETS)
    valid = []
    for entry in unique:
        if validate_lead_magnet(entry):
            valid.append(entry)
        else:
            logger.warning("Invalid lead magnet entry: %s — excluded", entry.get("id", "unknown"))
    return valid


def get_lead_magnet_by_slug(slug: str) -> dict | None:
    """Return a single lead magnet matching the given slug (case-insensitive)."""
    if not slug:
        return None
    normalized = slug.strip().lower()
    for entry in get_lead_magnets():
        if entry["slug"].strip().lower() == normalized:
            return entry
    return None
