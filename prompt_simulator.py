"""
prompt_simulator.py
Feature 6: Prompt Injection Simulator

Simulates 15 prompt variations to test brand visibility across different
ways users ask AI about a category. Identifies who gets recommended instead.
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

# 6 fixed prompt templates + 9 LLM-generated
FIXED_TEMPLATES = [
    "best {keyword}",
    "top {keyword} brands",
    "recommend {keyword} for beginners",
    "what {keyword} should I buy",
    "{keyword} comparison",
    "{keyword} vs alternatives",
]


def init_simulator_tables():
    """Create prompt_simulations table."""
    from db import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prompt_simulations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL DEFAULT %s,
                brand VARCHAR(255) NOT NULL,
                keyword VARCHAR(500) NOT NULL,
                hit_count INTEGER DEFAULT 0,
                miss_count INTEGER DEFAULT 0,
                hit_rate REAL DEFAULT 0.0,
                prompt_results JSONB NOT NULL,
                competitors_cited JSONB,
                gap_analysis TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """, (DEFAULT_PROJECT_ID,))
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_ps_brand ON prompt_simulations(brand)",
            "CREATE INDEX IF NOT EXISTS idx_ps_created ON prompt_simulations(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ps_project ON prompt_simulations(project_id)",
        ]:
            try:
                cur.execute(idx)
            except Exception:
                pass
        conn.commit()
        logger.info("prompt_simulations table verified")


def _generate_extra_prompts(keyword):
    """Use LLM to generate 9 additional natural prompt variations."""
    from ai_provider import generate
    prompt = (
        f"Generate 9 different ways a user might ask an AI chatbot about '{keyword}'. "
        f"Each should be a natural question or request. Return ONLY the 9 prompts, one per line, numbered 1-9. "
        f"Examples of style: 'Which {keyword} are worth the money?', 'Help me choose {keyword}'"
    )
    try:
        raw = generate(prompt, provider="nova")
        lines = [re.sub(r'^\d+[.)]\s*', '', line).strip() for line in raw.strip().split('\n') if line.strip()]
        return [l for l in lines if len(l) > 10][:9]
    except Exception as e:
        logger.warning("Failed to generate extra prompts: %s", e)
        return [
            f"which {keyword} are worth the money",
            f"help me choose {keyword}",
            f"{keyword} buying guide",
            f"most popular {keyword} right now",
            f"{keyword} for professionals",
            f"affordable {keyword} recommendations",
            f"{keyword} review and comparison",
            f"what experts say about {keyword}",
            f"{keyword} that people love",
        ]


def _detect_brands_in_text(text):
    """Extract likely brand names from AI response (capitalized words/phrases)."""
    # Find capitalized words that look like brand names (2+ chars, not common words)
    common = {'the','and','for','are','but','not','you','all','can','had','her','was','one','our','out',
              'has','its','let','may','who','did','get','how','him','his','she','too','use','best','top',
              'most','very','good','great','high','well','also','just','more','some','than','them','then',
              'what','when','with','will','from','have','been','this','that','they','each','make','like',
              'many','over','such','take','long','only','come','made','find','here','know','want','give',
              'first','could','these','other','which','their','about','would','there','after','should',
              'right','think','every','where','might','while','still','being','those','never','before',
              'between','through','running','shoes','tools','software','products','brands','options',
              'recommend','recommended','popular','quality','price','value','features','performance'}
    words = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', text)
    brands = [w for w in words if w.lower() not in common]
    # Count occurrences
    brand_counts = {}
    for b in brands:
        brand_counts[b] = brand_counts.get(b, 0) + 1
    # Return sorted by frequency
    return sorted(brand_counts.items(), key=lambda x: -x[1])


def _run_single_prompt(prompt_text, brand, provider):
    """Run a single prompt and check if brand is mentioned."""
    from ai_provider import generate
    try:
        response = generate(prompt_text, provider=provider)
        pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
        mentioned = bool(pattern.search(response))
        competitors = []
        if not mentioned:
            competitors = _detect_brands_in_text(response)[:5]
        return {
            "prompt": prompt_text,
            "brand_mentioned": mentioned,
            "competitors_cited": [{"brand": b, "count": c} for b, c in competitors],
            "response_snippet": response[:600],
            "status": "ok",
        }
    except Exception as e:
        return {
            "prompt": prompt_text,
            "brand_mentioned": False,
            "competitors_cited": [],
            "response_snippet": "",
            "status": "error",
            "error": str(e)[:200],
        }


def run_simulation(brand, keyword, provider="nova", project_id=None):
    """Run full prompt simulation: 15 prompts, detect hits/misses, gap analysis."""
    pid = project_id or DEFAULT_PROJECT_ID
    t0 = time.time()

    # Build 15 prompts
    fixed = [t.format(keyword=keyword) for t in FIXED_TEMPLATES]
    extra = _generate_extra_prompts(keyword)
    all_prompts = fixed + extra
    all_prompts = all_prompts[:15]

    # Run all prompts concurrently
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_run_single_prompt, p, brand, provider): p
            for p in all_prompts
        }
        for future in as_completed(futures):
            results.append(future.result())

    # Sort by original prompt order
    prompt_order = {p: i for i, p in enumerate(all_prompts)}
    results.sort(key=lambda r: prompt_order.get(r["prompt"], 99))

    hits = sum(1 for r in results if r["brand_mentioned"])
    misses = len(results) - hits
    hit_rate = round((hits / max(len(results), 1)) * 100, 1)

    # Aggregate competitor mentions from misses
    comp_agg = {}
    for r in results:
        if not r["brand_mentioned"]:
            for c in r["competitors_cited"]:
                name = c["brand"]
                comp_agg[name] = comp_agg.get(name, 0) + c["count"]
    top_competitors = sorted(comp_agg.items(), key=lambda x: -x[1])[:10]

    # Generate gap analysis
    gap_analysis = _generate_gap_analysis(brand, keyword, hit_rate, top_competitors)

    elapsed = round(time.time() - t0, 2)

    # Save to DB
    from db import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO prompt_simulations
                (project_id, brand, keyword, hit_count, miss_count, hit_rate,
                 prompt_results, competitors_cited, gap_analysis)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (pid, brand, keyword, hits, misses, hit_rate,
              json.dumps(results),
              json.dumps([{"brand": b, "mentions": c} for b, c in top_competitors]),
              gap_analysis))
        sim_id = str(cur.fetchone()[0])
        conn.commit()

    return {
        "simulation_id": sim_id,
        "brand": brand,
        "keyword": keyword,
        "total_prompts": len(results),
        "hits": hits,
        "misses": misses,
        "hit_rate": hit_rate,
        "prompt_results": results,
        "top_competitors": [{"brand": b, "mentions": c} for b, c in top_competitors],
        "gap_analysis": gap_analysis,
        "elapsed_seconds": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _generate_gap_analysis(brand, keyword, hit_rate, top_competitors):
    """Use LLM to generate plain-English gap analysis."""
    from ai_provider import generate
    comp_list = ", ".join([f"{b} ({c} mentions)" for b, c in top_competitors[:5]])
    prompt = (
        f"A brand '{brand}' was tested across 15 AI prompt variations for '{keyword}'. "
        f"Hit rate: {hit_rate}% (appeared in {hit_rate}% of AI responses). "
        f"Top competitors appearing instead: {comp_list or 'none detected'}.\n\n"
        f"Write 3-4 concise, actionable recommendations for {brand} to improve their AI visibility "
        f"for '{keyword}'. Focus on content strategy, structured data, and authority signals. "
        f"Be specific and practical. No fluff."
    )
    try:
        return generate(prompt, provider="nova")
    except Exception as e:
        return f"Gap analysis unavailable: {str(e)[:200]}"


def get_simulation_history(brand, limit=5, project_id=None):
    """Get past simulation results."""
    from db import get_conn
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, brand, keyword, hit_count, miss_count, hit_rate,
                   competitors_cited, gap_analysis, created_at
            FROM prompt_simulations
            WHERE brand = %s AND project_id = %s
            ORDER BY created_at DESC LIMIT %s
        """, (brand, pid, limit))
        rows = cur.fetchall()
        for r in rows:
            r["id"] = str(r["id"])
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
