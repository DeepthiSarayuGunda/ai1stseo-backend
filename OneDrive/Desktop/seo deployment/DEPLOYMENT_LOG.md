# AI 1st SEO — Deployment Log

⚠️ **READ THIS BEFORE DEPLOYING OR MAKING CHANGES** ⚠️

Check the latest entry below to understand the current state of all services before you start work.

---

## 2026-04-01 11:00 — Email Lead Collection Endpoint + DynamoDB Table (Troy)

**Per Amira's request:** PDF download email gate needs backend storage.

**What was done:**
- Created DynamoDB table: `ai1stseo-email-leads` (PK: `id`, GSI: `email-index`, PAY_PER_REQUEST)
- Added `POST /api/collect-email` endpoint to `app.py` — no auth required (public lead capture)
- Accepts: `{email, source, page_url, report_type}`
- Returns: `{status: "success"}` on save

**For Amira:** Update your PDF download JS to POST to `https://api.ai1stseo.com/api/collect-email` with the email before generating the PDF. Example:
```js
fetch('https://api.ai1stseo.com/api/collect-email', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({email: userEmail, source: 'pdf_download', page_url: window.location.href, report_type: 'seo_audit'})
});
```

**Note:** This endpoint is in `app.py` but NOT yet deployed to Lambda. Will be included in the next Lambda deploy (DynamoDB migration).

---

## 2026-04-01 02:40 — RDS Shutdown + Data Export (Troy)

**Per Gurbachan's directive:** Moving away from RDS PostgreSQL to individual DynamoDB tables per app.

**What was done:**
- Exported all 1,256 rows from 30 tables to `rds-backup/` as JSON files
- Exported full schema to `rds-backup/_schema.json`
- Created final RDS snapshot: `ai1stseo-final-backup-20260401`
- RDS instance stopped (not deleted — can be restarted if needed)
- Data is safe in 3 places: local JSON, RDS snapshot, stopped instance

**Tables with data (backed up):**
- `users` (8), `projects` (2), `audits` (14), `geo_probes` (336), `content_briefs` (11)
- `brief_keywords` (43), `admin_metrics` (8), `ai_usage_log` (18), `api_request_log` (570)
- `answer_fingerprints` (215), `model_comparisons` (11), `uptime_checks` (15)
- `monitored_sites` (1), `prompt_simulations` (2), `share_of_voice` (2)

**Impact:** All endpoints that write to RDS will return errors until DynamoDB migration is complete. Auth (Cognito) still works. SEO analyzer still works. Only data persistence is affected.

**Next:** Create DynamoDB tables and update the data API to use DynamoDB instead of PostgreSQL.

**DynamoDB tables created (2026-04-01):**
| DynamoDB Table | Replaces RDS | PK | GSI |
|---------------|-------------|-----|-----|
| ai1stseo-users | users | id | email-index |
| ai1stseo-audits | audits + audit_checks | id | url-index |
| ai1stseo-geo-probes | geo_probes | id | keyword-index |
| ai1stseo-content-briefs | content_briefs | id | — |
| ai1stseo-social-posts | social_posts | id | — |
| ai1stseo-admin-metrics | admin_metrics | metric_date | — |
| ai1stseo-api-logs | api_request_log | id | endpoint-index |
| ai1stseo-webhooks | webhooks | id | — |
| ai1stseo-api-keys | api_keys | key_hash | — |
| ai1stseo-competitors | competitors | id | — |
| ai1stseo-monitor | monitored_sites + uptime_checks | id | — |

All tables use PAY_PER_REQUEST billing. New modules: `dynamodb_helper.py` (DynamoDB operations) and `data_api_dynamo.py` (data API using DynamoDB).

---

## 2026-03-31 01:15 — Contact Form + Deepthi Lambda Deploy + DB Security (Troy)

**Contact form:**
- `POST /api/contact` endpoint live on `ai1stseo-backend` Lambda
- Accepts `{name, email, message}`, sends via SES to `support@ai1stseo.com`
- `contact.html` on the repo — Amira deploys to Amplify at `/contact`

**Deepthi's Lambda updated:**
- Deployed her latest code (GEO Scanner Agent, answer fingerprint, model comparison, multilang probe, prompt simulator, share of voice) to `ai1stseo-geo-engine` Lambda
- Her routes verified: geo-probe/models (200), geo-probe/history (200), aeo/analyze (400), chatbot/session (200), brand/resolve (400)
- Did NOT touch `ai1stseo-backend` — per-dev routing keeps them separate

**Database security hardening:**
- ✅ Deletion protection enabled
- ✅ SSL enforcement via custom parameter group (`ai1stseo-pg15-secure`, `rds.force_ssl=1`)
- ✅ `pgcrypto` extension installed for row-level encryption capability
- ✅ DB credentials stored in Secrets Manager (`ai1stseo/db-credentials`)
- ⚠️ Encryption at rest still off (requires new instance from encrypted snapshot — planned separately)

**EC2 fully terminated:**
- Instance `i-0d59b5c1a433f0255` terminated (not just stopped)
- AMI + snapshot cleaned up automatically
- No orphaned EBS volumes or Elastic IPs (EIP on RDS is needed)

---

## 2026-03-26 18:17 — Content Briefs & Scoring Routes Added (Troy)

**Issue:** GET `/api/content-briefs` was returning index.html instead of JSON. The route was never in the deployed `app.py` — it was in Samarveer's later commits but missed all previous merges.

**Fix:** Added three routes + three compute functions to `app.py`:
- `GET /api/content-briefs` — list briefs with keyword filter (calls `db.get_content_briefs()`)
- `GET /api/content-briefs/<id>` — get single brief (calls `db.get_content_brief_by_id()`)
- `POST /api/content-score` — score a URL for readability + SEO + AEO (40/35/25 weighted)
- `compute_readability_score()` — Flesch Reading Ease approximation
- `compute_seo_score()` — 5 on-page SEO checks (title, meta, H1, images, canonical)
- `compute_aeo_score()` — 5 AI-extractable content checks (FAQ schema, definitions, Q&A headings, lists, tables)

**Status:**
- `/api/content-score` — fully working (tested: ai1stseo.com → readability 66.4, SEO 40.0, AEO 0.0, overall 32.6)
- `/api/content-briefs` — route registered, returns JSON, but 500 because `get_content_briefs()` is not yet defined in `db.py`. **Samarveer needs to add this function and push.**

---

## 2026-03-26 18:07 — Full Team Merge + Deepthi's GEO Routes Fixed (Troy)

**What happened:** Rebuilt the Lambda with everyone's code merged. Used Samarveer's 73MB zip as the base (has all dependencies + Deepthi's GEO modules), injected Troy's blueprints (auth, admin, data API, webhooks, API keys), added Mangum Lambda handler, request logging, and CORS for all subdomains.

**What's now live (45+ routes):**
- Troy's infrastructure: auth, admin dashboard (9 endpoints), data API (22 endpoints), webhooks, API keys, request logging
- Samarveer's features: `/api/content-brief`, `/api/content-score`, `/api/content-briefs`, `call_llm`, citation gap analysis (10th category)
- Deepthi's GEO engine: `/api/geo-probe/*` (models, history, batch, compare, trend, schedule, site), `/api/aeo/analyze`, `/api/ai/*` (citation-probe, geo-monitor, ranking-recommendations), `/api/chatbot/*` (session, chat, history, sessions), `/api/brand/resolve`
- Shared: `/api/analyze` (251 checks across 10 categories), `/api/health`, `/api/ai-recommendations`

**Verified working:**
- All Samarveer routes: content-brief (400), content-score (400), content-briefs (500 — db connection, route exists)
- All Deepthi routes: geo-probe/models (200), geo-probe/history (200), chatbot/session (200), aeo/analyze (400)
- All Troy routes: auth (400), admin (401), data API (401), webhooks (200), API keys (401)
- CORS: automationhub + monitor both returning correct headers

**EC2 shutdown:** Stopped `i-0d59b5c1a433f0255` (54.226.251.216). All services migrated to Lambda/App Runner/Amplify. Saving ~$30/mo.

**DNS updates:** `seoaudit.ai1stseo.com` and `seoanalysis.ai1stseo.com` CNAMEs updated (Samarveer fixed to point to API Gateway).

---

## 2026-03-26 12:21 — Lambda Merge Fix (Troy)

**What happened:** Someone deployed a 73MB zip (`lambda_deploy.zip`) directly to the `ai1stseo-backend` Lambda, overwriting the existing 26MB package. The new deploy didn't include the auth module (`auth.py`), breaking login for all users (`/api/auth/login` returned 405).

**What was done:** Merged both packages — our original (auth, admin, data API, webhooks, API keys, psycopg2 3.11) as the foundation, with the new GEO/content modules (aeo_optimizer, geo_engine, content_generator, brand_resolver, etc.) added on top. Deployed the merged 78MB package.

**Current state:**
- `ai1stseo-backend` Lambda: 78MB, all endpoints working (auth, admin, data API, webhooks, API keys, SEO analyzer, GEO modules)
- `seo-analyzer-api` Lambda: 12MB, site monitor with vaporwave UI, RDS persistence, webhook dispatch
- `ai1stseo-admin-aggregation` Lambda: dedicated daily metrics job (02:00 UTC)

**DO NOT deploy directly to `ai1stseo-backend` without coordinating with Troy.**

---

## 2026-03-25 — Backend Infrastructure Complete (Troy)

**What was deployed:**
- Admin dashboard API (9 endpoints): overview, users, usage, ai-costs, metrics, errors, health, requests, me
- Shared Data API (22 endpoints): audits, GEO probes, AI visibility, content briefs, social posts, competitors, benchmarks, reports
- Webhook event system: 13 event types, HMAC signatures, delivery logging
- Developer API key system: generation, scopes (read/write/admin), rate limiting
- Request logging middleware: tracks all API calls to `api_request_log` table
- AI usage tracking: both inference modules log to `ai_usage_log` table
- Daily aggregation Lambda: EventBridge cron at 02:00 UTC
- Cross-subdomain SSO: shared cookie on `.ai1stseo.com`
- psycopg2 upgraded to Python 3.11 compatible binary

**RDS tables created:**
- `admin_metrics`, `ai_usage_log`, `api_request_log` (admin)
- `webhooks`, `webhook_deliveries` (webhooks)
- `api_keys` (developer API)
- All existing schema tables verified

**Site monitor updates:**
- Template fix (was missing from Lambda zip)
- Cognito auth + database modules added
- Social SEO meta tags, performance headers, security headers
- Vaporwave design system applied
- QoL UI: loading spinner, formatted results, scan history, copy button, deep scan buttons, collapsible sections
- RDS persistence: scans save to audits table, AI visibility saves to history
- Webhook dispatch: uptime.down, content.changed events

---

## Deployment Rules

1. **Never deploy directly to `ai1stseo-backend` Lambda** — it's shared infrastructure. Coordinate with Troy.
2. **Always pull latest from `main` before starting work** — `git pull origin main`
3. **Push your code to GitHub first** — don't deploy zips that aren't in the repo.
4. **Use the shared Data API** (`/api/data/*`) instead of building your own database connections.
5. **If you need a separate service**, ask Troy to set up a dedicated Lambda for it.

## Current API Endpoints (api.ai1stseo.com)

### Auth
- `POST /api/auth/signup`, `/login`, `/verify`, `/resend-code`, `/forgot-password`, `/reset-password`
- `GET /api/auth/me`

### Admin (require admin role)
- `GET /api/admin/overview`, `/users`, `/usage`, `/ai-costs`, `/metrics`, `/errors`, `/health`, `/requests`, `/me`

### Data API (require auth)
- Audits: `POST/GET /api/data/audits`, `GET /api/data/audits/:id`
- GEO Probes: `POST/GET /api/data/geo-probes`
- AI Visibility: `POST/GET /api/data/ai-visibility`
- Content Briefs: `POST/GET /api/data/content-briefs`, `GET /api/data/content-briefs/:id`
- Social Posts: `POST/GET/PUT/DELETE /api/data/social-posts`
- Competitors: `POST/GET/DELETE /api/data/competitors`
- Benchmarks: `POST/GET /api/data/competitors/:id/benchmarks`, `GET /api/data/benchmarks/compare`
- Reports: `POST/GET /api/data/reports`, `GET /api/data/reports/:id`

### Webhooks
- `POST/GET/DELETE /api/webhooks`, `POST /api/webhooks/:id/toggle`
- `GET /api/webhooks/events` (public — lists all event types)

### API Keys
- `POST/GET/DELETE /api/keys`, `POST /api/keys/:id/toggle`

### SEO Analyzer
- `POST /api/analyze`, `GET /api/health`
