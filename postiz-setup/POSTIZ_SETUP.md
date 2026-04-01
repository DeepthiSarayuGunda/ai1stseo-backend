# Postiz Self-Hosted — Step-by-Step Deployment Guide

## Overview

This guide deploys the open-source [Postiz](https://github.com/gitroomhq/postiz-app) social media scheduler on an AWS EC2 instance using Docker Compose. Postiz uses a Temporal workflow engine for reliable scheduling and supports 32+ social platforms.

**Architecture:** Postiz app + PostgreSQL + Redis + Temporal (with Elasticsearch) — all containerized.

---

## Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| EC2 Instance | t3.small (2GB RAM) | t3.medium (4GB RAM) |
| OS | Ubuntu 24.04 LTS or Amazon Linux 2023 | Ubuntu 24.04 LTS |
| Storage | 20GB EBS | 30GB+ EBS (gp3) |
| Ports | 4007, 22 | 4007, 8080, 22 |

You'll also need social media API credentials for the platforms you want to connect (LinkedIn, Facebook, X, etc.).

---

## Step 1: Launch EC2 Instance

1. Go to AWS Console > EC2 > Launch Instance
2. Select **Ubuntu Server 24.04 LTS** AMI
3. Choose **t3.medium** instance type
4. Configure storage: **30 GB gp3**
5. Security Group — add inbound rules:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | Your IP | SSH access |
| Custom TCP | 4007 | 0.0.0.0/0 | Postiz UI |
| Custom TCP | 8080 | Your IP | Temporal UI (optional) |

6. Launch with your key pair

## Step 2: Connect to EC2

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

## Step 3: Run the Deployment Script

Upload and run the automated deployment script:

```bash
# Upload the script (from your local machine)
scp -i your-key.pem deploy_postiz.sh ubuntu@<EC2_PUBLIC_IP>:~/

# On the EC2 instance
chmod +x deploy_postiz.sh
sudo ./deploy_postiz.sh
```

This installs Docker, creates the compose stack at `/opt/postiz/`, and starts all services.

## Step 4: Configure Social Media API Keys

Edit the environment file with your platform credentials:

```bash
sudo nano /opt/postiz/.env
```

### Getting API Credentials

**LinkedIn:**
1. Go to https://www.linkedin.com/developers/apps
2. Create an app, add products: "Share on LinkedIn", "Sign In with LinkedIn using OpenID Connect", and request "Advertising API" (needed for token refresh)
3. Under Auth tab, set OAuth 2.0 redirect URL to: `http://<EC2_IP>:4007/integrations/social/linkedin`
4. For LinkedIn Page posting, also add: `http://<EC2_IP>:4007/integrations/social/linkedin-page`
5. Copy Client ID and Client Secret to `.env`

**Facebook / Instagram:**
1. Go to https://developers.facebook.com
2. Create an app → select "Other" → select your business portfolio
3. Add "Facebook Login for Business" product
4. Set Valid OAuth Redirect URI to: `http://<EC2_IP>:4007/integrations/social/facebook`
5. Under App Review > Permissions, request: `pages_show_list`, `business_management`, `pages_manage_posts`, `pages_manage_engagement`, `pages_read_engagement`, `read_insights` (for personal use these are optional)
6. Set App Mode to "Live" (otherwise posts are only visible to you)
7. Copy App ID and App Secret to `.env` (same app works for both Facebook and Instagram)

**Twitter/X:**
1. Go to https://developer.x.com/en/portal/dashboard
2. Create a project and app
3. Enable OAuth 2.0, set callback URL to: `http://<EC2_IP>:4007/integrations/social/x`
4. Copy API Key and API Secret to `.env`

After editing, restart Postiz:

```bash
cd /opt/postiz
sudo docker compose restart postiz
```

## Step 5: Access the UI

Open your browser and go to:

```
http://<EC2_PUBLIC_IP>:4007
```

1. Create your admin account (first user becomes admin)
2. Go to **Settings > Channels** to connect social media accounts
3. Authorize each platform via OAuth

## Step 6: Verify Services Are Running

```bash
cd /opt/postiz
sudo docker compose ps
```

Expected output — all services should show `Up (healthy)` or `Up`:

```
NAME                      STATUS
postiz                    Up
postiz-postgres           Up (healthy)
postiz-redis              Up (healthy)
temporal                  Up
temporal-elasticsearch    Up
temporal-postgresql       Up
temporal-ui               Up
```

Check logs if something is wrong:

```bash
sudo docker compose logs -f postiz          # Postiz app logs
sudo docker compose logs -f temporal        # Temporal logs
```

## Step 7: Get API Key for Backend Integration

1. Log in to Postiz UI
2. Go to **Settings > Developers > Public API**
3. Generate an API key
4. The self-hosted API base URL is: `http://<EC2_IP>:4007/api/public/v1`

---

## Optional: Domain + HTTPS with Nginx

For production use, put Nginx in front with Let's Encrypt:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# Create Nginx config
sudo tee /etc/nginx/sites-available/postiz << 'EOF'
server {
    listen 80;
    server_name postiz.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:4007;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/postiz /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d postiz.yourdomain.com
```

After setting up HTTPS, update the `.env` URLs:

```bash
MAIN_URL=https://postiz.yourdomain.com
FRONTEND_URL=https://postiz.yourdomain.com
NEXT_PUBLIC_BACKEND_URL=https://postiz.yourdomain.com/api
```

And restart: `sudo docker compose restart postiz`

---

## Maintenance Commands

```bash
cd /opt/postiz

# Stop all services
sudo docker compose down

# Start all services
sudo docker compose up -d

# Update to latest version
sudo docker compose pull
sudo docker compose up -d

# View logs
sudo docker compose logs -f postiz

# Reset everything (WARNING: deletes all data)
sudo docker compose down -v
sudo docker compose up -d

# Backup PostgreSQL
sudo docker exec postiz-postgres pg_dump -U postiz-user postiz-db-local > backup.sql
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Postiz container keeps restarting | Check logs: `docker compose logs postiz`. Usually a DB connection issue — wait for postgres to be healthy. |
| "Cannot connect to Temporal" | Temporal takes 30-60s to start. Wait and check: `docker compose logs temporal` |
| OAuth redirect fails | Ensure your `.env` URLs match exactly what you configured in the platform's developer console |
| Out of memory | Upgrade to t3.medium (4GB). Elasticsearch + Temporal are memory-hungry. |
| Port 4007 not accessible | Check EC2 security group inbound rules |
