$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
  if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
  }
  & '.\.venv\Scripts\python.exe' -m pip install -r services/api/requirements.lock
  if ($LASTEXITCODE -ne 0) { throw 'Python dependency install failed' }
  Push-Location -LiteralPath 'apps\mobile'
  try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
  } finally { Pop-Location }
} finally { Pop-Location }
