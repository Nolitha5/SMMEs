$ErrorActionPreference = "Stop"
Write-Host "Customer Engagement Agent - local setup" -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20.19+ is required." }
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
