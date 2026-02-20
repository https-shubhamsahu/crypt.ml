$ErrorActionPreference = "SilentlyContinue"

function Get-ListenerInfo {
    param([int]$Port)

    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen | Select-Object -First 1
    if (-not $conn) {
        return [pscustomobject]@{
            Port = $Port
            Listening = $false
            ProcessId = $null
            CommandLine = $null
        }
    }

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"

    return [pscustomobject]@{
        Port = $Port
        Listening = $true
        ProcessId = $conn.OwningProcess
        CommandLine = $proc.CommandLine
    }
}

$apiInfo = Get-ListenerInfo -Port 8000
$uiInfo = Get-ListenerInfo -Port 8501

Write-Output "=== AEGIS-AML Service Status ==="
Write-Output ""

Write-Output "API (127.0.0.1:8000)"
Write-Output ("- Listening: {0}" -f $apiInfo.Listening)
if ($apiInfo.Listening) {
    Write-Output ("- PID: {0}" -f $apiInfo.ProcessId)
    Write-Output ("- Command: {0}" -f $apiInfo.CommandLine)
}

Write-Output ""
Write-Output "Dashboard (localhost:8501)"
Write-Output ("- Listening: {0}" -f $uiInfo.Listening)
if ($uiInfo.Listening) {
    Write-Output ("- PID: {0}" -f $uiInfo.ProcessId)
    Write-Output ("- Command: {0}" -f $uiInfo.CommandLine)
}

Write-Output ""
Write-Output "API Health Check"
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -Method GET -TimeoutSec 5
    Write-Output ("- Reachable: True")
    Write-Output ("- Response: {0}" -f ($health | ConvertTo-Json -Compress))
} catch {
    Write-Output "- Reachable: False"
    Write-Output ("- Error: {0}" -f $_.Exception.Message)
}

Write-Output ""
Write-Output "Dashboard URL: http://localhost:8501"
