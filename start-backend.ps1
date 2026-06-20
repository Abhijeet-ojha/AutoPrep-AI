# AutoPrep AI - Backend Startup Script
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  AutoPrep AI - Phase 2 Backend" -ForegroundColor Cyan
Write-Host "  Version: 2.0.0" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to API directory
Set-Location apps\api

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[1/4] Virtual environment found" -ForegroundColor Green
}

# Activate virtual environment and install dependencies
Write-Host "[2/4] Installing dependencies (this may take a few minutes)..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "✗ Dependency installation failed" -ForegroundColor Red
    exit 1
}

# Create storage directory
Write-Host "[3/4] Setting up storage..." -ForegroundColor Yellow
if (-not (Test-Path "..\..\storage")) {
    mkdir "..\..\storage" | Out-Null
}
Write-Host "✓ Storage directory ready" -ForegroundColor Green

# Start the server
Write-Host "[4/4] Starting FastAPI server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Server starting on:" -ForegroundColor Cyan
Write-Host "  http://localhost:8000" -ForegroundColor Green
Write-Host ""
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Health: http://localhost:8000/health" -ForegroundColor Green
Write-Host "  Metrics: http://localhost:8000/metrics" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
