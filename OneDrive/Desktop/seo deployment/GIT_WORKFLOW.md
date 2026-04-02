# Git Workflow for ai1stseo-backend

## Initial Setup (One-time)

```bash
# Clone the repo
git clone https://github.com/DeepthiSarayuGunda/ai1stseo-backend.git

# Navigate into it
cd ai1stseo-backend

# Set your identity (if not already set)
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

## Before Starting Any Work

Always pull the latest changes first:

```bash
git pull origin main
```

This ensures you have any updates from teammates before making changes.

## Making Changes

1. Pull latest: `git pull origin main`
2. Make your edits
3. Check what changed: `git status`
4. Stage changes: `git add .`
5. Commit with message: `git commit -m "Description of changes"`
6. Push to deploy: `git push origin main`

App Runner auto-deploys within 2-3 minutes after push.

## Quick Commands

| Action | Command |
|--------|---------|
| Pull latest | `git pull origin main` |
| See changes | `git status` |
| See diff | `git diff` |
| Stage all | `git add .` |
| Commit | `git commit -m "message"` |
| Push | `git push origin main` |
| Undo local changes | `git checkout -- filename` |
| View history | `git log --oneline -10` |

## If You Have Conflicts

```bash
# Pull will show conflict
git pull origin main

# Open conflicted files, look for:
# <<<<<<< HEAD
# your changes
# =======
# their changes
# >>>>>>> origin/main

# Edit to resolve, then:
git add .
git commit -m "Resolved merge conflict"
git push origin main
```

## Verify Deployment

After pushing, check the live site:
- API Health: https://sgnmqxb2sw.us-east-1.awsapprunner.com/api/health
- Full site: https://www.ai1stseo.com

Or check App Runner status:
```bash
aws apprunner list-operations --service-arn "arn:aws:apprunner:us-east-1:823766426087:service/ai1stseo-backend/96ecc3ff5e3943048f9772cbdbb1ca56" --query "OperationSummaryList[0]"
```

## Team Coordination

- Always pull before starting work
- Use descriptive commit messages
- Communicate in team chat before major changes
- Test locally if possible before pushing
