param (
    [ValidateSet("sync", "pull", "push")]
    [string]$Mode = "sync",
    [string]$CommitMessage = "Update",
    [string]$RemoteUrl = "git@github.com:JoecJia/lowcode_customer_service.git"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $ProjectRoot

git --version | Out-Null

if (-not (Test-Path ".git")) {
    git init | Out-Null
}

git branch -M main | Out-Null
$HasOrigin = $true
try { git remote get-url origin | Out-Null } catch { $HasOrigin = $false }

if ($HasOrigin) {
    git remote set-url origin $RemoteUrl | Out-Null
} else {
    git remote add origin $RemoteUrl | Out-Null
}

if ($Mode -eq "pull") {
    git pull --rebase --autostash origin main
    Write-Host ">>> Pull Complete!"
    exit 0
}

$Status = git status --porcelain
if ($Status) {
    git add -A
    git commit -m "$CommitMessage"
}

git pull --rebase origin main

if ($Mode -eq "push" -or $Mode -eq "sync") {
    git push origin main
    Write-Host ">>> Sync Complete!"
}
