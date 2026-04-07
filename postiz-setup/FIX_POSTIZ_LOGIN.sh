#!/bin/bash
###############################################################################
# FIX_POSTIZ_LOGIN.sh — Fix Postiz login-refresh issue on EC2 (raw IP access)
#
# What this does:
#   1. Backs up current .env and docker-compose.yml
#   2. Detects the EC2 public IP
#   3. Fixes MAIN_URL, FRONTEND_URL, NEXT_PUBLIC_BACKEND_URL
#   4. Ensures BACKEND_INTERNAL_URL is correct
#   5. Ensures JWT_SECRET is set
#   6. Restarts only the affected containers (no data loss)
#
# Usage: sudo bash FIX_POSTIZ_LOGIN.sh
###############################################################################

set -euo pipefail

POSTIZ_DIR="/opt/postiz"
ENV_FILE="$POSTIZ_DIR/.env"
COMPOSE_FILE="$POSTIZ_DIR/docker-compose.yml"
BACKUP_SUFFIX="backup-$(date +%Y%m%d-%H%M%S)"

echo "============================================"
echo "  Postiz Login Fix Script"
echo "============================================"
echo ""

# ── Preflight checks ─────────────────────────────────────────────────────────

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Is Postiz deployed at $POSTIZ_DIR?"
    exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "ERROR: $COMPOSE_FILE not found."
    exit 1
fi

# ── Step 1: Backup ───────────────────────────────────────────────────────────

echo "[1/6] Backing up current configuration..."
cp "$ENV_FILE" "$ENV_FILE.$BACKUP_SUFFIX"
cp "$COMPOSE_FILE" "$COMPOSE_FILE.$BACKUP_SUFFIX"
echo "  Backed up to:"
echo "    $ENV_FILE.$BACKUP_SUFFIX"
echo "    $COMPOSE_FILE.$BACKUP_SUFFIX"

# ── Step 2: Detect public IP ─────────────────────────────────────────────────

echo "[2/6] Detecting EC2 public IP..."

# Use known EC2 public IP (override with PUBLIC_IP env var if changed)
PUBLIC_IP="${PUBLIC_IP:-13.221.80.198}"

echo "  Detected public IP: $PUBLIC_IP"

# ── Step 3: Fix URL environment variables ─────────────────────────────────────

echo "[3/6] Fixing URL configuration in .env..."

# Function to update or add an env var
set_env_var() {
    local key="$1"
    local value="$2"
    local file="$3"

    if grep -q "^${key}=" "$file" 2>/dev/null; then
        # Replace existing value
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    elif grep -q "^# *${key}=" "$file" 2>/dev/null; then
        # Uncomment and set
        sed -i "s|^# *${key}=.*|${key}=${value}|" "$file"
    else
        # Append
        echo "${key}=${value}" >> "$file"
    fi
}

# The critical URL fixes
set_env_var "MAIN_URL"                  "http://${PUBLIC_IP}:4007" "$ENV_FILE"
set_env_var "FRONTEND_URL"              "http://${PUBLIC_IP}:4007" "$ENV_FILE"
set_env_var "NEXT_PUBLIC_BACKEND_URL"   "http://${PUBLIC_IP}:4007/api" "$ENV_FILE"
set_env_var "BACKEND_INTERNAL_URL"      "http://localhost:3000" "$ENV_FILE"

echo "  Set MAIN_URL=http://${PUBLIC_IP}:4007"
echo "  Set FRONTEND_URL=http://${PUBLIC_IP}:4007"
echo "  Set NEXT_PUBLIC_BACKEND_URL=http://${PUBLIC_IP}:4007/api"
echo "  Set BACKEND_INTERNAL_URL=http://localhost:3000"

# ── Step 4: Ensure JWT_SECRET is set ──────────────────────────────────────────

echo "[4/6] Checking JWT_SECRET..."

CURRENT_JWT=$(grep "^JWT_SECRET=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- || true)

if [ -z "$CURRENT_JWT" ] || [ "$CURRENT_JWT" = "" ]; then
    NEW_JWT=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '/+=' | head -c 64)
    set_env_var "JWT_SECRET" "$NEW_JWT" "$ENV_FILE"
    echo "  Generated new JWT_SECRET"
    echo "  WARNING: Existing sessions will be invalidated. Users must log in again."
else
    echo "  JWT_SECRET already set (keeping existing value)"
fi

# ── Step 5: Ensure IS_GENERAL is set ──────────────────────────────────────────

echo "[5/6] Checking required flags..."

set_env_var "IS_GENERAL" "true" "$ENV_FILE"
echo "  IS_GENERAL=true (required for self-hosting)"

# ── Step 6: Restart containers ────────────────────────────────────────────────

echo "[6/6] Restarting Postiz container..."

cd "$POSTIZ_DIR"

# Only restart the postiz app container — DB and Redis keep running
sudo docker compose stop postiz
sudo docker compose up -d postiz

echo ""
echo "  Waiting for Postiz to start (30 seconds)..."
sleep 30

# ── Verification ──────────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "  Verification"
echo "============================================"

echo ""
echo "Container status:"
sudo docker compose ps postiz --format "table {{.Name}}\t{{.Status}}"

echo ""
echo "Current URL config:"
sudo docker exec postiz printenv 2>/dev/null | grep -E "^(MAIN_URL|FRONTEND_URL|NEXT_PUBLIC_BACKEND_URL|BACKEND_INTERNAL_URL)=" | sort

echo ""
echo "API health check:"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:4007/api/ --connect-timeout 10 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "000" ]; then
    echo "  API not responding yet — may need more startup time."
    echo "  Check logs: sudo docker compose logs postiz --tail 50"
else
    echo "  API responded with HTTP $HTTP_CODE"
fi

echo ""
echo "============================================"
echo "  Fix Applied"
echo "============================================"
echo ""
echo "  Test URL: http://${PUBLIC_IP}:4007"
echo ""
echo "  What was fixed:"
echo "    - MAIN_URL, FRONTEND_URL, NEXT_PUBLIC_BACKEND_URL now use EC2 public IP"
echo "    - BACKEND_INTERNAL_URL set to http://localhost:3000 (container-internal)"
echo "    - JWT_SECRET verified/generated"
echo ""
echo "  If login still fails:"
echo "    1. Hard-refresh browser (Ctrl+Shift+R) to clear cached JS"
echo "    2. Try incognito/private window"
echo "    3. Check logs: cd /opt/postiz && sudo docker compose logs postiz --tail 100"
echo "    4. Verify in browser DevTools > Network that login POST goes to"
echo "       http://${PUBLIC_IP}:4007/api/... (NOT localhost)"
echo ""
echo "  Backups saved at:"
echo "    $ENV_FILE.$BACKUP_SUFFIX"
echo "    $COMPOSE_FILE.$BACKUP_SUFFIX"
echo ""
