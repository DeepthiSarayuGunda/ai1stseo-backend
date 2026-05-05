# AEO Rank Tracker — Frontend Integration Guide

Backend: **STABLE / LOCKED** — no further changes required.

## Endpoints

### POST /api/aeo-tracker/run

Trigger a multi-LLM citation scan.

**Request:**
```json
{
  "brand_name": "AI1stSEO",
  "target_domain": "ai1stseo.com",
  "queries": [
    "best SEO tools",
    "top AI marketing platforms",
    "how to improve website ranking"
  ]
}
```

`queries` is required (1–20 items). `llms` is optional — omit it to auto-detect available providers.

**Response:**
```json
{
  "status": "ok",
  "scan_id": "uuid-string",
  "active_llms": ["gemini", "ollama"],
  "results": [
    {
      "query": "best SEO tools",
      "llm": "gemini",
      "citation_found": true,
      "match_type": "brand_mention",
      "matches": ["brand:AI1stSEO"],
      "response_snippet": "First 300 chars of LLM response...",
      "sources": ["https://example.com"],
      "brand_name": "AI1stSEO",
      "target_domain": "ai1stseo.com",
      "timestamp": "2026-04-30T12:00:00+00:00",
      "scan_id": "uuid-string",
      "mock": false
    }
  ],
  "summary": {
    "visibility_score": 42.0,
    "best_llm": "gemini",
    "top_query": "best SEO tools",
    "llm_performance": {
      "gemini": { "total": 3, "cited": 2, "rate": 66.7 }
    },
    "query_performance": {
      "best SEO tools": { "total": 2, "cited": 1, "rate": 50.0 }
    },
    "total_scanned": 6,
    "total_cited": 3,
    "active_llms": ["gemini", "ollama"],
    "skipped_llms": {
      "openai": "OPENAI_API_KEY not set",
      "claude": "ANTHROPIC_API_KEY not set",
      "perplexity": "PERPLEXITY_API_KEY not set"
    },
    "errors_by_llm": {},
    "scan_id": "uuid-string",
    "brand_name": "AI1stSEO",
    "target_domain": "ai1stseo.com",
    "timestamp": "2026-04-30T12:00:00+00:00"
  }
}
```

### GET /api/aeo-tracker/history

Retrieve stored scan results.

**Query params:** `query`, `llm`, `brand`, `limit` (default 50)

**Response:**
```json
{
  "status": "ok",
  "count": 12,
  "results": [ /* same shape as results[] above */ ]
}
```

### GET /api/aeo-tracker/summary

Aggregated analytics from stored results.

**Query params:** `brand`, `limit` (default 100)

**Response:**
```json
{
  "status": "ok",
  "summary": {
    "visibility_score": 42.0,
    "best_llm": "gemini",
    "top_query": "best SEO tools",
    "llm_performance": { ... },
    "query_performance": { ... },
    "total_scanned": 20,
    "total_cited": 8
  }
}
```

### GET /api/aeo-tracker/providers

Check which LLM providers are active.

**Response:**
```json
{
  "status": "ok",
  "active": ["gemini", "ollama"],
  "skipped": {
    "openai": "OPENAI_API_KEY not set",
    "claude": "ANTHROPIC_API_KEY not set",
    "perplexity": "PERPLEXITY_API_KEY not set"
  },
  "priority_order": ["gemini", "openai", "claude", "perplexity", "ollama", "mock"]
}
```

## Key Fields for Frontend

| Field | Type | Description |
|-------|------|-------------|
| `results[]` | array | One entry per query × LLM combination |
| `results[].citation_found` | bool | Whether brand/domain was cited |
| `results[].mock` | bool | Whether this used simulated data |
| `results[].match_type` | string/null | `brand_mention`, `domain_mention`, `brand_and_domain`, `url_citation`, `source_citation` |
| `summary.visibility_score` | float | Overall citation rate (0–100) |
| `summary.best_llm` | string | LLM with highest citation rate |
| `summary.top_query` | string | Query with highest citation rate |
| `summary.llm_performance` | object | Per-LLM stats: `{total, cited, rate}` |
| `summary.query_performance` | object | Per-query stats: `{total, cited, rate}` |
| `active_llms` | array | Providers used in this scan |
| `summary.skipped_llms` | object | Providers skipped with reasons |
| `summary.errors_by_llm` | object | Runtime errors per provider |

## Environment Variables (Optional)

None are required. The system auto-detects and falls back to mock mode.

| Variable | Provider | Notes |
|----------|----------|-------|
| `GEMINI_API_KEY` | Google Gemini | Free tier available |
| `OPENAI_API_KEY` | ChatGPT | Paid |
| `ANTHROPIC_API_KEY` | Claude | Paid |
| `PERPLEXITY_API_KEY` | Perplexity | Paid |
| `OLLAMA_URL` | Ollama (local) | Default: `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model | Default: `llama3` |

## Safety Guarantees

- No API keys → mock mode runs automatically
- DB write fails → scan still returns results (logged, not crashed)
- Any LLM fails → skipped, error logged in `errors_by_llm`, scan continues
- All errors return `{"error": "...", "status": "error"}` with appropriate HTTP codes
