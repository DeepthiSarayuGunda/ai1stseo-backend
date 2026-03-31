"""
answer_fingerprint.py
Feature 1: AI Answer Fingerprinting

Tracks how AI model responses change over time for a brand/keyword.
Diffs new responses against previous ones and triggers alerts on changes.
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone

import psycopg2.extras

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


def init_fingerprint_tables():
    """Create the answer_fingerprints table if it doesn't exist."""
    from db import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS answer_fingerprints (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL DEFAULT %s,
                brand_name VARCHAR(255) NOT NULL,
                keyword VARCHAR(500) NOT NULL,
                ai_model VARCHAR(100) NOT NULL,
                full_response TEXT NOT NULL,
                response_hash VARCHAR(64) NOT NULL,
                diff_summary JSONB,
                change_detected BOOLEAN DEFAULT FALSE,
                probe_id UUID,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """, (DEFAULT_PROJECT_ID,))
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_fp_brand ON answer_fingerprints(brand_name, keyword)",
            "CREATE INDEX IF NOT EXISTS idx_fp_created ON answer_fingerprints(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_fp_project ON answer_fingerprints(project_id)",
        ]:
            try:
                cur.execute(idx)
            except Exception:
                pass
        conn.commit()
        logger.info("answer_fingerprints table verified")


def _split_sentences(text):
    """Split text into sentences for diffing."""
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]


def _compute_diff(old_text, new_text):
    """Compute added/removed sentences between two responses."""
    old_sentences = set(_split_sentences(old_text))
    new_sentences = set(_split_sentences(new_text))
    added = list(new_sentences - old_sentences)
    removed = list(old_sentences - new_sentences)
    return {
        "added": added[:20],
        "removed": removed[:20],
        "added_count": len(added),
        "removed_count": len(removed),
        "changed": len(added) > 0 or len(removed) > 0,
    }


def save_fingerprint(brand_name, keyword, ai_model, full_response, probe_id=None, project_id=None):
    """Save a response fingerprint and diff against the previous one."""
    from db import get_conn
    pid = project_id or DEFAULT_PROJECT_ID
    response_hash = hashlib.sha256(full_response.encode()).hexdigest()

    # Get the last fingerprint for this brand/keyword/model
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT full_response, response_hash FROM answer_fingerprints
            WHERE brand_name = %s AND keyword = %s AND ai_model = %s AND project_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (brand_name, keyword, ai_model, pid))
        prev = cur.fetchone()

    diff_summary = None
    change_detected = False
    if prev:
        if prev["response_hash"] != response_hash:
            diff_summary = _compute_diff(prev["full_response"], full_response)
            change_detected = diff_summary["changed"]
        else:
            diff_summary = {"added": [], "removed": [], "added_count": 0, "removed_count": 0, "changed": False}

    # Insert new fingerprint
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO answer_fingerprints
                (project_id, brand_name, keyword, ai_model, full_response, response_hash,
                 diff_summary, change_detected, probe_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (pid, brand_name, keyword, ai_model, full_response, response_hash,
              json.dumps(diff_summary) if diff_summary else None,
              change_detected, probe_id))
        fp_id = str(cur.fetchone()[0])
        conn.commit()

    # Publish change event to Redis if answer changed
    if change_detected:
        try:
            _publish_change_event(pid, brand_name, keyword, ai_model, diff_summary)
        except Exception as e:
            logger.warning("Redis publish failed: %s", e)

    return {
        "fingerprint_id": fp_id,
        "change_detected": change_detected,
        "diff_summary": diff_summary,
        "response_hash": response_hash,
    }


def _publish_change_event(account_id, brand_name, keyword, ai_model, diff_summary):
    """Publish answer change event to Redis pub/sub."""
    import redis
    import os
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        logger.info("REDIS_URL not set, skipping pub/sub (change logged to DB)")
        return
    r = redis.from_url(redis_url)
    channel = f"geo:answer_changed:{account_id}"
    payload = json.dumps({
        "brand_name": brand_name,
        "keyword": keyword,
        "ai_model": ai_model,
        "diff_summary": diff_summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    r.publish(channel, payload)
    logger.info("Published change event to %s", channel)


def get_fingerprint_history(brand_name, keyword=None, ai_model=None, limit=10, project_id=None):
    """Get the last N fingerprints for a brand, with diff summaries."""
    from db import get_conn
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = """
            SELECT id, brand_name, keyword, ai_model, response_hash,
                   diff_summary, change_detected, created_at
            FROM answer_fingerprints
            WHERE brand_name = %s AND project_id = %s
        """
        params = [brand_name, pid]
        if keyword:
            query += " AND keyword = %s"
            params.append(keyword)
        if ai_model:
            query += " AND ai_model = %s"
            params.append(ai_model)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        for r in rows:
            r["id"] = str(r["id"])
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
