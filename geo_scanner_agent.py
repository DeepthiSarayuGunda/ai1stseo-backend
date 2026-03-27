"""
geo_scanner_agent.py
GEO Scanner Agent — Orchestrator skeleton that coordinates scanner agents
and returns structured, user-friendly results.

Phase 1 — Dev 1 (Deepthi)

Architecture:
  - Orchestrator receives a scan request (brand + keywords + options)
  - Dispatches to individual scanner agents (GEO probe, AEO, ranking, site)
  - Aggregates results into a unified, non-technical report
  - Persists all results to RDS via POST /api/data/geo-probes and /api/data/ai-visibility
  - Returns structured JSON with plain-English summaries

Scanner Agents:
  1. BrandVisibilityScanner  — GEO probe across AI models
  2. ContentReadinessScanner — AEO page analysis
  3. CompetitorGapScanner    — Cross-model compare
  4. SiteMentionScanner      — URL/domain detection in AI output
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Scanner Agent Base ────────────────────────────────────────────────────────

class ScannerAgent:
    """Base class for all scanner agents."""
    name: str = "base"
    description: str = ""

    def run(self, context: dict) -> dict:
        raise NotImplementedError

    def _friendly_summary(self, result: dict) -> str:
        """Override to produce a plain-English summary for non-technical users."""
        return "Scan complete."


# ── 1. Brand Visibility Scanner ───────────────────────────────────────────────

class BrandVisibilityScanner(ScannerAgent):
    name = "brand_visibility"
    description = "Checks if AI models mention your brand when users ask about your industry"

    def run(self, context: dict) -> dict:
        from geo_probe_service import geo_probe_batch
        brand = context["brand_name"]
        keywords = context.get("keywords", [])
        provider = context.get("provider", "nova")

        if not keywords:
            return {"status": "skipped", "reason": "No keywords provided"}

        result = geo_probe_batch(brand, keywords, provider)
        result["scanner"] = self.name
        result["friendly_summary"] = self._friendly_summary(result)
        return result

    def _friendly_summary(self, result: dict) -> str:
        score = result.get("geo_score", 0)
        cited = result.get("cited_count", 0)
        total = result.get("total_prompts", 0)
        pct = round(score * 100)

        if pct >= 70:
            return (
                f"Great news — AI models mention your brand in {cited} out of "
                f"{total} searches ({pct}% visibility). Your brand is well-recognized "
                f"in AI-powered search results."
            )
        elif pct >= 40:
            return (
                f"Your brand appears in {cited} out of {total} AI searches ({pct}% visibility). "
                f"There's room to grow — optimizing your content for AI engines could "
                f"increase how often you're recommended."
            )
        else:
            return (
                f"Your brand was only mentioned in {cited} out of {total} AI searches "
                f"({pct}% visibility). AI models aren't recommending you yet. "
                f"Adding structured content, FAQ pages, and comparison articles "
                f"can help AI engines discover and cite your brand."
            )


# ── 2. Content Readiness Scanner ─────────────────────────────────────────────

class ContentReadinessScanner(ScannerAgent):
    name = "content_readiness"
    description = "Analyzes your website for AI-friendliness — schema markup, content structure, and authority signals"

    def run(self, context: dict) -> dict:
        url = context.get("url")
        if not url:
            return {"status": "skipped", "reason": "No URL provided"}

        from aeo_optimizer import analyze_aeo
        try:
            result = analyze_aeo(url, context.get("brand_name"))
            result["scanner"] = self.name
            result["friendly_summary"] = self._friendly_summary(result)
            return result
        except Exception as e:
            return {"scanner": self.name, "status": "error", "error": str(e)}

    def _friendly_summary(self, result: dict) -> str:
        score = result.get("aeo_score", 0)
        high = result.get("severity_breakdown", {}).get("high", 0)
        total = result.get("total_issues", 0)

        if score >= 80:
            return (
                f"Your page scores {score}/100 for AI readiness. "
                f"It's well-structured for AI engines to understand and cite."
            )
        elif score >= 50:
            fixes = f"Fix {high} high-priority issues" if high else f"Address {total} improvements"
            return (
                f"Your page scores {score}/100 for AI readiness. {fixes} "
                f"to help AI engines better understand and recommend your content."
            )
        else:
            return (
                f"Your page scores {score}/100 for AI readiness — there's significant "
                f"room for improvement. {high} critical issues need attention, like "
                f"adding structured data and improving content organization."
            )


# ── 3. Competitor Gap Scanner ─────────────────────────────────────────────────

class CompetitorGapScanner(ScannerAgent):
    name = "competitor_gap"
    description = "Compares your brand visibility across all available AI models simultaneously"

    def run(self, context: dict) -> dict:
        from geo_probe_service import geo_probe_compare
        brand = context["brand_name"]
        keyword = context.get("primary_keyword")
        if not keyword:
            keywords = context.get("keywords", [])
            keyword = keywords[0] if keywords else None
        if not keyword:
            return {"status": "skipped", "reason": "No keyword provided"}

        try:
            result = geo_probe_compare(brand, keyword)
            result["scanner"] = self.name
            result["friendly_summary"] = self._friendly_summary(result)
            return result
        except Exception as e:
            return {"scanner": self.name, "status": "error", "error": str(e)}

    def _friendly_summary(self, result: dict) -> str:
        score = result.get("visibility_score", 0)
        cited = result.get("cited_count", 0)
        total = result.get("total_providers", 0)
        providers = result.get("providers_queried", [])

        if score >= 60:
            return (
                f"Your brand is mentioned by {cited} out of {total} AI models "
                f"({score}% cross-model visibility). You have strong presence across "
                f"AI search engines."
            )
        elif score >= 30:
            missing = [p for p in providers if not result.get("results", {}).get(p, {}).get("brand_present")]
            missing_str = ", ".join(missing[:3]) if missing else "some models"
            return (
                f"Your brand appears in {cited} of {total} AI models ({score}% visibility). "
                f"You're missing from {missing_str}. Targeted content optimization "
                f"can help close this gap."
            )
        else:
            return (
                f"Only {cited} of {total} AI models mention your brand ({score}% visibility). "
                f"Most AI search engines don't know about you yet. Building authoritative, "
                f"well-structured content is the first step to getting cited."
            )


# ── 4. Site Mention Scanner ───────────────────────────────────────────────────

class SiteMentionScanner(ScannerAgent):
    name = "site_mention"
    description = "Checks if AI models link to or mention your actual website URL"

    def run(self, context: dict) -> dict:
        from geo_probe_service import geo_probe_site
        url = context.get("url")
        keyword = context.get("primary_keyword")
        if not keyword:
            keywords = context.get("keywords", [])
            keyword = keywords[0] if keywords else None
        if not url or not keyword:
            return {"status": "skipped", "reason": "URL and keyword required"}

        provider = context.get("provider", "nova")
        try:
            result = geo_probe_site(url, keyword, provider)
            result["scanner"] = self.name
            result["friendly_summary"] = self._friendly_summary(result)
            return result
        except Exception as e:
            return {"scanner": self.name, "status": "error", "error": str(e)}

    def _friendly_summary(self, result: dict) -> str:
        mentioned = result.get("site_mentioned", False)
        domain = result.get("domain", "your site")
        if mentioned:
            return (
                f"AI models are linking directly to {domain} in their responses. "
                f"This means users can find your website through AI search."
            )
        else:
            return (
                f"AI models are not linking to {domain} yet. "
                f"To get direct links, ensure your site is authoritative, "
                f"well-indexed, and frequently referenced by other sources."
            )


# ── Scanner Registry ──────────────────────────────────────────────────────────

SCANNERS = {
    "brand_visibility": BrandVisibilityScanner(),
    "content_readiness": ContentReadinessScanner(),
    "competitor_gap": CompetitorGapScanner(),
    "site_mention": SiteMentionScanner(),
}


# ── Orchestrator ──────────────────────────────────────────────────────────────

class GEOScannerOrchestrator:
    """
    Coordinates all scanner agents and returns a unified report.

    Usage:
        orchestrator = GEOScannerOrchestrator()
        report = orchestrator.run_scan(
            brand_name="Notion",
            url="https://notion.so",
            keywords=["best project management tools", "top productivity apps"],
            provider="nova",
            scanners=["brand_visibility", "content_readiness", "competitor_gap", "site_mention"]
        )
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def run_scan(
        self,
        brand_name: str,
        url: str = None,
        keywords: list[str] = None,
        provider: str = "nova",
        scanners: list[str] = None,
        primary_keyword: str = None,
    ) -> dict:
        """
        Run a full GEO scan using selected scanner agents.

        Returns a structured report with:
          - overall_score: weighted average across scanners (0-100)
          - scanner_results: individual results per scanner
          - executive_summary: plain-English summary for non-technical users
          - recommendations: prioritized list of next steps
          - rds_status: whether results were persisted to RDS
        """
        t0 = time.time()
        context = {
            "brand_name": brand_name,
            "url": url,
            "keywords": keywords or [],
            "provider": provider,
            "primary_keyword": primary_keyword or (keywords[0] if keywords else None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Select scanners to run
        selected = scanners or list(SCANNERS.keys())
        agents = {k: SCANNERS[k] for k in selected if k in SCANNERS}

        # Run scanners concurrently
        scanner_results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self._safe_run, agent, context): name
                for name, agent in agents.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                scanner_results[name] = future.result()

        # Compute overall score
        overall_score = self._compute_overall_score(scanner_results)

        # Generate executive summary
        executive_summary = self._build_executive_summary(
            brand_name, overall_score, scanner_results
        )

        # Generate recommendations
        recommendations = self._build_recommendations(scanner_results)

        # Persist to RDS
        rds_status = self._persist_to_rds(brand_name, context, scanner_results, overall_score)

        elapsed = round(time.time() - t0, 2)

        return {
            "status": "complete",
            "brand_name": brand_name,
            "url": url,
            "overall_score": overall_score,
            "executive_summary": executive_summary,
            "scanner_results": scanner_results,
            "recommendations": recommendations,
            "rds_status": rds_status,
            "scanners_run": list(scanner_results.keys()),
            "elapsed_seconds": elapsed,
            "timestamp": context["timestamp"],
        }

    def _safe_run(self, agent: ScannerAgent, context: dict) -> dict:
        """Run a scanner agent with error handling."""
        try:
            return agent.run(context)
        except Exception as e:
            logger.exception("Scanner %s failed", agent.name)
            return {
                "scanner": agent.name,
                "status": "error",
                "error": str(e),
                "friendly_summary": f"This scan couldn't complete due to a technical issue. Our team has been notified.",
            }

    def _compute_overall_score(self, scanner_results: dict) -> int:
        """Weighted average of scanner scores (0-100)."""
        weights = {
            "brand_visibility": 40,
            "content_readiness": 25,
            "competitor_gap": 20,
            "site_mention": 15,
        }
        total_weight = 0
        weighted_sum = 0

        for name, result in scanner_results.items():
            if result.get("status") in ("error", "skipped"):
                continue
            w = weights.get(name, 10)
            score = self._extract_score(name, result)
            if score is not None:
                weighted_sum += score * w
                total_weight += w

        return round(weighted_sum / total_weight) if total_weight else 0

    def _extract_score(self, scanner_name: str, result: dict) -> Optional[float]:
        """Extract a 0-100 score from a scanner result."""
        if scanner_name == "brand_visibility":
            return round(result.get("geo_score", 0) * 100)
        elif scanner_name == "content_readiness":
            return result.get("aeo_score")
        elif scanner_name == "competitor_gap":
            return result.get("visibility_score")
        elif scanner_name == "site_mention":
            return 100 if result.get("site_mentioned") else 0
        return None

    def _build_executive_summary(
        self, brand: str, overall_score: int, scanner_results: dict
    ) -> str:
        """Build a plain-English executive summary for non-technical stakeholders."""
        summaries = []
        for name in ["brand_visibility", "content_readiness", "competitor_gap", "site_mention"]:
            r = scanner_results.get(name)
            if r and r.get("friendly_summary"):
                summaries.append(r["friendly_summary"])

        if overall_score >= 70:
            headline = (
                f"{brand} has strong AI search visibility ({overall_score}/100). "
                f"When people ask AI assistants like ChatGPT or Perplexity about your industry, "
                f"your brand is being recommended. Keep up the good work."
            )
        elif overall_score >= 40:
            headline = (
                f"{brand} has moderate AI search visibility ({overall_score}/100). "
                f"AI assistants sometimes mention your brand, but not consistently. "
                f"With targeted improvements to your content and website structure, "
                f"you can significantly increase how often AI recommends you."
            )
        else:
            headline = (
                f"{brand} has low AI search visibility ({overall_score}/100). "
                f"Right now, when potential customers ask AI assistants about your industry, "
                f"your brand is rarely mentioned. This is a growth opportunity — "
                f"the recommendations below will help you get noticed by AI search engines."
            )

        # Add a "what this means" section for non-technical readers
        what_it_means = (
            "What does this score mean? AI search engines like ChatGPT, Perplexity, and Google AI "
            "are increasingly how people discover products and services. Your AI visibility score "
            "measures how often these AI tools mention and recommend your brand when users ask "
            "questions related to your industry."
        )

        parts = [headline, what_it_means] + summaries
        return "\n\n".join(parts)

    def _build_recommendations(self, scanner_results: dict) -> list[dict]:
        """Generate prioritized, plain-English recommendations from all scanner results."""
        recs = []
        priority = 1

        # From brand visibility
        bv = scanner_results.get("brand_visibility", {})
        bv_score = bv.get("geo_score", 1)
        if bv_score < 0.4:
            recs.append({
                "priority": priority,
                "category": "AI Visibility",
                "title": "Improve brand presence in AI search",
                "description": (
                    "AI models rarely mention your brand when users search for your industry. "
                    "To fix this, create content that directly answers common customer questions — "
                    "think FAQ pages, 'best of' comparison guides, and detailed product descriptions. "
                    "The more authoritative and helpful your content, the more likely AI will cite you."
                ),
                "impact": "high",
                "effort": "medium",
                "timeframe": "2-4 weeks to see initial results",
            })
            priority += 1
        elif bv_score < 0.7:
            recs.append({
                "priority": priority,
                "category": "AI Visibility",
                "title": "Strengthen brand mentions in AI responses",
                "description": (
                    "Your brand appears in some AI searches but not consistently. "
                    "Focus on creating comparison content and industry roundup articles "
                    "that position your brand alongside well-known competitors. "
                    "AI models learn from these patterns."
                ),
                "impact": "medium",
                "effort": "low",
                "timeframe": "1-2 weeks",
            })
            priority += 1

        # From content readiness
        cr = scanner_results.get("content_readiness", {})
        cr_score = cr.get("aeo_score", 100)
        if cr_score < 60:
            high_issues = cr.get("severity_breakdown", {}).get("high", 0)
            recs.append({
                "priority": priority,
                "category": "Content Structure",
                "title": f"Fix {high_issues} critical content issues on your website",
                "description": (
                    "Your website has structural issues that make it hard for AI engines "
                    "to understand your content. Key fixes: add structured data (JSON-LD schema), "
                    "organize content with clear headings (H1, H2, H3), and include FAQ sections. "
                    "These changes help AI 'read' your page and cite it in responses."
                ),
                "impact": "high",
                "effort": "medium",
                "timeframe": "1-2 weeks for technical implementation",
            })
            priority += 1
        elif cr_score < 80:
            recs.append({
                "priority": priority,
                "category": "Content Structure",
                "title": "Fine-tune your page for AI readability",
                "description": (
                    "Your page is reasonably well-structured but could be improved. "
                    "Add FAQ schema markup, ensure every section has a clear heading, "
                    "and include concise summary paragraphs that AI can easily extract."
                ),
                "impact": "medium",
                "effort": "low",
                "timeframe": "A few days",
            })
            priority += 1

        # From competitor gap
        cg = scanner_results.get("competitor_gap", {})
        cg_score = cg.get("visibility_score", 100)
        if cg_score < 50:
            missing_models = []
            for prov, r in cg.get("results", {}).items():
                if isinstance(r, dict) and not r.get("brand_present"):
                    missing_models.append(prov)
            missing_str = ", ".join(missing_models[:3]) if missing_models else "several AI models"
            recs.append({
                "priority": priority,
                "category": "Cross-Model Coverage",
                "title": f"Expand presence to {missing_str}",
                "description": (
                    f"Your brand is missing from {missing_str}. Different AI models "
                    f"pull from different data sources — to get cited everywhere, ensure your "
                    f"content is indexed broadly. Get mentioned on industry blogs, review sites, "
                    f"and authoritative publications that these AI models train on."
                ),
                "impact": "medium",
                "effort": "medium",
                "timeframe": "Ongoing — 2-6 weeks for initial coverage",
            })
            priority += 1

        # From site mention
        sm = scanner_results.get("site_mention", {})
        if sm.get("status") != "skipped" and not sm.get("site_mentioned"):
            recs.append({
                "priority": priority,
                "category": "Direct Links",
                "title": "Get AI models to link directly to your website",
                "description": (
                    "AI models discuss topics in your space but don't link to your site. "
                    "To earn direct links: build high-quality backlinks from authoritative sources, "
                    "ensure your site is well-indexed by search engines, and create content "
                    "that AI models want to reference as a primary source."
                ),
                "impact": "medium",
                "effort": "high",
                "timeframe": "4-8 weeks",
            })
            priority += 1

        # Always include general best practices
        recs.append({
            "priority": priority,
            "category": "Best Practice",
            "title": "Add Schema.org structured data to key pages",
            "description": (
                "Structured data (FAQPage, HowTo, Product, Organization schemas) helps "
                "AI engines understand exactly what your page is about and cite it more accurately. "
                "This is one of the highest-impact, lowest-effort changes you can make."
            ),
            "impact": "medium",
            "effort": "low",
            "timeframe": "A few hours with a developer",
        })

        return recs

    def _persist_to_rds(
        self, brand: str, context: dict, scanner_results: dict, overall_score: int
    ) -> dict:
        """Persist scan results to RDS via db.py functions."""
        status = {"geo_probes": "not_attempted", "ai_visibility": "not_attempted"}

        # Persist individual probe results (geo_probes table)
        bv = scanner_results.get("brand_visibility", {})
        if bv.get("results"):
            try:
                from db import insert_probe
                for r in bv["results"]:
                    insert_probe(
                        keyword=r.get("keyword", ""),
                        brand=brand,
                        ai_model=r.get("ai_model", context.get("provider", "nova")),
                        cited=r.get("brand_present", False),
                        citation_context=r.get("citation_context", ""),
                        confidence=r.get("confidence", 0.0),
                        response_snippet=r.get("response_snippet", ""),
                        sentiment=r.get("sentiment", "neutral"),
                    )
                status["geo_probes"] = f"saved_{len(bv['results'])}_probes"
            except Exception as e:
                logger.warning("Failed to persist geo_probes: %s", e)
                status["geo_probes"] = f"error: {e}"

        # Persist batch visibility (ai_visibility_history table)
        if bv.get("geo_score") is not None:
            try:
                from db import insert_visibility_batch
                import json
                insert_visibility_batch(
                    brand=brand,
                    ai_model=context.get("provider", "nova"),
                    keyword=", ".join(context.get("keywords", [])),
                    geo_score=bv.get("geo_score", 0),
                    cited_count=bv.get("cited_count", 0),
                    total_prompts=bv.get("total_prompts", 0),
                    batch_results=json.dumps(bv.get("results", [])),
                )
                status["ai_visibility"] = "saved"
            except Exception as e:
                logger.warning("Failed to persist ai_visibility: %s", e)
                status["ai_visibility"] = f"error: {e}"

        return status


# ── Module-level convenience ──────────────────────────────────────────────────

_orchestrator = GEOScannerOrchestrator()


def run_full_scan(
    brand_name: str,
    url: str = None,
    keywords: list[str] = None,
    provider: str = "nova",
    scanners: list[str] = None,
) -> dict:
    """Convenience function — runs a full GEO scan and returns structured results."""
    return _orchestrator.run_scan(
        brand_name=brand_name,
        url=url,
        keywords=keywords,
        provider=provider,
        scanners=scanners,
    )


def get_available_scanners() -> list[dict]:
    """List all registered scanner agents."""
    return [
        {"name": s.name, "description": s.description}
        for s in SCANNERS.values()
    ]
