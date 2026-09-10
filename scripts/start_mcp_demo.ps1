param([string]$ContractPath = "contracts/boundary_list_0.2.json")

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$contract = Get-Content -LiteralPath $ContractPath -Encoding UTF8 -Raw | ConvertFrom-Json
$panelTool = $contract.tools | Where-Object { $_.name -eq 'create_panel' }
if ($contract.status -ne 'confirmed' -or $panelTool.inputSchema.properties.boundaries.type -ne 'array') {
    throw "The boundary-list demo requires a confirmed array contract. Use contracts/boundary_list_0.2.json."
}
$env:CAD_BACKEND = "mcp"
$env:MCP_CONTRACT_PATH = $ContractPath
$env:MCP_TIMEOUT_SECONDS = "10"

Write-Host "AI Ship CAD Copilot MCP demo is starting..."
Write-Host "Open: http://127.0.0.1:8000"
Write-Host "Backend: MCP Contract Mock (does not modify a real CAD project)"

conda run --no-capture-output -n ai_cad_agent python -X utf8 run_web.py
exit $LASTEXITCODE
