param([Parameter(Mandatory=$true)][string]$VmHost, [string]$SshUser = 'root')
$Repo = Split-Path $PSScriptRoot -Parent
Write-Host 'This corrects the VM clock using its already configured, reachable chrony NTP source.'
Write-Host 'It does not change the timezone, NTP servers, firewall, containers or volumes.'
$Remote = 'chronyc tracking && chronyc sources -v && chronyc makestep && sleep 2 && LC_ALL=C date -u && chronyc tracking'
& ssh -o ConnectTimeout=10 ("{0}@{1}" -f $SshUser, $VmHost) $Remote | Tee-Object -FilePath (Join-Path $Repo 'artifacts\verification\baseline\vm-clock-sync.txt')
Read-Host 'Press Enter to close'
