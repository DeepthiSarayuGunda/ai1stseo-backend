READMEDEV2 - Samar's Changes Summary (Dev 2 - Content & NLP)
==============================================================
Updated: April 2, 2026 (covers March 23 - April 2 work)

FILES MODIFIED/CREATED BY DEV 2:
----------------------------------
1. app.py (modified — routes, functions, DynamoDB default, Lambda cold start fix)
2. db.py (modified — added content briefs CRUD, keyword filtering)
3. db_dynamo.py (NEW — DynamoDB replacement for db.py)
4. bedrock_helper.py (modified — Nova Lite field name fix)
5. audit.html (modified — citation gap UI, content brief UI, API_BASE fix, dropdown styling)
6. DEV2-CHANGES.md (NEW — full changelog for team)
7. MERGE-FOR-TROY.py (NEW — merge checklist)
8. dns-update.json (NEW — DNS fix for seoaudit/seoanalysis subdomains)

========================================================================
FULL CHANGELOG (March 23 - April 2)
========================================================================

1. CITATION GAP ANALYSIS (10th SEO Category) — March 23
---------------------------------------------------------
- extract_primary_keyword() — extracts topic from page signals
- analyze_citation_gap() — 20 checks: Google Signals (5), AI Citation
  Readiness (5), Gap Analysis (5), Bridge Strategy (5)
- Registered as 'citationgap' in /api/analyze analyzers dict

2. CONTENT BRIEF GENERATOR — March 23-24
-------------------------------------------
- POST /api/content-brief endpoint
- call_llm() — 3-tier LLM fallback: Nova Lite → Ollama sageaios → Ollama databi → raw SERP
- scrape_serp_results() — scrapes top 5 Google results
- generate_brief_with_llm() — structured brief via LLM
- UI in audit.html: content type dropdown, competitor table, heading structure

3. LLM FALLBACK CHAIN FIX — March 24
---------------------------------------
- Fixed bedrock_helper.py: maxNewTokens → max_new_tokens (Nova Lite)
- Fixed Ollama model: llama3.1:latest → qwen3:30b-a3b
- DO NOT change Ollama URLs or model names

4. CONTENT BRIEF PERSISTENCE (RDS → DynamoDB) — March 25-26, April 1
----------------------------------------------------------------------
- db.py: save_content_brief(), get_content_briefs(keyword_filter=), get_content_brief_by_id()
- GET /api/content-briefs with ?keyword= filtering
- POST /api/content-brief auto-saves to DB after generation

5. CONTENT SCORING ENGINE — March 26
---------------------------------------
- compute_readability_score() — Flesch Reading Ease
- compute_seo_score() — 13 on-page SEO checks
- compute_aeo_score() — 13 AI Engine Optimization checks
- POST /api/content-score — weighted: 40% SEO + 35% AEO + 25% Readability

6. LAMBDA DEPLOYMENT — March 25-26, April 2
----------------------------------------------
- Backend migrated to Lambda + API Gateway (from App Runner)
- Lambda: ai1stseo-backend (python3.11, handler: app.handler via Mangum)
- API Gateway: cwb0hb27bf.execute-api.us-east-1.amazonaws.com
- Deploy bucket: s3://ai1stseo-lambda-deploy
- April 2: Re-deployed with all Dev 2 code merged, DynamoDB default, cold start fix

7. AUTOMATION HUB (Lambda) — March 25-26
-------------------------------------------
- Lambda: automation-hub (Node.js 20.x, CommonJS)
- API Gateway: aa3889gca0
- Domain: automationhub.ai1stseo.com
- Cognito login/signup with SECRET_HASH
- Control room dashboard: content scoring, workflows, task creator, activity feed
- Proxies /api/content-score to SEO backend

8. DNS FIXES — March 26
--------------------------
- seoaudit.ai1stseo.com → API Gateway (was pointing to dead EC2)
- seoanalysis.ai1stseo.com → API Gateway (was pointing to dead EC2)
- automationhub.ai1stseo.com CORS added to backend

9. DYNAMODB MIGRATION — April 1-2
------------------------------------
- Created db_dynamo.py — drop-in DynamoDB replacement for db.py
  - save_content_brief() → ai1stseo-content-briefs table
  - get_content_briefs(keyword_filter=) → scan with Attr filter
  - get_content_brief_by_id() → get_item by id
  - insert_probe() → ai1stseo-geo-probes table
  - insert_visibility_batch() → ai1stseo-geo-probes table
- Updated app.py: USE_DYNAMODB defaults to True (RDS is stopped)
  - Set env var USE_RDS=1 to re-enable RDS if needed
- All 'from db import' calls check USE_DYNAMODB first
- RDS is stopped per Troy/Gurbachan directive — DynamoDB is the new backend
- No changes to Troy's code or anyone else's modules

10. LAMBDA COLD START FIX — April 2
--------------------------------------
- Problem: Lambda init was timing out (10s+) because app.py tried to
  connect to the stopped RDS instance before falling back to DynamoDB
- Fix: USE_DYNAMODB now defaults to True, skipping the RDS connection
  attempt entirely. Cold start dropped from 10s+ timeout to under 3s.
- To re-enable RDS: set Lambda env var USE_RDS=1

11. CLOUDFRONT /api/* FIX — April 2
--------------------------------------
- Problem: CloudFront /api/* behavior was forwarding the Host header
  (ai1stseo.com) to API Gateway, which returned 403 Forbidden because
  ai1stseo.com isn't a configured custom domain on the HTTP API
- Fix: Removed Host from forwarded headers in /api/* cache behavior
  (kept Authorization, Origin, Accept, Content-Type)
- All frontend API calls now route correctly through CloudFront

12. AUDIT.HTML API_BASE FIX — April 2
----------------------------------------
- Problem: S3 audit.html had API_BASE pointing to the dead App Runner
  URL (sgnmqxb2sw.us-east-1.awsapprunner.com) — all API calls failed
- Fix: Updated API_BASE to Lambda API Gateway
  (cwb0hb27bf.execute-api.us-east-1.amazonaws.com)
- Synced local audit.html with S3 version (59KB full version)
- Uploaded to S3 and invalidated CloudFront cache

13. DROPDOWN STYLING FIX — April 2
-------------------------------------
- Content type dropdown in AI Content Brief Generator had white
  background with invisible text on the options
- Fixed: dark background (#1a1a2e) + white text on all <option> elements
- Matches the dark theme of the rest of the UI

========================================================================
VERIFIED WORKING ENDPOINTS (April 2)
========================================================================
All tested via both direct API Gateway and CloudFront:
  GET  /api/health          — 200, 200 checks, 10 categories, citationgap:20
  POST /api/content-score   — 200, returns SEO+AEO+readability scores
  GET  /api/content-briefs  — 200, returns briefs from DynamoDB
  POST /api/content-brief   — 200, generates AI brief via Nova Lite, saves to DynamoDB
  POST /api/analyze         — 200, full 200-check SEO audit

========================================================================
DO NOT TOUCH
========================================================================
- call_llm() or Ollama URLs/model names (set per Gurbachan's instructions)
- categoryMeta in audit.html (add to it, don't modify existing)
- Content brief persistence functions
- Troy's auth, admin, data API, webhooks modules
- directory/ module (Troy's AI Business Directory — isolated, no impact)

========================================================================
CURRENT ARCHITECTURE (as of April 2)
========================================================================
Frontend:
  - S3 bucket: ai1stseo-website
  - CloudFront: E16GYTIVXY9IOU
  - Domain: www.ai1stseo.com / ai1stseo.com
  - Deploy: Amira does manual S3 upload (NOT auto-deploy from GitHub)
  - audit.html API_BASE: cwb0hb27bf.execute-api.us-east-1.amazonaws.com

Backend API:
  - Lambda: ai1stseo-backend (python3.11)
  - API Gateway: cwb0hb27bf.execute-api.us-east-1.amazonaws.com
  - Custom domains: api.ai1stseo.com, seoaudit.ai1stseo.com, seoanalysis.ai1stseo.com
  - CloudFront /api/* routes to API Gateway (Host header NOT forwarded)

Automation Hub:
  - Lambda: automation-hub (Node.js 20.x)
  - Domain: automationhub.ai1stseo.com

Database:
  - DynamoDB (ACTIVE): ai1stseo-content-briefs, ai1stseo-geo-probes, + 9 more tables
  - RDS PostgreSQL: STOPPED (backup in rds-backup/ on repo)
  - USE_DYNAMODB=True by default; set USE_RDS=1 env var to re-enable

LLM Config:
  - Primary: Nova Lite (amazon.nova-lite-v1:0) via AWS Bedrock
  - Fallback 1: Ollama at https://ollama.sageaios.com (qwen3:30b-a3b)
  - Fallback 2: Ollama at https://api.databi.io (qwen3:30b-a3b)
  - Last resort: Raw SERP data

Auth: Cognito us-east-1_DVvth47zH (unaffected by DB migration)

========================================================================
API ENDPOINTS (Dev 2 owned)
========================================================================
POST /api/analyze            — 200-check SEO audit (10 categories incl citationgap)
POST /api/content-brief      — AI content brief generator
GET  /api/content-briefs     — List saved briefs (?keyword= filter)
POST /api/content-score      — Content scoring engine (SEO+AEO+readability)
POST /api/keyword-cluster    — Keyword clustering & TF-IDF analysis
POST /api/ai-recommendations — AI-powered SEO recommendations
GET  /api/health             — Health check with category counts

14. KEYWORD CLUSTERING & TF-IDF ENGINE — April 6
---------------------------------------------------
- POST /api/keyword-cluster endpoint
  - Accepts URL (scrapes page, extracts keywords) or seed keyword (LLM generates related terms)
  - TF-IDF scoring: term frequency analysis on page content
  - Bigram/trigram extraction for multi-word phrases
  - Search intent clustering: informational, commercial, transactional, navigational, local
  - LLM fallback: if seed keyword only, uses Nova Lite to generate 30 related keywords grouped by intent
- Frontend: "Keyword Clustering & TF-IDF Analysis" section added to audit.html
  - Seed keyword input or auto-uses audited URL
  - Color-coded intent clusters with keyword pills
  - TF-IDF table with frequency and score columns
  - Key phrases section showing bigrams (cyan) and trigrams (purple)
- Removed duplicate blueprint registrations in app.py (were registered twice after merge)

15. TEMPLATE BENCHMARK ENGINE — April 7
------------------------------------------
- POST /api/template-benchmark endpoint
  - Compares any URL against the perfect AEO/GEO/SEO template for its business type
  - 4 business types: service, manufacturing, ecommerce, saas
  - Each template defines: ideal title/meta format, required schema types, heading structure,
    min word count, required AEO elements (FAQs, definitions, lists, tables, citations),
    and required content sections with word budgets
  - Returns gap analysis: what's missing, current vs ideal, points lost per gap
  - AI recommendations via LLM for top gaps
- GET /api/template-types — lists available business types
- Standalone frontend: template-benchmark.html
  - URL input + business type dropdown
  - Score rings: Overall, AEO (first per client feedback), SEO, Content
  - Gap breakdown by category with point deductions
  - Content section checklist (found vs missing)
  - AI fix recommendations panel
- Per Gurbachan's directive: create perfect templates for different business types
  that score 100% and serve as benchmarks for AEO/GEO/SEO scoring

========================================================================
API ENDPOINTS (Dev 2 owned)
========================================================================
POST /api/analyze            — 200-check SEO audit (10 categories incl citationgap)
POST /api/content-brief      — AI content brief generator
GET  /api/content-briefs     — List saved briefs (?keyword= filter)
POST /api/content-score      — Content scoring engine (SEO+AEO+readability)
POST /api/keyword-cluster    — Keyword clustering & TF-IDF analysis
POST /api/template-benchmark — Template benchmark (URL vs perfect business template)
GET  /api/template-types     — List available business template types
POST /api/ai-recommendations — AI-powered SEO recommendations
GET  /api/health             — Health check with category counts

========================================================================
BRANCH INFO
========================================================================
Branch: dev2-samar-merge (merged into main April 2)
All Dev 2 code is on both branches. Kept in sync.
