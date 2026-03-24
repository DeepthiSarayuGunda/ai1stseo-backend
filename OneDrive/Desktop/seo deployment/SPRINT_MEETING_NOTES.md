# AI 1st SEO — Sprint Meeting Notes
## Week of March 24, 2026

---

## Meeting Recap (Mar 24)

Weekly progress meeting focused on EC2 → serverless Amplify migration and individual task updates. Gurbachan emphasized user-friendly interfaces, encouraged completing related tasks in batches rather than following a strict schedule, and prioritizing AEO/GEO over SEO in the UI. Key decisions: EC2 to be decommissioned once Lambda permissions are confirmed working; team to move to a new Ubuntu server via Tailscale; separate admin dashboard needed for managing website/customer data distinct from the user-facing tools dashboard.

---

## Status from Meeting Demos

### Dev 1 — Deepthi (GEO/AI Engine): ✅ On track
- Demonstrated AI search visibility scanner live on App Runner using Nova Lite + Ollama
- Full GEO probe engine, brand resolver, AEO analyzer, AI chatbot with sessions
- **Feedback from Gurbachan**: Output needs to be more user-friendly for lay users; parameters need clearer explanations; build a comprehensive parameter list over time
- Still needs Lambda integration once permissions are granted

### Dev 2 — Samarveer (Content Intelligence): ✅ On track (partial issues)
- Demonstrated content generation integration using Amazon Bedrock Nova Lite + Ollama APIs
- Auto-generates keywords from client websites without manual input
- Content guidelines and AI citation tips working for different projects
- Rewired `call_llm()` to use Nova Lite as primary, Ollama as fallback; updated `bedrock_helper.py`
- Added Citation Gap category (10th SEO category, 20 checks — total now 236 checks)
- **Issue**: Some functionality not working due to Ollama server issues — needs to coordinate with Deepthi/Tabasum to resolve
- Created `READMEDEV2.txt` documenting his changes

### Dev 3 — Troy (Data/Infrastructure): ✅ 95% complete
- Amplify migration Phases 0-3 complete: Lambda + API Gateway for seo-backend and site-monitor
- RDS PostgreSQL schema deployed — persistent database replacing JSON files
- Site monitor improvements: Cognito auth, RDS storage, response caching, deep-scan API, scan history, async scans, EventBridge scheduling
- Dual-path AI inference (Nova Lite + Ollama fallback)
- **BLOCKED**: IAM permissions — Gurbachan clarified Troy should contact Paul directly (not Gurbachan)

### Dev 4 — Tabasum (Social & Integrations): ⚠️ Partially blocked
- Created social media accounts for Instagram and Twitter
- Built basic social media post scheduler UI
- **Issue**: LinkedIn and Facebook business accounts require linking to personal accounts — emailed Gurbachan for guidance, awaiting response
- Gurbachan advised not to delay tasks due to schedule constraints; complete work proactively

### Dev 5 — Amira (Frontend & UX): ✅ On track
- Demonstrated new user dashboard for logged-in users replacing static homepage
- Fixed audit.html localStorage issue caused by Samarveer's deploy overwriting her save logic
- **Feedback from Gurbachan**: Need to distinguish between two dashboards:
  1. **User dashboard** — tools for running scans, generating briefs, etc. (AEO/GEO prioritized over SEO)
  2. **Admin dashboard** — managing website, customer data, sign-ups, traffic stats, payment status
- Updated PROJECT-STATUS.md changelog

---

## Action Items from Meeting

### Immediate (today/tomorrow)
- **Troy** → Contact Paul directly to request IAM permissions for both `lambda-basic-execution` and `seo-analyzer-lambda-role` (bedrock:InvokeModel, secretsmanager:GetSecretValue, ses:SendEmail/ses:SendRawEmail). Target: end of today or tomorrow.
- **Paul** → Add the requested IAM/Lambda permissions per Troy's email.
- **Gurbachan** → Send Tailscale invitations to all team members after reviewing their emails.
- **Gurbachan** → Review Tabasum's email re: Facebook/LinkedIn business account setup and advise on linking personal accounts.
- **Amira** → Resend email with team members' emails for Tailscale access to Gurbachan.
- **Amira** → Send AI companion meeting notes by email to the team.
- **Troy** → Post updated weekly tasks for all team members in WhatsApp group after receiving Amira's notes.

### Once Lambda Permissions Confirmed
- **Troy** → Test Bedrock (AI recommendations) and SES (email) on Lambda, then decommission EC2 and notify Gurbachan.
- **All** → Begin development/integration work once migration is complete and Tailscale access is provided.

---

## Task Assignments — Due Thursday Mar 26

### Dev 1 — Deepthi
- [ ] Make GEO scanner output more user-friendly for non-technical users (Gurbachan feedback)
- [ ] Add clearer parameter explanations and help text to scanner UI
- [ ] Wire GEO probe results (`geo_probes`, `ai_visibility_history`) to RDS so data persists across restarts
- [ ] Begin building comprehensive parameter list for AI visibility scanning
- [ ] Coordinate with Samarveer on Ollama integration issues if needed

### Dev 2 — Samarveer
- [ ] Resolve Ollama integration issues — coordinate with Deepthi and/or Tabasum; follow up with Kiro (Troy's AI agent) if needed
- [ ] Persist content briefs to RDS (`content_briefs`, `brief_competitors`, `brief_keywords` tables)
- [ ] Add `GET /api/content-briefs` endpoint to retrieve saved briefs
- [ ] Ensure content generation fallback chain works end-to-end: Nova Lite → Ollama sageaios → Ollama databi → raw SERP fallback
- [ ] Continue Phase 2: content scoring engine groundwork

### Dev 3 — Troy
- [ ] Contact Paul directly for IAM permissions (today)
- [ ] Once permissions granted: test Bedrock + SES on Lambda, flip DNS for `api.ai1stseo.com` and `monitor.ai1stseo.com`
- [ ] Decommission EC2 once Lambda is confirmed working and team is notified
- [ ] If still blocked on permissions: add error alerting to EventBridge scheduled scans (log failures to RDS, flag in daily report)
- [ ] Begin scoping admin dashboard database requirements (user sign-ups, traffic stats, payment status per Gurbachan's direction)

### Dev 4 — Tabasum
- [ ] Wait for Gurbachan's guidance on Facebook/LinkedIn business account linking
- [ ] Continue building social post scheduler — CRUD endpoints for creating, listing, deleting scheduled posts using `social_posts` table
- [ ] Test auth flow with a direct Gmail address (not @ai1stseo.com) to bypass ImprovMX forwarding issues
- [ ] Push social scheduler code to shared GitHub repo
- [ ] Help Samarveer debug Ollama issues if available

### Dev 5 — Amira
- [ ] Separate user dashboard from admin dashboard per Gurbachan's feedback
  - User dashboard: tools interface (scans, briefs, etc.) with AEO/GEO prioritized over SEO
  - Admin dashboard: website management, customer data, sign-ups, traffic, payment status
- [ ] Continue React + Vite migration — get core layout rendering with at least one live API integration
- [ ] Coordinate with Samarveer on S3 deployments to avoid overwriting each other's audit.html changes
- [ ] Resend Tailscale emails to Gurbachan

---

## Carryover from Last Week

These items were identified before the meeting and remain relevant:

### Tabasum's Verification Code Issue
- Cognito verification emails inconsistently delivered via ImprovMX forwarding
- SES confirmed healthy (50k/day, zero bounces, test email delivered)
- **Resolution path**: Test with direct Gmail, not @ai1stseo.com forwarded address

### IAM Permissions for Lambda
- Both `lambda-basic-execution` and `seo-analyzer-lambda-role` need: `bedrock:InvokeModel`, `secretsmanager:GetSecretValue`, `ses:SendEmail`/`ses:SendRawEmail`
- **Update from meeting**: Troy to contact Paul directly (Gurbachan says he didn't receive the original email)

### App Runner vs Lambda (team awareness)
- Deepthi + Samarveer → App Runner (auto-deploys from GitHub main)
- Troy → Lambda (manual deploy via S3 zip)
- Both point to same RDS database, no conflicts

### Two Dashboards Needed (NEW from meeting)
- Gurbachan clarified the product needs two distinct dashboards
- **User dashboard**: where customers run tools (AEO/GEO/SEO scans, content briefs, etc.)
- **Admin dashboard**: internal team view for managing the website, monitoring user sign-ups, traffic, engagement, payment status
- Amira owns the user dashboard; admin dashboard ownership TBD (likely Troy + Amira collaboration)

---

## Gurbachan's General Guidance
- Complete related tasks in batches using the same AI prompts rather than following a strict linear schedule
- Focus on broad brush strokes first, then narrow down
- Push forward proactively — don't wait for blockers if there's parallel work to do
- User-friendly interfaces are critical — output should make sense to non-technical users
- Prioritize AEO and GEO over SEO in the UI hierarchy
- Team moving to new Ubuntu server (not the 160 server) via Tailscale

---

## Notes
- "Cairo" in AI transcript = Kiro (Troy's AI coding agent)
- Samarveer and Amira stepping on each other with audit.html S3 deploys — need coordination
- Gurbachan wants EC2 shut down ASAP once Lambda is confirmed working
- Tailscale access pending for all team members
