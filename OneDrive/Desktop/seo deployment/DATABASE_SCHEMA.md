# AI 1st SEO — Database Schema (DynamoDB)

> **NOTE:** This project migrated from RDS PostgreSQL to DynamoDB on April 1, 2026.
> RDS has been deleted. Snapshot preserved: `ai1stseo-final-backup-20260401`.
> All data now lives in DynamoDB tables below.

## Connection

DynamoDB is accessed via `boto3` with IAM role authentication. No connection strings needed.

```python
import boto3
ddb = boto3.resource('dynamodb', region_name='us-east-1')
table = ddb.Table('ai1stseo-users')
```

Helper module: `backend/dynamodb_helper.py` provides `put_item`, `get_item`, `scan_table`, `query_index`, `update_item`, `delete_item`, `count_items`.

## DynamoDB Tables (15)

All tables use PAY_PER_REQUEST billing (no provisioned capacity, $0 at low scale).

### Core Tables

| Table | PK | GSI | Owner | Purpose |
|-------|-----|-----|-------|---------|
| ai1stseo-users | userId | email-index | Core | User accounts, roles, subscription tiers |
| ai1stseo-audits | id | url-index | Dev 3 (Troy) | SEO audit scan results |
| ai1stseo-documents | id | uploader-index | Dev 3 (Troy) | Document repository metadata |

### GEO / AI Tables

| Table | PK | GSI | Owner | Purpose |
|-------|-----|-----|-------|---------|
| ai1stseo-geo-probes | id | keyword-index | Dev 1 (Deepthi) | AI citation probe results |
| ai1stseo-content-briefs | id | — | Dev 2 (Samar) | AI content brief output |
| ai1stseo-social-posts | id | — | Dev 4 (Tabasum) | Scheduled social media posts |

### Admin & Analytics Tables

| Table | PK | GSI | Owner | Purpose |
|-------|-----|-----|-------|---------|
| ai1stseo-admin-metrics | metric_date | — | Dev 3 (Troy) | Daily aggregated metrics + white-label config |
| ai1stseo-api-logs | id | endpoint-index | Dev 3 (Troy) | API request logs + AI usage + attribution events + inference cache |
| ai1stseo-api-keys | key_hash | — | Dev 3 (Troy) | Developer API keys with scopes and rate limits |
| ai1stseo-email-leads | id | — | Dev 3 (Troy) | Email lead collection |

### Monitoring & Webhooks

| Table | PK | GSI | Owner | Purpose |
|-------|-----|-----|-------|---------|
| ai1stseo-webhooks | id | — | Dev 3 (Troy) | Webhooks + Slack/email notification subscriptions |
| ai1stseo-monitor | id | — | Monitor | Monitored sites + uptime checks + multi-site dashboard |
| ai1stseo-competitors | id | — | Dev 3 (Troy) | Tracked competitor domains |

### Backlink Intelligence

| Table | PK | GSI | Owner | Purpose |
|-------|-----|-----|-------|---------|
| ai1stseo-backlinks | id | domain-index | Dev 3 (Troy) | Domain scores, link gaps, citation probes, fingerprints, sentiment, mention scans, reports |
| ai1stseo-backlink-opportunities | id | — | Dev 3 (Troy) | Unified backlink opportunity queue |

## Record Types in ai1stseo-api-logs

This table stores multiple record types distinguished by the `type` or `log_type` field:

| log_type / type | Purpose |
|-----------------|---------|
| (default) | API request log (endpoint, method, status, response time) |
| ai_usage | AI inference call log (provider, model, tokens, cost, latency) |
| inference_cache | Cached AI response (24h TTL, keyed by prompt hash) |
| ai_referral | AI referral attribution event (source, landing page, session) |
| ai_conversion | Conversion event tied to AI referral session |

## Record Types in ai1stseo-backlinks

| type | Purpose |
|------|---------|
| domain_score | Domain authority score (0-100) with signal breakdown |
| link_gap | Link gap analysis result (your domain vs competitors) |
| citation_authority | LLM citation probe result (which domains AI models cite) |
| brand_sentiment | Brand sentiment probe (positive/neutral/negative + hallucination flags) |
| answer_fingerprint | AI response hash + cited domains for change detection |
| brief_citation_probe | Citation probe for content brief generator |
| competitor_alert | Competitor DA change detection |
| backlink_report | Comprehensive backlink report |
| backlink_report_download | White-label HTML report with S3 presigned URL |
| mention_scan | Google News + Reddit brand mention scan |
| internal_link_analysis | Site-wide internal link graph analysis |
| monitor_run | Scheduled backlink monitor execution summary |

## Multi-Tenancy

All records include `project_id` for account isolation:
- Default: `24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2`
- All queries should filter by project_id for multi-tenant support
- S3 document storage partitioned by user email path

## Backup & Recovery

- Point-in-time recovery: ENABLED on all 15 tables (35-day retention)
- RDS snapshot preserved: `ai1stseo-final-backup-20260401` (981 rows migrated)
- Data exported to `rds-backup/` as JSON files

---

## Legacy RDS Schema (ARCHIVED — DO NOT USE)

> The content below is the original RDS PostgreSQL schema, preserved for reference only.
> RDS was deleted on April 2, 2026. All data now lives in DynamoDB.
> Do NOT add `from database import` to any backend file.
- Security Group: `sg-0859c7cfcb529b8ff` (ai1stseo-rds-sg)
- Subnet Group: `ai1stseo-db-subnets` (us-east-1a, us-east-1b, us-east-1c)
- Backup Retention: 7 days

## How to Connect

From EC2:
```bash
psql -h ai1stseo-db.ca5mm2skodf2.us-east-1.rds.amazonaws.com -U ai1stseo_admin -d ai1stseo
```

From Python:
```python
import psycopg2

conn = psycopg2.connect(
    host="ai1stseo-db.ca5mm2skodf2.us-east-1.rds.amazonaws.com",
    database="ai1stseo",
    user="ai1stseo_admin",
    password="Ai1stSEO_db2026!",
    port=5432
)
```

## Schema Design

All tables include `project_id` for multi-tenancy isolation per the product spec.

### Core Tables

```sql
-- Projects / Accounts (multi-tenancy root)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_email VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_projects_owner ON projects(owner_email);

-- Users (mirrors Cognito, local reference)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cognito_sub VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'member',
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_project ON users(project_id);
CREATE INDEX idx_users_cognito ON users(cognito_sub);

-- Audits (scan results)
CREATE TABLE audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    overall_score INTEGER,
    technical_score INTEGER,
    onpage_score INTEGER,
    content_score INTEGER,
    mobile_score INTEGER,
    performance_score INTEGER,
    security_score INTEGER,
    social_score INTEGER,
    local_score INTEGER,
    geo_aeo_score INTEGER,
    total_checks INTEGER DEFAULT 0,
    passed_checks INTEGER DEFAULT 0,
    failed_checks INTEGER DEFAULT 0,
    warning_checks INTEGER DEFAULT 0,
    load_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

CREATE INDEX idx_audits_project ON audits(project_id);
CREATE INDEX idx_audits_url ON audits(url);
CREATE INDEX idx_audits_created ON audits(created_at DESC);

-- Individual audit check results
CREATE TABLE audit_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pass, fail, warning, info
    description TEXT,
    value TEXT,
    recommendation TEXT,
    impact VARCHAR(20)  -- high, medium, low
);

CREATE INDEX idx_checks_audit ON audit_checks(audit_id);
CREATE INDEX idx_checks_category ON audit_checks(category);
CREATE INDEX idx_checks_status ON audit_checks(status);
```

### Content Intelligence Tables (Dev 2 — Samar)

```sql
-- Content briefs
CREATE TABLE content_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    keyword VARCHAR(500) NOT NULL,
    content_type VARCHAR(50),  -- blog, faq, landing_page, comparison
    target_word_count INTEGER,
    brief_json JSONB,  -- full structured brief output
    seo_score INTEGER,
    aeo_score INTEGER,
    status VARCHAR(50) DEFAULT 'draft',  -- draft, generated, approved
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

CREATE INDEX idx_briefs_project ON content_briefs(project_id);
CREATE INDEX idx_briefs_keyword ON content_briefs(keyword);

-- Brief competitor analysis
CREATE TABLE brief_competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_id UUID NOT NULL REFERENCES content_briefs(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    domain VARCHAR(255),
    title TEXT,
    word_count INTEGER,
    heading_structure JSONB,
    content_json JSONB
);

CREATE INDEX idx_brief_comp_brief ON brief_competitors(brief_id);

-- Brief keywords
CREATE TABLE brief_keywords (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_id UUID NOT NULL REFERENCES content_briefs(id) ON DELETE CASCADE,
    keyword VARCHAR(500) NOT NULL,
    volume INTEGER,
    difficulty INTEGER,
    intent VARCHAR(50),
    placement VARCHAR(50)  -- title, h2, body, faq
);

CREATE INDEX idx_brief_kw_brief ON brief_keywords(brief_id);
```

### GEO / AI Citation Tables (Dev 1 — Deepthi)

```sql
-- GEO citation probes
CREATE TABLE geo_probes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(2048),
    brand_name VARCHAR(255),
    keyword VARCHAR(500) NOT NULL,
    ai_model VARCHAR(100) NOT NULL,  -- chatgpt, gemini, perplexity, bedrock
    cited BOOLEAN DEFAULT FALSE,
    citation_context TEXT,
    response_snippet TEXT,
    citation_rank INTEGER,            -- 1st, 2nd, 3rd source mentioned (from client research)
    sentiment VARCHAR(20),            -- positive, neutral, negative
    ai_platform VARCHAR(50),          -- claude, chatgpt, perplexity, gemini
    query_text TEXT,                   -- the actual query sent to the AI
    probe_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_geo_project ON geo_probes(project_id);
CREATE INDEX idx_geo_keyword ON geo_probes(keyword);
CREATE INDEX idx_geo_timestamp ON geo_probes(probe_timestamp DESC);

-- AI visibility scores over time
CREATE TABLE ai_visibility_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    visibility_score INTEGER,
    citation_count INTEGER DEFAULT 0,
    extractable_answers INTEGER DEFAULT 0,
    factual_density_score NUMERIC(5,2),
    schema_coverage_score NUMERIC(5,2),
    share_of_voice NUMERIC(5,2),
    competitor_citations INTEGER DEFAULT 0,
    ai_referral_sessions INTEGER DEFAULT 0,
    citation_sentiment_positive INTEGER DEFAULT 0,
    citation_sentiment_neutral INTEGER DEFAULT 0,
    citation_sentiment_negative INTEGER DEFAULT 0,
    measured_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_aiviz_project ON ai_visibility_history(project_id);
CREATE INDEX idx_aiviz_url ON ai_visibility_history(url);
CREATE INDEX idx_aiviz_measured ON ai_visibility_history(measured_at DESC);
```

### Monitoring Tables (Site Monitor)

```sql
-- Monitored sites
CREATE TABLE monitored_sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    check_interval_minutes INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    last_checked TIMESTAMP,
    last_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_monsites_project ON monitored_sites(project_id);

-- Uptime checks
CREATE TABLE uptime_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES monitored_sites(id) ON DELETE CASCADE,
    is_up BOOLEAN NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    checked_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_uptime_site ON uptime_checks(site_id);
CREATE INDEX idx_uptime_checked ON uptime_checks(checked_at DESC);

-- Content change history
CREATE TABLE content_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES monitored_sites(id) ON DELETE CASCADE,
    change_type VARCHAR(50),  -- title, meta, heading, content, schema
    old_value TEXT,
    new_value TEXT,
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_content_site ON content_changes(site_id);

-- Report subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    channels TEXT[] DEFAULT '{}',  -- email, slack, whatsapp, telegram, discord
    frequency VARCHAR(20) DEFAULT 'daily',
    sites TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subs_user ON subscriptions(user_id);
CREATE INDEX idx_subs_project ON subscriptions(project_id);
```

### Reports Table

```sql
-- Generated reports
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL,  -- audit, brief, monitoring, competitor
    title VARCHAR(500),
    data JSONB NOT NULL,
    format VARCHAR(20) DEFAULT 'json',  -- json, html, pdf
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

CREATE INDEX idx_reports_project ON reports(project_id);
CREATE INDEX idx_reports_type ON reports(report_type);
CREATE INDEX idx_reports_created ON reports(created_at DESC);
```

### Scan Error Tracking Table

```sql
-- Scan errors logged by EventBridge scheduled scans and daily reports
CREATE TABLE scan_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(2048),
    scan_type VARCHAR(50) NOT NULL,       -- scheduled_scan, daily_report_scan
    error_message TEXT NOT NULL,
    source VARCHAR(50) DEFAULT 'scheduled', -- scheduled, daily_report, manual
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scan_errors_project ON scan_errors(project_id);
CREATE INDEX idx_scan_errors_created ON scan_errors(created_at DESC);
CREATE INDEX idx_scan_errors_resolved ON scan_errors(resolved);
```

### Social & Integrations Tables (Dev 4 — Tabasum)

```sql
-- Scheduled social posts
CREATE TABLE social_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    platforms TEXT[] DEFAULT '{}',  -- linkedin, twitter, facebook, instagram
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'draft',  -- draft, scheduled, published, failed
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

CREATE INDEX idx_social_project ON social_posts(project_id);
CREATE INDEX idx_social_status ON social_posts(status);
CREATE INDEX idx_social_scheduled ON social_posts(scheduled_at);
```

### Competitor Benchmarking Tables (Dev 3 — Troy)

```sql
-- Competitor domains
CREATE TABLE competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL,
    label VARCHAR(255),
    added_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_competitors_project ON competitors(project_id);

-- Competitor benchmark snapshots
CREATE TABLE benchmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id UUID NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    seo_score INTEGER,
    ai_visibility_score INTEGER,
    keyword_overlap JSONB,
    domain_authority INTEGER,
    measured_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_benchmarks_competitor ON benchmarks(competitor_id);
CREATE INDEX idx_benchmarks_measured ON benchmarks(measured_at DESC);
```

### AI Referral Traffic (from client GEO research — TXT.rtf)

```sql
-- AI referral traffic tracking (maps to research doc's measurement framework)
CREATE TABLE ai_referral_traffic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    referral_source VARCHAR(100) NOT NULL,  -- chatgpt.com, claude.ai, perplexity.ai, etc.
    session_count INTEGER DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    avg_time_on_site_seconds INTEGER,
    measured_date DATE DEFAULT CURRENT_DATE
);

CREATE INDEX idx_airef_project ON ai_referral_traffic(project_id);
CREATE INDEX idx_airef_source ON ai_referral_traffic(referral_source);
CREATE INDEX idx_airef_date ON ai_referral_traffic(measured_date DESC);
```

### Content Citation Readiness Scores (from client GEO research — TXT.rtf)

```sql
-- Scores how "citation-ready" a page is based on the Princeton/Georgia Tech GEO factors
CREATE TABLE content_citation_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    answer_first_structure BOOLEAN DEFAULT FALSE,   -- does content lead with direct answers?
    citation_count INTEGER DEFAULT 0,               -- # of authoritative citations in content
    statistics_count INTEGER DEFAULT 0,             -- # of specific stats with sources
    expert_quotes_count INTEGER DEFAULT 0,          -- # of attributed expert quotes
    faq_section_present BOOLEAN DEFAULT FALSE,      -- has FAQ section?
    schema_types_found TEXT[] DEFAULT '{}',          -- Article, FAQ, HowTo, etc.
    author_bio_present BOOLEAN DEFAULT FALSE,       -- E-E-A-T: author credentials visible?
    eeat_score INTEGER,                             -- composite E-E-A-T score
    paragraph_avg_words INTEGER,                    -- target: 50-75 words per paragraph
    content_freshness_days INTEGER,                 -- days since last update
    overall_citation_readiness INTEGER,             -- composite score 0-100
    scored_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_citscores_audit ON content_citation_scores(audit_id);
```

## Table Summary

| Table | Owner | Purpose |
|-------|-------|---------|
| projects | Core | Multi-tenancy root, account isolation |
| users | Core | User records mirroring Cognito |
| audits | Dev 3 (Troy) | SEO audit scan results |
| audit_checks | Dev 3 (Troy) | Individual check results per audit |
| content_briefs | Dev 2 (Samar) | AI content brief generator output |
| brief_competitors | Dev 2 (Samar) | SERP competitor analysis per brief |
| brief_keywords | Dev 2 (Samar) | Keyword clusters per brief |
| geo_probes | Dev 1 (Deepthi) | AI citation probe results (with rank, sentiment, platform) |
| ai_visibility_history | Dev 1 (Deepthi) | AI visibility scores over time (with share of voice, referral sessions, sentiment breakdown) |
| ai_referral_traffic | Dev 3 (Troy) | Traffic from AI platforms (ChatGPT, Claude, Perplexity referrals) |
| content_citation_scores | Dev 1 (Deepthi) / Dev 3 (Troy) | Citation readiness scoring per page (E-E-A-T, answer structure, freshness) |
| monitored_sites | Monitor | Sites being tracked |
| uptime_checks | Monitor | Uptime check history |
| content_changes | Monitor | Content change detection log |
| subscriptions | Monitor | Report delivery subscriptions |
| reports | Core | Generated reports (all types) |
| scan_errors | Monitor | Scan failure tracking for EventBridge scheduled scans and daily reports |
| social_posts | Dev 4 (Tabasum) | Scheduled social media posts |
| competitors | Dev 3 (Troy) | Competitor domains to benchmark |
| benchmarks | Dev 3 (Troy) | Competitor benchmark snapshots |

## Notes

- All tables use UUID primary keys for security (no sequential IDs exposed)
- All queries MUST filter by `project_id` for multi-tenancy isolation
- JSONB columns used for flexible structured data (briefs, reports, benchmarks)
- PostgreSQL arrays (`TEXT[]`) used for channels and platforms lists
- Indexes on foreign keys and common query patterns
- 7-day automated backups enabled on RDS
- Resize path: db.t3.micro → db.t3.small → db.t3.medium as usage grows
