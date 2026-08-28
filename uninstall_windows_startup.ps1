[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskName = 'PC Display Control'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    $arguments = @(
        '-NoProfile'
        '-ExecutionPolicy', 'Bypass'
        '-File', ('"' + $PSCommandPath + '"')
    )
    Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs
    Write-Host 'Approve the UAC prompt to remove the startup task.'
    exit
}

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "$taskName is not installed."
    exit
}

Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "$taskName was stopped and removed."

