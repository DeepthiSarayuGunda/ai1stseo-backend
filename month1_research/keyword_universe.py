"""
keyword_universe.py
Deliverable 2: Master Keyword Universe — 200 Natural-Language Queries

Generates and categorises 200 natural-language queries across the core topic space.
Each query is categorised by:
  - intent_type: definition, how-to, comparison, recommendation, troubleshooting
  - answer_format: direct, list, table, paragraph
  - commercial_value: high, medium, low
  - topic_cluster: which pillar topic it belongs to

Usage:
  python keyword_universe.py --brand "YourBrand" --topic "your industry/niche"
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from api_client import content_generate, llm_citation_probe, now_iso
from utils import save_json, print_header, print_section

# ── Intent-based query templates ──────────────────────────────────────────────
# These generate natural-language queries that users would ask AI engines.

INTENT_TEMPLATES = {
    "definition": [
        "What is {topic}?",
        "What does {subtopic} mean in {topic}?",
        "How would you define {subtopic}?",
        "Explain {subtopic} in simple terms",
        "What is the difference between {subtopic} and {alt_subtopic}?",
    ],
    "how_to": [
        "How do I {action} with {topic}?",
        "What is the best way to {action}?",
        "Step by step guide to {action}",
        "How to get started with {subtopic}",
        "How to improve {metric} using {topic}",
    ],
    "comparison": [
        "What are the best {topic} tools?",
        "{subtopic} vs {alt_subtopic} — which is better?",
        "Compare the top {topic} solutions",
        "Best {topic} for small businesses",
        "Best {topic} for enterprises",
    ],
    "recommendation": [
        "What {topic} do you recommend?",
        "Top {topic} brands in 2026",
        "Which {topic} should I choose?",
        "Best {topic} for beginners",
        "Most popular {topic} right now",
    ],
    "troubleshooting": [
        "Why is my {subtopic} not working?",
        "Common {topic} mistakes to avoid",
        "How to fix {problem} in {topic}",
        "Troubleshooting {subtopic} issues",
        "{topic} best practices to prevent problems",
    ],
}

ANSWER_FORMAT_MAP = {
    "definition": "paragraph",
    "how_to": "list",
    "comparison": "table",
    "recommendation": "list",
    "troubleshooting": "list",
}

# ── Default topic clusters for SEO/AEO/GEO industry ──────────────────────────

DEFAULT_CLUSTERS = {
    "seo_fundamentals": {
        "subtopics": ["on-page SEO", "technical SEO", "link building", "keyword research", "content optimization"],
        "actions": ["optimize a website for search engines", "do keyword research", "build backlinks", "improve page speed", "fix crawl errors"],
        "metrics": ["organic traffic", "search rankings", "domain authority", "page speed score", "crawl efficiency"],
        "problems": ["ranking drops", "indexing issues", "duplicate content", "slow page speed", "broken links"],
        "alt_subtopics": ["off-page SEO", "local SEO", "mobile SEO", "voice search optimization", "image SEO"],
    },
    "aeo_answer_engine": {
        "subtopics": ["answer engine optimization", "FAQ schema", "featured snippets", "AI-friendly content", "structured data"],
        "actions": ["optimize content for AI engines", "add FAQ schema markup", "get featured snippets", "structure content for AI", "improve AI visibility"],
        "metrics": ["AI citation rate", "featured snippet presence", "schema coverage", "answer box appearances", "AI readiness score"],
        "problems": ["missing schema markup", "poor AI visibility", "content not cited by AI", "FAQ schema errors", "low AI readiness score"],
        "alt_subtopics": ["voice search optimization", "conversational search", "zero-click results", "knowledge panel optimization", "entity optimization"],
    },
    "geo_generative_engine": {
        "subtopics": ["generative engine optimization", "AI brand mentions", "LLM visibility", "cross-model visibility", "AI citation tracking"],
        "actions": ["track brand mentions in AI", "improve GEO score", "monitor AI visibility", "optimize for ChatGPT", "get cited by AI models"],
        "metrics": ["GEO score", "visibility score", "citation confidence", "cross-model presence", "brand mention rate"],
        "problems": ["low GEO score", "inconsistent AI mentions", "competitor outranking in AI", "model disagreement", "declining AI visibility"],
        "alt_subtopics": ["AI search optimization", "ChatGPT optimization", "Perplexity optimization", "Gemini optimization", "Claude optimization"],
    },
    "content_strategy": {
        "subtopics": ["content marketing", "pillar content", "topic clusters", "content calendar", "content briefs"],
        "actions": ["create a content strategy", "build topic clusters", "write pillar content", "plan a content calendar", "generate content briefs"],
        "metrics": ["content engagement", "time on page", "content freshness", "topical authority", "content coverage"],
        "problems": ["thin content", "content cannibalization", "outdated content", "poor content structure", "missing topic coverage"],
        "alt_subtopics": ["blog strategy", "video content", "infographics", "case studies", "whitepapers"],
    },
    "eeat_authority": {
        "subtopics": ["E-E-A-T signals", "domain authority", "brand authority", "expert authorship", "trust signals"],
        "actions": ["build E-E-A-T signals", "improve domain authority", "establish brand authority", "add author credentials", "build trust signals"],
        "metrics": ["E-E-A-T score", "domain authority", "trust flow", "citation flow", "brand search volume"],
        "problems": ["low E-E-A-T score", "missing author bios", "no trust signals", "weak brand authority", "poor reputation signals"],
        "alt_subtopics": ["brand reputation", "online reviews", "social proof", "industry certifications", "thought leadership"],
    },
    "ai_tools_platforms": {
        "subtopics": ["AI SEO tools", "SEO automation", "AI content generation", "SEO monitoring platforms", "AI analytics"],
        "actions": ["choose an AI SEO tool", "automate SEO tasks", "use AI for content creation", "set up SEO monitoring", "analyze SEO with AI"],
        "metrics": ["tool ROI", "automation efficiency", "content quality score", "monitoring coverage", "analysis accuracy"],
        "problems": ["tool overload", "inaccurate AI content", "monitoring gaps", "integration issues", "data silos"],
        "alt_subtopics": ["manual SEO", "traditional analytics", "human content creation", "spreadsheet tracking", "basic reporting"],
    },
    "competitive_intelligence": {
        "subtopics": ["competitor analysis", "market positioning", "competitive benchmarking", "gap analysis", "share of voice"],
        "actions": ["analyze competitors", "benchmark against competitors", "find competitive gaps", "track competitor visibility", "measure share of voice"],
        "metrics": ["competitive gap", "share of voice", "market position", "competitor citation rate", "visibility differential"],
        "problems": ["competitor outranking", "losing market share", "blind spots in analysis", "stale competitive data", "unclear positioning"],
        "alt_subtopics": ["market research", "industry analysis", "SWOT analysis", "positioning strategy", "differentiation strategy"],
    },
    "technical_implementation": {
        "subtopics": ["schema markup", "JSON-LD", "site architecture", "crawl optimization", "Core Web Vitals"],
        "actions": ["implement schema markup", "optimize site architecture", "improve Core Web Vitals", "fix crawl issues", "set up structured data"],
        "metrics": ["Core Web Vitals scores", "crawl budget efficiency", "schema validation score", "page load time", "mobile usability score"],
        "problems": ["schema validation errors", "poor site architecture", "slow Core Web Vitals", "crawl budget waste", "mobile usability issues"],
        "alt_subtopics": ["server-side rendering", "progressive web apps", "AMP pages", "headless CMS", "CDN optimization"],
    },
}


def generate_keyword_universe(brand: str, topic: str, clusters: dict = None) -> dict:
    """Generate 200 categorised natural-language queries."""
    print_header("DELIVERABLE 2: Master Keyword Universe")

    if clusters is None:
        clusters = DEFAULT_CLUSTERS

    keywords = []
    keyword_id = 0

    for cluster_name, cluster_data in clusters.items():
        print_section(f"Cluster: {cluster_name}")
        subtopics = cluster_data["subtopics"]
        actions = cluster_data["actions"]
        metrics = cluster_data["metrics"]
        problems = cluster_data["problems"]
        alt_subtopics = cluster_data["alt_subtopics"]

        for intent_type, templates in INTENT_TEMPLATES.items():
            for i, template in enumerate(templates):
                # Fill template with cluster-specific data
                query = template.format(
                    topic=topic if "{topic}" in template else subtopics[i % len(subtopics)],
                    subtopic=subtopics[i % len(subtopics)],
                    alt_subtopic=alt_subtopics[i % len(alt_subtopics)],
                    action=actions[i % len(actions)],
                    metric=metrics[i % len(metrics)],
                    problem=problems[i % len(problems)],
                )

                # Determine commercial value based on intent
                if intent_type in ("recommendation", "comparison"):
                    commercial_value = "high"
                elif intent_type in ("how_to", "troubleshooting"):
                    commercial_value = "medium"
                else:
                    commercial_value = "low"

                keyword_id += 1
                keywords.append({
                    "id": keyword_id,
                    "query": query,
                    "intent_type": intent_type,
                    "answer_format": ANSWER_FORMAT_MAP[intent_type],
                    "commercial_value": commercial_value,
                    "topic_cluster": cluster_name,
                    "subtopic": subtopics[i % len(subtopics)],
                    "status": "active",
                    "geo_score": None,
                    "visibility_score": None,
                    "priority_tier": None,
                })

                if keyword_id >= 200:
                    break
            if keyword_id >= 200:
                break
        if keyword_id >= 200:
            break

    # Assign priority tiers
    high_value = [k for k in keywords if k["commercial_value"] == "high"]
    med_value = [k for k in keywords if k["commercial_value"] == "medium"]
    low_value = [k for k in keywords if k["commercial_value"] == "low"]

    for k in high_value[:30]:
        k["priority_tier"] = 1
    for k in high_value[30:] + med_value[:50]:
        k["priority_tier"] = 2
    for k in med_value[50:] + low_value:
        k["priority_tier"] = 3

    # Summary stats
    by_intent = {}
    by_cluster = {}
    by_value = {}
    for k in keywords:
        by_intent[k["intent_type"]] = by_intent.get(k["intent_type"], 0) + 1
        by_cluster[k["topic_cluster"]] = by_cluster.get(k["topic_cluster"], 0) + 1
        by_value[k["commercial_value"]] = by_value.get(k["commercial_value"], 0) + 1

    result = {
        "deliverable": "Master Keyword Universe",
        "generated_at": now_iso(),
        "brand": brand,
        "topic": topic,
        "total_keywords": len(keywords),
        "summary": {
            "by_intent_type": by_intent,
            "by_topic_cluster": by_cluster,
            "by_commercial_value": by_value,
            "tier_1_count": len([k for k in keywords if k["priority_tier"] == 1]),
            "tier_2_count": len([k for k in keywords if k["priority_tier"] == 2]),
            "tier_3_count": len([k for k in keywords if k["priority_tier"] == 3]),
        },
        "keywords": keywords,
    }

    print(f"\n  Total keywords: {len(keywords)}")
    print(f"  By intent: {by_intent}")
    print(f"  By value: {by_value}")
    print(f"  Tier 1 (priority): {result['summary']['tier_1_count']}")

    save_json("keyword_universe", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Master Keyword Universe")
    parser.add_argument("--brand", required=True, help="Primary brand name")
    parser.add_argument("--topic", required=True, help="Core topic/industry")
    args = parser.parse_args()
    generate_keyword_universe(args.brand, args.topic)
