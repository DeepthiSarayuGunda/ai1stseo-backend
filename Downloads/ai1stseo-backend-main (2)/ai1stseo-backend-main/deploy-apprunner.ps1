# AI1STSEO Backend - AWS App Runner Deployment Script
# This script deploys the backend to AWS App Runner from GitHub

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubRepoUrl,
    
    [string]$Region = "us-east-1",
    [string]$ServiceName = "ai1stseo-backend",
    [string]$Branch = "main",
    [string]$ConnectionName = "ai1stseo-github-connection"
)

Write-Host "🚀 AI1STSEO Backend - AWS App Runner Deployment" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

# Validate GitHub URL
if ($GitHubRepoUrl -notmatch "^https://github\.com/[\w-]+/[\w-]+") {
    Write-Host "❌ Invalid GitHub URL format" -ForegroundColor Red
    Write-Host "Expected format: https://github.com/username/repo" -ForegroundColor Yellow
    exit 1
}

Write-Host "📋 Configuration:" -ForegroundColor Cyan
Write-Host "  GitHub Repo: $GitHubRepoUrl" -ForegroundColor White
Write-Host "  Branch: $Branch" -ForegroundColor White
Write-Host "  Service Name: $ServiceName" -ForegroundColor White
Write-Host "  Region: $Region" -ForegroundColor White
Write-Host ""

# Step 1: Check if connection exists
Write-Host "🔗 Step 1: Checking GitHub connection..." -ForegroundColor Yellow

$existingConnections = aws apprunner list-connections --region $Region --query "ConnectionSummaryList[?ConnectionName=='$ConnectionName'].ConnectionArn" --output text

if ($existingConnections) {
    Write-Host "✓ Found existing connection: $ConnectionName" -ForegroundColor Green
    $connectionArn = $existingConnections
    
    # Check connection status
    $connectionStatus = aws apprunner describe-connection --connection-arn $connectionArn --region $Region --query "Connection.Status" --output text
    
    if ($connectionStatus -ne "AVAILABLE") {
        Write-Host "⚠️  Connection status: $connectionStatus" -ForegroundColor Yellow
        Write-Host "Please complete the GitHub handshake in AWS Console:" -ForegroundColor Yellow
        Write-Host "  1. Go to: https://console.aws.amazon.com/apprunner/home?region=$Region#/connections" -ForegroundColor Cyan
        Write-Host "  2. Find connection: $ConnectionName" -ForegroundColor Cyan
        Write-Host "  3. Click 'Complete handshake'" -ForegroundColor Cyan
        Write-Host "  4. Authorize AWS to access your GitHub account" -ForegroundColor Cyan
        Write-Host ""
        $continue = Read-Host "Press Enter when handshake is complete, or 'q' to quit"
        if ($continue -eq 'q') { exit 0 }
    } else {
        Write-Host "✓ Connection is active" -ForegroundColor Green
    }
} else {
    Write-Host "Creating new GitHub connection..." -ForegroundColor Yellow
    
    $createResult = aws apprunner create-connection `
        --connection-name $ConnectionName `
        --provider-type GITHUB `
        --region $Region `
        --output json | ConvertFrom-Json
    
    $connectionArn = $createResult.Connection.ConnectionArn
    
    Write-Host "✓ Connection created: $connectionArn" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Complete GitHub handshake" -ForegroundColor Yellow
    Write-Host "  1. Go to: https://console.aws.amazon.com/apprunner/home?region=$Region#/connections" -ForegroundColor Cyan
    Write-Host "  2. Find connection: $ConnectionName" -ForegroundColor Cyan
    Write-Host "  3. Click 'Complete handshake'" -ForegroundColor Cyan
    Write-Host "  4. Authorize AWS to access your GitHub account" -ForegroundColor Cyan
    Write-Host ""
    $continue = Read-Host "Press Enter when handshake is complete, or 'q' to quit"
    if ($continue -eq 'q') { exit 0 }
}

Write-Host ""

# Step 2: Check if service already exists
Write-Host "🔍 Step 2: Checking if service exists..." -ForegroundColor Yellow

$existingService = aws apprunner list-services --region $Region --query "ServiceSummaryList[?ServiceName=='$ServiceName'].ServiceArn" --output text

if ($existingService) {
    Write-Host "⚠️  Service '$ServiceName' already exists" -ForegroundColor Yellow
    Write-Host "Service ARN: $existingService" -ForegroundColor Gray
    
    $action = Read-Host "Choose action: [u]pdate, [d]elete and recreate, [q]uit"
    
    if ($action -eq 'q') {
        exit 0
    } elseif ($action -eq 'd') {
        Write-Host "Deleting existing service..." -ForegroundColor Yellow
        aws apprunner delete-service --service-arn $existingService --region $Region
        Write-Host "✓ Service deletion initiated (this may take a few minutes)" -ForegroundColor Green
        Write-Host "Waiting for deletion to complete..." -ForegroundColor Yellow
        Start-Sleep -Seconds 60
    } elseif ($action -eq 'u') {
        Write-Host "Triggering deployment to existing service..." -ForegroundColor Yellow
        aws apprunner start-deployment --service-arn $existingService --region $Region
        Write-Host "✓ Deployment started" -ForegroundColor Green
        $serviceArn = $existingService
        $isUpdate = $true
    }
}

Write-Host ""

# Step 3: Create App Runner service (if not updating)
if (-not $isUpdate) {
    Write-Host "🚀 Step 3: Creating App Runner service..." -ForegroundColor Yellow
    
    $sourceConfig = @{
        AuthenticationConfiguration = @{
            ConnectionArn = $connectionArn
        }
        AutoDeploymentsEnabled = $true
        CodeRepository = @{
            RepositoryUrl = $GitHubRepoUrl
            SourceCodeVersion = @{
                Type = "BRANCH"
                Value = $Branch
            }
            CodeConfiguration = @{
                ConfigurationSource = "API"
                CodeConfigurationValues = @{
                    Runtime = "PYTHON_3"
                    BuildCommand = "pip install -r requirements.txt"
                    StartCommand = "gunicorn application:application --bind 0.0.0.0:8000 --workers 4 --timeout 120"
                    Port = "8000"
                    RuntimeEnvironmentVariables = @{}
                }
            }
        }
    } | ConvertTo-Json -Depth 10 -Compress
    
    $instanceConfig = @{
        Cpu = "1 vCPU"
        Memory = "2 GB"
    } | ConvertTo-Json -Compress
    
    Write-Host "Creating service with configuration:" -ForegroundColor Gray
    Write-Host "  CPU: 1 vCPU" -ForegroundColor Gray
    Write-Host "  Memory: 2 GB" -ForegroundColor Gray
    Write-Host "  Runtime: Python 3" -ForegroundColor Gray
    Write-Host ""
    
    $createServiceResult = aws apprunner create-service `
        --service-name $ServiceName `
        --source-configuration $sourceConfig `
        --instance-configuration $instanceConfig `
        --region $Region `
        --output json | ConvertFrom-Json
    
    $serviceArn = $createServiceResult.Service.ServiceArn
    
    Write-Host "✓ Service creation initiated" -ForegroundColor Green
    Write-Host "Service ARN: $serviceArn" -ForegroundColor Gray
}

Write-Host ""

# Step 4: Wait for service to be ready
Write-Host "⏳ Step 4: Waiting for service to be ready..." -ForegroundColor Yellow
Write-Host "This typically takes 5-10 minutes for initial deployment" -ForegroundColor Gray
Write-Host ""

$maxAttempts = 60
$attempt = 0

while ($attempt -lt $maxAttempts) {
    Start-Sleep -Seconds 15
    $attempt++
    
    $serviceInfo = aws apprunner describe-service `
        --service-arn $serviceArn `
        --region $Region `
        --output json | ConvertFrom-Json
    
    $status = $serviceInfo.Service.Status
    $serviceUrl = $serviceInfo.Service.ServiceUrl
    
    Write-Host "  Status: $status | Attempt: $attempt/$maxAttempts" -ForegroundColor Gray
    
    if ($status -eq "RUNNING") {
        Write-Host ""
        Write-Host "✅ SERVICE DEPLOYED SUCCESSFULLY!" -ForegroundColor Green
        Write-Host ""
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
        Write-Host "📍 Your API Base URL:" -ForegroundColor Cyan
        Write-Host "   https://$serviceUrl" -ForegroundColor White -BackgroundColor DarkGreen
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
        Write-Host ""
        Write-Host "🧪 Test your API:" -ForegroundColor Cyan
        Write-Host "   curl https://$serviceUrl/api/health" -ForegroundColor White
        Write-Host ""
        Write-Host "📝 API Endpoints:" -ForegroundColor Cyan
        Write-Host "   GET  https://$serviceUrl/api/health" -ForegroundColor White
        Write-Host "   POST https://$serviceUrl/api/analyze" -ForegroundColor White
        Write-Host "   POST https://$serviceUrl/api/ai-recommendations" -ForegroundColor White
        Write-Host ""
        Write-Host "🔧 Update your frontend:" -ForegroundColor Cyan
        Write-Host "   const API_BASE_URL = 'https://$serviceUrl';" -ForegroundColor White
        Write-Host ""
        Write-Host "📊 Monitor your service:" -ForegroundColor Cyan
        Write-Host "   https://console.aws.amazon.com/apprunner/home?region=$Region#/services/$ServiceName" -ForegroundColor White
        Write-Host ""
        Write-Host "✨ CORS is already configured for:" -ForegroundColor Cyan
        Write-Host "   - https://ai1stseo.com" -ForegroundColor White
        Write-Host "   - https://www.ai1stseo.com" -ForegroundColor White
        Write-Host ""
        
        # Test the health endpoint
        Write-Host "🧪 Testing health endpoint..." -ForegroundColor Yellow
        try {
            $response = Invoke-RestMethod -Uri "https://$serviceUrl/api/health" -Method Get
            Write-Host "✓ Health check passed!" -ForegroundColor Green
            Write-Host "  Total checks: $($response.totalChecks)" -ForegroundColor Gray
        } catch {
            Write-Host "⚠️  Health check failed (service may still be starting)" -ForegroundColor Yellow
        }
        
        break
    } elseif ($status -eq "CREATE_FAILED" -or $status -eq "OPERATION_FAILED") {
        Write-Host ""
        Write-Host "❌ Service deployment failed" -ForegroundColor Red
        Write-Host "Check the App Runner console for error details:" -ForegroundColor Yellow
        Write-Host "https://console.aws.amazon.com/apprunner/home?region=$Region#/services/$ServiceName" -ForegroundColor Cyan
        exit 1
    }
}

if ($attempt -ge $maxAttempts) {
    Write-Host ""
    Write-Host "⚠️  Timeout waiting for service to be ready" -ForegroundColor Yellow
    Write-Host "The service is still deploying. Check status in AWS Console:" -ForegroundColor Yellow
    Write-Host "https://console.aws.amazon.com/apprunner/home?region=$Region#/services/$ServiceName" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "🎉 Deployment script completed!" -ForegroundColor Green
