# Agent Core Analysis & Multi-Agent Backend Proposal
## AI First SEO — Optimal Backend Agent Architecture
### Prepared by Troy | March 17, 2026
### Updated: March 17, 2026 — Added NVIDIA NemoClaw & NeMo Agent Toolkit analysis (GTC 2026)
### Updated: March 19, 2026 — Added project context, conclusion & monetization recommendation

---

## 0. Project Context — What is AI 1st SEO?

**AI 1st SEO** (ai1stseo.com) is a web-based platform that helps website owners optimize their sites for both traditional search engines (SEO) and AI-powered search/answer engines (AEO — Answer Engine Optimization, GEO — Generative Engine Optimization). The project is built by a team of 5 (Troy, Tabasum, Deepthi, Amira, Samarveer) under the guidance of instructor Gurbachan.

### What the Platform Does Today

The platform currently offers:

- **SEO Audit Tool** (seoaudit.ai1stseo.com) — Runs 231 automated checks across 9 categories (Technical SEO, On-Page SEO, Content SEO, Mobile, Performance, Security, Social/Open Graph, Local SEO, and GEO/AEO) against any URL. Returns a scored report with prioritized recommendations.
- **SEO Analysis Tool** (seoanalysis.ai1stseo.com) — Deeper analysis with AI-generated recommendations powered by Ollama/Llama 3.1 running locally on EC2.
- **Site Monitor Microproject** (monitor.ai1stseo.com) — A standalone monitoring dashboard that tracks uptime, content changes, AI citation visibility, and SEO health for subscribed sites. Includes email report subscriptions via AWS SES.
- **Implementation Guides** (ai1stseo.com/guides) — Step-by-step AEO/SEO guides for website owners to implement improvements themselves.
- **Doc Summarizer** (docsummarizer.ai1stseo.com) — AI-powered document summarization tool.
- **Automation Hub** (automationhub.ai1stseo.com) — Central hub for automated SEO workflows.

### Tech Stack

- **Frontend:** Static HTML/JS served via AWS CloudFront (CDN) from S3
- **Backend:** Python/Flask on EC2 (t3.medium, 54.226.251.216), 6 PM2-managed services
- **Auth:** AWS Cognito user pool with SES email integration (no-reply@ai1stseo.com)
- **DNS:** Route 53 (migrated from Cloudflare), domain registered at Spaceship.com
- **SSL:** Let's Encrypt (auto-renewing) for all EC2 subdomains, ACM cert for CloudFront
- **AI/ML:** Ollama running Llama 3.1 locally on EC2 for recommendations
- **Database:** DynamoDB (user data), JSON file storage (monitor subscriptions/history)
- **Email:** AWS SES (production access, 50k/day, domain-verified DKIM)

### What We're Trying to Accomplish Next

The current system **scans and reports** — it tells you what's wrong and suggests fixes. The next evolution is to make it **act autonomously**: scan a site, prioritize issues, generate platform-specific fix code (WordPress, Shopify, custom HTML), and optionally push those fixes directly via CMS APIs.

This requires moving from a single-model, single-prompt architecture (Llama 3.1 generating a text blob) to a **multi-agent system** where specialized AI agents handle different parts of the pipeline — scanning, content generation, code writing, and execution — coordinated by an orchestrator.

That's what this proposal addresses.

---

## 1. What is Agent Core?

"Agent Core" refers to the central orchestration layer that coordinates multiple specialized AI agents to perform complex, multi-step tasks autonomously. In our context, it's the backbone that would allow our SEO/AEO platform to go beyond static audits and into **automated detection + correction** across diverse web platforms.

Our existing system already has the foundation:
- `backend/app.py` runs 216 checks across 9 categories (Technical, On-Page, Content, Mobile, Performance, Security, Social, Local, GEO/AEO)
- Ollama + Llama 3.1 generates AI recommendations via `/api/ai-recommendations`
- The `GEO/orchestrator_agent.py` template defines a LangGraph-based multi-agent workflow

The gap: our current system **scans and reports** but doesn't **act**. Agent Core bridges that gap.

---

## 2. Model Evaluation: Gemini Flash vs Nova Micro vs Nemo

### Comparison Matrix

| Criteria | Gemini 2.0 Flash | Amazon Nova Micro | NVIDIA Llama Nemotron |
|----------|------------------|-------------------|----------------------|
| **Input Cost** | $0.10/M tokens | $0.035/M tokens | Free (self-hosted) |
| **Output Cost** | $0.40/M tokens | $0.14/M tokens | Free (self-hosted) |
| **Context Window** | 1M tokens | 128K tokens | 128K tokens |
| **Modality** | Text + Image + Video | Text only | Text only |
| **Hosting** | Google Cloud API | AWS Bedrock | Self-hosted (Ollama/NIM) |
| **Latency** | ~200ms TTFT | ~150ms TTFT | Depends on GPU |
| **Best For** | Complex analysis, multimodal | High-volume, low-cost tasks | On-prem, full control |
| **Free Tier** | 15 RPM, 1000 RPD | None (pay-per-use) | Unlimited (self-hosted) |
| **Agent Framework** | LangChain/LangGraph | AWS Bedrock Agents | NeMo Agent Toolkit |

### Cost Analysis (1000 audits/month, ~50K tokens per audit)

| Model | Input Cost | Output Cost | Monthly Total |
|-------|-----------|-------------|---------------|
| Gemini 2.0 Flash | $5.00 | $20.00 | **$25/mo** |
| Gemini 2.5 Flash | $15.00 | $125.00 | **$140/mo** |
| Nova Micro | $1.75 | $7.00 | **$8.75/mo** |
| Llama 3.1 (Ollama) | $0 | $0 | **$0 (EC2 cost only)** |
| Llama Nemotron | $0 | $0 | **$0 (EC2 cost only)** |

---

## 3. Recommended Architecture: Hybrid Multi-Model Approach

Rather than picking one model, the optimal setup uses **different models for different agent roles** based on their strengths:

```
┌─────────────────────────────────────────────────────┐
│              ORCHESTRATOR (LangGraph)                │
│         Coordinates all agents, manages state        │
│              Model: Gemini 2.0 Flash                 │
│     (cheap, fast, 1M context for full-site view)     │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│   SCANNER    ││  CONTENT     ││  EXECUTOR    │
│   AGENTS     ││  AGENTS      ││  AGENTS      │
│              ││              ││              │
│ Nova Micro   ││ Gemini Flash ││ Nova Micro   │
│ (cheapest,   ││ (best for    ││ (fast, cheap │
│  fast parse) ││  writing)    ││  API calls)  │
└──────────────┘└──────────────┘└──────────────┘
        │              │              │
        ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│ Technical    ││ Rewrite meta ││ Push fixes   │
│ On-Page      ││ Generate FAQ ││ via CMS API  │
│ GEO/AEO      ││ Author bios  ││ WordPress    │
│ Security     ││ Schema gen   ││ Shopify etc  │
│ Social/Local ││              ││              │
└──────────────┘└──────────────┘└──────────────┘
```

### Why This Hybrid Approach?

1. **Orchestrator → Gemini 2.0 Flash**: Needs to see the full picture (all scan results, priorities, dependencies). The 1M token context window is unmatched. At $0.10/M input, it's dirt cheap for coordination.

2. **Scanner Agents → Nova Micro**: These do structured parsing (check if header exists, count words, validate schema). They don't need creative intelligence — just fast, accurate extraction. At $0.035/M input, Nova Micro is 3x cheaper than Gemini Flash.

3. **Content Agents → Gemini Flash**: Writing meta descriptions, generating FAQ sections, creating schema markup — these need quality output. Gemini Flash balances quality and cost well here.

4. **Executor Agents → Nova Micro**: API calls to WordPress/Shopify don't need intelligence — they need speed and reliability. Nova Micro's low latency is ideal.

5. **Fallback → Llama 3.1 (Ollama on EC2)**: Already running on our EC2 instance. Zero marginal cost. Use for non-critical tasks or when API budgets are tight.

---

## 4. Agent Framework Recommendation: LangGraph

### Why LangGraph over CrewAI or AutoGen?

| Factor | LangGraph | CrewAI | AutoGen |
|--------|-----------|--------|---------|
| **State Management** | Explicit typed state | Implicit | Conversation-based |
| **Control Flow** | Graph-based (precise) | Sequential/hierarchical | Conversational |
| **Production Ready** | Yes (used by major cos) | Growing | Enterprise version |
| **Debugging** | Excellent (graph viz) | Limited | Moderate |
| **Our Existing Code** | Already templated | Would need rewrite | Would need rewrite |
| **Python Native** | Yes | Yes | Yes |
| **Rollback Support** | Built-in checkpoints | Manual | Manual |

**LangGraph wins because:**
- We already have `GEO/orchestrator_agent.py` built on it
- Graph-based workflows map perfectly to our scan → prioritize → execute → validate pipeline
- Built-in state persistence means we can pause/resume long audits
- Checkpoint system enables rollback if corrections fail
- Works with any LLM provider (Gemini, Nova, Ollama)

---

## 5. Implementation Plan (Phase 1 MVP)

### What to Build First (2-3 weeks)

**Goal:** Replace the current single-prompt Llama 3.1 recommendation system with a multi-agent pipeline that can scan, prioritize, and generate platform-specific fix instructions.

```python
# Phase 1 Architecture
Agents:
  1. Orchestrator Agent (Gemini Flash)
     - Receives URL + audit results from existing app.py
     - Coordinates scanner and content agents
     
  2. Technical Scanner Agent (Nova Micro)
     - Reuses existing analyze_technical_seo() logic
     - Outputs structured JSON findings
     
  3. GEO Scanner Agent (Nova Micro)  
     - Reuses existing analyze_geo_aeo() logic
     - Outputs AI-readiness report
     
  4. Recommendation Agent (Gemini Flash)
     - Takes prioritized findings
     - Generates platform-specific fix instructions
     - Produces code snippets ready to implement
     
  5. Report Agent (Nova Micro)
     - Compiles final report
     - Generates before/after projections
```

### Integration with Existing Backend

```
Current Flow:
  User → app.py → analyze_*() functions → JSON results → Llama 3.1 → recommendations

New Flow:
  User → app.py → analyze_*() functions → JSON results
                                              ↓
                                    LangGraph Orchestrator
                                              ↓
                                    Scanner Agents (validate/enrich)
                                              ↓
                                    Prioritization (Gemini Flash)
                                              ↓
                                    Recommendation Agent (Gemini Flash)
                                              ↓
                                    Structured report with code snippets
```

### Files to Create

```
backend/
  agents/
    __init__.py
    orchestrator.py      # LangGraph workflow definition
    scanner_agent.py     # Wraps existing analyze_*() functions
    content_agent.py     # Generates fixes, rewrites, schema
    report_agent.py      # Compiles final output
  config/
    models.py            # Model configs (Gemini, Nova, Ollama)
    prompts.py           # Agent system prompts
```

---

## 6. AWS Integration Points

Since we're already on AWS (EC2 at 54.226.251.216):

- **Nova Micro** → AWS Bedrock (same region, low latency)
- **Gemini Flash** → Google AI API (external, but fast)
- **Ollama/Llama 3.1** → Already on EC2 (zero cost fallback)
- **State Storage** → Redis on EC2 or ElastiCache
- **Audit Logs** → DynamoDB or PostgreSQL on RDS

### Required AWS Services
- **Bedrock** — Nova Micro access (needs IAM role)
- **SSO login** — Required for Bedrock API access
- **Existing EC2** — Already running, just add agent code

---

## 7. NVIDIA NemoClaw & NeMo Agent Toolkit — GTC 2026 Deep Dive

> Updated March 17, 2026 after reviewing Jensen Huang's GTC 2026 keynote and official NVIDIA documentation.

### 7.1 What is NemoClaw?

NemoClaw is NVIDIA's open-source enterprise AI agent platform, announced at GTC 2026 (March 15-19). It wraps the viral open-source project OpenClaw with enterprise-grade security, privacy, and sandboxing — turning autonomous AI agents into something companies can actually deploy safely.

Key quote from Jensen Huang: "OpenClaw is the operating system for personal AI. This is the beginning of a new renaissance in software."

NemoClaw is NOT a competitor to OpenClaw — it's a hardened layer on top of it. Think of OpenClaw as the engine and NemoClaw as the enterprise vehicle built around it.

Sources: [NVIDIA Official Announcement](https://nvidianews.nvidia.com/news/nvidia-announces-nemoclaw), [NVIDIA Developer Blog](https://developer.nvidia.com/blog/run-autonomous-self-evolving-agents-more-safely-with-nvidia-openshell/), [NVIDIA NemoClaw Docs](https://docs.nvidia.com/nemoclaw/latest/index.html)

### 7.2 NemoClaw Architecture (3 Core Components)

```
┌─────────────────────────────────────────────────────────┐
│                    NemoClaw Stack                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  nemoclaw CLI (TypeScript plugin)               │    │
│  │  Entry point — onboard, setup, launch commands  │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Blueprint (versioned Python artifact)          │    │
│  │  Orchestrates sandbox, policy, inference setup  │    │
│  │  Digest-verified, immutable, reproducible       │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │  OpenShell Runtime (NVIDIA Agent Toolkit)       │    │
│  │                                                 │    │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────┐  │    │
│  │  │ Sandbox  │ │ Policy   │ │ Privacy Router │  │    │
│  │  │ (Docker  │ │ Engine   │ │ (routes to     │  │    │
│  │  │  isola-  │ │ (network,│ │  local or      │  │    │
│  │  │  tion)   │ │  fs, proc│ │  cloud models) │  │    │
│  │  │          │ │  control)│ │                │  │    │
│  │  └──────────┘ └──────────┘ └────────────────┘  │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  Models: Nemotron 3 Super 120B (default), swappable     │
│  License: Apache 2.0 (fully open source)                │
│  Hardware: NVIDIA GPUs, but hardware-agnostic            │
└─────────────────────────────────────────────────────────┘
```

The three pillars:

1. **Sandbox** — Docker-based isolation for long-running agents. Agents can break things inside the sandbox without touching the host. Filesystem restricted to `/sandbox` and `/tmp`. Skill development happens in isolation with verification before promotion.

2. **Policy Engine** — Out-of-process enforcement (not prompt-based). Controls network access (allowlist-only), filesystem permissions, process execution. The agent cannot override policies even if compromised. Live policy updates without restarting the sandbox.

3. **Privacy Router** — Routes inference requests based on YOUR policy, not the agent's preference. Sensitive data stays on-device with local Nemotron models; non-sensitive requests can route to cloud APIs (Claude, GPT, etc.). Model-agnostic by design.

### 7.3 NeMo Agent Toolkit (Separate but Related)

The NeMo Agent Toolkit ([GitHub](https://github.com/NVIDIA/AgentIQ)) is NVIDIA's open-source library for building, profiling, and optimizing multi-agent systems. It's framework-agnostic and works alongside LangChain, CrewAI, LlamaIndex, and custom agents.

Key capabilities relevant to us:
- **Framework Agnostic** — works with LangChain/LangGraph (our current choice)
- **Profiling** — profile entire workflows down to individual tokens to find bottlenecks
- **Observability** — trace execution flows in production
- **Evaluation System** — validate accuracy of agentic workflows
- **MCP Support** — publish workflows as MCP servers, integrate MCP tools
- **Agent-to-Agent (A2A) Protocol** — distributed agent teams with authentication
- **Agent Performance Primitives** — parallel execution, speculative branching for graph-based frameworks like LangGraph

Install: `pip install nemo-agent-toolkit` (requires Python 3.11+)

### 7.4 NemoClaw vs Our Current Proposal — Comparison

| Aspect | Our Current Plan (Section 3-5) | NemoClaw Approach |
|--------|-------------------------------|-------------------|
| **Agent Framework** | LangGraph (custom orchestrator) | OpenClaw + OpenShell (pre-built) |
| **Security** | None (agents run in-process) | Sandbox isolation, policy engine, out-of-process enforcement |
| **Inference** | Multi-model API calls (Gemini, Nova, Ollama) | Privacy router with local Nemotron + cloud fallback |
| **Cost** | ~$34/mo (API fees) | $0 for local inference (Nemotron), cloud optional |
| **Setup Complexity** | Build from scratch (weeks) | `npm install -g nemoclaw && nemoclaw onboard` |
| **Production Monitoring** | Manual logging | NeMo Agent Toolkit profiling + observability |
| **Hardware Needed** | Our existing EC2 (no GPU) | Needs NVIDIA GPU for local inference |
| **Maturity** | Custom code, untested | NVIDIA-backed, Apache 2.0, active community |
| **Our Existing Code** | Wraps our 216-check scanner | Would need adaptation to run inside sandbox |

### 7.5 Honest Assessment — Should We Use NemoClaw?

**What NemoClaw does well for us:**
- Enterprise-grade security we'd never build ourselves
- The privacy router solves the "which model for which task" problem we're solving manually in Section 3
- Zero-cost local inference with Nemotron models eliminates API fees
- The NeMo Agent Toolkit's profiling would help us optimize our multi-agent pipeline
- Apache 2.0 license means no vendor lock-in

**What doesn't fit (yet):**
- Our EC2 instance has NO GPU — NemoClaw's local inference needs NVIDIA hardware (RTX, DGX, or GPU instance)
- Our Python backend is 3.9 on EC2 — NeMo Agent Toolkit requires 3.11+
- NemoClaw is designed for always-on autonomous agents (claws) — our use case is request-response audits
- OpenClaw is a coding/task agent — we'd need to adapt it for SEO scanning, which is a different paradigm
- Brand new (literally announced 2 days ago) — docs are thin, community is forming

**Bottom line:** NemoClaw is the future direction, but it's not a drop-in replacement for our current plan. The NeMo Agent Toolkit, however, IS immediately useful — we can layer it on top of our LangGraph pipeline for profiling and observability without changing our architecture.

### 7.6 Recommended Integration Path

**Phase 1 (Now — stick with current plan):**
- Build the LangGraph multi-agent pipeline as described in Section 5
- Add NeMo Agent Toolkit for profiling and observability (`pip install nemo-agent-toolkit`)
- Use its evaluation system to validate agent output quality
- This works on our current EC2 with Python 3.11 upgrade

**Phase 2 (When GPU available):**
- Evaluate NemoClaw for the always-on monitoring agents (site-monitor use case)
- Replace Ollama with Nemotron via NIM for better self-hosted inference
- Use OpenShell sandbox for long-running monitoring tasks that need security isolation

**Phase 3 (Full migration):**
- Move the entire agent backend into NemoClaw/OpenShell
- Use privacy router to handle model selection automatically
- Deploy on GPU instance (g5.xlarge ~$1/hr) or DGX Spark if budget allows

### 7.7 Nemotron 3 Models (New at GTC 2026)

NemoClaw ships with Nemotron 3 Super 120B as the default model. The Nemotron family now includes:

| Model | Parameters | Best For | Notes |
|-------|-----------|----------|-------|
| Nemotron 3 Super 120B | 120B | Complex reasoning, orchestration | Default in NemoClaw, needs serious GPU |
| Nemotron 3 Nano | ~8B | Fast tasks, edge deployment | Could run on our EC2 with CPU (slow) |
| Nemotron (original) | 70B | General agent tasks | Already available via Ollama |

For our cost-sensitive setup, Nemotron 3 Nano is the most practical self-hosted option until we get GPU access.

---

## 8. Firm Proposal Summary

### Recommended Stack
| Component | Choice | Reason |
|-----------|--------|--------|
| **Agent Framework** | LangGraph | Already templated, best for our workflow |
| **Orchestrator Model** | Gemini 2.0 Flash | 1M context, $0.10/M, fast |
| **Scanner Model** | Amazon Nova Micro | $0.035/M, fastest, AWS-native |
| **Content Model** | Gemini 2.0 Flash | Best quality/cost for writing |
| **Fallback Model** | Llama 3.1 (Ollama) | Already deployed, zero cost |
| **Profiling/Observability** | NeMo Agent Toolkit | NVIDIA open-source, works with LangGraph |
| **State Management** | Redis | Fast, simple, on EC2 |
| **Deployment** | Existing EC2 | No new infra needed |
| **Future Direction** | NemoClaw + Nemotron | When GPU available (Phase 2-3) |

### Estimated Monthly Cost (1000 audits)
- Gemini Flash (orchestrator + content): ~$25/mo
- Nova Micro (scanners + executors): ~$9/mo  
- EC2 (already running): $0 incremental
- **Total: ~$34/month** for 1000 multi-agent audits

### vs Current System
- Current: Llama 3.1 only, single-prompt, no agent coordination, $0/mo but limited quality
- Proposed: Multi-model, multi-agent, specialized roles, ~$34/mo with dramatically better output

### Timeline
- **Week 1:** Set up Bedrock access, Gemini API key, create agent scaffolding
- **Week 2:** Implement orchestrator + scanner agents wrapping existing code
- **Week 3:** Add content/recommendation agent, integrate with app.py
- **Week 4:** Testing, optimization, deploy to EC2

---

## 9. Open Questions for Team Discussion

1. Do we want to keep Ollama/Llama 3.1 as the primary (free) and only use paid APIs for premium users?
2. Should we implement a credit/usage system for API-based agent runs?
3. Priority: WordPress executor first, or keep it recommendation-only for now?
4. Do we need real-time streaming of agent progress to the UI?
5. **NemoClaw GPU question:** Should we budget for a GPU instance (g5.xlarge ~$1/hr on-demand, ~$0.40/hr spot) to unlock NemoClaw + local Nemotron inference? This would eliminate API costs entirely but adds ~$300-700/mo in EC2 GPU costs.
6. **Python upgrade:** Our EC2 runs Python 3.9. NeMo Agent Toolkit needs 3.11+. Should we upgrade now (low risk) or wait until Phase 2?
7. **NemoClaw for site-monitor:** The OpenClaw site monitor already has an agent architecture. Should we pilot NemoClaw there first as a proof-of-concept before touching the main backend?
8. **Tabasum's multi-agent research:** How does NemoClaw compare to the approaches Tabasum is evaluating? Should we consolidate into one recommendation?

---

## 10. Conclusion & Recommendation

After evaluating all options — model costs, framework maturity, our existing codebase, and infrastructure constraints — the clear path forward is the **hybrid LangGraph approach**.

**Use Gemini 2.0 Flash** as the orchestrator and content generation model, **Amazon Nova Micro** for high-volume scanner and executor agents, and **Llama 3.1 via Ollama** as the zero-cost fallback. This gives us multi-agent capabilities at ~$34/month for 1,000 audits, running entirely on our existing EC2 instance with no new infrastructure.

This is the right call because:
- We already have the LangGraph orchestrator template (`GEO/orchestrator_agent.py`) ready to build on
- Our 231-check scanner in `app.py` is ready to wrap as agent tools — no rewrite needed
- Everything runs on existing EC2 — no GPU, no new services, no additional AWS costs beyond API fees
- NeMo Agent Toolkit can be layered on for profiling and observability once we upgrade to Python 3.11

**NemoClaw is the future direction**, but it requires GPU hardware we don't have and is too new (days old) to depend on for production. We revisit it in Phase 2 when GPU access is available.

**Monetization strategy:** Consider keeping Ollama/Llama 3.1 as the default for free-tier users and only routing through paid APIs (Gemini/Nova) for premium users. This keeps operating costs at zero until there's revenue, and creates a natural upsell — free users get basic recommendations, paid users get multi-agent, platform-specific fix instructions with code snippets. This aligns cost with value.

**Immediate next step:** Team consensus on this approach, then Week 1 begins with Bedrock access setup and Gemini API key provisioning.
