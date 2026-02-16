# Setup GitHub Repository for AI1STSEO Backend

Write-Host "📦 AI1STSEO Backend - GitHub Setup" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green
Write-Host ""

# Check if git is installed
try {
    git --version | Out-Null
} catch {
    Write-Host "❌ Git is not installed" -ForegroundColor Red
    Write-Host "Please install Git from: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Git is installed" -ForegroundColor Green
Write-Host ""

# Check if already a git repository
if (Test-Path ".git") {
    Write-Host "✓ Git repository already initialized" -ForegroundColor Green
    
    # Check for remote
    $remote = git remote get-url origin 2>$null
    if ($remote) {
        Write-Host "✓ Remote origin: $remote" -ForegroundColor Green
        Write-Host ""
        Write-Host "Your repository is ready!" -ForegroundColor Green
        Write-Host "To deploy, run:" -ForegroundColor Cyan
        Write-Host "  .\deploy-apprunner.ps1 -GitHubRepoUrl '$remote'" -ForegroundColor White
        exit 0
    }
} else {
    Write-Host "Initializing Git repository..." -ForegroundColor Yellow
    git init
    Write-Host "✓ Repository initialized" -ForegroundColor Green
}

Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Create a new repository on GitHub:" -ForegroundColor Yellow
Write-Host "   - Go to: https://github.com/new" -ForegroundColor White
Write-Host "   - Repository name: ai1stseo-backend (or your choice)" -ForegroundColor White
Write-Host "   - Visibility: Private or Public" -ForegroundColor White
Write-Host "   - Do NOT initialize with README" -ForegroundColor White
Write-Host "   - Click 'Create repository'" -ForegroundColor White
Write-Host ""

$repoUrl = Read-Host "2. Enter your GitHub repository URL (e.g., https://github.com/username/ai1stseo-backend)"

if (-not $repoUrl) {
    Write-Host "❌ Repository URL is required" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "3. Setting up Git configuration..." -ForegroundColor Yellow

# Add remote
git remote add origin $repoUrl
Write-Host "✓ Remote added: $repoUrl" -ForegroundColor Green

# Create .gitignore if it doesn't exist
if (-not (Test-Path ".gitignore")) {
    @"
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
*.egg-info/
dist/
build/
*.zip
.elasticbeanstalk/
.DS_Store
*.log
"@ | Out-File -FilePath ".gitignore" -Encoding utf8
    Write-Host "✓ Created .gitignore" -ForegroundColor Green
}

# Add all files
git add .
Write-Host "✓ Files staged" -ForegroundColor Green

# Commit
git commit -m "Initial commit - AI1STSEO backend API"
Write-Host "✓ Changes committed" -ForegroundColor Green

# Set branch to main
git branch -M main
Write-Host "✓ Branch set to main" -ForegroundColor Green

Write-Host ""
Write-Host "4. Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "   (You may be prompted for GitHub credentials)" -ForegroundColor Gray

try {
    git push -u origin main
    Write-Host "✓ Code pushed to GitHub!" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Push failed. You may need to authenticate with GitHub" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If using HTTPS, you'll need a Personal Access Token:" -ForegroundColor Cyan
    Write-Host "  1. Go to: https://github.com/settings/tokens" -ForegroundColor White
    Write-Host "  2. Generate new token (classic)" -ForegroundColor White
    Write-Host "  3. Select 'repo' scope" -ForegroundColor White
    Write-Host "  4. Use token as password when prompted" -ForegroundColor White
    Write-Host ""
    Write-Host "Or configure SSH:" -ForegroundColor Cyan
    Write-Host "  https://docs.github.com/en/authentication/connecting-to-github-with-ssh" -ForegroundColor White
    Write-Host ""
    Write-Host "After authentication, run:" -ForegroundColor Yellow
    Write-Host "  git push -u origin main" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "✅ GitHub repository setup complete!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Repository URL: $repoUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "🚀 Ready to deploy to AWS App Runner!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run the deployment script:" -ForegroundColor Yellow
Write-Host "  .\deploy-apprunner.ps1 -GitHubRepoUrl '$repoUrl'" -ForegroundColor White
Write-Host ""
