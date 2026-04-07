"""
model_comparison.py
Feature 2: AI Model Disagreement Detector

Fires the same prompt at multiple AI models simultaneously,
then uses a secondary LLM call to produce a structured comparison.
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import psycopg2.extras

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


def init_comparison_tables():
    """Create the model_comparisons table if it doesn't exist."""
    from db import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_comparisons (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL DEFAULT %s,
                brand_name VARCHAR(255) NOT NULL,
                keyword VARCHAR(500) NOT NULL,
                models_queried JSONB NOT NULL,
                raw_responses JSONB NOT NULL,
                comparison_result JSONB NOT NULL,
                models_mentioning JSONB,
                disagreements JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """, (DEFAULT_PROJECT_ID,))
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_mc_brand ON model_comparisons(brand_name)",
            "CREATE INDEX IF NOT EXISTS idx_mc_created ON model_comparisons(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_mc_project ON model_comparisons(project_id)",
        ]:
            try:
                cur.execute(idx)
            except Exception:
                pass
        conn.commit()
        logger.info("model_comparisons table verified")


def _build_probe_prompt(brand_name, keyword):
    """Build the probe prompt sent to each AI model."""
    return (
        f"I'm researching '{keyword}'. What are the best options available? "
        f"Please provide a detailed, factual answer with specific product or brand recommendations."
    )


def _call_model(model_name, prompt):
    """Call a specific AI model and return the response."""
    from ai_provider import call_nova, call_ollama, call_groq
    try:
        if model_name == "nova":
            return {"model": "nova", "response": call_nova(prompt), "status": "ok"}
        elif model_name == "ollama":
            return {"model": "ollama", "response": call_ollama(prompt), "status": "ok"}
        elif model_name == "groq":
            return {"model": "groq", "response": call_groq(prompt), "status": "ok"}
        else:
            return {"model": model_name, "response": "", "status": "error", "error": f"Unknown model: {model_name}"}
    except Exception as e:
        return {"model": model_name, "response": "", "status": "error", "error": str(e)[:200]}


def _analyze_comparison(brand_name, keyword, responses):
    """Use a secondary LLM call to produce structured comparison."""
    from ai_provider import generate

    # Build the analysis prompt
    response_texts = ""
    for r in responses:
        if r["status"] == "ok":
            snippet = r["response"][:800]
            response_texts += f"\n--- {r['model'].upper()} ---\n{snippet}\n"

    analysis_prompt = (
        f"I asked multiple AI models about '{keyword}' to check if they mention the brand '{brand_name}'. "
        f"Here are their responses:\n{response_texts}\n\n"
        f"Analyze these responses and return ONLY a JSON object (no markdown, no explanation) with this structure:\n"
        f'{{"brand_mentioned_by": ["model1", "model2"], '
        f'"brand_not_mentioned_by": ["model3"], '
        f'"disagreements": [{{"topic": "...", "models_disagree": ["model1", "model2"], "details": "..."}}], '
        f'"consensus": "brief summary of what models agree on", '
        f'"brand_sentiment": {{"model1": "positive/neutral/negative"}}}}'
    )

    try:
        raw = generate(analysis_prompt, provider="nova")
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            return json.loads(json_match.group())
        return {"raw_analysis": raw, "parse_error": "Could not extract JSON"}
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)[:200]}"}


def probe_all_models(brand_name, keyword, project_id=None):
    """Fire the same prompt at all available models and compare responses."""
    pid = project_id or DEFAULT_PROJECT_ID
    prompt = _build_probe_prompt(brand_name, keyword)
    models = ["nova", "groq", "ollama"]

    t0 = time.time()

    # Fire all models concurrently
    responses = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_call_model, m, prompt): m for m in models}
        for future in as_completed(futures):
            responses.append(future.result())

    # Analyze comparison (only with successful responses)
    successful = [r for r in responses if r["status"] == "ok"]
    failed = [r for r in responses if r["status"] == "error"]
    comparison = _analyze_comparison(brand_name, keyword, successful) if successful else {"error": "All models failed"}

    elapsed = round(time.time() - t0, 2)

    # Save to DB
    comp_id = None
    try:
        from db import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO model_comparisons
                    (project_id, brand_name, keyword, models_queried, raw_responses,
                     comparison_result, models_mentioning, disagreements)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                pid, brand_name, keyword,
                json.dumps(models),
                json.dumps({r["model"]: r["response"][:2000] if r["status"] == "ok" else r.get("error", "failed") for r in responses}),
                json.dumps(comparison),
                json.dumps(comparison.get("brand_mentioned_by", [])),
                json.dumps(comparison.get("disagreements", [])),
            ))
            comp_id = str(cur.fetchone()[0])
            conn.commit()
    except Exception as e:
        logger.warning("Failed to persist model comparison to RDS: %s", e)

    return {
        "comparison_id": comp_id,
        "brand_name": brand_name,
        "keyword": keyword,
        "models_queried": models,
        "models_responding": [r["model"] for r in successful],
        "models_failed": [{"model": r["model"], "reason": r.get("error", "unknown")} for r in failed],
        "comparison": comparison,
        "elapsed_seconds": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_comparison_history(brand_name=None, limit=10, project_id=None):
    """Get past model comparisons."""
    try:
        from db import get_conn
        pid = project_id or DEFAULT_PROJECT_ID
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if brand_name:
                cur.execute("""
                    SELECT id, brand_name, keyword, models_queried, comparison_result,
                           models_mentioning, disagreements, created_at
                    FROM model_comparisons
                    WHERE project_id = %s AND brand_name = %s
                    ORDER BY created_at DESC LIMIT %s
                """, (pid, brand_name, limit))
            else:
                cur.execute("""
                    SELECT id, brand_name, keyword, models_queried, comparison_result,
                           models_mentioning, disagreements, created_at
                    FROM model_comparisons
                    WHERE project_id = %s
                    ORDER BY created_at DESC LIMIT %s
                """, (pid, limit))
            rows = cur.fetchall()
            for r in rows:
                r["id"] = str(r["id"])
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()
            return rows
    except Exception as e:
        logger.warning("Failed to fetch comparison history: %s", e)
        return []
