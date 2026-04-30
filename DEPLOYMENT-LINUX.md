# Deployment — Linux Server (OpenShell/NVIDIA Layer)

> **Last Updated:** April 8, 2026 — Dev 1 (Deepthi)
> **Target:** Linux server with Docker + NVIDIA GPU support

---

## Prerequisites

- Linux server with Docker installed
- NVIDIA Container Toolkit (for GPU-accelerated Ollama)
- Network access to AWS (Bedrock, RDS)
- Git access to `DeepthiSarayuGunda/ai1stseo-backend` repo

## Environment Variables

Create a `.env` file (never commit this):

```env
# Database mode — DynamoDB is default (no RDS needed)
# Set USE_RDS=1 only if RDS PostgreSQL is running
# USE_RDS=1

# RDS PostgreSQL (only needed if USE_RDS=1)
# DB_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
# DB_PORT=5432
# DB_NAME=ai1stseo
# DB_USER=postgres
# DB_PASSWORD=your-password

# AWS (for Bedrock Nova Lite + DynamoDB)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret

# Ollama (local or remote)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:30b-a3b

# Optional LLM providers
GROQ_API_KEY=your-groq-key
# OPENAI_API_KEY=
# GEMINI_API_KEY=
# PERPLEXITY_API_KEY=

# App config
DEFAULT_PROJECT_ID=00000000-0000-0000-0000-000000000001
FLASK_SKIP_DOTENV=1
```

## Quick Start (Docker)

```bash
# 1. Clone the repo
git clone https://github.com/DeepthiSarayuGunda/ai1stseo-backend.git
cd ai1stseo-backend

# 2. Build the Docker image
docker build -t ai1stseo-backend .

# 3. Run with environment variables
docker run -d \
  --name ai1stseo \
  --env-file .env \
  -p 5001:5001 \
  --restart unless-stopped \
  ai1stseo-backend

# 4. Verify it's running
curl http://localhost:5001/api/health
```

## With NVIDIA GPU (for local Ollama)

```bash
# 1. Start Ollama with GPU support
docker run -d \
  --name ollama \
  --gpus all \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  ollama/ollama

# 2. Pull the model
docker exec ollama ollama pull qwen3:30b-a3b

# 3. Start the backend (link to Ollama)
docker run -d \
  --name ai1stseo \
  --env-file .env \
  -e OLLAMA_URL=http://ollama:11434 \
  --link ollama:ollama \
  -p 5001:5001 \
  --restart unless-stopped \
  ai1stseo-backend
```

## Without Docker (Direct)

```bash
# 1. Clone and install
git clone https://github.com/DeepthiSarayuGunda/ai1stseo-backend.git
cd ai1stseo-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Export environment variables
export $(cat .env | xargs)

# 3. Run with gunicorn
gunicorn --bind 0.0.0.0:5001 --workers 4 --timeout 120 application:application
```

## Verify Deployment

```bash
# Health check (shows DB, Bedrock, Ollama status)
curl http://localhost:5001/api/health

# Test GEO Scanner Agent
curl -X POST http://localhost:5001/api/geo-scanner/scan \
  -H "Content-Type: application/json" \
  -d '{"brand_name":"Notion","keywords":["best project management tools"],"provider":"nova"}'

# Test RDS persistence
curl -X POST http://localhost:5001/api/data/geo-probes \
  -H "Content-Type: application/json" \
  -d '{"keyword":"test","brand":"TestBrand","ai_model":"nova","cited":true}'

# List scanner agents
curl http://localhost:5001/api/geo-scanner/agents

# Open dashboards in browser
# http://your-server:5001/dev1-dashboard
# http://your-server:5001/geo-scanner
```

## Key URLs After Deployment

| Page | URL |
|------|-----|
| Dev 1 Dashboard | `http://your-server:5001/dev1-dashboard` |
| GEO Scanner Agent | `http://your-server:5001/geo-scanner` |
| GEO Probe (Simple) | `http://your-server:5001/geo-test` |
| SEO Analyzer | `http://your-server:5001/analyze` |
| Health Check | `http://your-server:5001/api/health` |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| RDS connection refused | Check DB_HOST, security group allows inbound 5432 from server IP |
| Bedrock access denied | Verify IAM credentials have `bedrock:InvokeModel` permission |
| Ollama timeout | Model is large (30B params), allow 60-120s. Or use Nova Lite instead. |
| Port 5001 in use | Change port: `docker run -p 8080:5001 ...` |
| Static files 404 | Ensure `assets/` folder is in the same directory as `app.py` |
| `psycopg2` build fails | See psycopg2 section below |
| DynamoDB access denied | Ensure IAM credentials have `dynamodb:PutItem`, `dynamodb:Scan`, `dynamodb:GetItem` permissions |
| Empty scan response | AI provider may have timed out. Try Nova Lite (faster) or reduce keywords. |

## psycopg2 on Linux — Common Fixes

`psycopg2-binary` is included in `requirements.txt` and works on most systems. If it fails:

```bash
# Option 1: Install system dependencies (Debian/Ubuntu)
sudo apt-get install -y libpq-dev python3-dev gcc
pip install psycopg2-binary

# Option 2: Use pure-Python fallback (slower but no C compiler needed)
pip install psycopg2-binary
# If that still fails:
pip install pg8000  # pure Python PostgreSQL driver

# Option 3: Skip psycopg2 entirely (DynamoDB mode)
# The app defaults to DynamoDB when USE_RDS is not set.
# psycopg2 is only needed if you set USE_RDS=1 in .env
# You can safely ignore psycopg2 install errors if using DynamoDB.

# Option 4: Alpine Linux / Docker
# Alpine needs musl-compatible build:
apk add --no-cache postgresql-dev gcc musl-dev
pip install psycopg2-binary
```

## Database Mode

The backend supports two database modes:

| Mode | When | Config |
|------|------|--------|
| DynamoDB (default) | RDS is stopped or unavailable | No `USE_RDS` env var (or `USE_RDS` not set) |
| RDS PostgreSQL | RDS is running | Set `USE_RDS=1` + DB_HOST/DB_USER/DB_PASSWORD |

DynamoDB tables are pre-provisioned in AWS (`ai1stseo-geo-probes`, `ai1stseo-content-briefs`). No setup needed beyond IAM credentials.

## Team Setup — Step by Step

1. Clone the repo: `git clone https://github.com/DeepthiSarayuGunda/ai1stseo-backend.git`
2. Copy `.env.example` to `.env` and fill in your AWS credentials
3. Install dependencies: `pip install -r requirements.txt`
4. Run locally: `python app.py` (starts on port 5000)
5. Open `http://localhost:5000/geo-scanner` to test the GEO Scanner
6. Push to `main` branch — App Runner auto-deploys

For production deployment, push to GitHub and App Runner handles the rest. Do NOT deploy directly via AWS Console.
