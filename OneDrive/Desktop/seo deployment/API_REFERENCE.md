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

## Infrastructure

| Component | Detail |
|-----------|--------|
| Runtime | Python 3.11, Flask, AWS Lambda via Mangum |
| Database | Amazon DynamoDB (12 tables, PAY_PER_REQUEST) |
| Auth | Amazon Cognito (`us-east-1_DVvth47zH`) |
| Email | Amazon SES (`no-reply@ai1stseo.com`) |
| Frontend | S3 + CloudFront (`ai1stseo.com`) |
| API Gateway | `cwb0hb27bf` with per-developer Lambda routing |
| AI Models | Bedrock Nova Lite (primary) + Ollama qwen3:30b (fallback) |
| Monitoring | Site monitor on Tailscale server (`100.108.196.117:8888`) |
| Agent | OpenClaw Gateway on Tailscale server (port 18789) |
