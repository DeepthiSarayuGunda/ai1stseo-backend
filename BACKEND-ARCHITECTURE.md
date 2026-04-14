# AI1STSEO Shared Backend — Architecture & API Reference

> **Last Updated:** April 8, 2026
> **Maintainer:** Dev 1 (Deepthi) — AI/ML, GEO Engine, AEO, LLM Integrations
> **Purpose:** Single reference for the shared Lambda/App Runner backend — modules, endpoints, deployment path, and recent changes.

---

## Deployment Architecture

| Layer | Detail |
|-------|--------|
| Runtime | Python 3.11, Flask, deployed as AWS Lambda (via `handler()` in `app.py`) |
| App Runner (dev/test) | `https://sgnmqxb2sw.us-east-1.awsapprunner.com` — auto-deploys from `DeepthiSarayuGunda/ai1stseo-backend` `main` branch |
| Database | RDS PostgreSQL (`ai1stseo`) — connection pool in `db.py`; DynamoDB fallback in `db_dynamo.py` (default when RDS is stopped) |
| AI Providers | Bedrock Nova Lite (primary, IAM role), Ollama homelab (fallback) — routed via `ai_provider.py` |
| Auth | Cognito `us-east-1_DVvth47zH` — production auth on Troy's EC2 (`api.ai1stseo.com`) |
| Frontend | S3 `ai1stseo-website` + CloudFront `E16GYTIVXY9IOU` → `www.ai1stseo.com` |

### Deployment Path (for all devs)

1. Push changes to GitHub repo (`DeepthiSarayuGunda/ai1stseo-backend`, `main` branch)
2. App Runner auto-deploys on push (build: `pip install -r requirements.txt`, start: gunicorn)
3. For Lambda packaging: `build_zip.py` creates `lambda_deploy.zip`
4. **Do NOT** deploy directly to the Lambda or App Runner via AWS Console/CLI

---

## Module Map

| File | Owner | Purpose |
|------|-------|---------|
| `app.py` | Shared | Flask app, all route definitions, Lambda handler, SEO analysis (236 checks / 10 categories) |
| `application.py` | Shared | WSGI entry point for App Runner / gunicorn |
| `db.py` | Dev 1 | RDS PostgreSQL pool, schema init, CRUD for `geo_probes`, `ai_visibility_history`, `content_briefs` |
| `db_dynamo.py` | Dev 1 | DynamoDB replacement for `db.py` — same function signatures, used when `USE_RDS` is not set |
| `ai_provider.py` | Dev 1 | Unified AI abstraction — Bedrock Nova + Ollama, `generate()` and `get_available_providers()` |
| `geo_probe_service.py` | Dev 1 | GEO/AEO monitoring engine — single probe, batch, compare, site detection, trend, history |
| `geo_engine.py` | Dev 1 | GEO engine utilities |
| `aeo_optimizer.py` | Dev 1 | AEO page analysis — schema markup, content structure, meta, authority signals |
| `ai_ranking_service.py` | Dev 1 | AI ranking recommendations — brand presence analysis + prioritized suggestions |
| `content_generator.py` | Dev 1 | AI-optimized content generation — FAQ, comparison, meta descriptions, feature snippets |
| `brand_resolver.py` | Dev 1 | Brand ↔ domain resolution with caching |
| `llm_service.py` | Dev 1/2 | Multi-provider LLM abstraction (Groq, Claude/Nova, OpenAI, Perplexity, Gemini) |
| `ai_chatbot.py` | Dev 1 | SEO chatbot session management |
| `geo_scanner_agent.py` | Dev 1 | **NEW** — GEO Scanner Agent orchestrator — coordinates 4 scanner agents, returns structured reports with plain-English summaries, persists to RDS |
| `bedrock_helper.py` | Dev 2 | Bedrock helper — Nova Lite default, supports Nova + Anthropic formats |
| `build_zip.py` | Dev 3 | Lambda deployment ZIP builder |
| `patch_app.py` | — | App patching utility |
| `validate_geo_probe.py` | Dev 1 | GEO probe validation/test script |

---

## API Endpoints — Full Reference

### GEO Scanner Agent (`/api/geo-scanner/*`) — **NEW**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/geo-scanner/scan` | Full orchestrated scan — runs all scanner agents, returns structured report with overall score, executive summary, recommendations, and RDS persistence status |
| GET | `/api/geo-scanner/agents` | List available scanner agents (brand_visibility, content_readiness, competitor_gap, site_mention) |

### RDS Data Persistence (`/api/data/*`) — **NEW**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/data/geo-probes` | Persist individual GEO probe results to RDS `geo_probes` table |
| POST | `/api/data/ai-visibility` | Persist batch visibility results to RDS `ai_visibility_history` table |

### Auth (`/api/auth/*`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/signup` | Cognito user registration |
| POST | `/api/confirm` | Confirm signup with verification code |
| POST | `/api/resend-code` | Resend verification code |
| POST | `/api/login` | Cognito login, returns tokens |
| POST | `/api/logout` | Invalidate Cognito token |
| POST | `/api/delete-account` | Delete user from Cognito |
| POST | `/api/verify` | Verify if token is valid |
| POST | `/api/refresh-token` | Refresh expired access token |
| POST | `/api/send-welcome` | Send welcome email via SES |
| POST | `/api/forgot-password` | Initiate password reset |
| POST | `/api/reset-password` | Complete password reset with code |

### SEO Analysis

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/analyze` | Full SEO analysis — 236 checks across 10 categories |
| POST | `/api/ai-recommendations` | AI-powered SEO recommendations via LLM |
| GET | `/api/health` | Health check (DB, Bedrock, Ollama status) |

### GEO Monitoring (`/api/geo-probe/*`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/geo-probe` | Single GEO probe — brand + keyword + AI model |
| GET | `/api/geo-probe/models` | List available AI providers |
| POST | `/api/geo-probe/batch` | Batch probe — multiple keywords, computes geo_score |
| GET | `/api/geo-probe/history` | Probe history from RDS (batch summaries + individual) |
| POST | `/api/geo-probe/schedule` | Register scheduled monitoring job (placeholder) |
| GET | `/api/geo-probe/schedule` | List registered scheduled jobs |
| POST | `/api/geo-probe/compare` | Compare brand across ALL available AI providers |
| POST | `/api/geo-probe/site` | Detect if a URL/domain is mentioned in AI output |
| GET | `/api/geo-probe/trend` | Visibility trend for a brand over time (query: `brand`, `limit`) |

### AEO & AI Ranking

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/aeo/analyze` | AEO page analysis — schema, structure, meta, authority |
| POST | `/api/ai/ranking-recommendations` | AI ranking recommendations for a URL + brand |
| POST | `/api/ai/citation-probe` | Multi-provider citation probe (via `llm_service`) |
| POST | `/api/ai/geo-monitor` | Multi-provider GEO monitor (via `llm_service`) |

### Content

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/content/generate` | Content generation — FAQ, comparison, meta, snippets |
| POST | `/api/content-brief` | SERP-based content brief generation |
| GET | `/api/content-briefs` | List saved content briefs |

### Brand Resolution

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/brand/resolve` | Resolve brand name ↔ domain, suggest keywords |

### AI Chatbot

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chatbot/session` | Create new chatbot session |
| POST | `/api/chatbot/chat` | Send message to chatbot |
| GET | `/api/chatbot/history/<session_id>` | Get chat history for session |
| GET | `/api/chatbot/sessions` | List active sessions |

### LLM Multi-Provider

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/llm/providers` | List available LLM providers |
| POST | `/api/llm/citation-probe` | Citation probe via `llm_service` (Groq/Claude/OpenAI/Perplexity/Gemini) |

### Static Pages

| Path | Serves |
|------|--------|
| `/` | `index.html` |
| `/analyze` | `analyze.html` |
| `/audit/` | `audit.html` |
| `/geo-test` | `geo-test.html` |
| `/geo-scanner` | `geo-scanner.html` — **NEW** GEO Scanner Agent dashboard |
| `/dev1-dashboard` | `dev1-dashboard.html` |
| `/dashboard` | Redirects to `/dev1-dashboard` |

---

## Database Schema (RDS PostgreSQL)

### `projects`
Multi-tenancy root table. Default project: `00000000-0000-0000-0000-000000000001`.

### `geo_probes`
Individual GEO probe results — keyword, brand, AI model, cited (bool), citation_context, confidence, response_snippet, sentiment, probe_timestamp. Indexed on project_id, keyword, timestamp.

### `ai_visibility_history`
Batch visibility results — brand, AI model, keyword, geo_score, cited_count, total_prompts, batch_results (JSONB). Indexed on project_id, measured_at.

### `content_briefs` / `brief_competitors` / `brief_keywords`
Content brief storage with related competitors and keyword placements.

Schema is auto-initialized by `db.init_db()` on first connection (idempotent `CREATE TABLE IF NOT EXISTS` + safe column migrations).

---

## AI Provider Configuration

| Provider | Model | Access | Env Vars |
|----------|-------|--------|----------|
| Bedrock Nova Lite | `us.amazon.nova-lite-v1:0` | IAM role (Lambda/App Runner) | `NOVA_MODEL`, `AWS_REGION_NAME` |
| Ollama (homelab) | `qwen3:30b-a3b` | HTTPS to `ollama.sageaios.com` | `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` |
| Groq | `llama-3.3-70b-versatile` | API key | `GROQ_API_KEY` |
| OpenAI | `gpt-4o-mini` | API key | `OPENAI_API_KEY` |
| Perplexity | `llama-3.1-sonar-small-128k-online` | API key | `PERPLEXITY_API_KEY` |
| Gemini | `gemini-1.5-flash` | API key | `GEMINI_API_KEY` |
| Anthropic (fallback) | `claude-3-haiku-20240307` | API key | `ANTHROPIC_API_KEY` |

Primary routing: `ai_provider.py` → `generate(prompt, provider)` — used by GEO probes, content generation, AEO.
Extended routing: `llm_service.py` → `citation_probe()` / `geo_monitor()` — used by `/api/llm/*` and `/api/ai/*` endpoints.

---

## Recent Changes (March–April 2026)

### Apr 8 — Dev 1 Task Completion: DynamoDB Wiring, Deployment, Documentation
- Fixed GEO Scanner orchestrator `_persist_to_rds()` to auto-detect DynamoDB vs RDS mode (matches `app.py` behavior)
- Fixed `geo_probe_service.py` — all DB calls now route through DynamoDB when `USE_RDS` is not set
- Removed duplicate route decorator on `/api/geo-scanner/scan`
- Updated `DEPLOYMENT-LINUX.md` with psycopg2 troubleshooting, DynamoDB mode docs, and team setup guide
- Updated `SEO-CONTENT-WORKFLOWS.md` with quick-start guide and recommended end-to-end flow
- GEO Scanner link already present in admin dashboard (tab bar + quick access card)
- Parameter reference already built into both `geo-scanner.html` and `dev1-dashboard.html`
- All `/api/data/*` endpoints (geo-probes, ai-visibility) fully wired with DynamoDB support

### Mar 26 — GEO Scanner Agent Enhancements & Workflow Documentation
- Fixed parameter mismatch in `_persist_to_rds()` — `context_snippet` → `citation_context` to match `db.insert_probe()` signature
- Fixed same mismatch in `POST /api/data/geo-probes` endpoint in `app.py`
- Enhanced executive summary with "what this means" explainer for non-technical users
- Improved recommendations with `effort`, `timeframe` fields and more actionable descriptions
- Added intermediate score thresholds (40-70%) for more nuanced recommendations
- Competitor gap recommendations now list specific missing AI models
- Updated `geo-scanner.html` to display effort/timeframe in recommendation cards
- Created `SEO-CONTENT-WORKFLOWS.md` — full process documentation with ASCII diagrams for all 9 workflows
- Created `DEPLOYMENT-LINUX.md` — Docker + direct deployment instructions for Linux server

### Mar 26 — Shared Lambda Fix & Endpoint Audit
- Confirmed all GEO/AEO/content endpoints are live and functional in the shared backend
- No `/api/data/*` endpoints exist — dashboard pages should use the endpoints listed above
- Scheduled monitoring (`/api/geo-probe/schedule`) is an in-memory placeholder; production scheduling requires EventBridge + separate trigger Lambda
- All Dev 1 modules (`geo_probe_service`, `content_generator`, `aeo_optimizer`, `ai_ranking_service`, `brand_resolver`, `ai_chatbot`) are wired into `app.py` and deployed

### Mar 25 — Multi-Provider LLM Service
- `llm_service.py` added with 5 external providers (Groq, Claude/Nova, OpenAI, Perplexity, Gemini)
- Claude queries route through Bedrock Nova first, fall back to Anthropic API
- `/api/llm/providers`, `/api/llm/citation-probe` endpoints added
- `/api/ai/citation-probe` and `/api/ai/geo-monitor` endpoints added

### Mar 24 — GEO Engine + RDS Persistence
- `geo_probe_service.py` — full GEO monitoring with single probe, batch, compare, site detection, trend
- `db.py` — RDS connection pool, schema init, CRUD for geo_probes + ai_visibility_history + content_briefs
- `ai_provider.py` — unified Bedrock Nova + Ollama abstraction
- `content_generator.py` — FAQ, comparison, meta description, feature snippet generation
- `aeo_optimizer.py` — page-level AEO analysis (schema, structure, meta, authority)
- `ai_ranking_service.py` — brand presence analysis + prioritized recommendations
- All persisted to RDS with UUID PKs and project_id for multi-tenancy

### Mar 23-24 — Content & NLP (Dev 2 — Samar)
- `/api/content-brief` endpoint — SERP scraping + LLM-generated structured briefs
- 10th SEO category: `citationgap` — 20 checks (total now 236 across 10 categories)
- `call_llm()` with fallback chain: Nova Lite → Ollama sageaios → Ollama databi
- Content brief UI in `audit.html`

---

## Rules for Contributors

1. **Deploy via GitHub only** — push to `main` on `DeepthiSarayuGunda/ai1stseo-backend`, App Runner auto-deploys
2. **Do NOT** modify the deployed Lambda or App Runner directly via AWS Console/CLI
3. **Do NOT** change `call_llm()`, Ollama URLs, or `API_BASE` in S3-served HTML files
4. **Do NOT** remove or rename existing endpoints without coordinating with the team
5. **Do NOT** overwrite `audit.html` without preserving Dev 2's content brief features and localStorage saving
6. Update `PROJECT-STATUS.md` change log when adding features
7. Test locally before pushing: `python app.py` runs Flask dev server on port 5000
