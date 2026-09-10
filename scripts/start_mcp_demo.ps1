$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$env:CAD_BACKEND = "mcp"
$env:MCP_CONTRACT_PATH = "contracts/FULL_contract_with_data.json"
$env:MCP_TIMEOUT_SECONDS = "10"

Write-Host "AI Ship CAD Copilot MCP demo is starting..."
Write-Host "Open: http://127.0.0.1:8000"
Write-Host "Backend: MCP Contract Mock (does not modify a real CAD project)"

conda run -n ai_cad_agent python run_web.py
