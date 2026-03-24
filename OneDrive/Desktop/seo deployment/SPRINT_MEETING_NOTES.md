# AI 1st SEO — Sprint Meeting Notes
## Week of March 23, 2026

---

## Pre-Meeting Status Check

### Dev 1 — Deepthi (GEO/AI Engine): ✅ On track
- Delivered full GEO probe engine: multi-provider citation probing (Nova/Claude/OpenAI/Gemini), batch probes, cross-model comparison, site/URL detection, visibility trends, scheduled monitoring
- Brand resolver with keyword suggestions and domain probing
- AEO analyzer, AI ranking recommendations, content generator, AI chatbot with sessions
- Multi-provider LLM service layer
- All wired into app.py and live on App Runner

### Dev 2 — Samarveer (Content Intelligence): ✅ Delivered today (Mar 23)
- `/api/content-brief` endpoint — SERP scraping (top 5 Google results), heading/word count/schema extraction, LLM-powered brief generation with SERP-data fallback
- Still upcoming (Phase 2): content scoring engine, content repurposing, TF-IDF analysis

### Dev 3 — Troy (Data/Infrastructure): ✅ Done + extra
- Amplify migration complete (Phases 0-3): Lambda + API Gateway for seo-backend and site-monitor
- RDS PostgreSQL schema deployed with all tables
- Site monitor improvements: Cognito auth, RDS subscriptions, response caching, deep-scan API, scan history API, async scans, EventBridge scheduling (every 6h scans + daily reports)
- Dual-path AI inference (Nova Lite + Ollama fallback)
- **BLOCKED**: IAM permissions from Gurbachan for Bedrock/SES/SecretsManager on Lambda roles

### Dev 4 — Tabasum (Social & Integrations): ⚠️ Blocked
- No commits to shared repo this week
- **ISSUE**: Getting some Cognito verification codes forwarded but not others — intermittent email delivery problem preventing her from testing auth flows and building on top of them
- Assigned work: social media scheduler, social signal tracking, CMS integrations
- Need to resolve the verification code issue before she can make progress

### Dev 5 — Amira (Frontend & UX): ✅ On track
- Built dashboard.html with score widgets, category breakdown, audit history, light/dark mode
- Created logout.html, homepage login redirect, auth.js integration, CSS theming
- Created PROJECT-STATUS.md for team context sharing
- Working in separate repo (robinnic/seo-deployment), deploying to S3/CloudFront
- In progress: React + TypeScript + Vite migration of dashboard

---

## Loose Ends to Resolve in Meeting

### 1. Tabasum's Verification Code Issue
- **Problem**: Cognito verification emails are inconsistently delivered — some codes arrive, others don't
- **Possible causes**:
  - SES sending rate/throttling (unlikely — we have 50k/day production access)
  - Emails landing in spam/junk folder
  - ImprovMX forwarding dropping some messages (ImprovMX handles receiving/forwarding for @ai1stseo.com)
  - Cognito DEVELOPER mode email config issue
- **Action**: Check SES bounce/complaint dashboard, verify ImprovMX forwarding rules, test with a non-forwarded email address (e.g. direct Gmail)

### 2. IAM Permissions for Lambda (Gurbachan)
- Email sent, status doc shared in group chat
- Both `lambda-basic-execution` and `seo-analyzer-lambda-role` need: `bedrock:InvokeModel`, `secretsmanager:GetSecretValue`, `ses:SendEmail`/`ses:SendRawEmail`
- Everything else works — this is the last blocker for DNS cutover

### 3. App Runner vs Lambda
- Deepthi and Samarveer's code runs on App Runner (auto-deploys from GitHub main)
- Troy's seo-backend and site-monitor are on Lambda (manual deploy via S3 zip)
- Both point to the same RDS database
- No conflict, but team should be aware of the two deployment paths

---

## Task Assignments for This Week (to be filled in during meeting)

### Dev 1 — Deepthi
- [ ] _TBD_

### Dev 2 — Samarveer
- [ ] _TBD_

### Dev 3 — Troy
- [ ] _TBD_

### Dev 4 — Tabasum
- [ ] _TBD_ (resolve verification code issue first)

### Dev 5 — Amira
- [ ] _TBD_

---

## Notes
_Space for meeting discussion notes_
