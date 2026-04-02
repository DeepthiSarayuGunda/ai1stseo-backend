Subject: Moving from EC2 to AWS Amplify — What's Involved

Hi Gurbachan,

Wanted to put together a breakdown of what it would take to move our infrastructure from EC2 over to AWS Amplify, since you mentioned wanting to explore that direction. There's a fair amount to consider here, so I figured it's worth laying it all out before we commit to anything.

---

WHERE WE ARE NOW

We're running 6 services on a single EC2 instance (t3.medium, ~$30/mo):

- seo-analysis (Flask/Python) — our main analysis platform, runs Ollama/Llama 3.1 locally for AI recommendations, stores data in SQLite
- seo-audit-tool (Node.js) — technical SEO crawler, uses Bedrock/Claude for AI
- seo-backend (Flask/Python) — handles auth via Cognito and runs the 231-check audit engine
- site-monitor (Flask/Python) — monitoring dashboard with email subscriptions
- automation-hub (Node.js) — minimal right now
- ai-doc-summarizer (FastAPI) — minimal right now

On top of that we have Nginx handling reverse proxy and SSL termination, Let's Encrypt certs auto-renewing, and Ollama running Llama 3.1 for free on-device AI inference.

---

WHAT AMPLIFY GIVES US

Amplify is built for frontend hosting and serverless backends. It handles static sites, Lambda-based API functions, Cognito auth, SSL, and CI/CD from GitHub out of the box. No servers to manage, no SSH, no patching.

The catch is that it's serverless-only. There's no persistent process, no local filesystem, and no way to run something like Ollama in the background.

---

WHAT HAS TO CHANGE

Here's where it gets involved:

1. Ollama/Llama 3.1 has to go. There's nowhere to run a local LLM on Amplify. Every Ollama call in seo-analysis would need to be swapped to Bedrock (Claude Haiku or Nova Micro). seo-audit-tool already uses Bedrock so that one's fine. This adds roughly $25–35/mo in API costs that we currently don't pay.

2. SQLite and JSON file storage have to move to a managed database. Amplify doesn't have a persistent disk. We'd migrate to either DynamoDB (free tier covers us for now) or RDS PostgreSQL (free tier for 12 months on db.t3.micro). The product spec actually calls for PostgreSQL anyway, so this would be moving in the right direction.

3. All our Flask services need to be refactored into Lambda functions. Flask doesn't run natively on Lambda — we'd either use a wrapper like Mangum or rewrite the endpoints as Lambda handlers. Same story for the Node.js services, though that's a smoother transition since Lambda supports Node natively.

4. Cold starts become a factor. When a Lambda function hasn't been called in a while, the first request takes 1–3 extra seconds to spin up. Users would notice this on the first page load after idle periods.

5. Cognito carries over as-is. Amplify Auth is just a Cognito wrapper, so our user pool, app client, and SES email config stay the same. Minor URL changes on the frontend.

6. Nginx and SSL management go away entirely. Amplify handles that automatically, which is actually a nice simplification.

7. Background jobs (like scheduled monitoring or cron-based reports) would need EventBridge or Step Functions instead of running as persistent processes.

---

COST COMPARISON

Current EC2 setup: ~$30/mo total
- Compute: ~$30 (t3.medium)
- AI inference: $0 (Ollama runs locally)
- Database: $0 (SQLite on disk)
- SSL/DNS/SES/Cognito: $0

After Amplify migration: ~$30–65/mo total
- Compute: $0–15 (Amplify free tier covers 500K Lambda requests/mo)
- AI inference: $25–35 (Bedrock API calls replacing Ollama)
- Database: $0–15 (DynamoDB free tier or RDS PostgreSQL)
- SSL/DNS/SES/Cognito: $0

The cost increase is almost entirely from losing free local AI inference.

---

TIMELINE

Realistically this is a 2–3 week effort:

Week 1 — Move the static frontend to Amplify Hosting, set up Amplify Auth, provision the database, and replace Ollama calls with Bedrock in seo-analysis.

Week 2 — Refactor seo-backend and seo-audit-tool into Lambda functions, migrate data out of SQLite/JSON, update frontend API URLs.

Week 3 — Refactor seo-analysis and site-monitor into Lambda functions, run end-to-end testing, cut over DNS, and decommission the EC2 instance.

During those 2–3 weeks the team would mostly be focused on migration work rather than building new features from the product spec. That's the main tradeoff.

---

WHAT I'D SUGGEST

We can absolutely do this, but timing matters. We just assigned Phase 1 tasks to all five developers this week. Pulling everyone off feature work for 2–3 weeks right now would stall that momentum.

One option is a phased approach — move the static frontend to Amplify this week (that's a day or two of work and gives us the CI/CD benefits immediately), then plan the full backend migration for after Phase 1 stabilizes. That way we're not choosing between infrastructure and features.

Either way, happy to go whichever direction you think makes sense. Just wanted to make sure the full picture was on the table before we move forward.

Troy
