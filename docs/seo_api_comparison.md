# SEO API Integration Research: Ahrefs vs SEMrush

## API Overview

### Ahrefs API v3
- **Base URL:** `https://api.ahrefs.com/v3`
- **Authentication:** Bearer token (API key in `Authorization` header)
- **Response Format:** JSON
- **Rate Limit:** 60 requests/minute (default), dynamic throttling under load
- **Unit System:** API units per request (minimum 50 units per request)
- **Free Testing:** Test queries available using keywords `ahrefs` or `wordcount`

### SEMrush API
- **Base URL:** `https://api.semrush.com/`
- **Authentication:** API key as query parameter (`?key=YOUR_KEY`)
- **Response Format:** CSV (Standard API), JSON (Trends/Projects API)
- **Rate Limit:** 10 requests/second per IP
- **Unit System:** 1 API unit per line of data returned
- **Free Testing:** None (units consumed on every call)

---

## Comparison Table

| Feature | Ahrefs | SEMrush |
|---|---|---|
| **Authentication** | Bearer token (header) | API key (query param) |
| **Response Format** | JSON | CSV (Standard), JSON (Projects) |
| **Keyword Data** | Keywords Explorer: volume, difficulty, CPC, clicks, CPS, intents, SERP features, parent topic, traffic potential | Keyword Overview: volume, CPC, competition, trends, SERP features, intent, number of results |
| **Backlinks** | Site Explorer: full backlink profiles, referring domains, anchors, new/lost links | Backlink Analytics: backlink profiles, referring domains, anchors, new/lost |
| **Site Audit** | Site Audit API: health scores, issue reports, crawled page content | Projects API: site audit campaigns, issue tracking |
| **Domain Authority** | Domain Rating (DR) via Site Explorer/Batch Analysis | Authority Score via Domain Overview |
| **SERP Data** | SERP Overview: top 100 results per keyword | Organic Research: SERP positions, competitors |
| **Rank Tracking** | Rank Tracker API (project-based, free endpoints) | Position Tracking API (project-based) |
| **Keyword Ideas** | Matching terms, related terms, search suggestions | Keyword Magic Tool, related keywords |
| **Batch Requests** | Up to 100 targets per request (Batch Analysis) | Multiple keywords per call (comma-separated) |
| **AI Search Data** | Brand Radar: AI agent citations | Trends API: AI search traffic (ChatGPT, Gemini, Copilot) |
| **Rate Limit** | 60 req/min | 10 req/sec (~600 req/min) |
| **Min Cost Per Request** | 50 units | 1 unit per line |
| **Pricing Entry Point** | Enterprise plan ~$1,249/mo (includes 2M units) or separate API subscription $500-$10,000/mo | Business plan ~$499.95/mo + separate API unit packages |
| **Free Tier/Trial** | Free test queries (limited keywords) | No free API tier; 14-day trial of Business plan |
| **SDK/Libraries** | No official SDK; REST API with OpenAPI spec | No official SDK; REST API |
| **Serverless Compatible** | Yes (stateless HTTP) | Yes (stateless HTTP) |

---

## Recommendation: SEMrush

**Primary API choice: SEMrush Standard API**

### Rationale

1. **Cost Efficiency**
   - SEMrush Business plan starts at ~$499.95/mo vs Ahrefs Enterprise at ~$1,249/mo
   - SEMrush charges 1 unit per line of data (granular), while Ahrefs has a 50-unit minimum per request
   - SEMrush API units can be purchased as separate add-on packages, giving more budget control
   - Lower barrier to entry for startups and small teams

2. **Data Richness**
   - Both platforms offer comparable keyword, backlink, and domain data
   - SEMrush provides additional advertising research (PLA, ad history) useful for full-funnel SEO
   - SEMrush Trends API adds traffic analytics and market intelligence
   - SEMrush includes search intent classification in keyword data
   - Ahrefs has an edge in backlink data quality and unique metrics (clicks, CPS, traffic potential)

3. **Ease of Integration**
   - SEMrush API uses simple query-parameter authentication (no header management)
   - Higher rate limit (10 req/sec vs 60 req/min) means better throughput for batch operations
   - CSV response format is lightweight and easy to parse
   - Well-documented endpoint structure with clear parameter naming

### When to Consider Ahrefs Instead
- If backlink analysis is the primary use case (Ahrefs has the largest backlink index)
- If you need JSON responses natively (SEMrush Standard API returns CSV)
- If you already have an Ahrefs Enterprise subscription
- If you need Brand Radar / AI citation monitoring

---

## API Endpoints Reference

### SEMrush Key Endpoints (Recommended)

| Endpoint | Method | Path | Description |
|---|---|---|---|
| Keyword Overview | GET | `/?type=phrase_this&key=KEY&phrase=KEYWORD&database=us` | Single keyword metrics |
| Keyword Overview (All DBs) | GET | `/?type=phrase_all&key=KEY&phrase=KEYWORD` | Keyword data across all databases |
| Domain Overview | GET | `/?type=domain_ranks&key=KEY&domain=DOMAIN` | Domain authority and traffic |
| Organic Keywords | GET | `/?type=domain_organic&key=KEY&domain=DOMAIN&database=us` | Keywords a domain ranks for |
| Backlinks Overview | GET | `/?type=backlinks_overview&key=KEY&target=DOMAIN` | Backlink summary |
| Keyword Difficulty | GET | `/?type=phrase_kdi&key=KEY&phrase=KEYWORD&database=us` | Keyword difficulty score |

### Ahrefs Key Endpoints (Alternative)

| Endpoint | Method | Path | Description |
|---|---|---|---|
| Keywords Overview | GET | `/v3/keywords-explorer/overview` | Keyword metrics (volume, difficulty, CPC) |
| Matching Terms | GET | `/v3/keywords-explorer/matching-terms` | Keyword ideas |
| Organic Keywords | GET | `/v3/site-explorer/organic-keywords` | Domain organic keywords |
| Backlinks | GET | `/v3/site-explorer/backlinks` | Full backlink data |
| Domain Rating | GET | `/v3/site-explorer/overview` | DR and domain metrics |
| Batch Analysis | GET | `/v3/batch-analysis/overview` | Bulk domain/URL metrics |

---

## Sources
- [Ahrefs API Documentation](https://docs.ahrefs.com/api/docs/introduction)
- [SEMrush API Documentation](https://developer.semrush.com/api/basics/introduction/)
- [Ahrefs Pricing](https://ahrefs.com/blog/ahrefs-pricing/)
- [SEMrush Pricing](https://masterblogging.com/semrush-pricing/)

Content was rephrased for compliance with licensing restrictions.
