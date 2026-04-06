"""
growth/email_subscriber.py
Email Subscriber Capture — core module.

Handles validation, sanitization, CRUD, export, and table initialization
for the email_subscribers table. Zero Flask dependencies.

This module is part of the ai1stseo.com 5-month growth plan.
It does NOT modify any existing tables or shared logic.
"""

import csv
import io
import logging
import re

import psycopg2.extras

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

CSV_HEADERS = [
    "id", "email", "name", "source", "platform",
    "campaign", "opted_in", "status", "subscribed_at",
]


# ---------------------------------------------------------------------------
# Table initialisation (called via lazy-init, NOT from app.py)
# ---------------------------------------------------------------------------

def init_subscriber_table() -> None:
    """Create email_subscribers table and indexes. Idempotent."""
    from db import get_conn

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS email_subscribers (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) NOT NULL UNIQUE,
                name VARCHAR(255),
                source VARCHAR(100) DEFAULT 'unknown',
                platform VARCHAR(100),
                campaign VARCHAR(255),
                opted_in BOOLEAN DEFAULT TRUE,
                status VARCHAR(50) DEFAULT 'active',
                subscribed_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_es_email ON email_subscribers(email)",
            "CREATE INDEX IF NOT EXISTS idx_es_source ON email_subscribers(source)",
            "CREATE INDEX IF NOT EXISTS idx_es_platform ON email_subscribers(platform)",
            "CREATE INDEX IF NOT EXISTS idx_es_campaign ON email_subscribers(campaign)",
            "CREATE INDEX IF NOT EXISTS idx_es_subscribed ON email_subscribers(subscribed_at DESC)",
        ]:
            try:
                cur.execute(idx)
            except Exception:
                pass
        conn.commit()
        logger.info("email_subscribers table verified")


# ---------------------------------------------------------------------------
# Validation & sanitisation helpers
# ---------------------------------------------------------------------------

def validate_email(email: str) -> bool:
    """Return True if *email* looks like a valid address."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def sanitize_input(value, max_length: int = 255):
    """Strip whitespace and truncate. Returns None if empty."""
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:max_length]


def normalize_filter(value):
    """Lowercase + strip a filter value to match stored format."""
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def add_subscriber(
    email: str,
    name=None,
    source: str = "unknown",
    platform=None,
    campaign=None,
    opted_in: bool = True,
) -> dict:
    """Validate, sanitise, and insert a subscriber. Returns result dict."""
    if not validate_email(email):
        return {"success": False, "error": "Invalid email format"}

    clean_email = email.strip().lower()
    clean_name = sanitize_input(name)
    clean_source = (sanitize_input(source, 100) or "unknown").lower()
    clean_platform = sanitize_input(platform, 100)
    if clean_platform:
        clean_platform = clean_platform.lower()
    clean_campaign = sanitize_input(campaign)
    if clean_campaign:
        clean_campaign = clean_campaign.lower()

    from db import get_conn

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO email_subscribers
                       (email, name, source, platform, campaign, opted_in)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (email) DO NOTHING
                   RETURNING id, email, subscribed_at""",
                (clean_email, clean_name, clean_source,
                 clean_platform, clean_campaign, opted_in),
            )
            row = cur.fetchone()
            conn.commit()
            if row is None:
                return {
                    "success": False,
                    "error": "Email already subscribed",
                    "duplicate": True,
                }
            return {
                "success": True,
                "subscriber": {
                    "id": str(row[0]),
                    "email": row[1],
                    "subscribed_at": row[2].isoformat() if row[2] else None,
                },
            }
    except Exception as e:
        logger.error("add_subscriber error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


def list_subscribers(
    page: int = 1,
    per_page: int = 25,
    source=None,
    platform=None,
    campaign=None,
) -> dict:
    """Paginated subscriber list with optional filters."""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    offset = (page - 1) * per_page

    clauses, params = [], []
    for val, col in [
        (normalize_filter(source), "source"),
        (normalize_filter(platform), "platform"),
        (normalize_filter(campaign), "campaign"),
    ]:
        if val:
            clauses.append(f"{col} = %s")
            params.append(val)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    from db import get_conn

    try:
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cur.execute(
                f"SELECT COUNT(*) AS cnt FROM email_subscribers {where}", params
            )
            total = cur.fetchone()["cnt"]

            cur.execute(
                f"SELECT * FROM email_subscribers {where} "
                f"ORDER BY subscribed_at DESC LIMIT %s OFFSET %s",
                params + [per_page, offset],
            )
            rows = cur.fetchall()
            for r in rows:
                r["id"] = str(r["id"])
                if r.get("subscribed_at"):
                    r["subscribed_at"] = r["subscribed_at"].isoformat()
                if r.get("updated_at"):
                    r["updated_at"] = r["updated_at"].isoformat()

            return {
                "success": True,
                "subscribers": rows,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": max(1, (total + per_page - 1) // per_page),
            }
    except Exception as e:
        logger.error("list_subscribers error: %s", e)
        return {"success": False, "error": f"Database error: {e}", "subscribers": []}


def export_subscribers(
    fmt: str = "json",
    source=None,
    platform=None,
    campaign=None,
):
    """Export ALL matching subscribers (no pagination).

    Returns a CSV string (fmt='csv') or a list of dicts (fmt='json').
    """
    clauses, params = [], []
    for val, col in [
        (normalize_filter(source), "source"),
        (normalize_filter(platform), "platform"),
        (normalize_filter(campaign), "campaign"),
    ]:
        if val:
            clauses.append(f"{col} = %s")
            params.append(val)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    from db import get_conn

    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            f"SELECT id, email, name, source, platform, campaign, "
            f"opted_in, status, subscribed_at "
            f"FROM email_subscribers {where} ORDER BY subscribed_at DESC",
            params,
        )
        rows = cur.fetchall()
        for r in rows:
            r["id"] = str(r["id"])
            if r.get("subscribed_at"):
                r["subscribed_at"] = r["subscribed_at"].isoformat()

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    return rows
