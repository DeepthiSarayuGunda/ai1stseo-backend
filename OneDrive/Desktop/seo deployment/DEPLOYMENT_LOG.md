# AI 1st SEO — Deployment Log

⚠️ **READ THIS BEFORE DEPLOYING OR MAKING CHANGES** ⚠️

Check the latest entry below to understand the current state of all services before you start work.

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
