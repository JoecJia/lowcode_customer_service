# Intelligent Customer Service - Quick Start

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Intelligent Customer Service Starting..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Start Backend
Write-Host ""
Write-Host "[1/2] Starting Backend (http://localhost:8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; python backend/main.py" -WindowStyle Minimized
Start-Sleep -Seconds 2
Write-Host "  Backend started" -ForegroundColor Green

# Start Frontend
Write-Host ""
Write-Host "[2/2] Starting Frontend (http://localhost:5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir\frontend'; npm run dev" -WindowStyle Minimized
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Customer Chat : http://localhost:5173/" -ForegroundColor White
Write-Host "  Admin Panel   : http://localhost:5173/admin" -ForegroundColor White
Write-Host "  Backend API   : http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "  Services are running in separate windows." -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

Read-Host "Press Enter to close this window"
