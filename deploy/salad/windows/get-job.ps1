param(
  [Parameter(Mandatory=$true)][string]$Queue,
  [Parameter(Mandatory=$true)][string]$JobId
)
$ErrorActionPreference = "Stop"
$headers = @{ "Salad-Api-Key" = $env:SALAD_API_KEY; Accept = "application/json" }
$uri = "https://api.salad.com/api/public/organizations/$($env:SALAD_ORGANIZATION)/projects/$($env:SALAD_PROJECT)/queues/$Queue/jobs/$JobId"
Invoke-RestMethod -Method Get -Headers $headers -Uri $uri | ConvertTo-Json -Depth 20
