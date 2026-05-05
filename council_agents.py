"""
council_agents.py
Multi-LLM AI Council — each agent uses a dedicated model via AWS Bedrock.

Architecture:
  - AEO Specialist       → Claude 3.5 Haiku (Anthropic)  — citation/attribution honesty
  - SEO Specialist       → Nova Lite (Amazon)            — structured on-page SEO checks
  - Content Analyst      → Llama 4 Maverick (Meta)       — natural language quality & E-E-A-T
  - Competitor Intel     → Mistral Large 2 (Mistral AI)  — comparative analysis
  - GEO/Local            → Nova Lite (Amazon)            — local signal pattern matching
  - Council Moderator    → Claude Sonnet 4 (Anthropic)   — conflict resolution & synthesis

Every agent returns a uniform JSON dict. If any LLM call fails, the rule-based
fallback from app.py runs so the Council never goes fully dark on the user.
"""

import json
import logging
import re

from bedrock_helper import invoke_converse

logger = logging.getLogger(__name__)


# ── Agent → Model assignment ─────────────────────────────────────────────── #

AGENT_MODELS = {
    "aeo": "claude-haiku",
    "seo": "nova-lite",
    "content": "llama-4-maverick",
    "competitor": "mistral-large",
    "geo": "nova-lite",
    "moderator": "claude-sonnet-4",
}

# Human-readable labels for UI surface
AGENT_MODEL_LABELS = {
    "aeo": "Claude 3.5 Haiku (Anthropic)",
    "seo": "Nova Lite (Amazon)",
    "content": "Llama 4 Maverick (Meta)",
    "competitor": "Mistral Large (Mistral AI)",
    "geo": "Nova Lite (Amazon)",
    "moderator": "Claude Sonnet 4 (Anthropic)",
}


# ── JSON extraction helper ────────────────────────────────────────────────── #

def _extract_json(text: str) -> dict:
    """Pull a JSON object out of an LLM response, tolerating prose or code fences."""
    if not text:
        return {}
    # Try fenced code block first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Fall back to first {...} in the response
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


def _normalize_agent_output(raw: dict, agent_name: str, focus: str, fallback_score: int) -> dict:
    """Guarantee a consistent shape regardless of how the model formatted things."""
    score = raw.get("score")
    if not isinstance(score, (int, float)):
        score = fallback_score
    score = max(0, min(100, int(score)))

    verdict = raw.get("verdict")
    if not isinstance(verdict, str) or not verdict:
        verdict = "Strong" if score >= 70 else ("Moderate" if score >= 40 else "Weak")

    def _as_list(v):
        if isinstance(v, list):
            return [str(x) for x in v if x]
        if isinstance(v, str) and v:
            return [v]
        return []

    return {
        "agent": agent_name,
        "focus": focus,
        "score": score,
        "verdict": verdict,
        "passed": _as_list(raw.get("strengths") or raw.get("passed")),
        "failed": _as_list(raw.get("weaknesses") or raw.get("failed")),
        "top_recommendations": _as_list(raw.get("top_3_actions") or raw.get("top_recommendations")),
    }


# ── Agent prompts ─────────────────────────────────────────────────────────── #

AEO_PROMPT = """You are an AEO (AI Engine Optimization) specialist. Your job is to judge whether AI chatbots (ChatGPT, Gemini, Perplexity, Copilot) would extract and cite this page's content.

Target keyword: "{keyword}"
URL: {url}

Technical signals already detected on the page:
- Schema types present: {schema_types}
- FAQ / Q&A patterns: {faq_count}
- Direct-answer paragraphs: {direct_answers}
- Author attribution: {has_author}
- Freshness signals: {has_freshness}
- Source citations: {has_citations}
- Word count: {word_count}

Page content excerpt (first 2500 chars):
{text_excerpt}

Evaluate AEO readiness on these dimensions:
1. Would an AI chatbot cite this page as a source? Why or why not?
2. Are there clear, concise answers that AI can extract verbatim?
3. Is the content structured for featured snippets (lists, tables, definitions)?
4. Does the page have authoritative signals AI would trust?
5. Are there FAQ schema or Q&A patterns AI assistants prefer?

Respond with ONLY a JSON object (no prose before or after):
{{
  "score": <0-100 integer>,
  "verdict": "Strong" | "Moderate" | "Weak",
  "strengths": ["<3 short bullet points of what is working>"],
  "weaknesses": ["<3 short bullet points of what is missing>"],
  "top_3_actions": ["<3 specific, actionable fixes ranked by impact>"]
}}"""


SEO_PROMPT = """You are an on-page SEO specialist. Evaluate this page against standard SEO best practices for target keyword "{keyword}".

Technical facts detected:
- Title: "{title}" ({title_len} chars)
- Meta description: "{meta_desc}" ({meta_len} chars)
- H1 count: {h1_count}, H2 count: {h2_count}, H3 count: {h3_count}
- Canonical present: {has_canonical}
- Schema blocks: {schema_count}
- Image alt coverage: {alt_pct}%
- Word count: {word_count}
- Internal links: {internal_links}, external links: {external_links}

Evaluate:
1. Title tag optimization (length, keyword placement, click-worthiness)
2. Meta description effectiveness
3. Heading hierarchy and keyword usage
4. Schema markup completeness
5. Internal linking strategy

Respond with ONLY a JSON object:
{{
  "score": <0-100 integer>,
  "verdict": "Strong" | "Moderate" | "Weak",
  "strengths": ["<3 items>"],
  "weaknesses": ["<3 items>"],
  "top_3_actions": ["<3 prioritized fixes>"]
}}"""


CONTENT_PROMPT = """You are a content quality analyst focused on E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness). Evaluate this page for "{keyword}".

Content metrics:
- Word count: {word_count}
- Readability grade (Flesch-Kincaid): {readability_grade}
- Readability score: {readability_score}
- Author attribution detected: {has_author}
- Publication/update date detected: {has_date}
- Source citations detected: {has_citations}

Page content excerpt (first 3500 chars):
{text_excerpt}

Evaluate:
1. Content depth — does it thoroughly cover the topic or is it thin?
2. Readability — clear, well-structured, engaging for the target reader?
3. E-E-A-T signals — credentials, experience, citations, firsthand expertise
4. Originality — unique insights vs rehashed common knowledge?
5. User intent match — does it actually satisfy someone searching "{keyword}"?

Respond with ONLY a JSON object:
{{
  "score": <0-100 integer>,
  "verdict": "Strong" | "Moderate" | "Weak",
  "strengths": ["<3 items>"],
  "weaknesses": ["<3 items>"],
  "top_3_actions": ["<3 prioritized fixes>"]
}}"""


COMPETITOR_PROMPT = """You are a competitor intelligence analyst. Compare this page against the structural patterns typical of pages ranking in the top 3 for "{keyword}".

Page structure:
- H2 headings: {h2_list}
- H3 headings: {h3_list}
- Schema types: {schema_types}
- Lists present: {list_count}, tables present: {table_count}
- Images: {image_count}
- Word count: {word_count}
- Internal links: {internal_links}

Evaluate against top-ranking patterns for this type of query:
1. Heading hierarchy — does it match what Google rewards for this intent?
2. Content depth — is the word count competitive for this keyword type?
3. Rich elements — enough lists, tables, images for featured snippets?
4. Schema markup — are the right types present for this business/content type?
5. Topic coverage gaps — what subtopics do top-ranking pages typically cover that this one doesn't?

Respond with ONLY a JSON object:
{{
  "score": <0-100 integer>,
  "verdict": "Strong" | "Moderate" | "Weak",
  "strengths": ["<3 items>"],
  "weaknesses": ["<3 items>"],
  "top_3_actions": ["<3 prioritized fixes>"]
}}"""


GEO_PROMPT = """You are a local SEO and GEO (Generative Engine Optimization) specialist. Evaluate local search signals for "{keyword}".

Local signals detected:
- Physical address present: {has_address}
- Phone number present: {has_phone}
- Business hours present: {has_hours}
- LocalBusiness schema: {has_local_schema}
- GeoCoordinates: {has_geo}
- Local/geographic keywords: {has_local_keywords}
- Service area mentions: {service_areas}

Evaluate:
1. NAP (Name, Address, Phone) consistency and visibility
2. LocalBusiness schema completeness
3. Geographic keyword optimization
4. Local trust signals (reviews, testimonials, community mentions)
5. GEO readiness — would an AI assistant recommend this business for local queries?

Respond with ONLY a JSON object:
{{
  "score": <0-100 integer>,
  "verdict": "Strong" | "Moderate" | "Weak",
  "strengths": ["<3 items>"],
  "weaknesses": ["<3 items>"],
  "top_3_actions": ["<3 prioritized fixes>"]
}}"""


MODERATOR_PROMPT = """You are the senior moderator of an AI Council. Five specialist agents from different firms have independently analyzed a webpage for "{keyword}". You do not know which model produced which report; judge each on its merits.

Overall weighted score: {overall_score}/100.

AGENT REPORTS:
{agent_reports}

As moderator, produce a single unified plan:

1. EXECUTIVE SUMMARY (2-3 sentences): the page's biggest strength and most critical weakness. Be direct.

2. PRIORITY ACTIONS (top 5, ranked by impact): for each, state what to do, why it matters, and which agents flagged it. If agents disagree, name the conflict and give your ruling.

3. QUICK WINS (2-3 changes under 1 hour of work each).

4. STRATEGIC RECOMMENDATION: the single bold move with the biggest impact on both search rankings and AI visibility.

Be concise, specific, and actionable. Use a numbered list. No fluff."""


# ── Public agent entry points ────────────────────────────────────────────── #

def run_aeo_agent(ctx: dict, fallback: dict) -> dict:
    """Claude 3.5 Haiku — AEO readiness."""
    try:
        prompt = AEO_PROMPT.format(
            keyword=ctx.get("keyword") or "(not specified)",
            url=ctx.get("url", ""),
            schema_types=", ".join(ctx.get("schema_types", [])) or "none",
            faq_count=ctx.get("faq_count", 0),
            direct_answers=ctx.get("direct_answers", 0),
            has_author=ctx.get("has_author", False),
            has_freshness=ctx.get("has_freshness", False),
            has_citations=ctx.get("has_citations", False),
            word_count=ctx.get("word_count", 0),
            text_excerpt=(ctx.get("text") or "")[:2500],
        )
        raw = _extract_json(invoke_converse(prompt, model=AGENT_MODELS["aeo"], max_tokens=800))
        if not raw:
            raise RuntimeError("empty JSON from AEO agent")
        out = _normalize_agent_output(
            raw, "AEO Specialist",
            "AI citation readiness — would chatbots cite this content?",
            fallback.get("score", 0),
        )
        out["model"] = AGENT_MODEL_LABELS["aeo"]
        return out
    except Exception as e:
        logger.warning("AEO agent fell back to rule-based: %s", e)
        fallback["model"] = AGENT_MODEL_LABELS["aeo"] + " (fallback)"
        return fallback


def run_seo_agent(ctx: dict, fallback: dict) -> dict:
    """Nova Lite — on-page SEO checklist."""
    try:
        prompt = SEO_PROMPT.format(
            keyword=ctx.get("keyword") or "(not specified)",
            title=ctx.get("title", "")[:120],
            title_len=len(ctx.get("title", "")),
            meta_desc=ctx.get("meta_desc", "")[:200],
            meta_len=len(ctx.get("meta_desc", "")),
            h1_count=ctx.get("h1_count", 0),
            h2_count=ctx.get("h2_count", 0),
            h3_count=ctx.get("h3_count", 0),
            has_canonical=ctx.get("has_canonical", False),
            schema_count=ctx.get("schema_count", 0),
            alt_pct=ctx.get("alt_pct", 0),
            word_count=ctx.get("word_count", 0),
            internal_links=ctx.get("internal_links", 0),
            external_links=ctx.get("external_links", 0),
        )
        raw = _extract_json(invoke_converse(prompt, model=AGENT_MODELS["seo"], max_tokens=700))
        if not raw:
            raise RuntimeError("empty JSON from SEO agent")
        out = _normalize_agent_output(
            raw, "SEO Specialist",
            "On-page SEO — title, meta, headings, structure, schema",
            fallback.get("score", 0),
        )
        out["model"] = AGENT_MODEL_LABELS["seo"]
        return out
    except Exception as e:
        logger.warning("SEO agent fell back to rule-based: %s", e)
        fallback["model"] = AGENT_MODEL_LABELS["seo"] + " (fallback)"
        return fallback


def run_content_agent(ctx: dict, fallback: dict) -> dict:
    """Llama 4 Maverick — content quality & E-E-A-T."""
    try:
        prompt = CONTENT_PROMPT.format(
            keyword=ctx.get("keyword") or "(not specified)",
            word_count=ctx.get("word_count", 0),
            readability_grade=ctx.get("readability_grade", "n/a"),
            readability_score=ctx.get("readability_score", 0),
            has_author=ctx.get("has_author", False),
            has_date=ctx.get("has_freshness", False),
            has_citations=ctx.get("has_citations", False),
            text_excerpt=(ctx.get("text") or "")[:3500],
        )
        raw = _extract_json(invoke_converse(prompt, model=AGENT_MODELS["content"], max_tokens=800))
        if not raw:
            raise RuntimeError("empty JSON from content agent")
        out = _normalize_agent_output(
            raw, "Content Quality Analyst",
            "Readability, depth, E-E-A-T signals, originality",
            fallback.get("score", 0),
        )
        out["model"] = AGENT_MODEL_LABELS["content"]
        # Preserve extra metrics from the rule-based fallback where useful
        if "metrics" in fallback:
            out["metrics"] = fallback["metrics"]
        return out
    except Exception as e:
        logger.warning("Content agent fell back to rule-based: %s", e)
        fallback["model"] = AGENT_MODEL_LABELS["content"] + " (fallback)"
        return fallback


def run_competitor_agent(ctx: dict, fallback: dict) -> dict:
    """Mistral Large — competitor intelligence."""
    try:
        prompt = COMPETITOR_PROMPT.format(
            keyword=ctx.get("keyword") or "(not specified)",
            h2_list=", ".join((ctx.get("h2s") or [])[:8]) or "none",
            h3_list=", ".join((ctx.get("h3s") or [])[:8]) or "none",
            schema_types=", ".join(ctx.get("schema_types", [])) or "none",
            list_count=ctx.get("list_count", 0),
            table_count=ctx.get("table_count", 0),
            image_count=ctx.get("image_count", 0),
            word_count=ctx.get("word_count", 0),
            internal_links=ctx.get("internal_links", 0),
        )
        raw = _extract_json(invoke_converse(prompt, model=AGENT_MODELS["competitor"], max_tokens=800))
        if not raw:
            raise RuntimeError("empty JSON from competitor agent")
        out = _normalize_agent_output(
            raw, "Competitor Intelligence",
            "How this page stacks up against typical top-ranking patterns",
            fallback.get("score", 0),
        )
        out["model"] = AGENT_MODEL_LABELS["competitor"]
        return out
    except Exception as e:
        logger.warning("Competitor agent fell back to rule-based: %s", e)
        fallback["model"] = AGENT_MODEL_LABELS["competitor"] + " (fallback)"
        return fallback


def run_geo_agent(ctx: dict, fallback: dict) -> dict:
    """Nova Lite — GEO/local signals."""
    try:
        prompt = GEO_PROMPT.format(
            keyword=ctx.get("keyword") or "(not specified)",
            has_address=ctx.get("has_address", False),
            has_phone=ctx.get("has_phone", False),
            has_hours=ctx.get("has_hours", False),
            has_local_schema=ctx.get("has_local_schema", False),
            has_geo=ctx.get("has_geo_coords", False),
            has_local_keywords=ctx.get("has_local_keywords", False),
            service_areas=", ".join(ctx.get("service_areas", [])) or "none detected",
        )
        raw = _extract_json(invoke_converse(prompt, model=AGENT_MODELS["geo"], max_tokens=700))
        if not raw:
            raise RuntimeError("empty JSON from GEO agent")
        out = _normalize_agent_output(
            raw, "GEO/Local Specialist",
            "Local search optimization, NAP data, geographic signals",
            fallback.get("score", 0),
        )
        out["model"] = AGENT_MODEL_LABELS["geo"]
        return out
    except Exception as e:
        logger.warning("GEO agent fell back to rule-based: %s", e)
        fallback["model"] = AGENT_MODEL_LABELS["geo"] + " (fallback)"
        return fallback


def run_moderator(agents: list, keyword: str, overall_score: int) -> str:
    """Claude Sonnet 4 — synthesize all 5 reports into a unified plan."""
    try:
        reports = []
        for a in agents:
            lines = [f"## {a.get('agent', 'Agent')}  —  Score: {a.get('score', 0)}  —  Verdict: {a.get('verdict', 'n/a')}"]
            if a.get("passed"):
                lines.append("Strengths: " + "; ".join(a["passed"][:3]))
            if a.get("failed"):
                lines.append("Weaknesses: " + "; ".join(a["failed"][:3]))
            if a.get("top_recommendations"):
                lines.append("Top actions: " + "; ".join(a["top_recommendations"][:3]))
            reports.append("\n".join(lines))

        prompt = MODERATOR_PROMPT.format(
            keyword=keyword or "(not specified)",
            overall_score=overall_score,
            agent_reports="\n\n".join(reports),
        )
        return invoke_converse(prompt, model=AGENT_MODELS["moderator"], max_tokens=1200, temperature=0.4)
    except Exception as e:
        logger.warning("Moderator failed: %s", e)
        return None
