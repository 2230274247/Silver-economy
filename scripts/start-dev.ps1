param([ValidateSet('api', 'h5', 'worker')][string]$Target = 'h5')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($Target -in @('api', 'worker')) {
  $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/setup.ps1 first' }
  Push-Location -LiteralPath (Join-Path $projectRoot 'services\api')
  try {
    if ($Target -eq 'worker') {
      & $python -m app.notifications.worker
    } else {
      & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
    }
    if ($LASTEXITCODE -ne 0) { throw 'Backend process stopped with an error' }
  } finally { Pop-Location }
} else {
  Push-Location -LiteralPath (Join-Path $projectRoot 'apps\mobile')
  try {
    npm.cmd run dev:h5
    if ($LASTEXITCODE -ne 0) { throw 'H5 failed to start' }
  } finally { Pop-Location }
}
