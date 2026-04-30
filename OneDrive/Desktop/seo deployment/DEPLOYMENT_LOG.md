# AI 1st SEO — Deployment Log

⚠️ **READ THIS BEFORE DEPLOYING OR MAKING CHANGES** ⚠️

Check the latest entry below to understand the current state of all services before you start work.

---

## 2026-04-30 — Stripe Integration + Attribution Pipeline + Admin Fix + Infrastructure Hardening (Troy)

**Stripe Payment Integration:**
- Stripe live keys configured as Lambda env vars (STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY)
- Webhook endpoint created on Stripe: `https://api.ai1stseo.com/api/webhooks/stripe` → `checkout.session.completed`
- `POST /api/stripe/create-checkout` — creates a $5 Pro trial checkout session, returns Stripe hosted URL
- `GET /api/stripe/config` — returns publishable key for frontend
- `POST /api/webhooks/stripe` — Stripe webhook handler, auto-upgrades user tier to `pro` on payment
- Subscription tier system: `subscription_tier` field on users (free/pro/admin), `GET /api/user/tier`

**AI Referral Attribution Pipeline:**
- `POST /api/attribution/track` (public) — receives referral events from JS snippet, normalizes 15+ AI referrer patterns
- `POST /api/attribution/convert` (public) — tracks conversion events tied to AI sessions
- `GET /api/attribution/ai-referrals` (auth) — aggregated dashboard by source
- `GET /api/attribution/snippet` (public) — returns copy-paste JS tracking snippet

**Admin Endpoint Fix:**
- Deepthi pushed 534 lines to app.py + new modules (month5_systems, aeo_engine). Lambda was stale.
- Redeployed with full sync: all Troy modules + Deepthi's new modules + Samar's directory modules
- All admin endpoints restored (system-status, audit-history, white-label, api-usage, documents)

**New Features from Product Spec:**
- AI inference response caching (24h DynamoDB TTL for low-temperature calls)
- Citation probe bridge for content brief generator (`POST /api/backlinks/brief-citation-probe`)
- SEO data API wrapper (`backend/seo_data_api.py`) — Ahrefs/DataForSEO/builtin fallback
- `database_rows` + `table_counts` added to admin overview response

**Infrastructure Hardening:**
- DynamoDB point-in-time recovery enabled on all 15 tables
- CloudWatch alarms: Lambda errors (>5/10min), throttles (>3/5min), duration (>25s avg)
- Node.js 20.x EOL notice received — affects `seo-audit-tool` and `automation-hub` Lambdas (not ours)

**Files changed:** `backend/auth.py`, `backend/admin_api.py`, `backend/ai_inference.py`, `backend/backlink_api.py`, `backend/attribution_api.py`, `backend/seo_data_api.py`, `backend/multisite_api.py`

---

## 2026-04-28 — App.py Merge + Full Lambda Sync + Backlink Doc Update (Troy)

**Root cause fix:** Two separate `app.py` files (root vs `backend/`) have been causing deploy overwrites for weeks. Merged all Troy-unique routes into Samar's root `app.py` so there is now ONE authoritative app.py.

**What was merged into root app.py:**
- `backlink_bp` blueprint registration (14 endpoints)
- Request logging middleware (`before_request` / `after_request` → DynamoDB)
- `POST /api/contact` — contact form via SES
- `POST /api/invest` — investor inquiry via SES
- `POST /api/collect-email` — email lead collection
- `POST/GET /api/content-freshness` — content freshness tracking
- `GET /api/content-briefs/<brief_id>` — single brief detail

**Lambda fully synced with git:**
- `app.py` now pulled from `git show origin/main:app.py` during deploys (never from local OneDrive)
- All 9 Troy DynamoDB module overlays deployed (admin_api, auth, webhook_api, apikey_api, ai_inference, admin_aggregation, dynamodb_helper, data_api_dynamo, backlink_api)
- Samar's new directory/sports modules included (directory_api, directory_db, sports_api, sports_db, sports_fetcher, scheduler)
- All endpoints verified: 0 404s, all admin routes returning 401 (auth required)

**System status fix deployed:**
- Cognito, SES, and DynamoDB table checks now gracefully degrade to "healthy" with a note when Lambda IAM role lacks detailed monitoring permissions (instead of showing "error")

**Auth bugfix:** Fixed duplicate `except Exception` block in `auth.py` `_sync_user_to_db`

**Backlink strategies document updated:** Added AWS service pairings for all 7 strategies (EventBridge, Bedrock, SQS, SES, SageMaker, Step Functions, SNS, Forecast). Generated `.docx` version.

**Deploy pattern going forward:**
- Root `app.py` is the ONLY app.py. `backend/app.py` is legacy — do not deploy it.
- Safe deploy script pulls app.py from git, not local filesystem.
- Module files (admin_api, auth, etc.) are overlaid from `backend/` directory.

**Files changed:** `app.py` (root), `backend/admin_api.py`, `backend/auth.py`, `BACKLINK_STRATEGIES_DEMO.md`

---

## 2026-04-22 — Slack/Email Notifications + Content Freshness API (Troy)

**New features deployed to Lambda:**

**Slack + Email Notification Channels (WBS 6.3):**
- `POST /api/notifications/subscribe` — subscribe to events via Slack webhook URL or email address
  - Body: `{"channel": "slack", "target": "https://hooks.slack.com/...", "events": ["audit.created", "*"]}`
  - Or: `{"channel": "email", "target": "user@example.com", "events": ["uptime.down"]}`
- `GET /api/notifications` — list notification subscriptions
- All `dispatch_event()` calls now trigger both webhook URLs AND Slack/email notifications
- Slack messages include emoji per event type and formatted payload
- Email notifications sent via SES from no-reply@ai1stseo.com

**Content Freshness API (for AI ranking maintenance):**
- `POST /api/content-freshness` — record a content update timestamp
  - Body: `{"url": "https://ai1stseo.com/page", "update_type": "content_refresh", "sections": ["faq", "pricing"]}`
- `GET /api/content-freshness?url=...` — get freshness history for a URL
- Gurbachan emphasized that AI algorithms require regular timestamped updates to maintain rankings

**Files changed:** `backend/webhook_api.py`, `backend/app.py`

**Reminder:** Read `IMPORTANT_READ_BEFORE_PUSHING.md` before merging to main. Do NOT revert backend files to RDS imports.

---

## 2026-04-09 17:00 — Admin API Fix + Rate Limiting + Investor Endpoint (Troy)

**Issue:** `admin_api.py` was reverted to the old RDS version by a team merge, causing all admin dashboard endpoints to fail (they tried to query the stopped RDS database).

**Fix:** Restored the DynamoDB version of `admin_api.py` with all endpoints working against DynamoDB. Redeployed Lambda.

**New endpoints deployed in this cycle:**
- `GET /api/admin/api-usage` — API key rate limiting dashboard (per-key stats)
- `GET /api/admin/api-usage/logs` — request log analytics with endpoint filtering
- `POST /api/invest` — investor inquiry form, sends via SES to gurbachan@ai1stseo.com
- `POST /api/admin/documents` — document upload (S3 + DynamoDB)
- `GET /api/admin/documents` — list documents, filter by `?developer=dev1`
- `GET /api/admin/documents/:id/download` — presigned S3 download URL
- `DELETE /api/admin/documents/:id` — delete document (admin only)
- `POST /api/collect-email` — email lead collection for PDF downloads
- `invest.html` + `contact.html` — restyled to match main site design, live on S3

**Infrastructure changes this week:**
- DynamoDB migration complete — all 6 backend modules rewritten, 981 rows migrated, RDS deleted ($15/mo saved)
- OpenClaw Gateway v2026.4.1 installed on seo-dev server (port 18789)
- Local Ollama accelerator connected with tiered models (8B/30B/235B + embeddings)
- 4 ClawHub skills installed (seo-geo-audit, site-monitor, seo-competitor-analysis, geo-seo-optimizer)
- OpenShell CLI + Podman installed — blocked on LXC seccomp restriction for sandbox creation
- Node.js upgraded to v22 on seo-dev
- Investor link added to homepage footer

**Reminder to all devs:** When merging branches to main, check the diff for `backend/*.py` files. If you see hundreds of deleted lines you didn't write, your merge is overwriting someone else's work. Always `git pull origin main` before pushing.

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
