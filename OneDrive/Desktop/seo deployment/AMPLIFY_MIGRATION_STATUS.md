# AI 1st SEO — Amplify Migration Status
## March 21, 2026

This document provides full context on the EC2 → Amplify/Lambda migration so all team members and their agents can understand the current state of the infrastructure.

---

## Why We're Migrating

We're moving from a single EC2 instance (t3.medium, ~$30/mo) to AWS serverless (Amplify Hosting + Lambda + API Gateway). Benefits:
- Cost drops to ~$5-15/mo (Lambda free tier, Nova Lite pennies/month, RDS free tier)
- No server maintenance, no Nginx, no Let's Encrypt renewals
- Auto-scaling, zero-downtime deploys via GitHub push
- Each service is independently deployable

This was approved by Gurbachan with the following guidance:
- Use Nova Lite ($0.06/1M tokens) as primary AI, not Claude
- Use `ollama.sageaios.com` (Gurbachan's homelab, free) as AI fallback
- Keep RDS PostgreSQL (Troy's decision)
- Launch without provisioned concurrency — cold starts are acceptable
- Realistic cost: $5-15/mo, not $30-65

---

## Current Architecture (EC2 — Still Running)

All 6 services run on EC2 `i-0d59b5c1a433f0255` (t3.medium, IP `54.226.251.216`) via PM2 + Nginx reverse proxy + Let's Encrypt SSL.

| PM2 Service | Port | Subdomain | Stack | Owner |
|---|---|---|---|---|
| seo-backend | 5000 | api.ai1stseo.com | Python/Flask | Troy |
| site-monitor | 8888 | monitor.ai1stseo.com | Python/Flask | Troy |
| seo-audit-tool | 8080 | seoaudit.ai1stseo.com | Node.js | Team |
| seo-analysis | 3000 | seoanalysis.ai1stseo.com | Python/Flask | Team |
| automation-hub | 3001 | automationhub.ai1stseo.com | Node.js | Team |
| ai-doc-summarizer | 8005 | docsummarizer.ai1stseo.com | Python/FastAPI | Team |

Supporting infra: RDS PostgreSQL (`ai1stseo-db`), Cognito (`us-east-1_DVvth47zH`), SES (production, 50k/day), Route 53 DNS.

---

## What Has Been Migrated (Phases 0-3)

### Phase 0: Safety — COMPLETE
- AMI snapshot: `ami-004b9dfb15994307b`
- PM2 configs saved, Nginx backed up to `/home/ec2-user/nginx-backup`
- RDS backups verified: 7-day retention
- All endpoints health-checked: all 200 OK
- Rollback plan: restore AMI, point DNS back to EC2. ~10 minutes.

### Phase 1: Static Frontend → Amplify Hosting — COMPLETE
- Amplify app: `d30a3tvkvr1a51`
- URL: `https://main.d30a3tvkvr1a51.amplifyapp.com`
- Files deployed: `index.html`, `analyze.html`, `audit.html`, `guides.html`, `assets/*`
- DNS not switched yet — `ai1stseo.com` still points to EC2

### Phase 2: seo-backend → Lambda — COMPLETE
- Lambda function: `ai1stseo-backend` (Python 3.11, 1024MB, 300s timeout)
- Code package: `s3://ai1stseo-lambda-deploy/seo-backend-lambda.zip` (26MB)
- API Gateway HTTP API: `cwb0hb27bf`
- Live URL: `https://cwb0hb27bf.execute-api.us-east-1.amazonaws.com`
- Custom domain ready: `api.ai1stseo.com` → `d-padfgc44dk.execute-api.us-east-1.amazonaws.com`
- Lambda role: `lambda-basic-execution`
- CORS configured for ai1stseo.com, www, and Amplify domain
- Tested: 231-check SEO analysis ✅, Cognito auth ✅, health endpoint ✅

**Technical note:** Flask is WSGI but Mangum 0.17+ is ASGI-only. We wrote a minimal WSGI-to-ASGI shim class (`_FlaskAsgi`) that bridges Flask to Mangum on Lambda. This pattern is reused across all Python/Flask services.

### Phase 3: site-monitor → Lambda — COMPLETE
- Lambda function: `seo-analyzer-api` (repurposed existing function, Python 3.11, 1024MB, 300s timeout)
- Code package: `s3://ai1stseo-lambda-deploy/site-monitor-lambda.zip` (13MB)
- Lambda wrapper: `web_ui_lambda.py` imports the Flask app and applies the same WSGI-to-ASGI shim
- API Gateway HTTP API: `w2duao5bg0`
- Live URL: `https://w2duao5bg0.execute-api.us-east-1.amazonaws.com`
- Custom domain ready: `monitor.ai1stseo.com` → `d-o6a36rgu1d.execute-api.us-east-1.amazonaws.com`
- Lambda role: `seo-analyzer-lambda-role`
- Tested: scan ✅, uptime ✅, health ✅

---

## What Has NOT Been Migrated (Phases 4-5) — Deferred

The following services remain on EC2 and are owned by other team members. We are not touching them.

| Service | Subdomain | Stack | Status |
|---|---|---|---|
| seo-audit-tool | seoaudit.ai1stseo.com | Node.js | Stays on EC2 |
| seo-analysis | seoanalysis.ai1stseo.com | Python/Flask | Stays on EC2 |
| automation-hub | automationhub.ai1stseo.com | Node.js | Stays on EC2 |
| ai-doc-summarizer | docsummarizer.ai1stseo.com | Python/FastAPI | Stays on EC2 |

API Gateway custom domains have been pre-created for these services so team members can migrate when ready:

| Domain | API Gateway Target |
|---|---|
| seoaudit.ai1stseo.com | d-gb39s1cajf.execute-api.us-east-1.amazonaws.com |
| seoanalysis.ai1stseo.com | d-2jl900y7pd.execute-api.us-east-1.amazonaws.com |
| automationhub.ai1stseo.com | d-c96c1crynj.execute-api.us-east-1.amazonaws.com |
| docsummarizer.ai1stseo.com | d-3k7jpgl2qj.execute-api.us-east-1.amazonaws.com |

**EC2 must stay running until all services are migrated.**

---

## What's Blocking Completion

Troy's SSO role (PowerUserAccess) cannot modify IAM. We need Gurbachan to add 3 permissions to 2 existing Lambda roles:

**Roles:** `lambda-basic-execution` and `seo-analyzer-lambda-role`

**Permissions needed:**
- `bedrock:InvokeModel` (Resource: `*`) — AI recommendations via Nova Lite
- `secretsmanager:GetSecretValue` (Resource: `arn:aws:secretsmanager:us-east-1:823766426087:secret:ai1stseo/*`) — Cognito client credentials
- `ses:SendEmail`, `ses:SendRawEmail` (Resource: `*`) — email notifications

**What works without these permissions:** SEO analysis, auth, monitoring scans, health checks — all core functionality.

**What's blocked:** AI-powered recommendations (Bedrock), email notifications (SES), Cognito secret from Secrets Manager (currently using env var fallback which works).

---

## What Happens Next (After Permissions)

1. Test AI recommendations and email on Lambda
2. Switch DNS for `api.ai1stseo.com` and `monitor.ai1stseo.com` from EC2 to API Gateway
3. EC2 keeps running for other team members' services
4. Migration complete for seo-backend and site-monitor

---

## Key Infrastructure Reference

| Resource | Value |
|---|---|
| AWS Account | 823766426087 |
| EC2 Instance | i-0d59b5c1a433f0255 (t3.medium, 54.226.251.216) |
| EC2 AMI Backup | ami-004b9dfb15994307b |
| RDS Endpoint | ai1stseo-db.ca5mm2skodf2.us-east-1.rds.amazonaws.com |
| RDS Database | ai1stseo (PostgreSQL 15.12, db.t3.micro) |
| Cognito User Pool | us-east-1_DVvth47zH |
| Cognito App Client | 7scsae79o2g9idc92eputcrvrg |
| Amplify App | d30a3tvkvr1a51 |
| S3 Deploy Bucket | ai1stseo-lambda-deploy |
| Route 53 Zone | Z04191651BC18HQZO55JQ |
| ACM Wildcard Cert | arn:aws:acm:us-east-1:823766426087:certificate/b53fcc4d-aca6-4add-afb1-102ecfa4bf6a |
| Domain Registrar | Spaceship.com (nameservers → Route 53) |
| Ollama Endpoint | https://ollama.sageaios.com (Gurbachan's homelab) |
| Nova Lite Model | amazon.nova-lite-v1:0 |
| GitHub Repo | https://github.com/DeepthiSarayuGunda/ai1stseo-backend.git |

## Lambda Functions

| Function | Role | API Gateway | Custom Domain | Service |
|---|---|---|---|---|
| ai1stseo-backend | lambda-basic-execution | cwb0hb27bf | api.ai1stseo.com | seo-backend |
| seo-analyzer-api | seo-analyzer-lambda-role | w2duao5bg0 | monitor.ai1stseo.com | site-monitor |

## AI Inference Path

```
Lambda → Nova Lite (Bedrock, primary, ~$0.06/1M tokens)
      → ollama.sageaios.com (fallback, free)
          → Bell router (DDNS) → NPM (192.168.2.150) → Ollama GPU (192.168.2.200:11434, Tesla P40)
```

Models on Ollama: `qwen3:30b-a3b`, `qwen3:235b-a22b`, `nomic-embed-text`

---

## For Team Members Migrating Their Services

If you want to migrate your service to Lambda, here's the pattern:

1. **Python/Flask apps:** Add the WSGI-to-ASGI shim (see `backend/app.py` or `web_ui_lambda.py` for the `_FlaskAsgi` class), wrap with Mangum
2. **Node.js apps:** Export a Lambda handler function, no shim needed
3. **FastAPI apps:** Mangum works directly with FastAPI (it's already ASGI)
4. **Dependencies:** Install into the package directory with `pip install --target .`, zip everything, upload to `s3://ai1stseo-lambda-deploy/`
5. **API Gateway:** Custom domains are already created (see table above). You just need a Lambda function and an API Gateway HTTP API to wire them together
6. **Blocker:** Creating new Lambda functions requires `iam:PassRole` which PowerUserAccess doesn't have. Ask Gurbachan to either create the function or grant PassRole.

The `mangum` version in our packages is 0.17.0. Do NOT upgrade to 0.21+ unless you remove the WSGI shim and use a native ASGI framework.
