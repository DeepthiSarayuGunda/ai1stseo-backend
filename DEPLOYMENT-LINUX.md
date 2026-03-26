# Deployment — Linux Server (OpenShell/NVIDIA Layer)

> **Last Updated:** March 26, 2026 — Dev 1 (Deepthi)
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
# RDS PostgreSQL
DB_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=ai1stseo
DB_USER=postgres
DB_PASSWORD=your-password

# AWS (for Bedrock Nova Lite)
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
