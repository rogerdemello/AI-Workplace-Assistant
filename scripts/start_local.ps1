param(
    [string]$BackendHost = "127.0.0.1",
    [int]$BackendPort = 8000,
    [string]$FrontendHost = "127.0.0.1",
    [int]$FrontendPort = 8080,
    [switch]$RunSmoke,
    [switch]$SkipFrontendInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $res = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 3
            if ($res.StatusCode -ge 200 -and $res.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 800
        }
    }
    return $false
}

$root = (Resolve-Path ".").Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendUrl = "http://$BackendHost`:$BackendPort"
$frontendUrl = "http://$FrontendHost`:$FrontendPort"

if (-not (Test-Path $backendDir)) { throw "Missing backend directory: $backendDir" }
if (-not (Test-Path $frontendDir)) { throw "Missing frontend directory: $frontendDir" }

Write-Step "Starting backend API server"
$backendArgs = "-NoExit", "-Command", "Set-Location '$backendDir'; uvicorn app.main:app --host $BackendHost --port $BackendPort"
$backendProc = Start-Process -FilePath "powershell" -ArgumentList $backendArgs -PassThru
Write-Host "Backend process started (PID: $($backendProc.Id))"

Write-Step "Starting frontend dev server"
if (-not $SkipFrontendInstall) {
    Push-Location $frontendDir
    try {
        npm install
    } finally {
        Pop-Location
    }
}
$frontendArgs = "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev -- --host $FrontendHost --port $FrontendPort"
$frontendProc = Start-Process -FilePath "powershell" -ArgumentList $frontendArgs -PassThru
Write-Host "Frontend process started (PID: $($frontendProc.Id))"

Write-Step "Waiting for backend readiness"
if (-not (Test-HttpReady -Url "$backendUrl/health" -TimeoutSeconds 90)) {
    Write-Warning "Backend health endpoint did not respond in time."
} else {
    Write-Host "Backend is ready at $backendUrl"
}

Write-Step "Waiting for frontend readiness"
if (-not (Test-HttpReady -Url $frontendUrl -TimeoutSeconds 90)) {
    Write-Warning "Frontend did not respond in time."
} else {
    Write-Host "Frontend is ready at $frontendUrl"
}

Write-Host ""
Write-Host "Local stack launched:" -ForegroundColor Green
Write-Host "- Backend:  $backendUrl"
Write-Host "- Frontend: $frontendUrl"
Write-Host "- Backend PID:  $($backendProc.Id)"
Write-Host "- Frontend PID: $($frontendProc.Id)"

if ($RunSmoke) {
    Write-Step "Running smoke release script"
    $smokeScript = Join-Path $root "scripts/smoke_release.ps1"
    if (-not (Test-Path $smokeScript)) {
        throw "Missing smoke script: $smokeScript"
    }
    & powershell -ExecutionPolicy Bypass -File $smokeScript -BackendBaseUrl $backendUrl -SkipBuild
}

Write-Host ""
Write-Host "Tip: close spawned PowerShell windows to stop servers." -ForegroundColor Yellow
