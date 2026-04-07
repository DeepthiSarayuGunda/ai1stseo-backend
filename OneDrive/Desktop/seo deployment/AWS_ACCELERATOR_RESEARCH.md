# AWS H100/H200 GPU Accelerator Research

**Author:** Troy Sauriol (Dev 3) | **Date:** April 15, 2026
**Context:** Gurbachan offered 4-5 hours of accelerator time for the team to learn and experiment.

---

## Pricing Summary

| Instance | GPU | GPUs | vCPUs | RAM | On-Demand $/hr | 5 hrs cost |
|----------|-----|------|-------|-----|----------------|------------|
| p5.4xlarge | H100 | 1 | 16 | 256 GB | ~$6.88 | ~$34 |
| p5.48xlarge | H100 | 8 | 192 | 2 TB | ~$98.32 | ~$492 |
| p5e.48xlarge | H200 | 8 | 192 | 2 TB | ~$49.75 | ~$249 |

Spot instances can reduce costs by 60-70% but may be interrupted. Capacity Blocks (pre-reserved) are available for planned workloads.

Sources: [AWS EC2 Pricing](https://aws.amazon.com/ec2/pricing/on-demand/), [AWS Capacity Blocks](https://aws.amazon.com/ec2/capacityblocks/pricing/)

---

## Recommendation: Use p5.4xlarge (single H100)

For our 4-5 hour budget, a single H100 at ~$7/hr ($35 total) gives us enough power to run Llama 3.1 70B or Qwen 72B locally and batch-process thousands of pages. The 8-GPU instances are overkill for our workload and would burn through the budget in under an hour.

---

## Proposed Use Cases by Developer

### Dev 1 — Deepthi (AI/ML)
- Batch GEO probes across all 4 AI models simultaneously for the Ottawa business directory
- Run the 235B Qwen model for deep citation analysis on directory listings
- Train/fine-tune a small classifier for AI citation prediction

### Dev 2 — Samarveer (Content & NLP)
- Batch-analyze top 100 websites per business category to extract "perfect template" patterns
- Run TF-IDF clustering across thousands of pages at once
- Generate benchmark data for AEO/GEO/SEO scoring templates

### Dev 3 — Troy (Infrastructure)
- Batch-process site monitor scans across all monitored sites simultaneously
- Run the heavy tier (235B) analysis on competitor datasets
- Benchmark inference latency across model sizes for tiered routing optimization

### Dev 4 — Tabasum (Integrations)
- Batch-generate social media content for multiple platforms simultaneously
- Test multi-modal content generation (text + image descriptions)

### Dev 5 — Amira (Frontend)
- Generate sample audit data at scale for dashboard testing
- Batch-create PDF reports for demo/investor presentations

---

## Recommended Approach

1. Use a single p5.4xlarge (1x H100, ~$7/hr)
2. Pre-prepare all batch jobs before starting the instance
3. Run Samarveer's template benchmarking first (highest value — directly supports Gurbachan's directive)
4. Then Deepthi's GEO batch probes
5. Then Troy's competitor analysis batch
6. Total estimated time: 3-4 hours, cost: ~$25-30
7. Shut down immediately when done

---

## What NOT to Use Accelerators For

- Real-time API calls (Nova Lite is cheaper and fast enough)
- Development/debugging (use the local Ollama accelerator on seo-dev instead)
- Running the website or any production services
- Anything that can run on the existing Ollama setup (8B/30B models)

---

## Alternative: Gurbachan's Local Accelerator

We already have access to a 235B parameter model on the local Ollama server (192.168.2.200). For most tasks, this is sufficient and free. The AWS H100 is only worth it for:
- Workloads that need to run faster than the local server can handle
- Batch jobs that would take days on the local server but hours on H100
- Running models larger than what fits in the local server's memory
