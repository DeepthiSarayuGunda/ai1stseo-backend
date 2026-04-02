# OpenClaw Integration Plan — Site Monitor Microproject

**Author:** Troy Sauriol (Dev 3 — Data & Infrastructure)
**Date:** April 2, 2026
**Status:** Pending — requires OpenClaw Gateway installation on seo-dev server

---

## Current State

The site monitor microproject is fully operational on Gurbachan's Tailscale server (`seo-dev`, `100.108.196.117:8888`):

- Flask web UI with 6 monitoring dimensions (SEO, uptime, content, AI citation, competitor, transaction)
- Connected to local Ollama accelerator (`192.168.2.200:11434`) with tiered model access:
  - Fast (llama3.1:8b) — chat, summaries
  - Standard (qwen3:30b) — SEO analysis
  - Heavy (qwen3:235b) — deep competitor intel
  - Embeddings (nomic-embed-text) — semantic similarity
- Agent code structured for OpenClaw (`AGENT_CONFIG`, tool registration, `.env` with `OPENCLAW_API_URL`)
- Notifier module supports WhatsApp, Slack, Telegram, Discord, email
- AI Analyzer with conversational Q&A, fix generation, competitor gap analysis

**Missing:** The OpenClaw Gateway runtime is not installed on the server.

---

## What OpenClaw Is

OpenClaw is a self-hosted multi-channel gateway for AI agents. It runs as a single daemon that:

1. **Connects to messaging channels** — WhatsApp (via Baileys/QR pairing), Slack, Telegram, Discord, WebChat
2. **Runs an embedded agent runtime** — with workspace, tools, skills, and scheduling
3. **Exposes a control plane** — WebSocket API on port 18789 for operator/automation access
4. **Supports plugins** — TypeScript/Node SDK for registering custom tools, channels, skills
5. **Has built-in cron** — persistent scheduled jobs with delivery to channels or webhooks

Config lives at `~/.openclaw/openclaw.json`. It's MIT licensed (core).

---

## Integration Strategy: Phased Approach

### Phase 1: Gateway + Conversation + Delivery (Strategy A)

**Goal:** OpenClaw handles chat and report delivery. Python keeps scan orchestration.

**What Gurbachan needs to do:**
1. Install OpenClaw Gateway on seo-dev (`192.168.2.105`)
2. Run: `openclaw gateway --port 18789` (or install as systemd service)
3. Configure at least one channel (WhatsApp QR pairing recommended for demo)
4. Share the gateway auth token with Troy

**What we build:**
- Python scheduler runs scans as it does today
- When a report is ready, Python calls `POST /hooks/agent` on localhost:18789 with:
  - The formatted report text
  - Delivery target (channel + recipient)
  - Optional model override for summarization
- OpenClaw delivers the report via the configured channel
- Users can reply to the report in WhatsApp/Slack and OpenClaw routes the conversation to the agent
- Agent uses our AI Analyzer (via `/hooks/agent` or tool invocation) to answer questions

**Endpoints we'd use:**
- `POST /hooks/agent` — trigger agent turn with delivery target
- `POST /hooks/wake` — wake the agent for a system event
- `POST /tools/invoke` — direct tool invocation (operator access)

**Timeline:** 1-2 days once Gateway is installed.

### Phase 2: Register Tools as OpenClaw Plugin (Strategy B)

**Goal:** OpenClaw can orchestrate scans directly. Users can say "scan my site" in chat.

**What we build:**
- TypeScript plugin package with `openclaw.plugin.json`
- Register 7 tools using async start/poll/get pattern:

| OpenClaw Tool | Python Backend | Pattern |
|--------------|---------------|---------|
| `ocsm_seo_scan_start` | `POST /api/async-deep-scan` | Returns job_id |
| `ocsm_scan_poll` | `GET /api/scan-status/<job_id>` | Returns progress |
| `ocsm_scan_get` | `GET /api/scan-status/<job_id>` | Returns results |
| `ocsm_uptime_check` | `GET /api/uptime?url=` | Sync (fast) |
| `ocsm_content_diff` | `GET /api/content?url=` | Sync (fast) |
| `ocsm_ai_visibility` | `GET /api/ai-visibility?domain=` | Sync |
| `ocsm_competitor_scan` | Custom endpoint | Async |
| `ocsm_notify_send` | Internal notifier | Delivery |

- Create a workspace skill (`SKILL.md`) that defines:
  - The 6 monitoring dimensions and when to use each
  - Required tool sequence (start → poll → summarize)
  - Channel-specific formatting (WhatsApp chunk limits, Slack threading)
  - Guardrails: never scrape directly, always use our scanners as ground truth

**Timeline:** 3-5 days after Phase 1 is validated.

### Phase 3: Scheduled Reports via OpenClaw Cron

**Goal:** Replace our Python scheduler with OpenClaw's built-in cron.

**What we configure:**
- Cron job in OpenClaw: daily at 08:00 UTC
- Isolated session mode (not main session)
- Prompt: "Call ocsm_dispatch_due_reports. Summarize: how many succeeded, failed, top failure reasons."
- Delivery mode: `announce` to configured channel targets

**Alternative:** Use cron `delivery.mode = "webhook"` pointing at our Flask endpoint, keeping report formatting in Python.

**Timeline:** 1 day after Phase 2.

### Phase 4: Multi-Agent Routing (Strategy C — Future)

**Goal:** Separate admin agent from customer-facing agent.

- **Admin agent:** Full tool access, bound to internal Slack/admin WebChat
- **Customer agent:** Restricted tools (only scan + Q&A), bound to customer WhatsApp/channels
- Agent bindings route inbound messages by channel/peer to the correct agent
- Authorization checks in Python API (subscription/site ownership)

**Timeline:** When the product goes to paying customers.

---

## Relevant OpenClaw Skills (from ClawHub)

| Skill | Relevance |
|-------|-----------|
| `uptime-kuma` | Uptime monitoring integration pattern |
| `web-perf` | Lighthouse/Core Web Vitals audit |
| SEO Audit (marketing library) | SEO expert recommendations |
| `seo-competitor-analysis` | Competitor SEO analysis |
| `aeo-prompt-research-free` | Answer Engine Optimization — maps to our AI citation tracking |
| SEO Content Autopilot (Citedy) | Shows cron + API integration pattern |

---

## Security Considerations

- Gateway auth credentials = root access to the agent. Keep on loopback/Tailscale only.
- `POST /tools/invoke` is full operator access — hard deny list blocks exec/shell/fs_write by default.
- Webhook endpoints (`/hooks/*`) use a dedicated hook token, not per-user auth.
- Our Python API must enforce authorization (subscription checks, site ownership) — don't rely on OpenClaw channel allowlists alone.
- Untrusted web content (HTML from scans) flows into LLM prompts — assume prompt injection attempts.
- Local Ollama models need strong context/guardrails (quantized models are more susceptible).

---

## What We Need from Gurbachan

1. **Install OpenClaw Gateway** on seo-dev server (port 18789)
   - `openclaw gateway install` + systemd service, OR
   - Provide install instructions so Troy can do it
2. **Share the gateway auth token** for API access
3. **Pair at least one channel** (WhatsApp QR recommended for demo)
4. **Confirm Ollama provider config** — OpenClaw should use `http://192.168.2.200:11434` with native Ollama API (not /v1 OpenAI-compatible URL, which breaks tool calling)

---

## Files Ready for Integration

| File | Purpose | Status |
|------|---------|--------|
| `agents/monitor_agent.py` | Agent orchestrator with AGENT_CONFIG | Ready |
| `ai_inference.py` | Tiered model inference (fast/standard/heavy) | Ready |
| `tools/ai_analyzer.py` | Conversational AI analysis (7 methods) | Ready |
| `tools/notifier.py` | Multi-channel alert delivery | Ready |
| `tools/seo_scanner.py` | 231-check SEO analysis | Ready |
| `tools/uptime_monitor.py` | Uptime + SSL monitoring | Ready |
| `tools/content_monitor.py` | Content change detection | Ready |
| `tools/ai_citation_tracker.py` | AI visibility scoring | Ready |
| `tools/competitor_monitor.py` | Competitor benchmarking | Ready |
| `tools/transaction_monitor.py` | Form + API testing | Ready |
| `tools/conversation_handler.py` | Chat session management | Ready |
| `.env` | `OPENCLAW_API_URL=http://127.0.0.1:18789` | Configured |
