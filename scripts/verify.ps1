param(
    [switch]$Install
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv/Scripts/python.exe'

if ($Install -or -not (Test-Path -LiteralPath $python)) {
    & (Join-Path $PSScriptRoot 'setup.ps1')
}

Push-Location $root
try {
    Write-Host '[1/5] Compile Python sources'
    & $python -m compileall -q bridge_report tests tools skills\bridge-drawing-recognition\scripts skills\bridge-seismic-pipeline\scripts
    if ($LASTEXITCODE -ne 0) { throw 'Python compilation failed.' }

    Write-Host '[2/5] Run Report Agent unit tests'
    & $python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }

    Write-Host '[3/5] Check drawing-recognition runtime'
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = Join-Path $root 'skills/bridge-drawing-recognition/scripts'
    try {
        & $python -m bridge_drawing_agent.cli doctor
        if ($LASTEXITCODE -ne 0) { throw 'Drawing-recognition doctor failed.' }
    }
    finally {
        $env:PYTHONPATH = $oldPythonPath
    }

    Write-Host '[4/5] Run Subagent 3 dry-run smoke test'
    $pipelineOut = Join-Path $root 'build/verification/pipeline'
    if (Test-Path -LiteralPath $pipelineOut) {
        $resolvedRoot = [IO.Path]::GetFullPath($root).TrimEnd('\', '/')
        $resolvedOut = [IO.Path]::GetFullPath($pipelineOut)
        if (-not $resolvedOut.StartsWith(
            $resolvedRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing to remove output outside the repository: $resolvedOut"
        }
        Remove-Item -LiteralPath $resolvedOut -Recurse -Force
    }
    & $python 'skills/bridge-seismic-pipeline/scripts/run_pipeline.py' `
        'skills/bridge-seismic-pipeline/scripts/bridge_modeler' `
        --outdir $pipelineOut --select 'K44+430'
    if ($LASTEXITCODE -ne 0) { throw 'Pipeline dry-run failed.' }
    if (-not (Test-Path -LiteralPath (Join-Path $pipelineOut 'batch_summary.md'))) {
        throw 'Pipeline dry-run did not produce batch_summary.md.'
    }

    Write-Host '[5/5] Verify repository hygiene'
    if (Test-Path -LiteralPath (Join-Path $root '.git')) {
        $tracked = @(& git -C $root ls-files)
        $polluted = $tracked | Where-Object {
            $_ -match '(^|/)(\.venv|build|__pycache__|测试资料)(/|$)'
        }
        if ($polluted) {
            throw "Generated or private paths are tracked: $($polluted -join ', ')"
        }
    }

    Write-Host 'Verification passed.'
}
finally {
    Pop-Location
}
