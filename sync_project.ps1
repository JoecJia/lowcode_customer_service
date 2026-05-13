# 极简同步脚本 (Simplified Sync Script)
param (
    [string]$CommitMessage = "Update"
)

Write-Host ">>> Checking Git status..."

# 1. Initialize if .git folder doesn't exist
if (-not (Test-Path ".git")) {
    Write-Host "Initializing local repository..."
    git init
}

# 2. Try to add remote (ignore error if already exists)
Write-Host "Confirming remote repository..."
git remote add origin https://github.com/JoecJia/lowcode_customer_service.git 2>$null

# 3. Pull remote updates
Write-Host "Syncing remote documents..."
git pull origin main --rebase

# 4. Commit local changes
Write-Host "Saving local changes..."
git add .
git commit -m "$CommitMessage"

# 5. Push to GitHub
Write-Host "Uploading to GitHub..."
git branch -M main
git push -u origin main

Write-Host ">>> Sync Complete!"
