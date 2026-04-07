"""
share_of_voice.py
Feature 5: AI Share of Voice

Calculates what % of AI-generated answers mention your brand vs competitors.
The headline market intelligence metric for CMOs.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import psycopg2.extras

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


def init_sov_tables():
    """Create share_of_voice table."""
    from db import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS share_of_voice (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL DEFAULT %s,
                brand VARCHAR(255) NOT NULL,
                competitors JSONB NOT NULL,
                keywords JSONB NOT NULL,
                results JSONB NOT NULL,
                sov_summary JSONB NOT NULL,
                total_probes INTEGER DEFAULT 0,
                scanned_at TIMESTAMP DEFAULT NOW()
            )
        """, (DEFAULT_PROJECT_ID,))
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_sov_brand ON share_of_voice(brand)",
            "CREATE INDEX IF NOT EXISTS idx_sov_scanned ON share_of_voice(scanned_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sov_project ON share_of_voice(project_id)",
        ]:
            try:
                cur.execute(idx)
            except Exception:
                pass
        conn.commit()
        logger.info("share_of_voice table verified")


def _detect_brand_in_text(text, brand):
    """Case-insensitive brand detection in AI response."""
    pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
    return bool(pattern.search(text))


def _probe_keyword(keyword, all_brands, provider):
    """Probe a single keyword with 10 prompt variations and detect all brand mentions."""
    from ai_provider import generate

    prompts = [
        f"What are the best {keyword}? Please recommend specific brands.",
        f"Recommend top {keyword} brands. Be specific.",
        f"What {keyword} should I buy? Name specific brands.",
        f"Best {keyword} for beginners — which brands?",
        f"Top rated {keyword} brands in 2025",
        f"Compare the leading {keyword} brands",
        f"Which {keyword} brands do experts recommend?",
        f"Most popular {keyword} right now — name brands",
        f"Premium vs budget {keyword} — which brands for each?",
        f"If I want the best {keyword}, which brand should I choose?",
    ]

    mentions = {b: 0 for b in all_brands}
    responses = []

    for prompt in prompts:
        try:
            response = generate(prompt, provider=provider)
            responses.append({"prompt": prompt, "response": response[:800], "status": "ok"})
            for brand in all_brands:
                if _detect_brand_in_text(response, brand):
                    mentions[brand] += 1
        except Exception as e:
            responses.append({"prompt": prompt, "response": "", "status": "error", "error": str(e)[:200]})

    return {
        "keyword": keyword,
        "mentions": mentions,
        "total_prompts": len(prompts),
        "responses": responses,
    }


def calculate_sov(brand, competitors, keywords, provider="nova", project_id=None):
    """Calculate AI Share of Voice for brand vs competitors across keywords."""
    pid = project_id or DEFAULT_PROJECT_ID
    all_brands = [brand] + competitors[:5]
    keywords = keywords[:10]
    t0 = time.time()

    # Probe all keywords concurrently
    keyword_results = []
    with ThreadPoolExecutor(max_workers=min(len(keywords), 4)) as pool:
        futures = {
            pool.submit(_probe_keyword, kw, all_brands, provider): kw
            for kw in keywords
        }
        for future in as_completed(futures):
            keyword_results.append(future.result())

    # Sort by original keyword order
    kw_order = {k: i for i, k in enumerate(keywords)}
    keyword_results.sort(key=lambda r: kw_order.get(r["keyword"], 99))

    # Calculate SOV per brand
    total_probes = sum(r["total_prompts"] for r in keyword_results)
    brand_mentions = {b: 0 for b in all_brands}
    for r in keyword_results:
        for b, count in r["mentions"].items():
            brand_mentions[b] += count

    sov_summary = {}
    for b in all_brands:
        pct = round((brand_mentions[b] / max(total_probes, 1)) * 100, 1)
        sov_summary[b] = {
            "mention_count": brand_mentions[b],
            "total_probes": total_probes,
            "sov_percentage": pct,
            "is_user_brand": b == brand,
        }

    # Find top competitor and gap
    user_sov = sov_summary[brand]["sov_percentage"]
    top_competitor = None
    top_comp_sov = 0
    for b in competitors:
        if b in sov_summary and sov_summary[b]["sov_percentage"] > top_comp_sov:
            top_comp_sov = sov_summary[b]["sov_percentage"]
            top_competitor = b

    gap_message = ""
    if top_competitor:
        diff = round(top_comp_sov - user_sov, 1)
        if diff > 0:
            gap_message = f"You are {diff}% behind {top_competitor}"
        elif diff < 0:
            gap_message = f"You are {abs(diff)}% ahead of {top_competitor}"
        else:
            gap_message = f"You are tied with {top_competitor}"

    elapsed = round(time.time() - t0, 2)

    # Save to DB
    sov_id = None
    try:
        from db import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO share_of_voice
                    (project_id, brand, competitors, keywords, results, sov_summary, total_probes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (pid, brand, json.dumps(competitors), json.dumps(keywords),
                  json.dumps(keyword_results), json.dumps(sov_summary), total_probes))
            sov_id = str(cur.fetchone()[0])
            conn.commit()
    except Exception as e:
        logger.warning("Failed to persist SOV to RDS: %s", e)

    return {
        "sov_id": sov_id,
        "brand": brand,
        "competitors": competitors,
        "keywords": keywords,
        "sov_summary": sov_summary,
        "top_competitor": top_competitor,
        "gap_message": gap_message,
        "total_probes": total_probes,
        "keyword_results": keyword_results,
        "elapsed_seconds": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_sov_latest(brand, project_id=None):
    """Get the latest SOV scan for a brand."""
    try:
        from db import get_conn
        pid = project_id or DEFAULT_PROJECT_ID
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT id, brand, competitors, keywords, sov_summary, total_probes, scanned_at
                FROM share_of_voice
                WHERE brand = %s AND project_id = %s
                ORDER BY scanned_at DESC LIMIT 1
            """, (brand, pid))
            row = cur.fetchone()
            if not row:
                return None
            row["id"] = str(row["id"])
            if row.get("scanned_at"):
                row["scanned_at"] = row["scanned_at"].isoformat()
            return row
    except Exception as e:
        logger.warning("Failed to fetch SOV latest: %s", e)
        return None
