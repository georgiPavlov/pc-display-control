# PC Display Control

A lightweight, cross-platform Python controller for the USB system-monitor
display exposed as HID device **VID `5131` / PID `2007`**. It sends live CPU,
GPU, memory, clock, power, and fan data without keeping the vendor Electron UI
open.

The packet layout is compatible with the 64-byte `Display Driver` report used
by this device. The program continuously updates the display every 200 ms by
default.

## ❗ WINDOWS AUTOSTART & CONTROL ❗

> [!IMPORTANT]
> Open **PowerShell as Administrator** before running the task-control commands.
> The scheduled task is named **`PC Display Control`**.

### Install autostart

Starts the controller immediately and automatically at every Windows logon:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_startup.ps1
```

### Start now

```powershell
Start-ScheduledTask -TaskName "PC Display Control"
```

### Stop now

Stops the current background process but keeps autostart enabled:

```powershell
Stop-ScheduledTask -TaskName "PC Display Control"
```

### Disable autostart

```powershell
Stop-ScheduledTask -TaskName "PC Display Control"
Disable-ScheduledTask -TaskName "PC Display Control"
```

### Enable autostart again

```powershell
Enable-ScheduledTask -TaskName "PC Display Control"
Start-ScheduledTask -TaskName "PC Display Control"
```

### Remove autostart completely

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_windows_startup.ps1
```

> [!NOTE]
> Removing the task does not delete this repository or the controller. See
> [Manage the Windows startup task later](#manage-the-windows-startup-task-later)
> for status, restart, and troubleshooting commands.

## Supported sensors

| Platform | CPU | GPU | Memory |
| --- | --- | --- | --- |
| Windows | `psutil` utilization plus LibreHardwareMonitor for Ryzen temperature, power, clock, and fans | LibreHardwareMonitor for Radeon temperature, utilization, power, clock, and fans | `psutil` |
| Linux | `psutil` plus `k10temp` through `/sys/class/hwmon` | `amdgpu` through `/sys/class/hwmon` | `psutil` |

The automatic backends are designed for AMD Ryzen and AMD Radeon hardware. The
HID packet and manual-value mode do not depend on a particular CPU or GPU.

Windows sensor access uses the official
[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)
release under its MPL-2.0 license. The installer downloads it directly from the
project's GitHub release page; its binaries are not stored in this repository.

> [!TIP]
> After running `install_windows_startup.ps1`, the original Display Driver
> application can be uninstalled. PC Display Control no longer reads or launches
> any Display Driver files.

## Requirements

- Python 3.10 or newer
- A HID display with VID `5131` and PID `2007`
- Windows: administrator access during startup-task installation so the script
  can download and use LibreHardwareMonitor
- Linux: the `hidraw`, `k10temp`, and `amdgpu` kernel drivers

## Windows setup

Open PowerShell in this repository and install the dependencies:

```powershell
py -m pip install -r requirements.txt
```

For live Ryzen and Radeon temperatures, start PowerShell with **Run as
administrator**. LibreHardwareMonitor requires elevation to access low-level
hardware sensors.

```powershell
py .\pc_display_control.py --live
```

Approve the Windows UAC prompt if it appears. The Python process reads
LibreHardwareMonitor directly and sends HID packets itself. The original
Display Driver application is not required or used.

Expected terminal output resembles:

```text
CPU  51 C   6% | GPU  48 C   1% | RAM  44%
```

Only run one controller instance at a time. Stop it with `Ctrl+C`.

### Start automatically with Windows

The included installer downloads the official LibreHardwareMonitor release and
creates a hidden Task Scheduler task at user logon. It runs with highest
privileges so Ryzen and Radeon sensors work without a UAC prompt after every
sign-in.

Run this once from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_startup.ps1
```

Approve the UAC prompt. The installer starts the task immediately, and it will
start automatically at future logons. Check it with:

```powershell
Get-ScheduledTask -TaskName "PC Display Control"
```

To stop the background controller and remove autostart:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_windows_startup.ps1
```

### Manage the Windows startup task later

The scheduled task is named `PC Display Control`. Open PowerShell as
administrator before using these commands.

Show its current state and last result:

```powershell
Get-ScheduledTask -TaskName "PC Display Control"
Get-ScheduledTaskInfo -TaskName "PC Display Control"
```

Start it now:

```powershell
Start-ScheduledTask -TaskName "PC Display Control"
```

Stop the currently running controller, while keeping it enabled for the next
logon:

```powershell
Stop-ScheduledTask -TaskName "PC Display Control"
```

Restart it:

```powershell
Stop-ScheduledTask -TaskName "PC Display Control"
Start-ScheduledTask -TaskName "PC Display Control"
```

Disable automatic execution without deleting the task:

```powershell
Stop-ScheduledTask -TaskName "PC Display Control"
Disable-ScheduledTask -TaskName "PC Display Control"
```

Enable automatic execution again and start it immediately:

```powershell
Enable-ScheduledTask -TaskName "PC Display Control"
Start-ScheduledTask -TaskName "PC Display Control"
```

Remove the task permanently using the included script:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_windows_startup.ps1
```

Stopping or disabling the task does not delete the controller or its settings.
The uninstall script removes only the Task Scheduler entry; the repository
files remain in place.

## Linux setup

> [!IMPORTANT]
> See **[LINUX.md](LINUX.md)** for the complete Linux-only installation,
> native AMD sensor setup, systemd autostart, service-control commands, logs,
> and removal instructions.

> [!TIP]
> Bazzite users should follow the dedicated **[BAZZITE.md](BAZZITE.md)** guide.
> It avoids `rpm-ostree` package layering and uses Homebrew `uv`, a host udev
> rule, and a systemd user service.

Install Python, pip, and the HID runtime package using your distribution's
package manager.

### Debian / Ubuntu

```bash
sudo apt install python3 python3-pip libhidapi-hidraw0
python3 -m pip install --user -r requirements.txt
```

### Fedora

```bash
sudo dnf install python3-pip hidapi
python3 -m pip install --user -r requirements.txt
```

### Arch Linux

```bash
sudo pacman -S python-pip hidapi
python3 -m pip install --user -r requirements.txt
```

Install the included udev rule so a regular desktop user can open the display:

```bash
sudo install -m 0644 99-pc-display-control.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and reconnect the display after installing the rule, then run:

```bash
python3 pc_display_control.py --live
```

Linux live mode reads Ryzen `Tctl`/`Tdie` from `k10temp` and Radeon temperature,
load, power, clock, and fan values from `amdgpu` under `/sys/class/hwmon`.

## Usage

List matching HID interfaces:

```bash
python pc_display_control.py --list
```

Run continuously with live sensors:

```bash
python pc_display_control.py --live
```

Change the interval to one second:

```bash
python pc_display_control.py --live --interval 1
```

Run for 30 seconds:

```bash
python pc_display_control.py --live --duration 30
```

Send one fixed report:

```bash
python pc_display_control.py --temp 65 --cpu-util 40 --gpu 55 --gpu-util 70 --once
```

Override one live value while fetching everything else automatically:

```bash
python pc_display_control.py --live --temp 65
```

Preview a packet without opening the device:

```bash
python pc_display_control.py --temp 65 --gpu 55 --dry-run
```

Run `python pc_display_control.py --help` for every option.

Print one sensor snapshot without opening the HID display:

```powershell
py .\pc_display_control.py --show-sensors
```

## Troubleshooting

### Temperatures show `0` on Windows

Re-run `install_windows_startup.ps1` and approve UAC. The installer downloads
the official LibreHardwareMonitor release to:

```text
%LOCALAPPDATA%\PCDisplayControl\LibreHardwareMonitor
```

The task must run with highest privileges for Ryzen temperature and power
sensors. Check that `pythonnet` is installed with `py -m pip show pythonnet`.

### HID write fails on Windows

Close other display-control programs and other copies of this controller. Only
one process should write to the display.

### Permission denied on Linux

Install the included udev rule, reload it, and reconnect the USB device. Check
detection with:

```bash
lsusb -d 5131:2007
python3 pc_display_control.py --list
```

### Linux temperatures show `0`

Confirm the AMD sensor drivers are visible:

```bash
grep . /sys/class/hwmon/hwmon*/name
find /sys/class/hwmon -name 'temp*_input' -o -name 'gpu_busy_percent'
```

The names should normally include `k10temp` and `amdgpu`.

## Protocol note

PID `2007` uses a report beginning with `01 00 01 02`. The different
`00 87 65 01 01` checksum report found in some Display Driver builds belongs to
other variants (notably PID `200F`) and is intentionally not used here.

## License

[MIT](LICENSE)
