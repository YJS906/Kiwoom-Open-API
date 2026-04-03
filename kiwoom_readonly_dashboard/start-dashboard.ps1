$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$backendPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"
$npmCmd = "C:\Program Files\nodejs\npm.cmd"
$nextCmd = Join-Path $frontendDir "node_modules\\.bin\\next.cmd"
$runtimeDir = Join-Path $projectRoot "runtime"
$backendHealthUrl = "http://127.0.0.1:8000/api/health"
$dashboardUrl = "http://127.0.0.1:3000/dashboard"
$frontendBuildLog = Join-Path $runtimeDir "launcher-frontend-build.log"
$frontendBuildErrLog = Join-Path $runtimeDir "launcher-frontend-build.err.log"
$frontendOutLog = Join-Path $runtimeDir "launcher-frontend.out.log"
$frontendErrLog = Join-Path $runtimeDir "launcher-frontend.err.log"
$backendOutLog = Join-Path $runtimeDir "launcher-backend.out.log"
$backendErrLog = Join-Path $runtimeDir "launcher-backend.err.log"
$frontendNextDir = Join-Path $frontendDir ".next"

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

function Stop-AppProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$MatchPatterns
    )

    $processes = Get-CimInstance Win32_Process |
        Where-Object {
            $commandLine = $_.CommandLine
            if (-not $commandLine) {
                return $false
            }
            foreach ($pattern in $MatchPatterns) {
                if ($commandLine -like $pattern) {
                    return $true
                }
            }
            return $false
        }

    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        } catch {
            Write-Warning "Failed to stop process $($process.ProcessId): $($_.Exception.Message)"
        }
    }
}

function Stop-PortListeners {
    param(
        [Parameter(Mandatory = $true)]
        [int[]]$Ports
    )

    foreach ($port in $Ports) {
        $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($processId in $listeners) {
            try {
                Stop-Process -Id $processId -Force -ErrorAction Stop
            } catch {
                Write-Warning "Failed to stop process on port $port (PID $processId): $($_.Exception.Message)"
            }
        }
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
    throw "Backend virtualenv python.exe was not found: $backendPython"
}

if (-not (Test-Path $npmCmd)) {
    throw "npm.cmd was not found: $npmCmd"
}

if (-not (Test-Path $nextCmd)) {
    throw "next.cmd was not found: $nextCmd"
}

Stop-AppProcesses -MatchPatterns @(
    "*uvicorn app.main:create_app*--host 127.0.0.1 --port 8000*"
)
Stop-AppProcesses -MatchPatterns @(
    "*kiwoom_readonly_dashboard\\frontend*run dev*",
    "*kiwoom_readonly_dashboard\\frontend*next* dev*",
    "*kiwoom_readonly_dashboard\\frontend*next* start*",
    "*next\\dist\\server\\lib\\start-server.js*kiwoom_readonly_dashboard\\frontend*"
)
Stop-PortListeners -Ports @(3000, 8000)
Start-Sleep -Seconds 2

if (Test-Path -LiteralPath $frontendNextDir) {
    Remove-Item -LiteralPath $frontendNextDir -Recurse -Force
}

@(
    $frontendBuildLog,
    $frontendBuildErrLog,
    $frontendOutLog,
    $frontendErrLog,
    $backendOutLog,
    $backendErrLog
) | ForEach-Object {
    if (Test-Path -LiteralPath $_) {
        try {
            Remove-Item -LiteralPath $_ -Force -ErrorAction Stop
        } catch {
            Write-Warning "Failed to clear log file $_ : $($_.Exception.Message)"
        }
    }
}

$backendCommand = 'start "" /min cmd /c ""' +
    $backendPython +
    '" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 > "' +
    $backendOutLog +
    '" 2> "' +
    $backendErrLog +
    '"""'
Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", $backendCommand) -WorkingDirectory $backendDir

$buildResult = Start-Process `
    -FilePath $npmCmd `
    -ArgumentList @("run", "build") `
    -WorkingDirectory $frontendDir `
    -WindowStyle Minimized `
    -RedirectStandardOutput $frontendBuildLog `
    -RedirectStandardError $frontendBuildErrLog `
    -Wait `
    -PassThru

if ($buildResult.ExitCode -ne 0) {
    throw "Frontend build failed. Check logs: $frontendBuildLog / $frontendBuildErrLog"
}

Start-Process `
    -FilePath $nextCmd `
    -ArgumentList @("start", "-H", "127.0.0.1", "-p", "3000") `
    -WorkingDirectory $frontendDir `
    -WindowStyle Minimized `
    -RedirectStandardOutput $frontendOutLog `
    -RedirectStandardError $frontendErrLog

$backendReady = Wait-HttpReady -Url $backendHealthUrl -RetryCount 40 -DelaySeconds 2
$frontendReady = Wait-HttpReady -Url $dashboardUrl -RetryCount 60 -DelaySeconds 2

if (-not $backendReady) {
    throw "Backend did not become ready. Check log: $backendErrLog"
}

if (-not $frontendReady) {
    throw "Frontend did not become ready. Check logs: $frontendOutLog / $frontendErrLog"
}

Start-Process $dashboardUrl | Out-Null
