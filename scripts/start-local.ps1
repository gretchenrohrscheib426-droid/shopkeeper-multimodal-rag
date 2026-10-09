$ErrorActionPreference = 'Stop'
$repoDirectory = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $repoDirectory '.venv_app\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Audited application Python not found. Follow docs/GETTING_STARTED_WINDOWS.md first.' }
$env:SHOPKEEPER_ENV_FILE = Join-Path $repoDirectory '.env.local'
$env:PYTHONUTF8 = '1'
$logDirectory = Join-Path $repoDirectory 'data'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$serverRecord = Join-Path $logDirectory 'server.json'
if (Test-Path -LiteralPath $serverRecord) {
    $record = Get-Content -LiteralPath $serverRecord -Raw | ConvertFrom-Json
    $existing = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$record.pid)
    if ($existing -and $existing.CommandLine -like '*scripts/serve.py*') {
        Write-Host ('Project server is already running; PID: ' + $record.pid)
        exit 0
    }
}
$occupied = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($occupied) { throw 'Port 8000 is occupied. Inspect its owner before starting; no process was stopped.' }
$serverProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $repoDirectory -WindowStyle Hidden -ArgumentList @('scripts/serve.py') -RedirectStandardOutput (Join-Path $logDirectory 'app.stdout.log') -RedirectStandardError (Join-Path $logDirectory 'app.stderr.log') -PassThru
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $live = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/live' -TimeoutSec 2
        if ($live.status -eq 'alive') { break }
    } catch { if ($serverProcess.HasExited) { throw 'Server exited. Inspect data/app.stderr.log.' } }
}
if (-not $live -or $live.status -ne 'alive') { throw 'Server liveness did not become ready. Inspect data/app.stderr.log.' }
Write-Host ('Local server is alive; launcher PID: ' + $serverProcess.Id)
Write-Host 'Open http://127.0.0.1:8000/front/chat.html . Model credentials never go in the browser.'
