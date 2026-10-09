$ErrorActionPreference = 'Stop'
$repoDirectory = Split-Path $PSScriptRoot -Parent
$env:SHOPKEEPER_ENV_FILE = Join-Path $repoDirectory '.env.local'
Push-Location $repoDirectory
try {
    & (Join-Path $repoDirectory '.venv_app\Scripts\python.exe') -c "from pathlib import Path; from knowledge.core.paths import get_local_base_dir; Path(get_local_base_dir(),'server.stop').write_text('stop',encoding='utf-8')"
    Write-Host 'Graceful stop requested. Active work is allowed to finish within the server shutdown deadline.'
} finally { Pop-Location }
