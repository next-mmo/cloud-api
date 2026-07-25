param([Parameter(Mandatory=$true)][string]$File)
$ErrorActionPreference = "Stop"
foreach ($name in @("SALAD_API_KEY", "SALAD_ORGANIZATION", "SALAD_PROJECT")) {
  if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) { throw "Set $name" }
}
if (-not (Test-Path $File)) { throw "File not found: $File" }
$headers = @{ "Salad-Api-Key" = $env:SALAD_API_KEY; "Content-Type" = "application/json"; Accept = "application/json" }
$uri = "https://api.salad.com/api/public/organizations/$($env:SALAD_ORGANIZATION)/projects/$($env:SALAD_PROJECT)/containers"
Invoke-RestMethod -Method Post -Headers $headers -Uri $uri -Body (Get-Content $File -Raw) | ConvertTo-Json -Depth 20
