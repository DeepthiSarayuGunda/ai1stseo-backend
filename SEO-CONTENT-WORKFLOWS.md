# SEO & Content Analysis Workflows — Process Documentation

> **Author:** Dev 1 (Deepthi)  
> **Last Updated:** April 8, 2026  
> **Purpose:** Document the end-to-end SEO and content analysis workflows, capturing the process, value-add steps, data ingestion, and backend architecture for the AI1STSEO platform.

---

## Quick-Start Guide — Which Workflow Do I Use?

| I want to… | Use this workflow | API endpoint |
|------------|-------------------|-------------|
| Check if AI mentions my brand | Workflow 1 — GEO Probe | `POST /api/geo-probe` |
| Get a visibility score across many keywords | Workflow 2 — Batch Probe | `POST /api/geo-probe/batch` |
| See which AI engines miss my brand | Workflow 3 — Cross-Model Compare | `POST /api/geo-probe/compare` |
| Fix my page for AI readability | Workflow 4 — AEO Analysis | `POST /api/aeo/analyze` |
| Get a prioritized improvement plan | Workflow 5 — AI Ranking | `POST /api/ai/ranking-recommendations` |
| Run a full one-click audit | Workflow 6 — GEO Scanner Agent | `POST /api/geo-scanner/scan` |
| Generate AI-optimized content | Workflow 7 — Content Generation | `POST /api/content/generate` |
| Plan content based on SERP data | Workflow 8 — Content Brief | `POST /api/content-brief` |
| Run a full 236-check SEO audit | Workflow 9 — SEO Analysis | `POST /api/analyze` |

## End-to-End Flow (Recommended Order)

```
Step 1: Run GEO Scanner Agent (Workflow 6) — get overall AI visibility score
   ↓
Step 2: Review recommendations — identify gaps
   ↓
Step 3: Fix content structure issues (Workflow 4 — AEO)
   ↓
Step 4: Generate optimized content (Workflow 7 — FAQ, comparisons)
   ↓
Step 5: Re-scan to measure improvement (Workflow 6 again)
   ↓
Step 6: Set up monitoring (Workflow 2 — Batch Probe on schedule)
```

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER / CLIENT                            │
│   Enters brand name, URL, keywords via Dashboard or Scanner     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK API GATEWAY (app.py)                    │
│   Routes requests to the appropriate service module             │
│   Auth: Cognito · Deploy: Lambda + App Runner                   │
└──────┬──────┬──────┬──────┬──────┬──────┬──────┬───────────────┘
       │      │      │      │      │      │      │
       ▼      ▼      ▼      ▼      ▼      ▼      ▼
   ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────────┐
   │ GEO  ││ AEO  ││ AI   ││Content││Brand ││ LLM  ││ Scanner  │
   │Probe ││Optim.││Rank  ││ Gen  ││Resolv││Multi ││  Agent   │
   │Svc   ││      ││Svc   ││      ││      ││Prov  ││Orchestr. │
   └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───────┘
      │       │       │       │       │       │       │
      ▼       ▼       ▼       ▼       ▼       ▼       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI PROVIDER LAYER                             │
│   ai_provider.py: Bedrock Nova Lite (primary) + Ollama          │
│   llm_service.py: Groq, OpenAI, Perplexity, Gemini, Claude     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RDS POSTGRESQL (db.py)                        │
│   geo_probes · ai_visibility_history · content_briefs           │
│   Multi-tenant via project_id · Auto-schema init                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Workflow 1 — GEO Probe (Single Brand Visibility Check)

**Purpose:** Check if a specific AI model mentions a brand when asked about a keyword.

**Value-Add:** Gives instant visibility into whether AI search engines recommend your brand.

```
User Input                    Processing                      Output
─────────                    ──────────                      ──────
brand_name ──┐
keyword ─────┤  ┌──────────────────────┐   ┌──────────────────────────┐
provider ────┘  │ 1. Build prompt      │   │ • cited (bool)           │
                │ 2. Call AI provider   │──▶│ • citation_context       │
                │ 3. Detect brand      │   │ • confidence (0-1)       │
                │ 4. Score confidence   │   │ • sentiment              │
                │ 5. Persist to RDS    │   │ • response_snippet       │
                └──────────────────────┘   └──────────────────────────┘
```

**Process Steps:**
1. `_build_prompt()` — Creates a natural product-reviewer prompt asking AI about the keyword
2. `ai_provider.generate()` — Sends prompt to Nova Lite or Ollama
3. `_detect_citation()` — Searches AI response for brand mentions using regex
4. `_score_confidence()` — Rates mention quality: recommendation (1.0), comparison (0.5), conditional (0.0)
5. `_is_conditional_mention()` — Filters out "if applicable" style non-genuine mentions
6. `db.insert_probe()` — Persists result to `geo_probes` table in RDS

**API:** `POST /api/geo-probe`

---

## 3. Workflow 2 — Batch GEO Probe (Multi-Keyword Visibility Score)

**Purpose:** Probe multiple keywords at once and compute an overall GEO visibility score.

**Value-Add:** Provides a single percentage score showing what fraction of industry queries mention your brand.

```
brand_name ──┐
keywords[] ──┤  ┌────────────────────────────┐   ┌─────────────────────┐
provider ────┘  │ For each keyword:           │   │ • geo_score (0-1)   │
                │   1. Run single GEO probe   │──▶│ • cited_count       │
                │ Then:                       │   │ • total_prompts     │
                │   2. Compute geo_score      │   │ • per-keyword results│
                │   3. Persist batch to RDS   │   │ • RDS batch saved   │
                └────────────────────────────┘   └─────────────────────┘
```

**Key Metric:** `geo_score = cited_count / total_prompts` (0.0 to 1.0)

**API:** `POST /api/geo-probe/batch`

---

## 4. Workflow 3 — Cross-Model Comparison

**Purpose:** Probe the SAME keyword across ALL available AI providers simultaneously.

**Value-Add:** Shows which AI engines mention your brand and which don't — identifies gaps.

```
brand_name ──┐
keyword ─────┘  ┌────────────────────────────┐   ┌──────────────────────┐
                │ Concurrent execution:       │   │ • visibility_score   │
                │   Nova Lite ──▶ result      │──▶│ • cited_count        │
                │   Ollama    ──▶ result      │   │ • total_providers    │
                │   Groq      ──▶ result      │   │ • per-provider detail│
                │ Aggregate scores            │   │ • providers_queried  │
                └────────────────────────────┘   └──────────────────────┘
```

**API:** `POST /api/geo-probe/compare`

---

## 5. Workflow 4 — AEO Page Analysis (Content Readiness)

**Purpose:** Analyze a webpage for AI-friendliness — schema markup, content structure, authority signals.

**Value-Add:** Identifies specific technical issues preventing AI engines from citing your content.

```
url ────────┐   ┌────────────────────────────┐   ┌──────────────────────┐
brand ──────┘   │ 1. Fetch page HTML         │   │ • aeo_score (0-100)  │
                │ 2. Parse with BeautifulSoup│──▶│ • issues[] with      │
                │ 3. Check schema markup     │   │   severity & fix     │
                │ 4. Check content structure │   │ • severity_breakdown │
                │ 5. Check meta tags         │   │ • recommendations    │
                │ 6. Check authority signals │   │                      │
                └────────────────────────────┘   └──────────────────────┘
```

**Checks Include:**
- JSON-LD structured data (FAQPage, HowTo, Product, Organization)
- Heading hierarchy (H1 → H2 → H3)
- FAQ sections and Q&A patterns
- Meta descriptions and Open Graph tags
- Content depth and word count
- Internal/external link quality

**API:** `POST /api/aeo/analyze`

---

## 6. Workflow 5 — AI Ranking Recommendations

**Purpose:** Analyze a URL + brand for E-E-A-T signals and generate prioritized improvement suggestions.

**Value-Add:** Actionable, prioritized list of changes to improve AI search ranking.

```
url ────────┐   ┌────────────────────────────┐   ┌──────────────────────┐
brand ──────┘   │ 1. Fetch & analyze page    │   │ • recommendations[]  │
                │ 2. Check E-E-A-T signals   │──▶│   with priority,     │
                │ 3. Analyze brand presence  │   │   category, impact   │
                │ 4. Generate AI suggestions │   │ • brand_analysis     │
                │ 5. Prioritize by impact    │   │ • eeat_signals       │
                └────────────────────────────┘   └──────────────────────┘
```

**API:** `POST /api/ai/ranking-recommendations`

---

## 7. Workflow 6 — GEO Scanner Agent (Full Orchestrated Scan)

**Purpose:** Run ALL scanner agents in parallel and produce a unified, non-technical report.

**Value-Add:** One-click comprehensive AI visibility audit with plain-English results and actionable recommendations.

```
brand_name ──┐
url ─────────┤
keywords[] ──┤
provider ────┘
                ┌─────────────────────────────────────────────┐
                │         GEO Scanner Orchestrator             │
                │                                              │
                │  ┌─────────────┐  ┌──────────────────┐      │
                │  │ Brand       │  │ Content           │      │
                │  │ Visibility  │  │ Readiness         │      │
                │  │ Scanner     │  │ Scanner           │      │
                │  │ (weight:40%)│  │ (weight:25%)      │      │
                │  └──────┬──────┘  └────────┬─────────┘      │
                │         │                  │                 │
                │  ┌──────┴──────┐  ┌────────┴─────────┐      │
                │  │ Competitor  │  │ Site Mention      │      │
                │  │ Gap Scanner │  │ Scanner           │      │
                │  │ (weight:20%)│  │ (weight:15%)      │      │
                │  └──────┬──────┘  └────────┬─────────┘      │
                │         │                  │                 │
                │         ▼                  ▼                 │
                │  ┌─────────────────────────────────┐        │
                │  │ Aggregate → Score → Summarize   │        │
                │  │ → Recommend → Persist to RDS    │        │
                │  └─────────────────────────────────┘        │
                └─────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌─────────────────────────────────────────────┐
                │              UNIFIED REPORT                  │
                │  • overall_score (0-100, weighted)           │
                │  • executive_summary (plain English)         │
                │  • scanner_results (per-scanner detail)      │
                │  • recommendations (prioritized, actionable) │
                │  • rds_status (persistence confirmation)     │
                └─────────────────────────────────────────────┘
```

**Scanner Agents:**

| Scanner | Weight | What It Does | Data Source |
|---------|--------|-------------|-------------|
| Brand Visibility | 40% | Batch probe keywords across AI model | `geo_probe_batch()` |
| Content Readiness | 25% | AEO page analysis for AI-friendliness | `aeo_optimizer.analyze_aeo()` |
| Competitor Gap | 20% | Cross-model comparison for one keyword | `geo_probe_compare()` |
| Site Mention | 15% | Check if AI links to your URL | `geo_probe_site()` |

**API:** `POST /api/geo-scanner/scan`

---

## 8. Workflow 7 — Content Generation Pipeline

**Purpose:** Generate AI-optimized content (FAQ, comparison, meta descriptions, feature snippets).

**Value-Add:** One-click content creation that's structured for AI citation.

```
brand ──────┐
topic ──────┤   ┌────────────────────────────┐   ┌──────────────────────┐
type ───────┘   │ 1. Build content prompt    │   │ • generated_content  │
                │ 2. Call AI provider        │──▶│ • content_type       │
                │ 3. Format output           │   │ • schema_markup      │
                │ 4. Add schema if FAQ       │   │   (for FAQ type)     │
                └────────────────────────────┘   └──────────────────────┘
```

**Content Types:**
- `faq` — FAQ with JSON-LD schema markup
- `comparison` — Brand comparison article
- `meta_description` — SEO meta description
- `feature_snippet` — Featured snippet optimized content

**API:** `POST /api/content/generate`

---

## 9. Workflow 8 — Content Brief Generation (SERP-Based)

**Purpose:** Scrape SERP results for a keyword and generate a structured content brief using AI.

**Value-Add:** Data-driven content planning based on what's actually ranking.

```
keyword ────┐
type ───────┘   ┌────────────────────────────┐   ┌──────────────────────┐
                │ 1. Scrape Google SERP      │   │ • brief (structured) │
                │ 2. Extract top results     │──▶│ • competitors[]      │
                │ 3. Analyze content gaps    │   │ • keyword_placements │
                │ 4. Generate brief via LLM  │   │ • saved to RDS       │
                │ 5. Save to content_briefs  │   │                      │
                └────────────────────────────┘   └──────────────────────┘
```

**API:** `POST /api/content-brief`

---

## 10. Data Persistence Flow

All probe and scan results are persisted to RDS PostgreSQL for historical tracking:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   geo_probes     │     │ ai_visibility_   │     │ content_briefs   │
│                  │     │ history          │     │                  │
│ • keyword        │     │ • brand_name     │     │ • keyword        │
│ • brand_name     │     │ • ai_model       │     │ • content_type   │
│ • ai_model       │     │ • geo_score      │     │ • brief_json     │
│ • cited (bool)   │     │ • cited_count    │     │ • competitors    │
│ • confidence     │     │ • total_prompts  │     │ • keywords       │
│ • citation_ctx   │     │ • batch_results  │     │                  │
│ • sentiment      │     │   (JSONB)        │     │                  │
│ • probe_timestamp│     │ • measured_at    │     │ • created_at     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                          project_id (UUID)
                     Multi-tenant isolation
```

---

## 11. SEO Analysis Workflow (236 Checks)

The full SEO analyzer (`POST /api/analyze`) runs 236 checks across 10 categories:

```
URL ────────┐   ┌────────────────────────────────────────────┐
            │   │           SEO ANALYSIS ENGINE               │
            │   │                                             │
            │   │  1. Technical SEO    (~30 checks)           │
            │   │  2. On-Page SEO      (~30 checks)           │
            │   │  3. Content SEO      (~25 checks)           │
            │   │  4. Mobile SEO       (~20 checks)           │
            │   │  5. Performance SEO  (~25 checks)           │
            │   │  6. Security SEO     (~20 checks)           │
            │   │  7. Social SEO       (~15 checks)           │
            │   │  8. Local SEO        (~25 checks)           │
            │   │  9. GEO/AEO SEO     (~26 checks)           │
            │   │  10. Citation Gap    (~20 checks)           │
            │   │                                             │
            └──▶│  Total: 236 checks                         │
                │                                             │
                │  Output per check:                          │
                │  • name, status (pass/fail/warning)         │
                │  • description, value, recommendation       │
                │  • impact (high/medium/low), category       │
                └────────────────────────────────────────────┘
```

**API:** `POST /api/analyze`

---

## 12. Value-Add Summary

| Workflow | Business Value | Who Benefits |
|----------|---------------|-------------|
| GEO Probe | Know if AI recommends you | Marketing, SEO teams |
| Batch Probe | Track visibility across many keywords | Content strategists |
| Cross-Model Compare | Find which AI engines miss you | Technical SEO |
| AEO Analysis | Fix technical AI-readiness issues | Developers, SEO |
| AI Ranking | Prioritized improvement roadmap | Product owners |
| Scanner Agent | One-click full audit with plain-English report | Executives, clients |
| Content Generation | AI-optimized content at scale | Content writers |
| Content Brief | Data-driven content planning | Content strategists |
| SEO Analysis | Comprehensive 236-check site audit | Everyone |

---

## 13. Deployment Architecture

```
GitHub (main branch)
       │
       ▼
AWS App Runner ──── auto-deploy on push
       │
       ├── Flask API (all endpoints)
       ├── Static HTML dashboards
       │
       ▼
AWS Lambda ──── production (via handler())
       │
       ├── API Gateway
       ├── Cognito Auth
       │
       ▼
RDS PostgreSQL ──── ai1stseo database
       │
       ├── geo_probes
       ├── ai_visibility_history
       └── content_briefs

S3 + CloudFront ──── www.ai1stseo.com (frontend)
```
