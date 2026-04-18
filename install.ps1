# Run Setup Script for Item Data Agent
# This script will check prerequisites and set up the environment

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Item Data Agent - Quick Setup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if UV is installed
Write-Host "Checking for UV package manager..." -ForegroundColor Yellow
$uvInstalled = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uvInstalled) {
    Write-Host "UV not found. Installing UV..." -ForegroundColor Yellow
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    Write-Host "✅ UV installed successfully" -ForegroundColor Green
} else {
    Write-Host "✅ UV is already installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
uv sync

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Running setup script..." -ForegroundColor Yellow
uv run python setup.py

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the server, run:" -ForegroundColor Yellow
Write-Host "  .\run.ps1" -ForegroundColor White
Write-Host ""
