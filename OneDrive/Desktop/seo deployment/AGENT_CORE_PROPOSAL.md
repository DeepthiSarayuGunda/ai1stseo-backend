# Agent Core Analysis & Multi-Agent Backend Proposal
## AI First SEO — Optimal Backend Agent Architecture
### Prepared by Troy | March 17, 2026

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

## 7. NVIDIA NeMo / Nemotron Relevance

NVIDIA's ecosystem is relevant in two ways:

1. **Llama Nemotron models** — NVIDIA-optimized versions of Llama specifically tuned for agentic workflows. These could replace our Ollama Llama 3.1 for better agent task performance at the same self-hosted cost.

2. **NeMo Agent Toolkit** — Production framework for deploying agents as APIs with observability, evaluation, and monitoring. Worth evaluating for Phase 2 when we need production monitoring.

3. **NIM (NVIDIA Inference Microservices)** — Containerized model serving that's faster than Ollama. Could upgrade our self-hosted inference.

**Recommendation:** Review relevant GTC 2026 sessions (Troy's task #3) for latest Nemotron agent capabilities, then evaluate for Phase 2.

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
| **State Management** | Redis | Fast, simple, on EC2 |
| **Deployment** | Existing EC2 | No new infra needed |

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
