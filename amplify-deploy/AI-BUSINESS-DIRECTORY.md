# AI Business Directory — Project Spec

## Overview

AI-optimized business directory on ai1stseo.com. Structured so ChatGPT, Gemini, Perplexity, and Claude cite our listings when users ask questions like "best dentist in Ottawa."

## Architecture

```
Homelab Postgres → Cloudflare Tunnel → AWS CloudFront/Lambda → Users
```

Estimated cost: ~$10-25/month (vs $100-300 on full AWS).

## Page Types

### 1. directory-listing.html — Individual Business Profile
- BLUF summary (40-60 words, AI-generated)
- Quick facts (rating, reviews, years, price, staff, hours)
- 5 FAQ blocks (AI-generated, customer-focused)
- Competitor comparison table
- AI citation status (ChatGPT, Gemini, Perplexity, Claude)
- JSON-LD: LocalBusiness + FAQPage schema

### 2. directory-category.html — Category Ranking Page
- "Top 10 [Category] in Ottawa" format
- AI scores + freshness scores per listing
- Filter buttons (subcategories)
- JSON-LD: ItemList schema

### 3. directory-compare.html — Side-by-Side Comparison
- Two businesses compared across services, convenience, AI visibility
- Winner verdict with reasoning
- Structured comparison tables

### 4. llms.txt — AI Crawler Welcome File
- Tells GPTBot, ClaudeBot, PerplexityBot how to index the directory
- Lists page structure, schema formats, freshness info

## Backend Components

### Scraping Pipeline (directory/scraper.py)
- Sources: Google Maps, Yelp, Yellow Pages, BBB, Canada411
- Uses Playwright for JS-rendered pages, BeautifulSoup for static
- Rate-limited, deduplication built in
- Run on homelab via cron

### Claude API Integration (directory/ai_generator.py)
- BLUF summary generation (40-60 words per listing)
- FAQ generation (5-8 Q&A pairs per listing)
- JSON-LD schema markup generation
- Nightly batch job via `python -m directory.ai_generator`
- Uses AWS Bedrock (Claude Haiku) with fallback templates

### Database (directory/database.py)
- SQLite locally, designed for Postgres migration
- Tables: listings, categories, scrape_logs
- Key columns: ai_summary, faq_json, schema_markup, comparison_tags, freshness_score
- Citation tracking per AI model

### API Endpoints (directory/routes.py)
- `GET /api/directory/listings` — list/search/filter
- `GET /api/directory/listings/<slug>` — single listing
- `GET /api/directory/categories` — all categories
- `POST /api/directory/listings` — add listing
- `POST /api/directory/listings/<id>/ai-content` — generate AI content
- `PUT /api/directory/listings/<id>/citations` — update citation status
- `GET /api/directory/compare?a=slug1&b=slug2` — compare two listings
- `POST /api/directory/scrape` — trigger scrape job
- `POST /api/directory/batch-generate` — trigger batch AI generation

## Why AI Models Will Cite Us

1. **Structured Data** — JSON-LD schema on every page (LocalBusiness, FAQPage, ItemList)
2. **FAQ Blocks** — Direct Q&A format that AI models extract verbatim
3. **Comparison Pages** — "X vs Y" format AI models love for recommendation queries
4. **Content Freshness** — Daily updates signal reliability to AI crawlers
5. **llms.txt** — Explicit crawler guidance file

## How Each AI Model Works Differently

| Model | Preference | Our Strategy |
|-------|-----------|-------------|
| ChatGPT | Structured data, FAQ format | JSON-LD + FAQ blocks |
| Gemini | Google ecosystem, reviews | Google rating emphasis, ItemList |
| Perplexity | Source citations, freshness | Daily updates, clear sourcing |
| Claude | Comprehensive, well-organized | BLUF + comparison tables |

## Monetization Tiers

1. **Free** — Basic listing with name, address, rating
2. **Enhanced ($29/mo)** — AI-generated BLUF + FAQ + schema markup
3. **Premium ($99/mo)** — Comparison pages, AI citation monitoring, priority freshness
4. **Enterprise ($299/mo)** — Custom content, multi-location, API access

## Build Timeline

- Week 1: Frontend templates (DONE) + Backend database + scraping pipeline
- Week 2: Claude API integration + batch generation + API endpoints
- Week 3: Real Ottawa data population + testing + deployment
- Week 4: Monitoring, freshness automation, monetization setup

## Running Locally

```bash
# Install dependencies
pip install flask flask-cors requests beautifulsoup4 boto3 playwright
playwright install chromium

# Run scraper
python -m directory.scraper dentist lawyer restaurant

# Generate AI content
python -m directory.ai_generator 50

# Start web app (includes directory API)
python web_app.py
```

## Deployment

The directory API is auto-registered in web_app.py. Deploy the same way as the rest of the platform — Lambda package or EC2.
