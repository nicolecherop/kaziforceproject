param([switch]$SkipNlp)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.13 is required and was not found on PATH.'
}

if (-not (Test-Path -LiteralPath '.venv')) {
    python -m venv .venv
}

$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
& $python -m pip install --disable-pip-version-check -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    & $python scripts/prepare_env.py
    Write-Host 'Created .env with a random secret. Add your PostgreSQL DATABASE_URL, then run this script again.'
    exit 0
}

& $python manage.py check_database
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python manage.py migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipNlp) {
    & $python manage.py setup_nlp
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $python manage.py check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'KaziForce development environment is ready.'
