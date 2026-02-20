$ErrorActionPreference = "Stop"

$port = 8000
$conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $conn) {
    throw "API is not listening on port $port. Start it first with ./scripts/start_all.ps1"
}

Write-Output "API detected on http://127.0.0.1:$port"
Write-Output "Starting public tunnel..."

if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
    Write-Output "Using cloudflared."
    Write-Output "Share the https://...trycloudflare.com URL shown below with your teammate."
    cloudflared tunnel --url "http://127.0.0.1:$port"
    exit $LASTEXITCODE
}

if (Get-Command ngrok -ErrorAction SilentlyContinue) {
    Write-Output "Using ngrok."
    Write-Output "Share the Forwarding https://...ngrok-free.app URL shown below with your teammate."
    ngrok http $port
    exit $LASTEXITCODE
}

throw "Neither cloudflared nor ngrok was found. Install one of them, then rerun ./scripts/share_backend.ps1"
