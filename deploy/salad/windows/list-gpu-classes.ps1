$ErrorActionPreference = "Stop"
if (-not $env:SALAD_API_KEY) { throw "Set SALAD_API_KEY" }
if (-not $env:SALAD_ORGANIZATION) { throw "Set SALAD_ORGANIZATION" }
$headers = @{ "Salad-Api-Key" = $env:SALAD_API_KEY; Accept = "application/json" }
Invoke-RestMethod -Method Get -Headers $headers -Uri "https://api.salad.com/api/public/organizations/$($env:SALAD_ORGANIZATION)/gpu-classes" | ConvertTo-Json -Depth 10
