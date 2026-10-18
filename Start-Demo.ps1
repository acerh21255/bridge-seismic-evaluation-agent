param([int]$Port = 8766, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$runtime = Join-Path $root '.venv/Scripts/python.exe'
$appId = 'bridge-report-agent'
if (-not (Test-Path -LiteralPath $runtime)) {
    Write-Host '首次启动：正在创建项目 Python 环境并安装依赖，请保持联网。'
    & python -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw '需要先安装 Python 3.12 及以上版本。' }
    & $runtime -m pip install -r (Join-Path $root 'requirements.lock.txt')
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请查看上方错误信息。' }
}
$address = "http://127.0.0.1:$Port"
Push-Location $root
try { $expectedRevision = (& $runtime -c "from bridge_report.server.app import SOURCE_REVISION; print(SOURCE_REVISION)") }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw '无法读取服务版本，请检查项目依赖。' }
$connected = $false
$other = $false
try {
    $response = Invoke-RestMethod "$address/api/config" -TimeoutSec 2
    $connected = ($response.app_id -eq $appId)
    $other = -not $connected
} catch {}
if ($other) { throw "端口 $Port 已被其他服务占用（可能是旧版演示服务）。请关闭后重试，或运行 .\Start-Demo.ps1 -Port 8770。" }
if ($connected -and $response.source_revision -ne $expectedRevision) {
    $activeRuns = @(Invoke-RestMethod "$address/api/runs" -TimeoutSec 5) | Where-Object { $_.status -in @('queued', 'running') }
    if ($activeRuns) { throw '检测到旧版服务仍有报告任务执行中。请等待完成后重新启动。' }
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
    $oldProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    $projectCommand = $oldProcess.CommandLine.StartsWith(('"' + $runtime + '" -m bridge_report.server.app'), [StringComparison]::OrdinalIgnoreCase)
    if (-not $projectCommand) {
        throw "检测到旧版服务，但无法确认属于本项目，请关闭占用 $Port 的服务后重试。"
    }
    Write-Host '检测到旧版后端，正在重启以加载最新母版、模型连接和案例接口。'
    Stop-Process -Id $oldProcess.ProcessId -ErrorAction Stop
    Wait-Process -Id $oldProcess.ProcessId -ErrorAction SilentlyContinue
    $connected = $false
}
if (-not $connected) {
    $logDir = Join-Path $root 'build/workbench'
    New-Item -ItemType Directory -Force $logDir | Out-Null
    $child = Start-Process -FilePath $runtime -ArgumentList @('-m', 'bridge_report.server.app', '--port', "$Port") -WorkingDirectory $root `
        -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'server.log') -RedirectStandardError (Join-Path $logDir 'server-error.log') -PassThru
    $child.Id | Set-Content (Join-Path $logDir 'server.pid')
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $response = Invoke-RestMethod "$address/api/config" -TimeoutSec 1; if ($response.app_id -eq $appId) { $connected = $true; break } } catch {}
        if ($child.HasExited) { break }
    }
}
if (-not $connected) { throw "服务未能启动。端口可能被占用，可运行 .\Start-Demo.ps1 -Port 8770；日志位于 build/workbench。" }
Write-Host "工程报告撰写 Agent 工作台已启动：$address"
Write-Host '默认使用离线脚本模型，无需 API key；运行记录与报告文件保存在 build/workbench。'
if (-not $NoBrowser) { Start-Process $address }
