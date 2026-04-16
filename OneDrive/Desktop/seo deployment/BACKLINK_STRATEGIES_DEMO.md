# AI 1st SEO — Backlink Analysis Module
## Implementation Guide with AWS Service Pairings | April 2026

---

## What We Built

A 14-endpoint backlink analysis system that goes beyond what Ahrefs and SEMrush offer by combining traditional link analysis with AI citation intelligence. All endpoints are built, tested, and backed by DynamoDB. This document maps each strategy to specific AWS services and third-party tools that make them production-ready.

---

## Current Infrastructure

| Resource | Service | Purpose |
|----------|---------|---------|
| Backlink data | DynamoDB (`ai1stseo-backlinks`) | Domain scores, link gaps, citation probes, reports |
| Opportunities | DynamoDB (`ai1stseo-backlink-opportunities`) | Unified priority queue across all sources |
| API compute | Lambda (`ai1stseo-backend`) | All 14 endpoints via Flask blueprint |
| AI inference | Ollama on Tailscale (`192.168.2.200:11434`) | Tiered models for citation probing |
| Auth | Cognito (`us-east-1_DVvth47zH`) | JWT on all endpoints |
| Notifications | SES + Slack webhooks | Alert dispatch for competitor changes |

---

## The 7 Strategies — With AWS Service Pairings

### 1. Domain Authority Scoring
**Endpoint:** `POST /api/backlinks/score`
**Status:** Implemented

Analyzes any domain and returns a 0-100 authority score based on 10+ real signals: HTTPS, response time, security headers, schema markup, meta tags, internal/external link counts, content depth, robots.txt, and sitemap presence.

**AWS Services to Enhance:**

| Service | How It Helps | Implementation |
|---------|-------------|----------------|
| **EventBridge Scheduler** | Schedule weekly DA re-scans for all tracked domains automatically | Create a rule targeting a Lambda that reads domains from DynamoDB and calls `/api/backlinks/score` for each |
| **DynamoDB Streams** | Trigger alerts when a domain's DA changes by more than 5 points | Enable streams on `ai1stseo-backlinks`, filter for `type=domain_score`, compare against previous score |
| **CloudWatch Metrics** | Track DA score distributions and trends across all clients | Publish custom metrics from the scoring endpoint: `avg_da`, `domains_scored`, `score_distribution` |
| **S3 + Athena** | Historical DA analysis across thousands of domains | Export scoring history to S3 as Parquet, query with Athena for trend reports |

**Implementation Path:**
```python
# EventBridge rule (add to template.yaml)
DAScanSchedule:
  Type: AWS::Events::Rule
  Properties:
    ScheduleExpression: "rate(7 days)"
    Targets:
      - Arn: !GetAtt BacklinkScanFunction.Arn
        Id: WeeklyDAScan
```

**Third-Party Pairing:** For production-grade DA, integrate the Moz Links API or Ahrefs API v3 as a secondary signal alongside our real-time scorer. Our scorer runs free and instant; the paid API provides crawl-based authority data. Blend both into a composite score.

---

### 2. Toxic Link Detection
**Endpoint:** `POST /api/backlinks/analyze-toxic`
**Status:** Implemented

Classifies backlinks as potentially toxic using heuristic signals: spammy TLDs, exact-match anchors, gambling/pharma keywords, long domains, deep subdomains.

**AWS Services to Enhance:**

| Service | How It Helps | Implementation |
|---------|-------------|----------------|
| **SageMaker** | Train a proper ML classifier on labeled toxic link data instead of heuristics | Use SageMaker built-in XGBoost with features: TLD, anchor text TF-IDF, domain length, subdomain depth, Ahrefs spam score. Deploy as a real-time endpoint |
| **Comprehend** | Detect sentiment and language of linking pages to flag foreign-language spam farms | Call `detect_dominant_language()` and `detect_sentiment()` on the linking page content |
| **Lambda + SQS** | Batch-process large backlink profiles (10k+ links) without timeout | Client submits profile → SQS queue → Lambda workers classify in parallel → results written to DynamoDB |
| **SNS** | Alert clients immediately when new toxic links are detected | Publish to an SNS topic per client; subscribers get email/SMS/Slack |

**Implementation Path:**
```python
# SQS batch processing pattern
import boto3
sqs = boto3.client('sqs', region_name='us-east-1')

def submit_toxic_scan(backlinks, callback_url):
    """Submit a large backlink list for async toxic classification."""
    for chunk in [backlinks[i:i+25] for i in range(0, len(backlinks), 25)]:
        sqs.send_message(
            QueueUrl='https://sqs.us-east-1.amazonaws.com/823766426087/backlink-toxic-scan',
            MessageBody=json.dumps({'backlinks': chunk, 'callback': callback_url})
        )
```

**Third-Party Pairing:** Google Search Console Disavow API — once toxic links are identified, generate a disavow file and optionally submit it programmatically. Also consider SpamZilla's database for known spam domain lists as training data for the SageMaker classifier.

---

### 3. Link Gap Analysis
**Endpoint:** `POST /api/backlinks/link-gap`
**Status:** Implemented

Compares a client's domain against up to 5 competitors. Scores all domains, identifies where competitors outperform, and returns specific signal gaps.

**AWS Services to Enhance:**

| Service | How It Helps | Implementation |
|---------|-------------|----------------|
| **Step Functions** | Orchestrate multi-competitor analysis as a workflow (score each domain → compare → generate report) | State machine: parallel scoring → gap calculation → store results → notify |
| **ElastiCache (Redis)** | Cache competitor DA scores for 24h to avoid redundant HTTP requests | Before scoring, check Redis. If cached and < 24h old, skip the live scan |
| **Bedrock (Claude)** | Generate natural-language gap analysis summaries from raw data | Feed gap data to Claude: "Explain these competitive gaps in plain English and suggest 3 actions" |
| **QuickSight** | Visual dashboards showing competitive positioning over time | Connect to DynamoDB via Athena, build gap trend charts per client |

**Implementation Path:**
```python
# Step Functions state machine definition
{
  "StartAt": "ScoreDomains",
  "States": {
    "ScoreDomains": {
      "Type": "Parallel",
      "Branches": [
        {"StartAt": "ScoreClient", "States": {"ScoreClient": {"Type": "Task", "Resource": "arn:aws:lambda:...score"}}},
        {"StartAt": "ScoreCompetitors", "States": {"ScoreCompetitors": {"Type": "Map", "Iterator": {"StartAt": "ScoreOne"}}}}
      ],
      "Next": "CalculateGaps"
    },
    "CalculateGaps": {"Type": "Task", "Resource": "arn:aws:lambda:...gap-calc", "Next": "GenerateReport"},
    "GenerateReport": {"Type": "Task", "Resource": "arn:aws:lambda:...report", "End": true}
  }
}
```

**Third-Party Pairing:** Ahrefs Content Explorer API — find content in the competitor's niche that has high referring domains but the client hasn't covered. This turns a link gap into a content gap, giving the client a specific page to create.

---

### 4. LLM Citation Authority Mapper (Novel — No Competitor Has This)
**Endpoint:** `POST /api/backlinks/citation-authority`
**Status:** Implemented

Probes AI models with topic-specific queries and tracks which domains they cite. Builds a citation authority score per domain.

**AWS Services to Enhance:**

| Service | How It Helps | Implementation |
|---------|-------------|----------------|
| **Bedrock** | Probe Claude, Titan, and Llama models natively without managing infrastructure | Use `bedrock-runtime` to invoke multiple foundation models with the same prompts, compare citation patterns across models |
| **EventBridge Scheduler** | Run citation probes weekly to track how AI citation patterns shift over time | Schedule a Lambda that runs the top 50 niche queries against 3 models every Monday |
| **DynamoDB TTL** | Auto-expire old citation data after 90 days to keep the dataset fresh | Set TTL on citation probe records; stale data degrades scoring accuracy |
| **Kinesis Data Streams** | Real-time citation tracking at scale when probing hundreds of queries | Stream probe results through Kinesis → Lambda consumer → DynamoDB + S3 archive |

**Implementation Path:**
```python
# Multi-model citation probe via Bedrock
import boto3, json, re
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def probe_model(model_id, query):
    """Probe a Bedrock model and extract cited domains."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": f"Answer this and cite sources with URLs: {query}"}],
        "max_tokens": 1024
    })
    resp = bedrock.invoke_model(modelId=model_id, body=body)
    text = json.loads(resp['body'].read())['content'][0]['text']
    urls = re.findall(r'https?://[^\s\)\]"\'<>]+', text)
    return [urlparse(u).netloc for u in urls if urlparse(u).netloc]

# Probe multiple models
models = ['anthropic.claude-3-5-sonnet-20241022-v2:0', 'amazon.titan-text-premier-v1:0']
for model in models:
    domains = probe_model(model, "What are the best SEO tools in 2026?")
```

**Third-Party Pairing:**
- **Perplexity API** — Perplexity explicitly cites sources with URLs, making it the highest-signal model for citation tracking
- **Google Gemini API** — Compare Google's own model citations against Google Search rankings for correlation analysis
- **OpenAI API** — ChatGPT citation patterns via the web-browsing model

This is the platform's key differentiator. No competitor tracks which domains AI chatbots trust. A backlink from a domain that ChatGPT cites is worth more than a traditional high-DA link because it boosts both Google authority AND AI visibility simultaneously.

---

### 5. Broken Link Reclaim Bot
**Endpoint:** `POST /api/backlinks/broken-links`
**Status:** Implemented

Scans pages for broken outbound links (404s, timeouts). Each broken link is a reclaim opportunity.

**AWS Services to Enhance:**

| Service | How It Helps | Implementation |
|---------|-------------|----------------|
| **SQS + Lambda** | Async crawling — submit a URL, get results via callback instead of waiting 30s+ | URL → SQS → Lambda checks all outbound links → writes results to DynamoDB → SNS notification |
| **Comprehend** | Classify the topic of the broken link's anchor text to match against client content | `detect_key_phrases()` on anchor text + surrounding paragraph → match to client's content topics |
| **SES** | Auto-generate and send outreach emails to site owners about their broken links | Template: "Hi, I noticed [broken_url] on your page [page_url] is returning a 404. We have a resource at [client_url] that covers the same topic." |
| **S3** | Store crawl snapshots for audit trail and dispute resolution | Save the full HTML of pages with broken links as evidence |

**Implementation Path:**
```python
# Async broken link scan with SQS
def submit_broken_link_scan(url):
    sqs.send_message(
        QueueUrl=BROKEN_LINK_QUEUE_URL,
        MessageBody=json.dumps({'url': url, 'max_links': 50, 'timeout': 5})
    )
    return {'status': 'queued', 'message': 'Results will appear in your opportunity queue'}

# SES outreach template
def send_reclaim_outreach(site_owner_email, broken_url, page_url, replacement_url):
    ses.send_templated_email(
        Source='outreach@ai1stseo.com',
        Destination={'ToAddresses': [site_owner_email]},
        Template='BrokenLinkReclaim',
        TemplateData=json.dumps({
            'broken_url': broken_url,
            'page_url': page_url,
            'replacement_url': replacement_url
        })
    )
```

**Third-Party Pairing:**
- **Hunter.io API** — Find the email address of the site owner/webmaster for outreach
- **Wayback Machine API** — Retrieve the original content of the dead page to confirm topic match before outreach
- **Screaming Frog API** — For large-scale crawls of entire domains (thousands of pages), offload to Screaming Frog's cloud crawler

---

### 6. Wikipedia Citation Gap Finder
**Endpoint:** `POST /api/backlinks/wikipedia-gaps`
**Status:** Implemented

Searches Wikipedia articles by topic, extracts external citations, checks which are dead or unreachable. Dead citations are replacement opportunities.

**AWS Services to Enhance:**

| Service | How It Helps | Implementation |
|---------|-------------|----------------|
| **Step Functions** | Orchestrate the multi-step pipeline: search articles → extract citations → check status → score → store | Each step is a Lambda; Step Functions handles retries and parallel citation checking |
| **Bedrock (Claude)** | Evaluate whether the client's content is a legitimate replacement for the dead citation | Prompt: "Compare this Wikipedia citation context [context] with this client page [url]. Is the client's content a valid replacement? Score 0-100." |
| **EventBridge** | Re-scan Wikipedia articles monthly — new dead links appear as sources go offline | Monthly schedule triggers a re-crawl of all previously identified articles |
| **DynamoDB Streams + Lambda** | When a new Wikipedia gap is found, auto-generate a suggested Wikipedia edit | Stream triggers a Lambda that drafts the edit using Claude, stores it for human review |

**Implementation Path:**
```python
# Bedrock-powered replacement validation
def validate_replacement(wiki_context, client_url, client_content_summary):
    """Use Claude to assess if client content is a legitimate Wikipedia citation replacement."""
    prompt = f"""You are evaluating whether a webpage is a suitable replacement citation for a Wikipedia article.

Wikipedia context where the citation appears:
{wiki_context}

Client's page URL: {client_url}
Client's content summary: {client_content_summary}

Score 0-100 on: relevance, authority, neutrality (Wikipedia requires neutral sources).
Respond with JSON: {{"score": N, "reasoning": "...", "suggested_edit": "..."}}"""

    resp = bedrock.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
        body=json.dumps({"anthropic_version": "bedrock-2023-05-31",
                         "messages": [{"role": "user", "content": prompt}],
                         "max_tokens": 512})
    )
    return json.loads(json.loads(resp['body'].read())['content'][0]['text'])
```

**Third-Party Pairing:**
- **Wikipedia API** (already integrated) — `action=query&prop=extlinks` for citation extraction
- **Wikimedia Pageviews API** — Prioritize gaps in high-traffic articles (more referral value)
- **Internet Archive Wayback Machine** — Verify the dead citation was actually relevant before suggesting a replacement

Wikipedia links are among the highest-value backlinks available. They simultaneously build Google trust, increase AI citation probability, and generate referral traffic.

---

### 7. Competitor Alert System + Link Decay Predictor
**Endpoints:** `POST /api/backlinks/competitor-alerts`, `POST /api/backlinks/decay-predict`
**Status:** Implemented

Monitors competitor DA changes and predicts which existing backlinks are at risk of disappearing.

**AWS Services to Enhance:**

| Service | How It Helps | Implementation |
|---------|-------------|----------------|
| **EventBridge Scheduler** | Run competitor checks daily instead of on-demand | Daily rule triggers Lambda that scores all tracked competitors and compares to history |
| **SNS** | Multi-channel alerts: email, SMS, Slack, mobile push when a competitor gains DA | Topic per client with protocol-specific subscriptions |
| **SageMaker** | Train a real link decay prediction model on historical data | Features: link age, source domain DA trend, source posting frequency, anchor text diversity. Target: link still alive after 90 days (binary) |
| **CloudWatch Alarms** | Alert when competitor DA change exceeds threshold | Custom metric `competitor_da_change` → alarm at ±10 points |
| **Forecast** | Time-series prediction of DA trends for both client and competitors | Feed historical DA scores into Amazon Forecast for 30/60/90-day projections |

**Implementation Path:**
```python
# Daily competitor monitoring with EventBridge + SNS
def daily_competitor_check():
    """Runs via EventBridge daily. Checks all tracked competitors."""
    competitors = scan_table('ai1stseo-backlinks', 200)
    tracked = set(i['competitor'] for i in competitors if i.get('type') == 'competitor_alert')

    sns = boto3.client('sns', region_name='us-east-1')
    for domain in tracked:
        current = _estimate_domain_authority(domain)
        # Compare to last stored score
        history = [i for i in competitors if i.get('domain') == domain and i.get('type') == 'domain_score']
        if history:
            prev = history[-1].get('da_score', 0)
            change = current['da_score'] - prev
            if abs(change) >= 5:
                sns.publish(
                    TopicArn='arn:aws:sns:us-east-1:823766426087:backlink-alerts',
                    Subject=f'Competitor DA Alert: {domain}',
                    Message=f'{domain} DA changed by {change} points ({prev} → {current["da_score"]})'
                )
```

**Third-Party Pairing:**
- **Ahrefs Alerts API** — Supplement our DA monitoring with Ahrefs' new/lost backlink alerts for competitors
- **Slack Incoming Webhooks** (already integrated) — Real-time team notifications
- **PagerDuty** — For agency clients who need SLA-level alerting on competitive threats

---

## Supporting Infrastructure — Service Pairings

| Feature | Current | AWS Enhancement | Third-Party Option |
|---------|---------|----------------|-------------------|
| Priority Queue | DynamoDB scan + sort | DynamoDB Streams → Lambda auto-re-score on new data | — |
| Citation Scores | DynamoDB scan | Bedrock multi-model probing + S3/Athena for trend analysis | Perplexity API, OpenAI API |
| Link Velocity | Manual check | EventBridge + CloudWatch custom metrics + anomaly detection | — |
| History Browser | DynamoDB scan | S3 export + Athena for SQL queries over full history | — |
| Report Generator | JSON response | Lambda + WeasyPrint → S3 presigned URL for PDF download | — |
| Outreach Automation | Not yet built | SES templates + SQS job queue + Step Functions workflow | Hunter.io, Lemlist, Mailshake |
| Content Matching | Not yet built | Comprehend key phrases + Bedrock semantic similarity | — |

---

## What Makes This Different From Ahrefs/SEMrush

| Capability | Ahrefs/SEMrush | AI 1st SEO | AWS Service Powering It |
|-----------|---------------|------------|------------------------|
| Domain authority scoring | Yes (proprietary crawl) | Yes (real-time, 10+ signals) | Lambda + DynamoDB |
| Toxic link detection | Yes | Yes + ML classifier path | SageMaker + Comprehend |
| Link gap analysis | Yes | Yes + AI citation dimension | Step Functions + Bedrock |
| LLM citation tracking | No | Yes — which domains do AI chatbots trust? | Bedrock + EventBridge |
| Wikipedia gap finder | No | Yes — dead citations as replacement opportunities | Step Functions + Bedrock |
| Broken link reclaim | Basic | Automated with opportunity queue + outreach | SQS + SES + Lambda |
| AI + Google dual scoring | No | Yes — backlinks scored for both channels | Bedrock + DynamoDB |
| Competitor DA alerts | Basic | Real-time with trend analysis + predictions | EventBridge + SNS + Forecast |
| Outreach automation | No | Planned — AI-personalized email sequences | SES + Bedrock + Step Functions |
| White-label PDF reports | Basic export | Branded agency reports with charts | Lambda + S3 + WeasyPrint |

---

## Implementation Roadmap — What's Built vs. What's Next

### Built (Months 1-4) — Live in Lambda
- Domain authority scoring (10+ signals, real-time)
- Toxic link classifier (heuristic-based)
- Link gap analysis (up to 5 competitors)
- LLM citation authority mapper (Ollama-backed)
- Broken link reclaim bot (50 links/page)
- Wikipedia citation gap finder
- Competitor DA alerts + link decay predictor
- Priority queue + report generator
- 2 DynamoDB tables, 14 API endpoints

### Next Phase — AWS Service Upgrades
| Priority | Enhancement | AWS Services | Effort | Impact |
|----------|------------|-------------|--------|--------|
| 1 | Scheduled competitor monitoring | EventBridge + Lambda | 1 day | Proactive instead of reactive alerts |
| 2 | Multi-model citation probing | Bedrock (Claude + Titan) | 2 days | Richer citation data across AI platforms |
| 3 | Async broken link scanning | SQS + Lambda workers | 1 day | Handle large sites without timeout |
| 4 | Outreach email automation | SES templates + Step Functions | 3 days | Close the loop from discovery to outreach |
| 5 | ML toxic link classifier | SageMaker XGBoost | 3 days | Replace heuristics with trained model |
| 6 | PDF report generation | Lambda + WeasyPrint + S3 | 2 days | White-label agency deliverable |
| 7 | Historical trend analysis | S3 + Athena | 1 day | SQL queries over months of backlink data |
| 8 | DA trend forecasting | Amazon Forecast | 2 days | Predict where competitors are heading |

### Month 5 — Scale and Enterprise
- Queue-based crawl refresh (SQS + Lambda fan-out)
- Multi-region link data ingestion
- Predictive link ROI scoring model (SageMaker)
- Public API endpoints for enterprise clients
- Full outreach CRM with pipeline stages (DynamoDB + Step Functions)
- Link acquisition attribution → GEO score lift correlation

---

## Cost Estimates for AWS Enhancements

| Service | Usage Pattern | Estimated Monthly Cost |
|---------|--------------|----------------------|
| EventBridge | 5 scheduled rules, ~1000 invocations/month | ~$1 |
| SQS | ~10,000 messages/month for async scanning | ~$0.01 |
| SNS | ~500 notifications/month | ~$0.50 |
| SES | ~2,000 outreach emails/month | ~$0.20 |
| Bedrock (Claude) | ~5,000 citation probes/month | ~$15-25 |
| Comprehend | ~2,000 text classifications/month | ~$2 |
| S3 + Athena | ~5GB storage, ~50 queries/month | ~$1 |
| SageMaker (inference) | Serverless endpoint, ~1,000 predictions/month | ~$5 |
| **Total incremental** | | **~$25-35/month** |

All services use pay-per-request or serverless pricing. No idle infrastructure costs.

---

## Technical Details

- **Database:** 2 DynamoDB tables (`ai1stseo-backlinks` with domain-index GSI, `ai1stseo-backlink-opportunities`)
- **AI Inference:** Tiered Ollama models (8B fast, 30B standard, 235B deep) + Bedrock for multi-model probing
- **Auth:** Cognito JWT required on all endpoints
- **14 total endpoints** in `backend/backlink_api.py` (880+ lines)
- **Blueprint:** `backlink_bp` — needs registration in root `app.py` by Samarveer
- **Zero external API dependencies for core features** — paid APIs (Ahrefs, Hunter.io) are optional enhancements
