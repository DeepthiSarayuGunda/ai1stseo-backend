# AI 1st SEO — Admin Dashboard Scope
## March 24, 2026

Per Gurbachan's direction in the Mar 24 meeting, the product needs two distinct dashboards:
1. **User Dashboard** — where customers run tools (scans, briefs, GEO probes). Amira owns this.
2. **Admin Dashboard** — internal team view for managing the platform. Scoped below.

This document covers the Admin Dashboard database requirements and data model.

---

## What the Admin Dashboard Shows

### 1. User & Account Management
- Total registered users (from Cognito / `users` table)
- New sign-ups over time (daily, weekly, monthly)
- Active vs inactive users (last login tracking)
- Users by plan tier (free, pro, enterprise)
- Account verification status

### 2. Platform Usage Stats
- Total scans run (from `audits` table — count by day/week)
- Scans by type: SEO audit, deep scan, content brief, GEO probe
- Most-scanned URLs
- Average scan scores over time (trending up or down?)
- API call volume by endpoint

### 3. Monitoring Health
- Scheduled scan success/failure rate (from `scan_errors` table)
- Active monitored sites count
- Uptime across all monitored sites (aggregate from `uptime_checks`)
- Recent scan errors with resolution status

### 4. Revenue & Payments (future)
- Users by plan tier
- MRR (monthly recurring revenue) when payments are added
- Churn rate (users who downgrade or cancel)
- Payment failure tracking

### 5. AI Usage & Costs
- Bedrock invocations (Nova Lite) — count and estimated cost
- Ollama fallback usage rate (indicates Bedrock failures)
- Token usage estimates
- AI recommendation generation count

### 6. Content & Engagement
- Content briefs generated (from `content_briefs`)
- GEO probes run (from `geo_probes`)
- Social posts scheduled (from `social_posts`)
- Report subscriptions active (from `subscriptions`)

---

## New Database Tables Needed

```sql
-- Platform-wide usage metrics (aggregated daily by a scheduled job)
CREATE TABLE admin_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_users INTEGER DEFAULT 0,
    new_signups INTEGER DEFAULT 0,
    active_users_24h INTEGER DEFAULT 0,
    active_users_7d INTEGER DEFAULT 0,
    total_scans INTEGER DEFAULT 0,
    total_deep_scans INTEGER DEFAULT 0,
    total_content_briefs INTEGER DEFAULT 0,
    total_geo_probes INTEGER DEFAULT 0,
    avg_seo_score NUMERIC(5,2),
    bedrock_calls INTEGER DEFAULT 0,
    ollama_fallback_calls INTEGER DEFAULT 0,
    scan_errors_count INTEGER DEFAULT 0,
    estimated_ai_cost_usd NUMERIC(8,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_admin_metrics_date ON admin_metrics(metric_date);

-- API request log (lightweight, for usage tracking)
CREATE TABLE api_request_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    user_id UUID REFERENCES users(id),
    project_id UUID REFERENCES projects(id),
    status_code INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_log_endpoint ON api_request_log(endpoint);
CREATE INDEX idx_api_log_created ON api_request_log(created_at DESC);
-- Partition or auto-delete after 30 days to keep table size manageable

-- AI usage tracking (per-call cost estimation)
CREATE TABLE ai_usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,        -- nova_lite, ollama_sageaios, ollama_databi
    model VARCHAR(100) NOT NULL,
    input_tokens_est INTEGER DEFAULT 0,
    output_tokens_est INTEGER DEFAULT 0,
    estimated_cost_usd NUMERIC(8,6) DEFAULT 0,
    success BOOLEAN DEFAULT TRUE,
    latency_ms INTEGER,
    triggered_by VARCHAR(50),             -- scan, content_brief, geo_probe, daily_report
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ai_usage_provider ON ai_usage_log(provider);
CREATE INDEX idx_ai_usage_created ON ai_usage_log(created_at DESC);
```

---

## Data Sources (already exist, just need admin queries)

| What | Source Table | Query Pattern |
|------|-------------|---------------|
| User count & growth | `users` | COUNT by created_at date range |
| Scan volume | `audits` | COUNT by created_at, GROUP BY date |
| Scan scores trend | `audits` | AVG(overall_score) GROUP BY week |
| Uptime health | `uptime_checks` | AVG(is_up) over time |
| Scan failures | `scan_errors` | COUNT WHERE resolved = false |
| Content briefs | `content_briefs` | COUNT by created_at |
| GEO probes | `geo_probes` | COUNT by probe_timestamp |
| Social posts | `social_posts` | COUNT by status |
| Subscriptions | `subscriptions` | COUNT WHERE is_active = true |
| Competitor tracking | `benchmarks` | Latest per competitor |

---

## API Endpoints Needed

```
GET /api/admin/overview          — top-level stats (users, scans, errors, revenue)
GET /api/admin/users             — paginated user list with last login, plan, scan count
GET /api/admin/usage             — scan volume over time, by type
GET /api/admin/ai-costs          — AI provider usage and estimated costs
GET /api/admin/errors            — scan errors dashboard (already partially done via /api/scan-errors)
GET /api/admin/health            — system health: uptime %, error rate, avg response time
```

All admin endpoints require auth + admin role check (`role = 'admin'` in `users` table).

---

## Implementation Priority

1. **Phase 1 (this sprint)**: ✅ DONE — Admin queries on existing tables — user count, scan volume, error rate. No new tables needed.
2. **Phase 2 (this sprint)**: ✅ DONE — `admin_metrics` daily aggregation job (EventBridge), `ai_usage_log` tracking in both inference modules, `/api/admin/ai-costs` + `/api/admin/metrics` endpoints added.
3. **Phase 3 (future)**: `api_request_log` middleware, payment tracking when Stripe/billing is added.

---

## Notes
- Admin dashboard is internal-only — not customer-facing
- Separate from the user dashboard Amira is building
- Troy + Amira collaboration: Troy builds the API/data layer, Amira builds the UI
- Nova Lite cost estimate: ~$0.06 per 1M input tokens, ~$0.24 per 1M output tokens
- Ollama usage is free (Gurbachan's homelab) but should still be tracked for reliability metrics
