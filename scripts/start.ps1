param(
  [string]$PythonVersion = "3.12",
  [int]$Port = 8000,
  [switch]$SkipSync,
  [switch]$SkipInfraCheck,
  [switch]$SkipMemorySchema,
  [switch]$NoReload
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $Name"
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
  Assert-Command "uv"

  if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
      Copy-Item ".env.example" ".env" -Force
      throw "Created .env from .env.example. Please edit MYSQL_DSN and REDIS_URL, then rerun scripts/start.ps1"
    }
    throw ".env not found, and .env.example is also missing."
  }

  if (-not $SkipSync) {
    Write-Step "Sync dependencies"
    & uv sync --python $PythonVersion
  } else {
    Write-Step "Skip dependency sync"
  }

  if (-not $SkipInfraCheck) {
    Write-Step "Check MySQL and Redis connectivity"
    $healthCheck = @'
import sys
from sqlalchemy import create_engine, text
import redis

sys.path.insert(0, "eleven-rag")
from core.config import settings

engine = create_engine(settings.mysql_dsn, pool_pre_ping=True)
with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
print("MySQL ok")

client = redis.Redis.from_url(settings.redis_url)
if not client.ping():
    raise RuntimeError("Redis ping failed")
print("Redis ok")
'@
    $healthCheck | & uv run --python $PythonVersion python -
  } else {
    Write-Step "Skip MySQL/Redis connectivity checks"
  }

  if (-not $SkipMemorySchema) {
    Write-Step "Apply memory schema migrations"
    & uv run --python $PythonVersion python scripts/manage_memory_schema.py --action apply
  } else {
    Write-Step "Skip memory schema migrations"
  }

  $uvicornArgs = @(
    "run", "--python", $PythonVersion,
    "uvicorn", "main:app",
    "--app-dir", "eleven-rag",
    "--port", "$Port"
  )
  if (-not $NoReload) {
    $uvicornArgs += "--reload"
  }
  Write-Step "Start Eleven-RAG API"
  Write-Host "Health: http://127.0.0.1:$Port/health"
  & uv @uvicornArgs
} finally {
  Pop-Location
}
