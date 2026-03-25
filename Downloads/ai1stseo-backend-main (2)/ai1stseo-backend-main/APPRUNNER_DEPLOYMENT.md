# Deploy AI1STSEO Backend to AWS App Runner

## Quick Start - Deploy from GitHub

### Step 1: Push Code to GitHub

If you don't have a GitHub repository yet, create one:

```bash
cd "seo deployment/backend"

# Initialize git repository
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - AI1STSEO backend"

# Create a new repository on GitHub (via web interface)
# Then add remote and push:
git remote add origin https://github.com/YOUR_USERNAME/ai1stseo-backend.git
git branch -M main
git push -u origin main
```

### Step 2: Create GitHub Connection in AWS

```bash
# Create a connection to GitHub
aws apprunner create-connection \
  --connection-name ai1stseo-github \
  --provider-type GITHUB \
  --region us-east-1
```

This will return a connection ARN. You'll need to complete the GitHub authorization in the AWS Console:
1. Go to AWS Console → App Runner → Connections
2. Find your connection and click "Complete handshake"
3. Authorize AWS to access your GitHub account

### Step 3: Create App Runner Service

Once the GitHub connection is active, create the service:

```bash
aws apprunner create-service \
  --service-name ai1stseo-backend \
  --source-configuration '{
    "AuthenticationConfiguration": {
      "ConnectionArn": "YOUR_CONNECTION_ARN"
    },
    "AutoDeploymentsEnabled": true,
    "CodeRepository": {
      "RepositoryUrl": "https://github.com/YOUR_USERNAME/ai1stseo-backend",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "main"
      },
      "CodeConfiguration": {
        "ConfigurationSource": "API",
        "CodeConfigurationValues": {
          "Runtime": "PYTHON_3",
          "BuildCommand": "pip install -r requirements.txt",
          "StartCommand": "gunicorn application:application --bind 0.0.0.0:8000 --workers 4 --timeout 120",
          "Port": "8000",
          "RuntimeEnvironmentVariables": {}
        }
      }
    }
  }' \
  --instance-configuration '{
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }' \
  --region us-east-1
```

### Step 4: Get Service URL

```bash
aws apprunner describe-service \
  --service-arn YOUR_SERVICE_ARN \
  --region us-east-1 \
  --query "Service.ServiceUrl" \
  --output text
```

Your API will be available at: `https://YOUR_SERVICE_ID.us-east-1.awsapprunner.com`

## Alternative: Deploy via AWS Console

### Step 1: Prepare GitHub Repository
1. Push your code to GitHub (see Step 1 above)

### Step 2: Create Service in Console
1. Go to AWS Console → App Runner
2. Click "Create service"
3. **Source**: Repository
4. **Repository type**: Source code repository
5. **Connect to GitHub**: Create new connection or use existing
6. **Repository**: Select your repository
7. **Branch**: main
8. **Deployment trigger**: Automatic
9. Click "Next"

### Step 3: Configure Build
1. **Runtime**: Python 3
2. **Build command**: `pip install -r requirements.txt`
3. **Start command**: `gunicorn application:application --bind 0.0.0.0:8000 --workers 4 --timeout 120`
4. **Port**: 8000
5. Click "Next"

### Step 4: Configure Service
1. **Service name**: ai1stseo-backend
2. **CPU**: 1 vCPU
3. **Memory**: 2 GB
4. **Environment variables**: (none needed)
5. Click "Next"

### Step 5: Review and Create
1. Review all settings
2. Click "Create & deploy"
3. Wait 5-10 minutes for deployment

### Step 6: Get Service URL
Once deployed, copy the service URL from the console.

## Using apprunner.yaml Configuration

If you prefer to use the `apprunner.yaml` file for configuration:

```bash
aws apprunner create-service \
  --service-name ai1stseo-backend \
  --source-configuration '{
    "AuthenticationConfiguration": {
      "ConnectionArn": "YOUR_CONNECTION_ARN"
    },
    "AutoDeploymentsEnabled": true,
    "CodeRepository": {
      "RepositoryUrl": "https://github.com/YOUR_USERNAME/ai1stseo-backend",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "main"
      },
      "CodeConfiguration": {
        "ConfigurationSource": "REPOSITORY"
      }
    }
  }' \
  --instance-configuration '{
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }' \
  --region us-east-1
```

This will use the `apprunner.yaml` file in your repository for build/run configuration.

## Testing Your Deployment

Once deployed, test your API:

```bash
# Get your service URL
SERVICE_URL=$(aws apprunner describe-service \
  --service-arn YOUR_SERVICE_ARN \
  --region us-east-1 \
  --query "Service.ServiceUrl" \
  --output text)

# Health check
curl https://$SERVICE_URL/api/health

# Test analysis
curl -X POST https://$SERVICE_URL/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "categories": ["technical", "onpage"]
  }'
```

## Update Frontend

Update your frontend to use the App Runner URL:

```javascript
const API_BASE_URL = 'https://YOUR_SERVICE_ID.us-east-1.awsapprunner.com';
```

## CORS Configuration

The backend is already configured with CORS for:
- https://ai1stseo.com
- https://www.ai1stseo.com
- http://localhost:5000

If you need to add more domains, update `app.py`:

```python
CORS(app, origins=[
    'https://ai1stseo.com',
    'https://www.ai1stseo.com',
    'https://your-new-domain.com',
    'http://localhost:5000'
])
```

Then commit and push to trigger auto-deployment.

## Custom Domain (Optional)

To use a custom domain like `api.ai1stseo.com`:

```bash
# Associate custom domain
aws apprunner associate-custom-domain \
  --service-arn YOUR_SERVICE_ARN \
  --domain-name api.ai1stseo.com \
  --region us-east-1

# Get validation records
aws apprunner describe-custom-domains \
  --service-arn YOUR_SERVICE_ARN \
  --region us-east-1
```

Add the CNAME records to your DNS (Route 53 or Cloudflare).

## Monitoring

### View Logs
```bash
# Get log streams
aws logs describe-log-streams \
  --log-group-name /aws/apprunner/ai1stseo-backend/service \
  --region us-east-1

# View logs
aws logs tail /aws/apprunner/ai1stseo-backend/service --follow
```

### Service Metrics
View in AWS Console → App Runner → Your Service → Metrics

## Cost Estimate

App Runner pricing:
- **Provisioned container**: $0.007/hour (~$5/month for 1 vCPU, 2GB)
- **Active container**: $0.064/vCPU-hour + $0.007/GB-hour
- **Build**: $0.005/build minute

Estimated monthly cost: **$10-20** depending on traffic

## Troubleshooting

### Build Fails
- Check build logs in App Runner console
- Verify `requirements.txt` is correct
- Ensure Python version matches (3.13)

### Service Won't Start
- Check start command is correct
- Verify port 8000 is configured
- Check application logs

### CORS Errors
- Verify domain is in CORS origins list
- Check browser console for specific error
- Ensure HTTPS is used (App Runner uses HTTPS by default)

### Connection to GitHub Fails
- Complete the GitHub handshake in AWS Console
- Verify repository URL is correct
- Check GitHub permissions

## Updating the Service

### Auto-Deploy (Recommended)
Just push to GitHub:
```bash
git add .
git commit -m "Update backend"
git push
```

App Runner will automatically detect changes and deploy.

### Manual Deploy
```bash
aws apprunner start-deployment \
  --service-arn YOUR_SERVICE_ARN \
  --region us-east-1
```

## Cleanup

To delete the service:
```bash
aws apprunner delete-service \
  --service-arn YOUR_SERVICE_ARN \
  --region us-east-1
```

## Next Steps

1. ✅ Push code to GitHub
2. ✅ Create GitHub connection in AWS
3. ✅ Create App Runner service
4. ✅ Get service URL
5. ✅ Test API endpoints
6. ✅ Update frontend with new URL
7. ⏳ Set up custom domain (optional)
8. ⏳ Configure monitoring and alerts

---

**Note**: App Runner automatically provides HTTPS, so your API will be secure by default!
