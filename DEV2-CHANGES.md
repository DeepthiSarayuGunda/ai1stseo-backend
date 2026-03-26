# Dev 2 (Samar) — Changes & Current Status
**Branch:** `dev2-samar-merge`  
**Date:** March 26, 2026  
**Status:** Ready for merge into Troy's Lambda package

---

## What's In This Branch

All code below is **additive** — nothing in Troy's existing codebase was modified or removed.

### 1. Citation Gap Analysis (10th SEO Category)
- `extract_primary_keyword()` — extracts topic from page signals (title, H1, meta, OG)
- `analyze_citation_gap()` — 20 checks comparing Google ranking signals vs AI citation readiness
- Registered as `'citationgap'` in `/api/analyze` analyzers dict
- Categories: Google Signals (5), AI Citation Readiness (5), Gap Analysis (5), Bridge Strategy (5)
- **Files:** `app.py`

### 2. Content Scoring Engine
- `compute_readability_score()` — Flesch Reading Ease approximation
- `compute_seo_score()` — 13 on-page SEO checks (title, meta, headings, word count, images, links, structured data, canonical, viewport)
- `compute_aeo_score()` — 13 AI Engine Optimization checks (definitions, Q&A, FAQ schema, lists, tables, headings, statistics, citations, freshness, paragraphs)
- `POST /api/content-score` — accepts `{ "url": "..." }`, returns weighted score (40% SEO + 35% AEO + 25% Readability)
- **Files:** `app.py`

### 3. Content Brief Generator
- `call_llm()` — centralized LLM caller with 3-tier fallback: Nova Lite (Bedrock) → Ollama sageaios → Ollama databi → raw SERP
- `scrape_serp_results()` — scrapes top 5 Google results for keyword analysis
- `generate_brief_with_llm()` — generates structured brief via LLM
- `POST /api/content-brief` — accepts `{ "keyword": "...", "content_type": "blog|faq|..." }`
- **Files:** `app.py`

### 4. Content Brief Persistence (RDS)
- `save_content_brief()` — saves brief + competitors + keywords in one transaction
- `get_content_briefs()` — retrieves past briefs with optional keyword ILIKE filter
- `get_content_brief_by_id()` — retrieves single brief with competitors/keywords
- `GET /api/content-briefs?keyword=` — list endpoint with keyword filtering
- **Tables used:** `content_briefs`, `brief_competitors`, `brief_keywords` (already in DATABASE_SCHEMA.md)
- **Files:** `db.py`, `app.py`

### 5. LLM Fallback Chain
- Primary: Nova Lite (`amazon.nova-lite-v1:0`) via AWS Bedrock — ~$0.06/1M tokens
- Fallback 1: Ollama at `https://ollama.sageaios.com` (model: `qwen3:30b-a3b`)
- Fallback 2: Ollama at `https://api.databi.io` (model: `qwen3:30b-a3b`)
- Last resort: Raw SERP data (no LLM)
- Fixed `bedrock_helper.py`: `maxNewTokens` → `max_new_tokens` (Nova Lite field name)
- **Files:** `app.py`, `bedrock_helper.py`

### 6. CORS Update
- Added `https://automationhub.ai1stseo.com` to CORS origins list
- **Files:** `app.py`

### 7. Health Endpoint Update
- Added `citationgap: 20` to categories
- Added `/api/content-score` and `/api/content-briefs` to endpoints list
- **Files:** `app.py`

---

## Merge Guide for Troy

See `MERGE-FOR-TROY.py` — contains all functions as clean copy-paste blocks with placement instructions. Nothing replaces existing code.

**Quick summary of what to add to the Lambda package:**
1. Add `'citationgap': ('Citation Gap', analyze_citation_gap)` to the analyzers dict in `analyze_url()`
2. Add `extract_primary_keyword()` and `analyze_citation_gap()` functions before the route
3. Add `compute_readability_score()`, `compute_seo_score()`, `compute_aeo_score()` functions
4. Add `POST /api/content-score` route
5. Update `GET /api/content-briefs` to accept `?keyword=` param
6. Update `db.py` with `save_content_brief()`, `get_content_briefs(keyword_filter=)`, `get_content_brief_by_id()`
7. Add `'https://automationhub.ai1stseo.com'` to CORS origins

---

## Current Architecture

| Component | Service | Endpoint |
|-----------|---------|----------|
| Frontend | S3 + CloudFront `E334N0LB3C46TV` | `ai1stseo.com` |
| Backend API | Lambda `ai1stseo-backend` | `cwb0hb27bf.execute-api.us-east-1.amazonaws.com` |
| Automation Hub | Lambda `automation-hub` (Node.js 20) | `automationhub.ai1stseo.com` |
| Database | RDS PostgreSQL | `ai1stseo-db.ca5mm2skodf2.us-east-1.rds.amazonaws.com` |
| Auth | Cognito `us-east-1_DVvth47zH` | — |
| LLM | Bedrock Nova Lite + Ollama fallback | — |

## Total SEO Checks: 236 across 10 categories
`technical` (35) · `onpage` (25) · `content` (20) · `mobile` (15) · `performance` (18) · `security` (12) · `social` (10) · `local` (15) · `geo` (30) · `citationgap` (20)

---

## DO NOT TOUCH
- `call_llm()` or Ollama URLs/model names
- `API_BASE` in S3 audit.html
- `categoryMeta` in audit.html (add to it, don't modify existing)
- Content brief persistence functions in `db.py`
