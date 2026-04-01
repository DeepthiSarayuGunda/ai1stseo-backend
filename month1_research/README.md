# Month 1 — Research & Platform Mastery

All 8 non-negotiable deliverables from the 6-Month Blueprint, implemented as Python scripts
that call the existing AI1stSEO backend API. No existing files were modified.

## Deliverables

| # | File | Blueprint Deliverable |
|---|------|-----------------------|
| 1 | `keyword_universe.py` | Master Keyword Universe — 200 natural-language queries, categorised by intent, format, commercial value, topic cluster |
| 2 | `benchmark_runner.py` | Benchmark Brand Research Report — full tool outputs for 5 brands (GEO, AEO, E-E-A-T, Site Detection, Cross-Model) |
| 3 | `provider_behaviour.py` | Provider Behaviour Guide — empirical analysis of Nova, Ollama, Claude, Groq, OpenAI, Gemini, Perplexity |
| 4 | `answer_format_taxonomy.py` | Answer Format Taxonomy — 8 proven formats with structural requirements and schema |
| 5 | `geo_baseline.py` | Month 1 GEO Baseline — geo_score + visibility_score for brand vs competitors |
| 6 | `monitoring_activator.py` | Scheduled Monitoring Jobs — weekly Nova, 3-day competitive, weekly Ollama |
| 7 | `eeat_gap_register.py` | E-E-A-T Gap Register — all authority signal gaps, prioritised with remediation |
| 8 | `technical_debt_register.py` | Technical Debt Register — 236-check findings with AI crawlability impact |

## Shared Modules

| File | Purpose |
|------|---------|
| `api_client.py` | HTTP client wrapping all backend API endpoints with retry logic |
| `utils.py` | Output directory management, JSON save/load, display helpers |
| `run_month1.py` | Master orchestrator — runs all 8 deliverables in sequence |

## Quick Start

```bash
# 1. Set your backend URL
export API_BASE_URL=http://localhost:5000
# Or for deployed: export API_BASE_URL=https://your-backend.com

# 2. Run everything at once
python month1_research/run_month1.py \
  --brand "AI1stSEO" \
  --url "https://ai1stseo.com" \
  --topic "AI SEO optimization" \
  --competitors "SEMrush,Ahrefs" \
  --visibility-brands "HubSpot,Moz" \
  --brand-pages "https://ai1stseo.com/,https://ai1stseo.com/features"
```

## Run Individual Deliverables

```bash
# Keyword Universe (run first — other scripts load from it)
python month1_research/keyword_universe.py \
  --brand "AI1stSEO" --topic "AI SEO optimization"

# Benchmark Research
python month1_research/benchmark_runner.py \
  --brand "AI1stSEO" --competitors "SEMrush,Ahrefs" \
  --visibility-brands "HubSpot,Moz"

# Provider Behaviour Guide
python month1_research/provider_behaviour.py \
  --brand "AI1stSEO"

# Answer Format Taxonomy
python month1_research/answer_format_taxonomy.py \
  --brand "AI1stSEO" --topic "AI SEO optimization"

# GEO Baseline
python month1_research/geo_baseline.py \
  --brand "AI1stSEO" --competitors "SEMrush,Ahrefs"

# Monitoring Activation
python month1_research/monitoring_activator.py --brand "AI1stSEO"

# E-E-A-T Gap Register
python month1_research/eeat_gap_register.py \
  --brand "AI1stSEO" \
  --pages "https://ai1stseo.com/,https://ai1stseo.com/features"

# Technical Debt Register
python month1_research/technical_debt_register.py \
  --url "https://ai1stseo.com"
```

## Output

All results are saved as timestamped JSON files in `month1_research/output/`:

```
output/
  keyword_universe_20260330_120000.json
  benchmark_report_20260330_121500.json
  provider_behaviour_guide_20260330_130000.json
  answer_format_taxonomy_20260330_140000.json
  geo_baseline_20260330_150000.json
  monitoring_activation_20260330_160000.json
  eeat_gap_register_20260330_170000.json
  technical_debt_register_20260330_180000.json
  month1_summary_20260330_190000.json
```

## How It Integrates

These scripts call the existing backend API — they don't modify any existing files.
The API client (`api_client.py`) wraps every endpoint from `app.py`:

- `/api/geo-probe/batch` → Batch GEO probes
- `/api/geo-probe/compare` → Cross-model visibility compare
- `/api/geo-probe/site` → Site/URL detection
- `/api/geo-probe/schedule` → Scheduled monitoring
- `/api/geo-probe/trend` → Visibility trend
- `/api/aeo/analyze` → AEO page analysis
- `/api/ai/ranking-recommendations` → E-E-A-T analysis
- `/api/content/generate` → Content generation pipeline
- `/api/analyze` → Full 236-check SEO audit
- `/api/llm/citation-probe` → Multi-provider citation probe
- `/api/geo/model-comparison` → Model disagreement detection
