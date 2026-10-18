param(
    [switch]$SkipPipelineDependencies
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root '.venv'
$python = Join-Path $venv 'Scripts/python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host 'Creating .venv with Python 3.12+...'
    & python -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        throw 'Python 3.12+ is required and must be available as "python".'
    }
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }

& $python -m pip install -r (Join-Path $root 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Report Agent dependency installation failed.' }

if (-not $SkipPipelineDependencies) {
    & $python -m pip install -r (Join-Path $root 'requirements-pipeline.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Pipeline dependency installation failed.' }
}

Write-Host "Environment ready: $venv"
