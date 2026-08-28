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
    Write-Host 'Approve the UAC prompt to install the startup task.'
    exit
}

$lhmVersion = 'v0.9.6'
$lhmRoot = Join-Path $env:LOCALAPPDATA 'PCDisplayControl\LibreHardwareMonitor'
$lhmMarker = Join-Path $lhmRoot '.pc-display-version'
$installedVersion = if (Test-Path -LiteralPath $lhmMarker) {
    (Get-Content -LiteralPath $lhmMarker -Raw).Trim()
} else {
    ''
}

if ($installedVersion -ne $lhmVersion) {
    $downloadUrl = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/$lhmVersion/LibreHardwareMonitor.zip"
    $archive = Join-Path $env:TEMP "LibreHardwareMonitor-$lhmVersion.zip"
    Write-Host "Downloading official LibreHardwareMonitor $lhmVersion..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archive
    if (Test-Path -LiteralPath $lhmRoot) {
        Remove-Item -LiteralPath $lhmRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $lhmRoot -Force | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $lhmRoot -Force
    Set-Content -LiteralPath $lhmMarker -Value $lhmVersion -Encoding ascii
    Get-ChildItem -LiteralPath $lhmRoot -File -Recurse | Unblock-File
    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
}

Write-Host 'Installing Python dependencies...'
& py -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    throw 'Python dependency installation failed.'
}

$python = (& py -c 'import sys; print(sys.executable)').Trim()
if (-not $python) {
    throw 'Python was not found through the py launcher.'
}

$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
$script = Join-Path $PSScriptRoot 'pc_display_control.py'
$userId = "$env:USERDOMAIN\$env:USERNAME"

if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "pythonw.exe was not found at $pythonw"
}
if (-not (Test-Path -LiteralPath $script)) {
    throw "Controller was not found at $script"
}

$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument ('"' + $script + '" --live') `
    -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $taskPrincipal `
    -Settings $settings `
    -Description 'Sends LibreHardwareMonitor Ryzen/Radeon data to HID display VID 5131 PID 2007.' `
    -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2
$task = Get-ScheduledTask -TaskName $taskName
Write-Host "$taskName installed and started. State: $($task.State)"
