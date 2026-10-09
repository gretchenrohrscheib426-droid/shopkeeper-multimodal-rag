param([Parameter(Mandatory=$true)][string]$VmHost, [string]$SshUser = 'root')
$Repo = Split-Path $PSScriptRoot -Parent
$Remote = 'LC_ALL=C date -u; timedatectl status; systemctl is-active chronyd; chronyc tracking; chronyc sources -v; systemctl is-active ntpd; ntpq -pn'
Write-Host 'Read-only clock diagnosis. Enter SSH password locally; password is not logged.'
& ssh -o ConnectTimeout=10 ("{0}@{1}" -f $SshUser, $VmHost) $Remote | Tee-Object -FilePath (Join-Path $Repo 'artifacts\verification\baseline\vm-clock.txt')
Read-Host 'Press Enter to close'
