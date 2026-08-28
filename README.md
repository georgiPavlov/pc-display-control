# PC Display Control

A lightweight, cross-platform Python controller for the USB system-monitor
display exposed as HID device **VID `5131` / PID `2007`**. It sends live CPU,
GPU, memory, clock, power, and fan data without keeping the vendor Electron UI
open.

The packet layout is compatible with the 64-byte `Display Driver` report used
by this device. The program continuously updates the display every 200 ms by
default.

## Supported sensors

| Platform | CPU | GPU | Memory |
| --- | --- | --- | --- |
| Windows | `psutil` utilization plus Display Driver's bundled HWiNFO helper for Ryzen temperature, power, clock, and fans | Bundled HWiNFO helper for Radeon temperature, utilization, power, clock, and fans | `psutil` |
| Linux | `psutil` plus `k10temp` through `/sys/class/hwmon` | `amdgpu` through `/sys/class/hwmon` | `psutil` |

The automatic backends are designed for AMD Ryzen and AMD Radeon hardware. The
HID packet and manual-value mode do not depend on a particular CPU or GPU.

## Requirements

- Python 3.10 or newer
- A HID display with VID `5131` and PID `2007`
- Windows: the vendor **Display Driver** installation for live temperature and
  power sensors
- Linux: the `hidraw`, `k10temp`, and `amdgpu` kernel drivers

## Windows setup

Open PowerShell in this repository and install the dependencies:

```powershell
py -m pip install -r requirements.txt
```

For live Ryzen and Radeon temperatures, start PowerShell with **Run as
administrator**. The bundled sensor helper requests elevation so it can access
the hardware-monitoring driver.

```powershell
py .\pc_display_control.py --live
```

Approve the Windows UAC prompt if it appears. The program reads the helper's
shared-memory feed but sends HID packets itself, so the full Display Driver UI
does not need to remain open.

Expected terminal output resembles:

```text
CPU  51 C   6% | GPU  48 C   1% | RAM  44%
```

Only run one controller instance at a time. Stop it with `Ctrl+C`.

## Linux setup

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

## Troubleshooting

### Temperatures show `0` on Windows

Run PowerShell as administrator and approve UAC. Live temperature and power
values depend on this signed helper:

```text
C:\Program Files\Display Driver\resources\main\SDK\VC#\SystemInfos\vs2008\bin\x64\Release\SystemInfos.exe
```

If Display Driver previously crashed, it can leave a stale sensor file at
`%TEMP%\Display_Driver_Thermaltake.bin`. Close all controller and Display Driver
processes before removing that stale file and trying again.

### HID write fails on Windows

Close the Display Driver/Thermaltake UI and other copies of this controller.
Only one process should write to the display.

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
