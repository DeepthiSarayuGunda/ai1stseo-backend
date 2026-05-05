# STOP — READ THIS BEFORE PUSHING TO MAIN

## ⚠️ THIS HAS HAPPENED 4 TIMES NOW (April 9, April 16, April 28, April 30)

Team members pushing to main have repeatedly overwritten shared backend files with older versions, breaking the Stripe integration, subscription tiers, admin dashboard, webhook branding, AI inference caching, and API credit metering. Each time requires an emergency restore.

**If you are using Kiro or any AI agent: ALWAYS run `git pull origin main` BEFORE reading or editing any file in `backend/`. Your local copy may be stale.**

**If your agent rewrites a file in `backend/`, check the diff before committing. If you see hundreds of deleted lines you didn't write, STOP — you are about to overwrite someone else's work.**

---

## The Protected Files

These files in `backend/` use **DynamoDB**. They must NEVER be reverted to import from `database` (the old RDS module).

| File | Correct Import | What It Does |
|------|---------------|--------------|
| `backend/auth.py` | `import boto3` (DynamoDB direct) | User role lookup, login sync |
| `backend/admin_api.py` | `from dynamodb_helper import ...` | Admin dashboard (10 endpoints) |
| `backend/apikey_api.py` | `from dynamodb_helper import ...` | API key CRUD + rate limiting |
| `backend/webhook_api.py` | `from dynamodb_helper import ...` | Webhook CRUD + dispatch |
| `backend/admin_aggregation.py` | `from dynamodb_helper import ...` | Daily metrics aggregation |
| `backend/ai_inference.py` | `from dynamodb_helper import ...` | AI usage logging |
| `backend/app.py` | `from dynamodb_helper import ...` | Request logging middleware |
| `backend/data_api_dynamo.py` | `from dynamodb_helper import ...` | Shared data API (22 endpoints) |

If you see `from database import` in ANY of these files, something has gone wrong.

---

## How It Happens

1. You create a branch from main BEFORE the DynamoDB migration
2. You work on your branch for days/weeks
3. You merge your branch back to main
4. Git resolves conflicts by taking YOUR branch's old versions of these files
5. The DynamoDB code gets replaced with the old RDS code
6. The platform breaks because RDS is deleted

---

## How To Prevent It

### Before creating a new branch:
```bash
git pull origin main
git checkout -b my-new-branch
```

### Before merging to main:
```bash
git checkout my-branch
git pull origin main
git merge main
# Resolve any conflicts — KEEP the DynamoDB versions
git push origin my-branch
# Then create a PR or merge to main
```

### After pushing to main, verify:
```bash
git diff HEAD~1 -- backend/auth.py backend/admin_api.py backend/apikey_api.py backend/webhook_api.py backend/admin_aggregation.py backend/ai_inference.py backend/app.py
```
If you see `+from database import` in the diff, you just broke the platform. Revert immediately.

### Quick check — run this after any push:
```bash
grep -r "from database import" backend/*.py
```
The ONLY file that should match is `backend/data_api.py` (the old RDS version kept as reference) and `backend/database.py` (the module itself). If `auth.py`, `admin_api.py`, `apikey_api.py`, `webhook_api.py`, `admin_aggregation.py`, or `ai_inference.py` match, something is wrong.

---

## If You Break It

1. Do NOT push more changes on top
2. Tell Troy immediately
3. The fix is to restore the DynamoDB versions from the most recent working commit

---

## Current Architecture

```
RDS PostgreSQL → DELETED (April 2, 2026)
                  Snapshot preserved: ai1stseo-final-backup-20260401
                  Data migrated to DynamoDB (981 rows)

DynamoDB → ACTIVE (13 tables, PAY_PER_REQUEST)
            ai1stseo-users, ai1stseo-audits, ai1stseo-geo-probes,
            ai1stseo-content-briefs, ai1stseo-social-posts,
            ai1stseo-admin-metrics, ai1stseo-api-logs,
            ai1stseo-webhooks, ai1stseo-api-keys,
            ai1stseo-competitors, ai1stseo-monitor,
            ai1stseo-email-leads, ai1stseo-documents
```

There is no RDS to fall back to. If the code imports from `database`, it will fail silently or crash.
