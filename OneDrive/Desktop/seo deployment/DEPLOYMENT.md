# AISEO Master - Deployment Guide

## Overview
AISEO Master is a comprehensive SEO analyzer with 180 checks across 9 categories. It consists of:
- **Flask Backend** (Python) - API that performs SEO analysis
- **HTML Frontend** - User interface for entering URLs and viewing results

---

## Prerequisites

### Server Requirements
- Python 3.8 or higher
- 512MB RAM minimum (1GB recommended)
- Linux, Windows, or macOS server

### Required Python Packages
All dependencies are listed in `backend/requirements.txt`:
- Flask
- Flask-CORS
- requests
- beautifulsoup4

---

## File Structure

Ensure this folder structure is maintained on the server:

```
/your-app-directory/
├── backend/
│   ├── app.py              # Main Flask application
│   └── requirements.txt    # Python dependencies
├── assets/
│   └── *.js                # React frontend assets
├── index.html              # Main entry page (React)
├── audit.html              # Results display page
├── analyze.html            # Standalone analyzer form
└── DEPLOYMENT.md           # This file
```

---

## Installation Steps

### Step 1: Upload Files
Upload all files to your server maintaining the folder structure above.

### Step 2: Install Python Dependencies

```bash
cd /path/to/your-app-directory/backend
pip install -r requirements.txt
```

Or install individually:
```bash
pip install flask flask-cors requests beautifulsoup4
```

### Step 3: Test the Application

For initial testing, run:
```bash
cd /path/to/your-app-directory/backend
python app.py
```

You should see:
```
🚀 AISEO Master Backend starting...
📊 Total Checks: 180 across 9 categories
📍 http://localhost:5000
```

Visit `http://your-server-ip:5000` to verify it works.

---

## Production Deployment

### Option A: Using Gunicorn (Recommended for Linux)

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run the application:
```bash
cd /path/to/your-app-directory/backend
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

3. For background running with systemd, create `/etc/systemd/system/aiseo.service`:
```ini
[Unit]
Description=AISEO Master SEO Analyzer
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/your-app-directory/backend
ExecStart=/usr/local/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

4. Enable and start:
```bash
sudo systemctl enable aiseo
sudo systemctl start aiseo
```

### Option B: Using Waitress (Windows/Linux)

1. Install Waitress:
```bash
pip install waitress
```

2. Run the application:
```bash
cd /path/to/your-app-directory/backend
waitress-serve --port=5000 app:app
```

### Option C: Using PM2 (Node.js process manager)

1. Install PM2:
```bash
npm install -g pm2
```

2. Create `ecosystem.config.js`:
```javascript
module.exports = {
  apps: [{
    name: 'aiseo-master',
    script: 'gunicorn',
    args: '-w 4 -b 127.0.0.1:5000 app:app',
    cwd: '/path/to/your-app-directory/backend',
    interpreter: 'none'
  }]
}
```

3. Start with PM2:
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

---

## Reverse Proxy Configuration

### Nginx Configuration

Create `/etc/nginx/sites-available/aiseo`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/ssl/certificate.crt;
    ssl_certificate_key /path/to/ssl/private.key;

    # Proxy to Flask app
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings for long-running analysis
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/aiseo /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Apache Configuration

Add to your Apache config or `.htaccess`:

```apache
<VirtualHost *:443>
    ServerName yourdomain.com
    
    SSLEngine on
    SSLCertificateFile /path/to/certificate.crt
    SSLCertificateKeyFile /path/to/private.key

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/
    
    # Timeout for long analysis
    ProxyTimeout 60
</VirtualHost>
```

Enable required modules:
```bash
sudo a2enmod proxy proxy_http ssl
sudo systemctl restart apache2
```

---

## Configuration Options

### Changing the Port

In `backend/app.py`, modify the last line:
```python
app.run(debug=False, port=8080, host='0.0.0.0')
```

### Enabling/Disabling Debug Mode

For production, ensure debug is OFF in `backend/app.py`:
```python
app.run(debug=False, port=5000)
```

### CORS Configuration

If frontend and backend are on different domains, update in `backend/app.py`:
```python
from flask_cors import CORS
CORS(app, origins=['https://yourdomain.com', 'https://www.yourdomain.com'])
```

### Request Timeout

The analyzer may take 15-30 seconds for comprehensive analysis. Ensure your reverse proxy and server have appropriate timeout settings (60 seconds recommended).

### LLM/AI Configuration (Optional)

The AI recommendations feature uses a local Ollama server. Configure the endpoint in `backend/app.py`:

```python
# Default: Uses reverse proxy to local Ollama server
OLLAMA_URL = 'https://api.databi.io/api'

# Alternative: Direct connection to local Ollama
# OLLAMA_URL = 'http://192.168.2.200:11434/api'

# Or if Ollama is on the same server:
# OLLAMA_URL = 'http://localhost:11434/api'
```

The AI feature requires:
- Ollama server running with Llama 3.1 model
- Network access to the Ollama endpoint
- Timeout of 120+ seconds for LLM responses

If the Ollama server is unavailable, the SEO analysis will still work - only the AI recommendations button will show an error.

---

## Firewall Configuration

If not using a reverse proxy, open port 5000:

```bash
# Ubuntu/Debian with UFW
sudo ufw allow 5000

# CentOS/RHEL with firewalld
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

---

## Troubleshooting

### Issue: "Module not found" errors
**Solution:** Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Issue: Permission denied on port 80/443
**Solution:** Use a reverse proxy (Nginx/Apache) or run on port 5000

### Issue: Analysis times out
**Solution:** Increase timeout in reverse proxy config to 60+ seconds

### Issue: CORS errors in browser
**Solution:** Update CORS configuration in `app.py` to include your domain

### Issue: Static files not loading
**Solution:** Verify folder structure matches the expected layout above

### Issue: "Address already in use"
**Solution:** Another process is using the port. Find and stop it:
```bash
lsof -i :5000
kill -9 <PID>
```

---

## Health Check

Verify the API is running:
```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "totalChecks": 180,
  "categories": {
    "technical": 35,
    "onpage": 25,
    "content": 20,
    "mobile": 15,
    "performance": 18,
    "security": 12,
    "social": 10,
    "local": 15,
    "geo": 30
  }
}
```

---

## Security Recommendations

1. **Always use HTTPS** in production
2. **Run behind a reverse proxy** (Nginx/Apache)
3. **Don't expose port 5000** directly to the internet
4. **Set debug=False** in production
5. **Use a non-root user** to run the application
6. **Keep Python and dependencies updated**

---

## Support

For issues or questions, contact your development team.

**Version:** 1.0  
**Last Updated:** February 2026  
**Total SEO Checks:** 180 across 9 categories
