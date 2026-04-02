READMEDEV2 - Samar's Changes Summary (Dev 2 - Content & NLP)
==============================================================
Date: March 23-24, 2026

FILES MODIFIED BY DEV 2 (DO NOT OVERWRITE):
--------------------------------------------
1. app.py
2. OneDrive/Desktop/seo deployment/audit.html
3. audit.html

WHAT CHANGED IN app.py:
------------------------
- Added new endpoint: POST /api/content-brief
  Input: { "keyword": "...", "content_type": "blog|faq|landing_page|how_to|comparison|listicle" }
  Output: Structured JSON brief with headings, questions, keywords, schema recommendations
- Added helper function: call_llm() - centralized LLM caller with fallback support
  Primary: https://ollama.sageaios.com/api (Gurbachan's homelab GPU server)
  Fallback: https://api.databi.io/api
  Model: llama3.1:latest
- Added helper function: scrape_serp_results() - scrapes top 5 Google results for a keyword
- Added helper function: generate_brief_with_llm() - generates structured brief via LLM
- Refactored existing get_ai_recommendations() to use call_llm() instead of direct requests
- Added analyze_citation_gap() - 10th SEO category with 20 checks (registered as 'citationgap')
- DO NOT change the Ollama URL or LLM config - this was set per client (Gurbachan) instructions

WHAT CHANGED IN audit.html (both versions):
---------------------------------------------
- Added "Generate Content Brief" button + UI section below AI Recommendations
  - Auto-extracts keyword from audit results (primary keyword check or title tag)
  - Content type dropdown (blog, FAQ, landing page, how-to, comparison, listicle)
  - Renders competitor table, heading structure, questions, keyword map, schema recommendations
- Added Citation Gap category to categoryMeta (key: 'citationgap')
- Added Tools dropdown (top-right corner) with links to all subdomains

S3 VERSION ONLY (OneDrive/Desktop/seo deployment/audit.html):
- Added const API_BASE = 'https://sgnmqxb2sw.us-east-1.awsapprunner.com'
- All fetch() calls use API_BASE + '/api/...' (required because S3 serves from different origin)
- Fixed grid layout: category-detail-wrapper uses display:none instead of max-height:0

DO NOT TOUCH:
--------------
- Do not remove or rename /api/content-brief endpoint
- Do not change call_llm() or the Ollama URLs
- Do not modify the categoryMeta object in audit.html without adding to it
- Do not remove the Tools dropdown from audit.html
- Do not change API_BASE in the S3 audit.html
- Do not remove the citationgap category from app.py or audit.html

ARCHITECTURE NOTES:
--------------------
- Frontend (www.ai1stseo.com): S3 bucket "ai1stseo-website" + CloudFront E334N0LB3C46TV
- Backend API: App Runner at https://sgnmqxb2sw.us-east-1.awsapprunner.com
- The S3-served HTML must use absolute URLs to App Runner (API_BASE), not relative /api/ paths
- The App Runner audit.html uses relative URLs (served from same origin) - that's fine
- LLM: Nova Lite as primary (AWS Bedrock, ~$0.06/1M tokens), Ollama homelab as free fallback per client directive
- call_llm() fallback chain: Nova Lite (Bedrock) → Ollama sageaios → Ollama databi
- bedrock_helper.py updated: default model is amazon.nova-lite-v1:0, supports both Nova and Anthropic formats
- Content brief has graceful fallback: if all LLMs are down, generates basic brief from raw SERP data

CURRENT TOTAL SEO CHECKS: 236 across 10 categories
Categories: technical, onpage, content, mobile, performance, security, social, local, geo, citationgap
