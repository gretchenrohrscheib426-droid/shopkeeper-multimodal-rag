param([Parameter(Mandatory=$true)][string]$VmHost, [string]$SshUser = 'root')
$ErrorActionPreference = 'Stop'
$Repo = Split-Path $PSScriptRoot -Parent
$Log = Join-Path $Repo 'artifacts\verification\baseline\vm-readonly.txt'
$Remote = 'date -u; uname -sr; docker version --format ''{{.Server.Version}}''; docker compose -f /root/docker-compose.yml config --services; docker ps -a --format ''{{json .}}''; docker inspect --format ''{{.Name}} {{json .Mounts}} {{json .NetworkSettings.Ports}} {{json .State.Health}}'' $(docker compose -f /root/docker-compose.yml ps -q)'
Write-Host 'Shopkeeper read-only VM audit. Enter SSH password in this window. Password is not logged.'
& ssh -o ConnectTimeout=10 ("{0}@{1}" -f $SshUser, $VmHost) $Remote | Tee-Object -FilePath $Log
Write-Host "Audit exit code: $LASTEXITCODE. You can close this window."
Read-Host 'Press Enter to close'
