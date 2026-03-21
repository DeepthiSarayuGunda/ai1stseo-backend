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

### PHASE 2: seo-backend (app.py) → Lambda ✅ COMPLETE
**Completed: March 21, 2026**

- [x] Lambda function `ai1stseo-backend` deployed (Python 3.11, 1024MB, 300s timeout)
- [x] Code: `s3://ai1stseo-lambda-deploy/seo-backend-lambda.zip` (26MB)
- [x] WSGI-to-ASGI shim added for Flask + Mangum 0.17.0 compatibility
- [x] API Gateway HTTP API: `cwb0hb27bf` → `https://cwb0hb27bf.execute-api.us-east-1.amazonaws.com`
- [x] CORS configured on API Gateway (ai1stseo.com, www, Amplify domain)
- [x] Custom domain `api.ai1stseo.com` created on API Gateway → `d-padfgc44dk.execute-api.us-east-1.amazonaws.com`
- [x] API mapping: `api.ai1stseo.com` → `cwb0hb27bf` ($default stage)
- [x] ACM wildcard cert: `arn:aws:acm:us-east-1:823766426087:certificate/b53fcc4d-aca6-4add-afb1-102ecfa4bf6a`
- [x] Health endpoint tested: 200 OK, 231 checks across 9 categories
- [x] SEO analysis tested: Score 39.3, 230 checks, 80 passed for ai1stseo.com
- [x] Auth endpoint tested: Cognito integration working (401 for invalid creds = correct)
- [x] Environment variables: DB, Cognito, Ollama, Nova Lite all configured
- [x] Lambda role: `lambda-basic-execution` (may need Bedrock/SES/SecretsManager policies added by Gurbachan)
- [x] DNS NOT switched yet — `api.ai1stseo.com` still points to EC2 (54.226.251.216)

**Known limitations:**
- API Gateway HTTP API max timeout: 30s (AI recommendations may need async pattern for long prompts)
- Lambda role `lambda-basic-execution` may lack Bedrock InvokeModel, SES, and Secrets Manager permissions
- DNS cutover deferred to Phase 7

**Testing URLs:**
- Lambda API: `https://cwb0hb27bf.execute-api.us-east-1.amazonaws.com/api/health`
- EC2 API (still live): `https://api.ai1stseo.com/api/health`

---

### PHASE 3: site-monitor (web_ui.py) → Lambda ✅ COMPLETE
**Completed: March 21, 2026**

- [x] Lambda function: `seo-analyzer-api` (repurposed, Python 3.11, 1024MB, 300s timeout)
- [x] Code: `s3://ai1stseo-lambda-deploy/site-monitor-lambda.zip` (13MB)
- [x] WSGI-to-ASGI shim via `web_ui_lambda.py` wrapper
- [x] API Gateway HTTP API: `w2duao5bg0` → `https://w2duao5bg0.execute-api.us-east-1.amazonaws.com`
- [x] CORS configured (ai1stseo.com, www, monitor, Amplify)
- [x] Custom domain `monitor.ai1stseo.com` → `d-o6a36rgu1d.execute-api.us-east-1.amazonaws.com`
- [x] Health endpoint tested: 200 OK, service=site-monitor, version=3.0
- [x] Scan endpoint tested: SEO score 39, uptime=True for ai1stseo.com
- [x] Lambda role: `seo-analyzer-lambda-role` (may have more permissions than lambda-basic-execution)
- [x] DNS NOT switched yet — `monitor.ai1stseo.com` still points to EC2

**Testing URLs:**
- Lambda API: `https://w2duao5bg0.execute-api.us-east-1.amazonaws.com/api/health`
- EC2 API (still live): `https://monitor.ai1stseo.com/api/health`

---

### PHASE 4: seo-audit-tool (Node.js) → Lambda
**Status: BLOCKED — needs new Lambda function (iam:PassRole required)**

Custom domain ready: `seoaudit.ai1stseo.com` → `d-gb39s1cajf.execute-api.us-east-1.amazonaws.com`

**Remaining work:**
1. Create Lambda function `ai1stseo-seo-audit` (needs Gurbachan to grant iam:PassRole or create function)
2. Package Node.js code with handler wrapper
3. Create API Gateway HTTP API and wire to Lambda
4. Map custom domain to API

**Lambda config:**
- Runtime: Node.js 20.x
- Memory: 512MB
- Timeout: 60s

---

### PHASE 5: automation-hub + ai-doc-summarizer → Lambda
**Status: BLOCKED — needs new Lambda functions (iam:PassRole required)**

Custom domains ready:
- `automationhub.ai1stseo.com` → `d-c96c1crynj.execute-api.us-east-1.amazonaws.com`
- `docsummarizer.ai1stseo.com` → `d-3k7jpgl2qj.execute-api.us-east-1.amazonaws.com`
- `seoanalysis.ai1stseo.com` → `d-2jl900y7pd.execute-api.us-east-1.amazonaws.com`

**automation-hub (Node.js):**
- Wrap with Lambda handler
- Create Lambda function (needs iam:PassRole)

**ai-doc-summarizer (FastAPI/Python):**
- Wrap with Mangum + WSGI-to-ASGI shim (same pattern as Phases 2-3)
- Create Lambda function (needs iam:PassRole)

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

## IAM Permissions Request for Gurbachan

**BLOCKING ISSUE:** Troy's SSO role (PowerUserAccess) cannot create IAM roles or pass roles to Lambda. The following changes are needed to complete the migration:

### 1. Update `lambda-basic-execution` role (used by `ai1stseo-backend`)
Add these managed policies or inline statements:
```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel"],
  "Resource": "*"
},
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "arn:aws:secretsmanager:us-east-1:823766426087:secret:ai1stseo/*"
},
{
  "Effect": "Allow",
  "Action": ["ses:SendEmail", "ses:SendRawEmail"],
  "Resource": "*"
}
```

### 2. Update `seo-analyzer-lambda-role` (used by `seo-analyzer-api` / site-monitor)
Same permissions as above (Bedrock, Secrets Manager, SES).

### 3. Create 3 new Lambda functions (or grant iam:PassRole to Troy's SSO role)
We need Lambda functions for:
- `ai1stseo-seo-audit` (Node.js 20.x) — for seoaudit.ai1stseo.com
- `ai1stseo-automation-hub` (Node.js 20.x) — for automationhub.ai1stseo.com
- `ai1stseo-doc-summarizer` (Python 3.11) — for docsummarizer.ai1stseo.com

Each needs the same role with: Lambda basic execution + Bedrock + Secrets Manager + SES.

**Alternative:** Add `iam:PassRole` to Troy's PowerUserAccess policy so we can create Lambda functions ourselves.

### Summary of API Gateway Custom Domains (all created, ready for DNS cutover)
| Domain | API Gateway Target | Service |
|--------|-------------------|---------|
| api.ai1stseo.com | d-padfgc44dk.execute-api.us-east-1.amazonaws.com | seo-backend |
| monitor.ai1stseo.com | d-o6a36rgu1d.execute-api.us-east-1.amazonaws.com | site-monitor |
| seoaudit.ai1stseo.com | d-gb39s1cajf.execute-api.us-east-1.amazonaws.com | seo-audit (pending) |
| seoanalysis.ai1stseo.com | d-2jl900y7pd.execute-api.us-east-1.amazonaws.com | seo-analysis (pending) |
| automationhub.ai1stseo.com | d-c96c1crynj.execute-api.us-east-1.amazonaws.com | automation-hub (pending) |
| docsummarizer.ai1stseo.com | d-3k7jpgl2qj.execute-api.us-east-1.amazonaws.com | doc-summarizer (pending) |

---

## Post-Migration Cleanup

- [ ] Remove Nginx configs from EC2
- [ ] Remove Let's Encrypt certs (no longer needed)
- [ ] Remove PM2 process configs
- [ ] Final AMI snapshot of EC2
- [ ] Terminate EC2 instance
- [ ] Update DEPLOYMENT.md with new architecture
- [ ] Update team on new deployment workflow (push to GitHub → Amplify auto-deploys)
