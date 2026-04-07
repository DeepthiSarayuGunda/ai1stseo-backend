# Postiz Login Debug Guide

## Symptom

Login page loads at `http://<EC2_IP>:4007`, credentials are entered, form is submitted, page refreshes, fields clear, no session is established.

---

## Root Causes (Ranked Most → Least Likely)

### 1. NEXT_PUBLIC_BACKEND_URL Mismatch (Most Likely)

The Postiz frontend (Next.js) uses `NEXT_PUBLIC_BACKEND_URL` at **build time** to know where to send API requests. The official Docker image was built with this baked to `http://localhost:4007/api` or similar. When you access the app from your browser at `http://<EC2_IP>:4007`, the frontend JS still sends login POST requests to `localhost:4007/api` — which resolves to **your local machine**, not the EC2 server. The login request silently fails or returns an error, and the page refreshes.

This is the #1 cause of the "login just refreshes" symptom on self-hosted Postiz.

**Verify:**
```bash
# Check what NEXT_PUBLIC_BACKEND_URL is set to
sudo docker exec postiz printenv | grep -i NEXT_PUBLIC_BACKEND_URL

# Check what the frontend actually uses (baked at build time)
sudo docker exec postiz sh -c "grep -r 'NEXT_PUBLIC_BACKEND_URL' /app/.next/ 2>/dev/null | head -5"

# From your LOCAL browser, open DevTools > Network tab, submit login
# Look at the POST request URL — if it goes to localhost:3000 or localhost:4007, this is the problem
```

**Fix:**
```bash
# In /opt/postiz/.env, ensure these are set to your EC2 public IP:
MAIN_URL=http://<EC2_IP>:4007
FRONTEND_URL=http://<EC2_IP>:4007
NEXT_PUBLIC_BACKEND_URL=http://<EC2_IP>:4007/api

# IMPORTANT: NEXT_PUBLIC_* vars are baked at build time in Next.js.
# The Postiz Docker image handles this at runtime via a startup script,
# but ONLY if the env var is correctly passed to the container.
# Restart the container (not just the process):
cd /opt/postiz
sudo docker compose down postiz
sudo docker compose up -d postiz
```

**Expected Result:** Login POST goes to `http://<EC2_IP>:4007/api/auth/login`, returns 200 with JWT, cookie is set, redirect to dashboard.

---

### 2. BACKEND_INTERNAL_URL Misconfigured

Inside the Postiz container, the Next.js frontend (port 5000) proxies API calls to the NestJS backend (port 3000) internally. `BACKEND_INTERNAL_URL` must be `http://localhost:3000` (internal to the container). If this is wrong, the server-side proxy fails silently.

**Verify:**
```bash
sudo docker exec postiz printenv | grep BACKEND_INTERNAL_URL

# Test internal backend reachability from inside the container
sudo docker exec postiz wget -qO- http://localhost:3000/api/health 2>&1 || \
sudo docker exec postiz curl -s http://localhost:3000/api/health 2>&1
```

**Fix:**
```bash
# In /opt/postiz/.env:
BACKEND_INTERNAL_URL=http://localhost:3000

# Restart:
cd /opt/postiz && sudo docker compose restart postiz
```

**Expected Result:** Internal API proxy works, login requests reach the NestJS backend.

---

### 3. JWT_SECRET Empty or Missing

If `JWT_SECRET` is empty, the backend cannot sign auth tokens. Login may appear to succeed server-side but the response cookie/token is invalid.

**Verify:**
```bash
sudo docker exec postiz printenv | grep JWT_SECRET
# Should output a long random string, NOT be empty
```

**Fix:**
```bash
# Generate a new secret and set it in /opt/postiz/.env:
JWT_SECRET=$(openssl rand -hex 32)
echo "JWT_SECRET=$JWT_SECRET"
# Paste into .env, then:
cd /opt/postiz && sudo docker compose restart postiz
```

**Expected Result:** JWT tokens are properly signed, auth cookie is valid.

---

### 4. Cookie Not Being Set (SameSite / Secure Flag Issues)

When accessing Postiz over plain HTTP with a raw IP address, browser cookie policies can interfere. Modern browsers may reject cookies with `SameSite=None` unless `Secure` (HTTPS) is also set. Postiz uses `httpOnly` cookies for auth.

**Verify:**
```bash
# From your local machine, check the Set-Cookie header:
curl -v -X POST http://<EC2_IP>:4007/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' 2>&1 | grep -i "set-cookie"

# In browser: DevTools > Application > Cookies — check if any postiz/auth cookie exists after login attempt
```

**Fix:**
HTTP + raw IP should work for `SameSite=Lax` (the Postiz default). If cookies are being set but the browser isn't sending them back, ensure:
- You're accessing via `http://<EC2_IP>:4007` (same origin as FRONTEND_URL)
- Not mixing `localhost` and IP access
- No browser extensions blocking cookies

**Expected Result:** `Set-Cookie` header present in login response, cookie visible in DevTools.

---

### 5. Database Not Initialized / User Table Missing

If the Prisma migrations haven't run, the users table may not exist. The backend returns a 500 on login, which the frontend handles by refreshing.

**Verify:**
```bash
# Check Postiz container logs for database errors
sudo docker compose logs postiz --tail 100 2>&1 | grep -iE "prisma|migration|database|error|500"

# Check if the database has tables
sudo docker exec postiz-postgres psql -U postiz-user -d postiz-db-local -c "\dt"

# Check if users exist
sudo docker exec postiz-postgres psql -U postiz-user -d postiz-db-local -c "SELECT id, email FROM \"User\" LIMIT 5;"
```

**Fix:**
```bash
# If tables are missing, the Postiz container should auto-migrate on startup.
# Force a fresh start (keeps volumes):
cd /opt/postiz
sudo docker compose restart postiz

# Check logs for migration output:
sudo docker compose logs postiz 2>&1 | grep -i "migrat"
```

**Expected Result:** Database has `User` table, registered users appear in query.

---

### 6. Port Mapping / Container Not Healthy

If the Postiz container is crash-looping or the internal port mapping is wrong, the frontend loads from cache/static but API calls fail.

**Verify:**
```bash
cd /opt/postiz

# Check container status
sudo docker compose ps

# Check if postiz container is healthy and not restarting
sudo docker inspect postiz --format='{{.State.Status}} restarts={{.RestartCount}}'

# Test the API endpoint directly
curl -s http://localhost:4007/api/health
curl -s http://<EC2_IP>:4007/api/health
```

**Fix:**
```bash
# If container is restarting, check logs:
sudo docker compose logs postiz --tail 200

# If port conflict, check what's using 4007:
sudo ss -tlnp | grep 4007

# Recreate the container:
cd /opt/postiz
sudo docker compose up -d --force-recreate postiz
```

**Expected Result:** `docker compose ps` shows postiz as `Up`, API health endpoint returns 200.

---

### 7. Redis Connection Failure

Postiz uses Redis for session/token management. If Redis is down, auth tokens can't be stored/validated.

**Verify:**
```bash
# Check Redis container
sudo docker compose ps postiz-redis

# Test Redis connectivity from Postiz container
sudo docker exec postiz sh -c "redis-cli -u redis://postiz-redis:6379 ping" 2>/dev/null || \
sudo docker exec postiz-redis redis-cli ping

# Check for Redis errors in logs
sudo docker compose logs postiz 2>&1 | grep -i redis
```

**Fix:**
```bash
cd /opt/postiz
sudo docker compose restart postiz-redis
sleep 5
sudo docker compose restart postiz
```

**Expected Result:** Redis responds with `PONG`, no Redis errors in Postiz logs.

---

### 8. Temporal Not Running (Indirect)

While Temporal is mainly for scheduling, if the Postiz app hard-fails on Temporal connection at startup, it may partially boot (serving static frontend) but fail on API routes.

**Verify:**
```bash
sudo docker compose ps temporal
sudo docker compose logs temporal --tail 50
sudo docker compose logs postiz 2>&1 | grep -i temporal
```

**Fix:**
```bash
cd /opt/postiz
sudo docker compose restart temporal
sleep 30  # Temporal takes a while to start
sudo docker compose restart postiz
```

**Expected Result:** Temporal shows as running, no Temporal connection errors in Postiz logs.

---

## Quick Full Diagnostic Script

Run this on the EC2 instance to get a complete picture:

```bash
cd /opt/postiz

echo "=== Container Status ==="
sudo docker compose ps

echo ""
echo "=== Postiz Env (URL-related) ==="
sudo docker exec postiz printenv | grep -iE "URL|FRONTEND|MAIN_URL|BACKEND|JWT_SECRET|IS_GENERAL"

echo ""
echo "=== Recent Postiz Errors ==="
sudo docker compose logs postiz --tail 50 2>&1 | grep -iE "error|fail|exception|warn" | tail -20

echo ""
echo "=== API Health Check ==="
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:4007/api/health 2>/dev/null
echo ""

echo ""
echo "=== Database Tables ==="
sudo docker exec postiz-postgres psql -U postiz-user -d postiz-db-local -c "\dt" 2>&1 | head -20

echo ""
echo "=== Redis Ping ==="
sudo docker exec postiz-redis redis-cli ping

echo ""
echo "=== Memory Usage ==="
free -h | head -2
```

---

## Important Note: Raw IP + HTTP Limitations

Accessing Postiz over `http://<raw-IP>:4007` works for basic login and usage. However:

- OAuth callbacks for social media platforms (LinkedIn, Facebook, etc.) may require HTTPS
- Some browsers in strict mode may warn about non-secure cookies
- TikTok explicitly requires HTTPS for redirect URIs

For login itself, HTTP + raw IP is fine as long as `MAIN_URL`, `FRONTEND_URL`, and `NEXT_PUBLIC_BACKEND_URL` all consistently use the same `http://<EC2_IP>:4007` base.
