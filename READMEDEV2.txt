READMEDEV2 - Samar's Changes Summary (Dev 2 - Content & NLP)
==============================================================
Updated: April 1, 2026 (covers March 23 - April 1 work)

FILES MODIFIED/CREATED BY DEV 2:
----------------------------------
1. app.py (modified — added routes, functions, DynamoDB fallback)
2. db.py (modified — added content briefs CRUD, keyword filtering)
3. db_dynamo.py (NEW — DynamoDB replacement for db.py)
4. bedrock_helper.py (modified — Nova Lite field name fix)
5. audit.html (modified — citation gap UI, content brief UI)
6. OneDrive/Desktop/seo deployment/audit.html (S3 version)
7. DEV2-CHANGES.md (NEW — full changelog for team)
8. MERGE-FOR-TROY.py (NEW — merge checklist)
9. dns-update.json (NEW — DNS fix for seoaudit/seoanalysis subdomains)

========================================================================
FULL CHANGELOG (March 23 - April 1)
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

6. LAMBDA DEPLOYMENT — March 25-26
-------------------------------------
- Backend migrated to Lambda + API Gateway (from App Runner)
- Lambda: ai1stseo-backend (python3.11, handler: app.handler via Mangum)
- API Gateway: cwb0hb27bf.execute-api.us-east-1.amazonaws.com
- Deploy bucket: s3://ai1stseo-lambda-deploy

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

9. DYNAMODB MIGRATION — April 1
----------------------------------
- Created db_dynamo.py — drop-in DynamoDB replacement for db.py
  - save_content_brief() → ai1stseo-content-briefs table
  - get_content_briefs(keyword_filter=) → scan with Attr filter
  - get_content_brief_by_id() → get_item by id
  - insert_probe() → ai1stseo-geo-probes table
  - insert_visibility_batch() → ai1stseo-geo-probes table
- Updated app.py: USE_DYNAMODB flag auto-detects when RDS is stopped
- All 'from db import' calls now check USE_DYNAMODB first
- RDS is stopped per Troy/Gurbachan directive — DynamoDB is the new backend
- No changes to Troy's code or anyone else's modules

========================================================================
DO NOT TOUCH
========================================================================
- call_llm() or Ollama URLs/model names (set per Gurbachan's instructions)
- categoryMeta in audit.html (add to it, don't modify existing)
- API_BASE in S3 audit.html
- Content brief persistence functions
- Troy's auth, admin, data API, webhooks modules

========================================================================
CURRENT ARCHITECTURE (as of April 1)
========================================================================
Frontend:
  - S3 bucket: ai1stseo-website
  - CloudFront: E16GYTIVXY9IOU (updated from E334N0LB3C46TV)
  - Domain: www.ai1stseo.com / ai1stseo.com
  - Deploy: Amira does manual S3 upload (NOT auto-deploy from GitHub)

Backend API:
  - Lambda: ai1stseo-backend (python3.11)
  - API Gateway: cwb0hb27bf.execute-api.us-east-1.amazonaws.com
  - Custom domains: api.ai1stseo.com, seoaudit.ai1stseo.com, seoanalysis.ai1stseo.com

Automation Hub:
  - Lambda: automation-hub (Node.js 20.x)
  - Domain: automationhub.ai1stseo.com

Database:
  - DynamoDB (NEW): ai1stseo-content-briefs, ai1stseo-geo-probes, + 9 more tables
  - RDS PostgreSQL: STOPPED (backup in rds-backup/ on repo)

LLM Config:
  - Primary: Nova Lite (amazon.nova-lite-v1:0) via AWS Bedrock
  - Fallback 1: Ollama at https://ollama.sageaios.com (qwen3:30b-a3b)
  - Fallback 2: Ollama at https://api.databi.io (qwen3:30b-a3b)
  - Last resort: Raw SERP data

Auth: Cognito us-east-1_DVvth47zH (unaffected by DB migration)

========================================================================
API ENDPOINTS (Dev 2 owned)
========================================================================
POST /api/analyze          — 236-check SEO audit (10 categories incl citationgap)
POST /api/content-brief    — AI content brief generator
GET  /api/content-briefs   — List saved briefs (?keyword= filter)
POST /api/content-score    — Content scoring engine (SEO+AEO+readability)
POST /api/ai-recommendations — AI-powered SEO recommendations

========================================================================
BRANCH INFO
========================================================================
Branch: dev2-samar-merge
All Dev 2 code is here. Troy merges into main when ready.
