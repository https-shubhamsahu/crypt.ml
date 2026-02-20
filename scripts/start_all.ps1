$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv-1\Scripts\python.exe"
$altVenvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} elseif (Test-Path $altVenvPython) {
    $pythonExe = $altVenvPython
} else {
    throw "No virtual environment python found. Expected .venv-1 or .venv in repo root."
}

function Get-ListenerProcessId {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { return $conn.OwningProcess }
    return $null
}

function Start-ServiceIfNeeded {
    param(
        [string]$Name,
        [int]$Port,
        [string[]]$ProcessArgs
    )

    $existingPid = Get-ListenerProcessId -Port $Port
    if ($existingPid) {
        Write-Output "$Name already running on port $Port (PID: $existingPid)."
        return
    }

    $proc = Start-Process -FilePath $pythonExe -ArgumentList $ProcessArgs -WorkingDirectory $repoRoot -PassThru

    $startedPid = $null
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        $startedPid = Get-ListenerProcessId -Port $Port
        if ($startedPid) { break }
    }

    if ($startedPid) {
        Write-Output "$Name started on port $Port (PID: $startedPid)."
    } else {
        Write-Output "$Name failed to bind port $Port. Check logs/process output."
    }
}

Start-ServiceIfNeeded -Name "API" -Port 8000 -ProcessArgs @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")
Start-ServiceIfNeeded -Name "Dashboard" -Port 8501 -ProcessArgs @("-m", "streamlit", "run", "app/ui/hackathon_dashboard.py", "--server.port", "8501", "--server.headless", "true")

Write-Output "Done."
