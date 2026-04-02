$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$backendPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"
$npmCmd = "C:\Program Files\nodejs\npm.cmd"
$runtimeDir = Join-Path $projectRoot "runtime"
$backendHealthUrl = "http://127.0.0.1:8000/api/health"
$dashboardUrl = "http://127.0.0.1:3000/dashboard"

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

function Test-PortListening {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    try {
        $listener = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
        return $null -ne $listener
    } catch {
        return $false
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$RetryCount = 60,
        [int]$DelaySeconds = 2
    )

    for ($index = 0; $index -lt $RetryCount; $index++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds $DelaySeconds
            continue
        }
        Start-Sleep -Seconds $DelaySeconds
    }

    return $false
}

if (-not (Test-Path $backendPython)) {
    throw "백엔드 가상환경 python.exe를 찾지 못했습니다: $backendPython"
}

if (-not (Test-Path $npmCmd)) {
    throw "npm.cmd를 찾지 못했습니다: $npmCmd"
}

if (-not (Test-PortListening -Port 8000)) {
    Start-Process `
        -FilePath $backendPython `
        -ArgumentList @("-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $backendDir `
        -WindowStyle Minimized `
        -RedirectStandardOutput (Join-Path $runtimeDir "launcher-backend.out.log") `
        -RedirectStandardError (Join-Path $runtimeDir "launcher-backend.err.log")
}

if (-not (Test-PortListening -Port 3000)) {
    Start-Process `
        -FilePath $npmCmd `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory $frontendDir `
        -WindowStyle Minimized `
        -RedirectStandardOutput (Join-Path $runtimeDir "launcher-frontend.out.log") `
        -RedirectStandardError (Join-Path $runtimeDir "launcher-frontend.err.log")
}

$backendReady = Wait-HttpReady -Url $backendHealthUrl -RetryCount 40 -DelaySeconds 2
$frontendReady = Wait-HttpReady -Url $dashboardUrl -RetryCount 60 -DelaySeconds 2

if (-not $backendReady) {
    Write-Warning "백엔드가 준비되지 않았습니다. 로그를 확인하세요: $(Join-Path $runtimeDir 'launcher-backend.err.log')"
}

if (-not $frontendReady) {
    Write-Warning "프론트엔드가 준비되지 않았습니다. 로그를 확인하세요: $(Join-Path $runtimeDir 'launcher-frontend.err.log')"
}

Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "start", "", $dashboardUrl) | Out-Null
