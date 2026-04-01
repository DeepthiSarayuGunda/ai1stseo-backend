#!/bin/bash
###############################################################################
# deploy_postiz.sh — Automated Postiz Self-Hosted Deployment on AWS EC2
#
# Tested on: Ubuntu 24.04 LTS (t3.medium or larger, 4GB+ RAM recommended)
# Usage:     chmod +x deploy_postiz.sh && sudo ./deploy_postiz.sh
#
# What this does:
#   1. Installs Docker & Docker Compose
#   2. Creates the postiz directory structure
#   3. Generates a docker-compose.yml with Temporal stack
#   4. Generates a .env file (edit with your API keys)
#   5. Creates the Temporal dynamic config
#   6. Starts all services
###############################################################################

set -euo pipefail

POSTIZ_DIR="/opt/postiz"
COMPOSE_FILE="$POSTIZ_DIR/docker-compose.yml"
ENV_FILE="$POSTIZ_DIR/.env"

echo "============================================"
echo "  Postiz Self-Hosted Deployment Script"
echo "============================================"

# ── 1. System updates & Docker install ────────────────────────────────────────

echo "[1/6] Installing Docker and Docker Compose..."

if ! command -v docker &>/dev/null; then
    # Works on Ubuntu 22.04/24.04 and Amazon Linux 2023
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [[ "$ID" == "amzn" ]]; then
            yum update -y
            yum install -y docker
            systemctl start docker
            systemctl enable docker
            # Docker Compose plugin
            mkdir -p /usr/local/lib/docker/cli-plugins
            curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
                -o /usr/local/lib/docker/cli-plugins/docker-compose
            chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
        else
            # Ubuntu / Debian
            apt-get update -y
            apt-get install -y ca-certificates curl gnupg
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$ID/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
                https://download.docker.com/linux/$ID $(lsb_release -cs) stable" \
                > /etc/apt/sources.list.d/docker.list
            apt-get update -y
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        fi
    fi
else
    echo "  Docker already installed."
fi

# Add current user to docker group (non-root usage)
if [ "${SUDO_USER:-}" ]; then
    usermod -aG docker "$SUDO_USER" 2>/dev/null || true
fi

docker --version
docker compose version

# ── 2. Create directory structure ─────────────────────────────────────────────

echo "[2/6] Creating directory structure at $POSTIZ_DIR..."

mkdir -p "$POSTIZ_DIR/dynamicconfig"

# Temporal dynamic config (required)
cat > "$POSTIZ_DIR/dynamicconfig/development-sql.yaml" << 'DYNEOF'
# Temporal dynamic configuration
limit.maxIDLength:
  - value: 255
    constraints: {}
system.forceSearchAttributesCacheRefreshOnRead:
  - value: true
    constraints: {}
DYNEOF

# ── 3. Generate .env file ────────────────────────────────────────────────────

echo "[3/6] Generating .env file..."

# Generate a random JWT secret
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '/+=' | head -c 64)

# Detect public IP
PUBLIC_IP=$(curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null \
    || curl -s --connect-timeout 5 https://ifconfig.me 2>/dev/null \
    || echo "YOUR_SERVER_IP")

cat > "$ENV_FILE" << ENVEOF
###############################################################################
# Postiz Self-Hosted Environment Configuration
# Edit this file with your actual API keys before starting
###############################################################################

# ── Server URLs (replace $PUBLIC_IP with your domain if using one) ──
MAIN_URL=http://$PUBLIC_IP:4007
FRONTEND_URL=http://$PUBLIC_IP:4007
NEXT_PUBLIC_BACKEND_URL=http://$PUBLIC_IP:4007/api
BACKEND_INTERNAL_URL=http://localhost:3000

# ── Security ──
JWT_SECRET=$JWT_SECRET

# ── Database ──
DATABASE_URL=postgresql://postiz-user:postiz-password@postiz-postgres:5432/postiz-db-local

# ── Redis ──
REDIS_URL=redis://postiz-redis:6379

# ── Temporal ──
TEMPORAL_ADDRESS=temporal:7233

# ── General Settings ──
IS_GENERAL=true
DISABLE_REGISTRATION=false
RUN_CRON=true
API_LIMIT=30

# ── Storage (local filesystem) ──
STORAGE_PROVIDER=local
UPLOAD_DIRECTORY=/uploads
NEXT_PUBLIC_UPLOAD_DIRECTORY=/uploads

# ── Social Media API Keys (fill in the ones you need) ──
# LinkedIn
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

# Facebook / Instagram
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=

# Twitter/X
X_API_KEY=
X_API_SECRET=

# YouTube
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=

# TikTok
TIKTOK_CLIENT_ID=
TIKTOK_CLIENT_SECRET=

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

# Threads
THREADS_APP_ID=
THREADS_APP_SECRET=

# Mastodon
MASTODON_URL=https://mastodon.social
MASTODON_CLIENT_ID=
MASTODON_CLIENT_SECRET=

# Discord
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_BOT_TOKEN_ID=

# Slack
SLACK_ID=
SLACK_SECRET=
SLACK_SIGNING_SECRET=

# Pinterest
PINTEREST_CLIENT_ID=
PINTEREST_CLIENT_SECRET=

# GitHub (for Postiz login, not social posting)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# ── AI Features (optional) ──
OPENAI_API_KEY=

# ── Misc ──
NX_ADD_PLUGINS=false
NEXT_PUBLIC_DISCORD_SUPPORT=
NEXT_PUBLIC_POLOTNO=
FEE_AMOUNT=0.05
STRIPE_PUBLISHABLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_SIGNING_KEY=
STRIPE_SIGNING_KEY_CONNECT=
ENVEOF

echo "  .env created at $ENV_FILE"

# ── 4. Generate docker-compose.yml ───────────────────────────────────────────

echo "[4/6] Generating docker-compose.yml..."

cat > "$COMPOSE_FILE" << 'COMPEOF'
services:
  # ── Postiz Application ──
  postiz:
    image: ghcr.io/gitroomhq/postiz-app:latest
    container_name: postiz
    restart: always
    env_file: .env
    environment:
      EXTENSION_ID: 'icpokdlcikdmemjkeoojhocmhmehpaia'
    volumes:
      - postiz-config:/config/
      - postiz-uploads:/uploads/
    ports:
      - "4007:5000"
    networks:
      - postiz-network
      - temporal-network
    depends_on:
      postiz-postgres:
        condition: service_healthy
      postiz-redis:
        condition: service_healthy

  # ── PostgreSQL for Postiz ──
  postiz-postgres:
    image: postgres:17-alpine
    container_name: postiz-postgres
    restart: always
    environment:
      POSTGRES_PASSWORD: postiz-password
      POSTGRES_USER: postiz-user
      POSTGRES_DB: postiz-db-local
    volumes:
      - postgres-volume:/var/lib/postgresql/data
    networks:
      - postiz-network
    healthcheck:
      test: pg_isready -U postiz-user -d postiz-db-local
      interval: 10s
      timeout: 3s
      retries: 3

  # ── Redis ──
  postiz-redis:
    image: redis:7.2
    container_name: postiz-redis
    restart: always
    healthcheck:
      test: redis-cli ping
      interval: 10s
      timeout: 3s
      retries: 3
    volumes:
      - postiz-redis-data:/data
    networks:
      - postiz-network

  # ── Temporal Stack ──
  temporal-elasticsearch:
    container_name: temporal-elasticsearch
    image: elasticsearch:7.17.27
    environment:
      - cluster.routing.allocation.disk.threshold_enabled=true
      - cluster.routing.allocation.disk.watermark.low=512mb
      - cluster.routing.allocation.disk.watermark.high=256mb
      - cluster.routing.allocation.disk.watermark.flood_stage=128mb
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms256m -Xmx256m
      - xpack.security.enabled=false
    networks:
      - temporal-network
    expose:
      - 9200
    volumes:
      - temporal-es-data:/usr/share/elasticsearch/data

  temporal-postgresql:
    container_name: temporal-postgresql
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: temporal
      POSTGRES_USER: temporal
    networks:
      - temporal-network
    expose:
      - 5432
    volumes:
      - temporal-pg-data:/var/lib/postgresql/data

  temporal:
    container_name: temporal
    image: temporalio/auto-setup:1.28.1
    ports:
      - '7233:7233'
    depends_on:
      - temporal-postgresql
      - temporal-elasticsearch
    environment:
      - DB=postgres12
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=temporal-postgresql
      - DYNAMIC_CONFIG_FILE_PATH=config/dynamicconfig/development-sql.yaml
      - ENABLE_ES=true
      - ES_SEEDS=temporal-elasticsearch
      - ES_VERSION=v7
      - TEMPORAL_NAMESPACE=default
    networks:
      - temporal-network
    volumes:
      - ./dynamicconfig:/etc/temporal/config/dynamicconfig
    labels:
      kompose.volume.type: configMap

  temporal-ui:
    container_name: temporal-ui
    image: temporalio/ui:2.34.0
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
      - TEMPORAL_CORS_ORIGINS=http://127.0.0.1:3000
    networks:
      - temporal-network
    ports:
      - '8080:8080'

volumes:
  postgres-volume:
  postiz-redis-data:
  postiz-config:
  postiz-uploads:
  temporal-es-data:
  temporal-pg-data:

networks:
  postiz-network:
  temporal-network:
    driver: bridge
    name: temporal-network
COMPEOF

echo "  docker-compose.yml created."

# ── 5. Configure EC2 Security Group reminder ─────────────────────────────────

echo "[5/6] Security group reminder..."
echo ""
echo "  Make sure your EC2 security group allows inbound traffic on:"
echo "    - Port 4007 (Postiz UI)"
echo "    - Port 8080 (Temporal UI — optional, for debugging)"
echo "    - Port 22   (SSH)"
echo ""

# ── 6. Start services ────────────────────────────────────────────────────────

echo "[6/6] Starting Postiz services..."

cd "$POSTIZ_DIR"
docker compose pull
docker compose up -d

echo ""
echo "============================================"
echo "  Deployment Complete!"
echo "============================================"
echo ""
echo "  Postiz UI:     http://$PUBLIC_IP:4007"
echo "  Temporal UI:   http://$PUBLIC_IP:8080"
echo ""
echo "  Config dir:    $POSTIZ_DIR"
echo "  Env file:      $ENV_FILE"
echo ""
echo "  Next steps:"
echo "    1. Edit $ENV_FILE with your social media API keys"
echo "    2. Run: cd $POSTIZ_DIR && docker compose restart postiz"
echo "    3. Open http://$PUBLIC_IP:4007 and create your admin account"
echo "    4. Connect social media accounts in Settings > Channels"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f postiz     # View Postiz logs"
echo "    docker compose ps                 # Check service status"
echo "    docker compose down               # Stop all services"
echo "    docker compose up -d              # Start all services"
echo ""
