$ErrorActionPreference = "SilentlyContinue"

$targets = @(
    "uvicorn app.main:app",
    "streamlit run app/ui/hackathon_dashboard.py"
)

$procs = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "python" -and
        ($targets | ForEach-Object { $_ }) -and
        ($_.CommandLine -match "uvicorn app\.main:app" -or $_.CommandLine -match "streamlit run app/ui/hackathon_dashboard\.py")
    }

if (-not $procs) {
    Write-Output "No matching API/dashboard python processes found."
} else {
    foreach ($proc in $procs) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Output "Stopped PID $($proc.ProcessId)"
    }
}

Start-Sleep -Milliseconds 500

$ports = 8000, 8501
foreach ($port in $ports) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    Write-Output ("PORT {0}: {1}" -f $port, $(if ($busy) {"BUSY"} else {"FREE"}))
}
