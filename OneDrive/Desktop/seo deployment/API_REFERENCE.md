# AI 1st SEO — API Reference

**Base URL:** `https://api.ai1stseo.com`
**Auth:** Bearer token (Cognito JWT) or API key (`ai1st_` prefix)
**Database:** Amazon DynamoDB (serverless)
**Runtime:** AWS Lambda (Python 3.11)

---

## Authentication

All authenticated endpoints accept either:
- `Authorization: Bearer <cognito_jwt_token>` (from login)
- `Authorization: Bearer ai1st_<api_key>` (developer API key)
- `X-API-Key: ai1st_<api_key>` (alternative header)

### POST /api/auth/signup
Register a new user.
```json
Request:  {"email": "user@example.com", "password": "Pass123!", "name": "User Name"}
Response: {"status": "success", "message": "Verification code sent to email"}
```

### POST /api/auth/verify
Verify email with confirmation code.
```json
Request:  {"email": "user@example.com", "code": "123456"}
Response: {"status": "success", "message": "Email verified"}
```

### POST /api/auth/resend-code
Resend verification code.
```json
Request:  {"email": "user@example.com"}
Response: {"status": "success"}
```

### POST /api/auth/login
Authenticate and receive JWT tokens.
```json
Request:  {"email": "user@example.com", "password": "Pass123!"}
Response: {"status": "success", "tokens": {"accessToken": "...", "idToken": "...", "refreshToken": "..."}, "user": {"email": "...", "name": "...", "role": "member"}}
```

### POST /api/auth/refresh
Refresh an expired access token.
```json
Request:  {"refreshToken": "..."}
Response: {"status": "success", "tokens": {"accessToken": "...", "idToken": "..."}}
```

### POST /api/auth/forgot-password
Initiate password reset.
```json
Request:  {"email": "user@example.com"}
Response: {"status": "success", "message": "Reset code sent"}
```

### POST /api/auth/reset-password
Complete password reset.
```json
Request:  {"email": "user@example.com", "code": "123456", "newPassword": "NewPass123!"}
Response: {"status": "success"}
```

### GET /api/auth/me *(auth required)*
Get current user profile.
```json
Response: {"status": "success", "email": "...", "name": "...", "role": "admin"}
```

### DELETE /api/auth/delete-account *(auth required)*
Delete the authenticated user's account.

---

## SEO Analysis

### POST /api/analyze
Run a comprehensive SEO audit (200+ checks across 10 categories).
```json
Request:  {"url": "https://example.com"}
Response: {"url": "...", "overallScore": 75, "categories": {...}, "checks": [...], "totalChecks": 200, "totalPassed": 150}
```
Categories: technical, onpage, content, mobile, performance, security, social, local, geo, citationgap

### GET /api/health
Service health check (no auth).
```json
Response: {"status": "ok", "totalChecks": 200, "categories": {...}}
```

### POST /api/ai-recommendations *(auth required)*
Get AI-powered SEO recommendations using LLM.
```json
Request:  {"url": "https://example.com", "scanResults": {...}}
Response: {"status": "success", "recommendations": "..."}
```

### POST /api/content-brief
Generate an AI content brief for a keyword.
```json
Request:  {"keyword": "best seo tools", "content_type": "blog"}
Response: {"status": "success", "brief": {...}}
```

### POST /api/content-score
Score a URL for readability, SEO, and AEO.
```json
Request:  {"url": "https://example.com"}
Response: {"readability": 66.4, "seo": 40.0, "aeo": 0.0, "overall": 32.6}
```

### GET /api/content-briefs
List saved content briefs. Query: `?keyword=seo`
```json
Response: {"briefs": [...]}
```

---

## GEO / AI Citation Probing

### POST /api/geo-probe
Run a single GEO citation probe.
```json
Request:  {"keyword": "best seo tools", "ai_model": "chatgpt", "url": "https://example.com", "brand_name": "Example"}
Response: {"status": "success", "probe": {...}}
```

### GET /api/geo-probe/models
List available AI models for probing (no auth).
```json
Response: {"models": ["chatgpt", "gemini", "perplexity", "claude", "bedrock"]}
```

### POST /api/geo-probe/batch
Run probes across multiple models simultaneously.
```json
Request:  {"keyword": "best seo tools", "url": "https://example.com", "models": ["chatgpt", "gemini"]}
Response: {"status": "success", "results": [...]}
```

### GET /api/geo-probe/history
Get probe history. Query: `?keyword=seo&limit=50`
```json
Response: {"status": "success", "probes": [...]}
```

### POST /api/geo-probe/compare
Compare citation across models.
```json
Request:  {"keyword": "best seo tools", "models": ["chatgpt", "gemini"]}
Response: {"status": "success", "comparison": {...}}
```

### GET /api/geo-probe/trend
Get citation trend over time. Query: `?keyword=seo`

### POST /api/geo-probe/schedule
Schedule recurring probes.

### POST /api/geo-probe/site
Run site-wide GEO analysis.

### POST /api/aeo/analyze
Run Answer Engine Optimization analysis.
```json
Request:  {"url": "https://example.com"}
Response: {"status": "success", "analysis": {...}}
```

### POST /api/brand/resolve
Resolve a brand name to its domain.
```json
Request:  {"brand": "AI 1st SEO"}
Response: {"status": "success", "domain": "ai1stseo.com"}
```

### POST /api/ai/citation-probe
Deep AI citation probe with LLM.

### POST /api/ai/geo-monitor
Monitor GEO visibility over time.

### POST /api/ai/ranking-recommendations
Get AI-powered ranking improvement suggestions.

---

## Content Generation

### POST /api/content/generate
Generate AI-optimized content.
```json
Request:  {"topic": "SEO best practices", "type": "faq", "keywords": ["seo", "optimization"]}
Response: {"status": "success", "content": "..."}
```

---

## AI Chatbot

### POST /api/chatbot/session
Create a new chat session.
```json
Response: {"status": "success", "session_id": "uuid"}
```

### POST /api/chatbot/chat
Send a message in a session.
```json
Request:  {"session_id": "uuid", "message": "How do I improve my SEO?"}
Response: {"status": "success", "response": "..."}
```

### GET /api/chatbot/history/:session_id
Get chat history for a session.

### GET /api/chatbot/sessions
List all chat sessions.

### GET /api/llm/providers
List available LLM providers and models.

### POST /api/llm/citation-probe
Run a citation probe via LLM.

---

## Shared Data API *(auth required)*

All data endpoints use DynamoDB. Responses include `{status, ...data}`.

### Audits
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/data/audits` | Create audit `{url, overall_score, checks, ...}` |
| GET | `/api/data/audits` | List audits. Query: `?url=example.com&limit=20` |
| GET | `/api/data/audits/:id` | Get single audit |

### GEO Probes
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/data/geo-probes` | Create probe `{keyword, ai_model, cited, ...}` |
| GET | `/api/data/geo-probes` | List probes. Query: `?keyword=seo&limit=50` |

### Content Briefs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/data/content-briefs` | Create brief `{keyword, content_type, ...}` |
| GET | `/api/data/content-briefs` | List briefs |
| GET | `/api/data/content-briefs/:id` | Get single brief |

### Social Posts
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/data/social-posts` | Create post `{content, platforms, scheduled_at}` |
| GET | `/api/data/social-posts` | List posts |
| PUT | `/api/data/social-posts/:id` | Update post |
| DELETE | `/api/data/social-posts/:id` | Delete post |

### Competitors
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/data/competitors` | Add competitor `{domain, label}` |
| GET | `/api/data/competitors` | List competitors |
| DELETE | `/api/data/competitors/:id` | Remove competitor |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/data/reports` | Create report `{report_type, title, data}` |
| GET | `/api/data/reports` | List reports |

---

## Webhooks

### POST /api/webhooks *(auth required)*
Register a webhook URL.
```json
Request:  {"url": "https://your-server.com/hook", "events": ["audit.created", "*"], "secret": "optional-hmac-secret"}
Response: {"status": "success", "id": "uuid", "events": [...]}
```

### GET /api/webhooks *(auth required)*
List registered webhooks.

### DELETE /api/webhooks/:id *(auth required)*
Remove a webhook.

### POST /api/webhooks/:id/toggle *(auth required)*
Enable/disable a webhook.

### GET /api/webhooks/events *(no auth)*
List all valid event types.
```json
Response: {"events": ["*", "audit.created", "competitor.created", "content.changed", "content_brief.created", "geo_probe.created", "report.created", "social_post.created", "social_post.updated", "uptime.down", ...]}
```

Webhook deliveries include HMAC signature in `X-Webhook-Signature` header if a secret was provided.

---

## Developer API Keys *(auth required)*

### POST /api/keys
Generate a new API key (shown once).
```json
Request:  {"label": "My App", "scopes": ["read", "write"], "rate_limit_per_hour": 100}
Response: {"status": "success", "key": "ai1st_abc123...", "prefix": "ai1st_abc123", "warning": "Save this key now."}
```

### GET /api/keys
List API keys (prefix only).

### DELETE /api/keys/:id
Revoke an API key.

### POST /api/keys/:id/toggle
Enable/disable an API key.

---

## Admin Dashboard *(admin role required)*

### GET /api/admin/overview
Top-level platform stats (users, scans, scores).

### GET /api/admin/users
Paginated user list. Query: `?limit=50&offset=0`

### PUT /api/admin/users/:id/role
Set user role. `{"role": "admin"}` or `{"role": "member"}`

### GET /api/admin/usage
Scan volume and trends. Query: `?days=30`

### GET /api/admin/ai-costs
AI provider usage and estimated costs. Query: `?days=30`

### GET /api/admin/metrics
Historical daily metrics from aggregation.

### GET /api/admin/errors
Recent scan errors.

### GET /api/admin/health
System health (uptime, response times, database status).

### GET /api/admin/requests
API request log (top endpoints, hourly volume). Query: `?hours=24`

### GET /api/admin/me *(auth required, not admin)*
Current user's role — used by frontend to decide admin access.

### POST /api/admin/documents *(auth required)*
Upload a document. Multipart/form-data with `file` field + optional `title`, `description`.
```
Response: {"status": "success", "id": "uuid", "filename": "research.pdf"}
```

### GET /api/admin/documents *(auth required)*
List documents. Query: `?uploader=email@example.com` to filter by developer.
```json
Response: {"status": "success", "documents": [...], "count": 5}
```

### GET /api/admin/documents/:id/download *(auth required)*
Get a presigned S3 download URL (valid 15 minutes).
```json
Response: {"status": "success", "url": "https://s3.amazonaws.com/...", "filename": "research.pdf"}
```

### DELETE /api/admin/documents/:id *(admin only)*
Delete a document and its S3 file.

### GET /api/admin/api-usage *(admin only)*
API key usage analytics — per-key request counts, rate limits, last used.
```json
Response: {"status": "success", "keys": [{"prefix": "ai1st_abc", "label": "My App", "requests_this_hour": 12, "rate_limit_per_hour": 100, ...}], "count": 3}
```

### GET /api/admin/api-usage/logs *(admin only)*
Request log analytics with endpoint filtering. Query: `?endpoint=/api/analyze&limit=100`
```json
Response: {"status": "success", "logs": [...], "top_endpoints": [{"endpoint": "/api/analyze", "count": 45}], "total": 200}
```

### GET /api/admin/system-status *(auth required)*
Real-time health check of all platform services (DynamoDB, Cognito, SES, S3, table counts).
```json
Response: {"status": "success", "overall": "healthy", "healthy_count": 5, "total_count": 5, "services": {"dynamodb": {"status": "healthy", "latency_ms": 45}, "cognito": {"status": "healthy"}, ...}}
```

### GET /api/admin/audit-history *(auth required)*
Browse all SEO audits with search/filter. Query: `?url=example.com&min_score=50&max_score=100&limit=50`
```json
Response: {"status": "success", "audits": [...], "total": 14, "filters": {...}}
```

### GET /api/admin/white-label *(auth required)*
Get current white-label branding configuration.
```json
Response: {"status": "success", "config": {"brand_name": "AI 1st SEO", "primary_color": "#00d4ff", "logo_url": "", ...}}
```

### PUT /api/admin/white-label *(admin only)*
Update white-label configuration.
```json
Request:  {"brand_name": "My Agency", "primary_color": "#ff6600", "support_email": "help@agency.com"}
Response: {"status": "success", "config": {...}}
```

---

## Email Lead Collection

### POST /api/collect-email *(no auth — public)*
Collect email from PDF download gate.
```json
Request:  {"email": "user@example.com", "source": "pdf_download", "page_url": "https://ai1stseo.com/audit", "report_type": "seo_audit"}
Response: {"status": "success", "message": "Email collected"}
```

---

## Contact Form

### POST /api/contact *(no auth — public)*
Send a contact form message via SES.
```json
Request:  {"name": "User Name", "email": "user@example.com", "message": "Hello..."}
Response: {"status": "success", "message": "Message sent"}
```

---

## Investor Inquiry

### POST /api/invest *(no auth — public)*
Send an investor inquiry via SES to gurbachan@ai1stseo.com.
```json
Request:  {"name": "Investor Name", "email": "investor@fund.com", "message": "Interested in...", "organization": "Fund LLC", "interest": "seed"}
Response: {"status": "success", "message": "Inquiry sent"}
```

---

## Content Freshness

### POST /api/content-freshness *(no auth)*
Record a content update timestamp for AI ranking freshness signals.
```json
Request:  {"url": "https://ai1stseo.com/page", "update_type": "content_refresh", "sections": ["faq", "pricing"]}
Response: {"status": "success", "id": "uuid", "timestamp": "2026-04-28T..."}
```

### GET /api/content-freshness *(no auth)*
Get content freshness history. Query: `?url=https://ai1stseo.com/page`
```json
Response: {"status": "success", "updates": [...]}
```

---

## Notification Subscriptions *(auth required)*

### POST /api/notifications/subscribe
Subscribe to event notifications via Slack or email.
```json
Request:  {"channel": "slack", "target": "https://hooks.slack.com/services/...", "events": ["audit.created", "*"]}
Request:  {"channel": "email", "target": "user@example.com", "events": ["uptime.down"]}
Response: {"status": "success", "id": "uuid", "channel": "slack"}
```

### GET /api/notifications
List notification subscriptions.
```json
Response: {"status": "success", "notifications": [...]}
```

---

## Backlink Analysis *(auth required)*

### POST /api/backlinks/score
Score a domain's authority (0-100) using 10+ real-time signals.
```json
Request:  {"domain": "example.com"}
Response: {"status": "success", "domain": "example.com", "da_score": 72, "signals": {"https": true, "response_time_ms": 340, "schema_markup": 3, ...}}
```

### POST /api/backlinks/analyze-toxic
Classify backlinks as potentially toxic.
```json
Request:  {"backlinks": [{"source_url": "https://spam.xyz/page", "anchor_text": "buy cheap seo", "nofollow": false}]}
Response: {"status": "success", "total": 1, "toxic_count": 1, "toxic_percentage": 100.0, "backlinks": [{...}]}
```

### POST /api/backlinks/link-gap
Compare your domain against competitors to find backlink gaps.
```json
Request:  {"domain": "ai1stseo.com", "competitors": ["semrush.com", "ahrefs.com"]}
Response: {"status": "success", "your_domain": {...}, "competitors": [...], "gaps": [...], "total_gaps": 2}
```

### POST /api/backlinks/citation-authority
Probe AI models to discover which domains they cite for a topic (novel — no competitor has this).
```json
Request:  {"queries": ["What are the best SEO tools?", "How to improve search rankings?"], "niche": "SEO"}
Response: {"status": "success", "total_domains_cited": 15, "top_cited": [{"domain": "moz.com", "citation_count": 4, "citation_frequency": 40.0}], "probes": [...]}
```

### GET /api/backlinks/citation-scores
Get stored citation authority scores by niche. Query: `?niche=SEO`

### POST /api/backlinks/velocity
Detect link velocity anomalies for a domain.
```json
Request:  {"domain": "competitor.com"}
Response: {"status": "success", "domain": "competitor.com", "trend": "improving", "anomaly": false, "total_change": 8}
```

### POST /api/backlinks/broken-links
Scan a page for broken outbound links (reclaim opportunities).
```json
Request:  {"url": "https://high-da-site.com/resources"}
Response: {"status": "success", "links_checked": 35, "broken_count": 3, "broken_links": [{...}]}
```

### POST /api/backlinks/wikipedia-gaps
Find dead citations in Wikipedia articles as replacement opportunities.
```json
Request:  {"topic": "search engine optimization"}
Response: {"status": "success", "articles_checked": 5, "gaps_found": 2, "gaps": [{...}]}
```

### POST /api/backlinks/competitor-alerts
Check if a competitor gained or lost significant DA.
```json
Request:  {"competitor": "competitor.com", "your_domain": "ai1stseo.com"}
Response: {"status": "success", "competitor": "competitor.com", "current_da": 65, "da_change": 8, "alert_type": "competitor_improving"}
```

### POST /api/backlinks/decay-predict
Predict which backlinks are at risk of disappearing.
```json
Request:  {"domain": "ai1stseo.com"}
Response: {"status": "success", "at_risk_count": 3, "at_risk": [{...}]}
```

### GET /api/backlinks/history
Browse backlink analysis history. Query: `?type=domain_score&domain=example.com&limit=50`

### GET /api/backlinks/opportunities
List all backlink opportunities ranked by priority.

### POST /api/backlinks/opportunities
Manually add a backlink opportunity.

### GET /api/backlinks/priority-queue
Unified opportunity queue with composite scoring across all sources.

### POST /api/backlinks/report
Generate a comprehensive backlink report for a domain.
```json
Request:  {"domain": "ai1stseo.com", "competitors": ["semrush.com"]}
Response: {"status": "success", "id": "uuid", "report": {"da_score": 45, "signals": {...}, "competitors": [...], "opportunities_count": 12}}
```

---

## Infrastructure

| Component | Detail |
|-----------|--------|
| Runtime | Python 3.11, Flask, AWS Lambda via Mangum |
| Database | Amazon DynamoDB (15 tables, PAY_PER_REQUEST) |
| Auth | Amazon Cognito (`us-east-1_DVvth47zH`) |
| Email | Amazon SES (`no-reply@ai1stseo.com`) |
| Frontend | S3 + CloudFront (`ai1stseo.com`, distribution `E16GYTIVXY9IOU`) |
| API Gateway | `cwb0hb27bf` with per-developer Lambda routing |
| AI Models | Bedrock Nova Lite (primary) + Ollama tiered: 8B fast, 30B standard, 235B deep |
| Monitoring | Site monitor on Tailscale server (`100.108.196.118:8888`) |
| Agent | OpenClaw Gateway on Tailscale server (port 18789) |
| Deploy bucket | S3 `ai1stseo-lambda-deploy` |
| Doc storage | S3 `ai1stseo-documents` |

### DynamoDB Tables
| Table | Purpose |
|-------|---------|
| ai1stseo-users | User accounts + roles (GSI: email-index) |
| ai1stseo-audits | SEO audit results (GSI: url-index) |
| ai1stseo-geo-probes | GEO citation probes (GSI: keyword-index) |
| ai1stseo-content-briefs | Content briefs |
| ai1stseo-social-posts | Social media posts |
| ai1stseo-admin-metrics | Daily aggregated metrics + white-label config |
| ai1stseo-api-logs | API request logs (GSI: endpoint-index) |
| ai1stseo-webhooks | Webhooks + notification subscriptions |
| ai1stseo-api-keys | Developer API keys |
| ai1stseo-competitors | Tracked competitors |
| ai1stseo-monitor | Monitored sites + uptime checks |
| ai1stseo-email-leads | Email lead collection |
| ai1stseo-documents | Document repository metadata |
| ai1stseo-backlinks | Backlink scores, analyses, reports (GSI: domain-index) |
| ai1stseo-backlink-opportunities | Backlink opportunity queue |
