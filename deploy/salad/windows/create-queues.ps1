$ErrorActionPreference = "Stop"
foreach ($name in @("SALAD_API_KEY", "SALAD_ORGANIZATION", "SALAD_PROJECT")) {
  if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) { throw "Set $name" }
}
$headers = @{ "Salad-Api-Key" = $env:SALAD_API_KEY; "Content-Type" = "application/json" }
$base = "https://api.salad.com/api/public/organizations/$($env:SALAD_ORGANIZATION)/projects/$($env:SALAD_PROJECT)"
$queues = @(
  @{ name = $(if ($env:SALAD_VOX_QUEUE) { $env:SALAD_VOX_QUEUE } else { "voxcpm2-jobs" }); display_name = "VoxCPM2 Jobs" },
  @{ name = $(if ($env:SALAD_WAN_QUEUE) { $env:SALAD_WAN_QUEUE } else { "wangp-jobs" }); display_name = "WanGP Jobs" }
)
foreach ($q in $queues) {
  $body = @{ name = $q.name; display_name = $q.display_name; description = "Created by WanGP + VoxCPM2 starter" } | ConvertTo-Json
  try {
    Invoke-RestMethod -Method Post -Headers $headers -Uri "$base/queues" -Body $body | ConvertTo-Json -Depth 10
  } catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 400) { Write-Host "Queue may already exist: $($q.name)" } else { throw }
  }
}
