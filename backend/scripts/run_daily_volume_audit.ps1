$ErrorActionPreference = "Stop"

$repoRoot = "C:\Users\ishit\ads_library"
$backendDir = Join-Path $repoRoot "backend"
$pythonExe = "C:\Users\ishit\AppData\Local\Programs\Python\Python313\python.exe"

Set-Location $backendDir

$dateTag = Get-Date -Format "yyyyMMdd"
$reportPath = "exports/ads_volume_audit_daily_${dateTag}.json"

& $pythonExe -m scripts.audit_ads_volume_errors `
  --days 7 `
  --focus-keywords "GLP-1,ダイエット,脱毛,投資,美容,健康" `
  --execute-recovery `
  --recovery-limit 15 `
  --timeout-sec 90 `
  --json-report $reportPath
