# 🚀 Quick Start - Deploy in 2 Commands

## Deploy AI1STSEO Backend to AWS App Runner

### Step 1: Setup GitHub
```powershell
.\setup-github.ps1
```
- Creates GitHub repo
- Pushes code
- Takes 2 minutes

### Step 2: Deploy to AWS
```powershell
.\deploy-apprunner.ps1 -GitHubRepoUrl "YOUR_GITHUB_URL"
```
- Creates App Runner service
- Deploys backend
- Takes 10 minutes

### Step 3: Get Your URL
Script will output:
```
📍 Your API Base URL:
   https://xxxxx.us-east-1.awsapprunner.com
```

### Step 4: Update Frontend
```javascript
const API_BASE_URL = 'https://xxxxx.us-east-1.awsapprunner.com';
```

## That's It! 🎉

Your backend is live with:
- ✅ HTTPS enabled
- ✅ CORS configured for ai1stseo.com
- ✅ Auto-scaling
- ✅ Automatic deployments from GitHub

## Test It
```bash
curl https://YOUR_URL/api/health
```

## Cost
~$13-15/month

## Need Help?
See `APPRUNNER_DEPLOYMENT_INSTRUCTIONS.md`
