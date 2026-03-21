# Amplify Migration Roadmap
## EC2 → AWS Amplify (Serverless)
### Revised per Gurbachan's feedback — March 21, 2026

---

## Current EC2 Architecture (What We're Migrating)

| PM2 Service | Port | Subdomain | Stack | Script Path |
|---|---|---|---|---|
| seo-analysis | 3000 | seoanalysis.ai1stseo.com | Python/Flask | `/home/ec2-user/seo-analysis/web_app.py` |
| seo-audit-tool | 8080 | seoaudit.ai1stseo.com | Node.js | `/home/ec2-user/seo-audit-tool/run-all-simple.js` |
| seo-backend | 5000 | api.ai1stseo.com | Python/Flask | `ai1stseo-backend/.../backend/app.py` |
| site-monitor | 8888 | monitor.ai1stseo.com | Python/Flask | `/home/ec2-user/openclaw-site-monitor/web_ui.py` |
| automation-hub | 3001 | automationhub.ai1stseo.com | Node.js | `/home/ec2-user/AutomationDemo/backend/server-cli.js` |
| ai-doc-summarizer | 8005 | docsummarizer.ai1stseo.com | Python/FastAPI | `/home/ec2-user/projects/ai-doc-summarizer/start.sh` |

Supporting infra: Nginx (reverse proxy + SSL), Let's Encrypt (certs), Ollama (Llama 3.1 on EC2)

---

## Target Architecture (Post-Migration)

```
                    ┌─────────────────────────────────┐
                    │       AWS Amplify Hosting        │
                    │   (Static frontend: index.html,  │
                    │    analyze.html, audit.html,     │
                    │    guides.html, assets/*)        │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │      API Gateway (REST)          │
                    │   Custom domains per service     │
                    │   Cognito Authorizer on /api/*   │
                    └──────────────┬──────────────────┘
                                   │
          ┌────────────┬───────────┼───────────┬────────────┐
          ▼            ▼           ▼           ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Lambda   │ │ Lambda   │ │ Lambda   │ │ Lambda   │ │ Lambda   │
    │ seo-     │ │ seo-     │ │ seo-     │ │ site-    │ │ ai-doc-  │
    │ analysis │ │ audit    │ │ backend  │ │ monitor  │ │ summary  │
    │ (Mangum) │ │ (Node)   │ │ (Mangum) │ │ (Mangum) │ │ (Mangum) │
    └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │            │            │
         ▼            ▼            ▼            ▼            ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    RDS PostgreSQL                            │
    │          ai1stseo-db (db.t3.micro, free tier)               │
    └─────────────────────────────────────────────────────────────┘
         │
         ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  AI Inference                                                │
    │  Primary: Nova Lite via Bedrock ($0.06/1M input tokens)     │
    │  Fallback: ollama.sageaios.com (free, Gurbachan's homelab)  │
    └─────────────────────────────────────────────────────────────┘
```

Other AWS services: Cognito (auth, existing), SES (email, existing), EventBridge (cron), CloudWatch (logs)

---

## Revised Cost Estimate

| Item | Current (EC2) | Post-Migration (Amplify) |
|---|---|---|
| Compute | $30/mo (t3.medium) | $0 (Lambda free tier: 1M req/mo) |
| AI Inference | $0 (Ollama on EC2) | $0-5 (Nova Lite + ollama.sageaios.com fallback) |
| Database | $0 (SQLite/JSON) | $0 (RDS db.t3.micro free tier 12mo) |
| SSL/DNS | $0 (Let's Encrypt) | $0 (Amplify/ACM auto) |
| Auth/Email | $0 (Cognito/SES) | $0 (same) |
| **Total** | **~$30/mo** | **~$5-15/mo** |

---

## Migration Phases

### PHASE 0: Pre-Flight Safety Checks (Before touching anything)
**Time: 1-2 hours**

- [x] Snapshot the EC2 instance → AMI `ami-004b9dfb15994307b` (2026-03-21)
- [x] Export all PM2 configs: `pm2 save` done
- [x] Backup Nginx configs: copied to `/home/ec2-user/nginx-backup`
- [x] Verify RDS automated backups: 7-day retention, latest restore point 2026-03-21T14:54
- [x] Confirm all 7 endpoints responding: ai1stseo.com, api, monitor, seoaudit, seoanalysis, automationhub, docsummarizer — all 200 OK
- [x] Document current Ollama endpoint: `https://api.databi.io/api`
- [x] Test Gurbachan's Ollama endpoint: `ollama.sageaios.com` → 200 OK, models: qwen3:30b-a3b, qwen3:235b-a22b, nomic-embed-text (no llama3.1 yet)
- [x] Nova Lite on Bedrock: ACTIVE (amazon.nova-lite-v1:0, up to 300K context)
- [x] GitHub repo up to date

**Rollback plan:** Restore AMI snapshot, point DNS back to EC2 IP. Total rollback time: ~10 minutes.

---

### PHASE 1: Static Frontend → Amplify Hosting
**Time: 2-3 hours | Risk: Low**

The static HTML/JS files currently served by Flask/Nginx move to Amplify Hosting (S3 + CloudFront behind the scenes).

**Files to deploy:**
- `index.html` (main landing page)
- `analyze.html` (standalone analyzer)
- `audit.html` (results page)
- `guides.html` (implementation guides)
- `assets/auth.js`, `assets/index-*.js` (React bundles)
- `s3-index.html` (if needed)

**Steps:**
1. Create Amplify app in console, connect to GitHub repo
2. Configure build settings (no build step — just copy static files)
3. Set up custom domain `ai1stseo.com` + `www.ai1stseo.com` in Amplify
4. Amplify auto-provisions ACM cert and CloudFront distribution
5. Update `assets/auth.js` API base URL to point to API Gateway (once created)
6. Test: all static pages load, auth modal works, links work

**What stays on EC2 during this phase:** All 6 API services still running. Only static file serving moves.

**DNS change:** `ai1stseo.com` A record → Amplify CloudFront (CNAME/ALIAS). API subdomains stay pointing to EC2.

---

### PHASE 2: seo-backend (app.py) → Lambda
**Time: 3-4 hours | Risk: Medium**

This is the core service — 231-check SEO analyzer + Cognito auth + AI recommendations.

**Refactoring needed:**
1. Wrap Flask app with Mangum: `handler = Mangum(app)`
2. Remove static file serving routes (`serve_index`, `serve_analyze`, `serve_guides`, `serve_assets`, `serve_audit`, `catch_all`) — frontend is now on Amplify
3. Replace Ollama URL (`https://api.databi.io/api`) with dual-path:
   - Primary: Nova Lite via `boto3.client('bedrock-runtime')`
   - Fallback: `https://ollama.sageaios.com/api/generate`
4. `auth.py` — works as-is (already uses boto3 for Cognito + Secrets Manager)
5. `database.py` — works as-is (already connects to RDS)
6. Add `requirements.txt` with mangum, psycopg2-binary, boto3, etc.

**Lambda config:**
- Runtime: Python 3.11
- Memory: 512MB (analysis is CPU-bound for HTML parsing)
- Timeout: 60s (analysis), 300s (AI recommendations)
- VPC: Same subnets/SG as RDS
- IAM: Bedrock InvokeModel, Secrets Manager read, SES send

**API Gateway:**
- Custom domain: `api.ai1stseo.com`
- Routes: `POST /api/analyze`, `GET /api/health`, `POST /api/ai-recommendations`, `/api/auth/*`
- Cognito authorizer on protected routes

**Testing:**
- Run full SEO analysis against ai1stseo.com
- Test auth flow (signup, verify, login, refresh, delete)
- Test AI recommendations with Nova Lite
- Compare results with current EC2 output

---

### PHASE 3: site-monitor (web_ui.py) → Lambda
**Time: 2-3 hours | Risk: Low (already partially refactored)**

This was already prepped for Lambda in Task 56 — Mangum wrapper, RDS integration, Cognito auth.

**Remaining work:**
1. The current `web_ui.py` on EC2 still uses local JSON auth (not the Cognito version we wrote). Deploy the refactored version.
2. `template.yaml` (SAM template) already exists — deploy it
3. Move `templates/index.html` to Amplify Hosting under `/monitor/` path or `monitor.ai1stseo.com` subdomain
4. EventBridge rule for daily reports (already defined in template.yaml)

**Lambda config:**
- Runtime: Python 3.11
- Memory: 512MB
- Timeout: 60s (scans), 300s (daily reports)
- VPC: Same as RDS

**API Gateway:**
- Custom domain: `monitor.ai1stseo.com`
- Routes: `/api/scan`, `/api/uptime`, `/api/content`, `/api/ai-visibility`, `/api/full-scan`, `/api/subscribe`, `/api/chat`, etc.

---

### PHASE 4: seo-audit-tool (Node.js) → Lambda
**Time: 2-3 hours | Risk: Medium**

Node.js service — Lambda supports Node natively, so no Mangum needed.

**Refactoring needed:**
1. Export handler function from `run-all-simple.js` (or create a `handler.js` wrapper)
2. Replace any file-system storage with RDS or S3
3. Bedrock integration already exists — verify it uses Nova Lite
4. Package with `node_modules` into deployment zip

**Lambda config:**
- Runtime: Node.js 20.x
- Memory: 512MB
- Timeout: 60s

**API Gateway:**
- Custom domain: `seoaudit.ai1stseo.com`

---

### PHASE 5: automation-hub + ai-doc-summarizer → Lambda
**Time: 2-3 hours | Risk: Low (both are minimal)**

Both services are described as "minimal right now" in the migration email.

**automation-hub (Node.js):**
- Wrap with Lambda handler
- Custom domain: `automationhub.ai1stseo.com`

**ai-doc-summarizer (FastAPI/Python):**
- Wrap with Mangum (FastAPI works with Mangum same as Flask)
- Custom domain: `docsummarizer.ai1stseo.com`

---

### PHASE 6: AI Inference Migration
**Time: 1-2 hours | Risk: Low**

Replace all Ollama calls with dual-path inference:

```python
# ai_inference.py — shared module
import boto3, requests, json

def generate(prompt, model="amazon.nova-lite-v1:0", max_tokens=4096):
    """Primary: Nova Lite via Bedrock. Fallback: ollama.sageaios.com"""
    # Try Nova Lite first
    try:
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        response = bedrock.invoke_model(
            modelId=model,
            body=json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": 0.7
                }
            })
        )
        result = json.loads(response['body'].read())
        return result['results'][0]['outputText']
    except Exception as e:
        print(f"Nova Lite failed: {e}, falling back to Ollama")

    # Fallback: Gurbachan's homelab Ollama
    try:
        resp = requests.post(
            "https://ollama.sageaios.com/api/generate",
            json={"model": "llama3.1:latest", "prompt": prompt, "stream": False},
            timeout=120
        )
        return resp.json().get("response", "")
    except Exception as e:
        return f"AI inference unavailable: {e}"
```

**Services that use AI inference:**
- `seo-backend/app.py` → `/api/ai-recommendations` (currently Ollama via api.databi.io)
- `site-monitor/tools/ai_analyzer.py` → chat/analysis features
- `seo-audit-tool` → already uses Bedrock

---

### PHASE 7: DNS Cutover + EC2 Decommission
**Time: 1-2 hours | Risk: Medium (but fully reversible)**

Once all services are verified on Lambda:

1. Update Route 53 records:
   - `ai1stseo.com` → Amplify CloudFront distribution
   - `api.ai1stseo.com` → API Gateway custom domain
   - `monitor.ai1stseo.com` → API Gateway custom domain
   - `seoaudit.ai1stseo.com` → API Gateway custom domain
   - `seoanalysis.ai1stseo.com` → API Gateway custom domain
   - `automationhub.ai1stseo.com` → API Gateway custom domain
   - `docsummarizer.ai1stseo.com` → API Gateway custom domain

2. Keep EC2 running for 48-72 hours as hot standby (DNS TTL propagation)
3. Monitor CloudWatch logs for errors
4. After 72 hours with no issues: stop EC2 instance (don't terminate yet)
5. After 1 week: create final AMI snapshot, then terminate EC2

**Rollback:** Change DNS records back to EC2 IP `54.226.251.216`. Services are still running on EC2 until we explicitly stop them.

---

## Migration Order & Dependencies

```
Phase 0 (Safety)
    │
    ▼
Phase 1 (Static Frontend) ──── no dependencies, do first
    │
    ▼
Phase 2 (seo-backend) ──────── depends on Phase 1 (frontend needs API URL)
    │
    ├──► Phase 3 (site-monitor) ── independent, can parallel with 4/5
    ├──► Phase 4 (seo-audit) ───── independent, can parallel with 3/5
    └──► Phase 5 (hub + docs) ──── independent, can parallel with 3/4
    │
    ▼
Phase 6 (AI Inference) ──────── can start anytime, but test after Phase 2
    │
    ▼
Phase 7 (DNS Cutover) ──────── only after ALL services verified on Lambda
```

---

## Safety Guardrails

1. **EC2 stays running** throughout the entire migration. We run both environments in parallel.
2. **AMI snapshot** taken before any changes — full rollback in 10 minutes.
3. **DNS TTL set to 300s (5 min)** before cutover — fast rollback if needed.
4. **Each phase is independently testable** — we verify before moving to the next.
5. **RDS is untouched** — same database, same connection string, just accessed from Lambda instead of EC2.
6. **Cognito is untouched** — same user pool, same app client.
7. **No data migration needed** — RDS PostgreSQL is already the target DB.

---

## What Gurbachan Handles Separately

- OpenClaw server → moves to his homelab (192.168.2.160 or 192.168.2.105)
- Tailscale access for team (needs non-Algonquin email addresses)
- Ollama GPU server maintenance (ollama.sageaios.com)
- DDNS cron for Bell router IP changes

---

## Post-Migration Cleanup

- [ ] Remove Nginx configs from EC2
- [ ] Remove Let's Encrypt certs (no longer needed)
- [ ] Remove PM2 process configs
- [ ] Final AMI snapshot of EC2
- [ ] Terminate EC2 instance
- [ ] Update DEPLOYMENT.md with new architecture
- [ ] Update team on new deployment workflow (push to GitHub → Amplify auto-deploys)
