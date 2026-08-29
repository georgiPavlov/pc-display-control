# Linux Installation, Running, and Autostart

> [!TIP]
> Using Bazzite? Follow the dedicated **[BAZZITE.md](BAZZITE.md)** guide for its
> immutable Fedora Atomic base and Homebrew-based setup.

PC Display Control does **not** require LibreHardwareMonitor, Display Driver, or
another sensor application on Linux. It reads AMD sensors directly from the
Linux kernel:

- Ryzen temperature: `k10temp` through `/sys/class/hwmon`
- Radeon temperature, utilization, power, clock, and fan: `amdgpu` through
  `/sys/class/hwmon`
- CPU and memory utilization: `psutil`

## 1. Install system packages

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip libhidapi-hidraw0
```

### Fedora

```bash
sudo dnf install git python3 python3-pip hidapi
```

### Arch Linux

```bash
sudo pacman -S git python python-pip hidapi
```

## 2. Download and install

Clone the repository into your home directory:

```bash
cd "$HOME"
git clone https://github.com/georgiPavlov/pc-display-control.git
cd pc-display-control
```

Create an isolated Python environment and install the dependencies:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

## 3. Allow access to the HID display

Install the included udev rule:

```bash
sudo install -m 0644 99-pc-display-control.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and reconnect the USB display. Verify that it is visible:

```bash
lsusb -d 5131:2007
./.venv/bin/python pc_display_control.py --list
```

## 4. Check AMD sensors

Show the available hardware-monitor drivers:

```bash
grep . /sys/class/hwmon/hwmon*/name
```

An AMD Ryzen/Radeon system should normally include:

```text
k10temp
amdgpu
```

Print one sensor snapshot without opening the HID display:

```bash
./.venv/bin/python pc_display_control.py --show-sensors
```

## 5. Run manually

Start continuous live updates:

```bash
cd "$HOME/pc-display-control"
./.venv/bin/python pc_display_control.py --live
```

Use `--wait-for-device` for a background process that should survive a missing
or unplugged display and reconnect automatically:

```bash
./.venv/bin/python pc_display_control.py --live --wait-for-device
```

Stop the foreground process with `Ctrl+C`.

## 6. Configure automatic startup with systemd

Create the user-service directory and service file:

```bash
mkdir -p "$HOME/.config/systemd/user"
nano "$HOME/.config/systemd/user/pc-display-control.service"
```

Paste this service definition:

```ini
[Unit]
Description=PC Display Control for HID 5131:2007
# Do not depend on a desktop target; this also runs in Bazzite Gaming Mode.

[Service]
Type=simple
WorkingDirectory=%h/pc-display-control
ExecStart=%h/pc-display-control/.venv/bin/python %h/pc-display-control/pc_display_control.py --live --wait-for-device
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

Save the file, reload systemd, and enable the service:

```bash
systemctl --user daemon-reload
systemctl --user enable --now pc-display-control.service
```

On Bazzite, enable user lingering once so the service is available when the
system enters Gamescope/Gaming Mode directly:

```bash
sudo loginctl enable-linger "$USER"
```

The service will now start automatically when you sign in.

### Start at boot before signing in (optional)

Enable user lingering once:

```bash
sudo loginctl enable-linger "$USER"
```

This allows the user service to start during boot without waiting for an
interactive login.

## 7. Manage the Linux service

Show current status:

```bash
systemctl --user status pc-display-control.service
```

Start it:

```bash
systemctl --user start pc-display-control.service
```

Stop it while leaving autostart enabled:

```bash
systemctl --user stop pc-display-control.service
```

Restart it after changing the Python code:

```bash
systemctl --user restart pc-display-control.service
```

Disable autostart and stop it:

```bash
systemctl --user disable --now pc-display-control.service
```

Enable autostart again and start it immediately:

```bash
systemctl --user enable --now pc-display-control.service
```

Follow live logs:

```bash
journalctl --user -u pc-display-control.service -f
```

Show logs from the current boot:

```bash
journalctl --user -u pc-display-control.service -b
```

## 8. Remove Linux autostart

Disable and remove the service:

```bash
systemctl --user disable --now pc-display-control.service
rm "$HOME/.config/systemd/user/pc-display-control.service"
systemctl --user daemon-reload
systemctl --user reset-failed
```

Optionally disable lingering if it was enabled only for this controller:

```bash
sudo loginctl disable-linger "$USER"
```

These commands remove only autostart. They do not remove the repository.

## Troubleshooting

### Permission denied while opening HID

Reinstall the udev rule, reload it, and reconnect the display:

```bash
sudo install -m 0644 99-pc-display-control.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### CPU or GPU temperature is zero

Check the drivers and their sensor files:

```bash
grep . /sys/class/hwmon/hwmon*/name
find /sys/class/hwmon -name 'temp*_input' -o -name 'gpu_busy_percent'
```

Check that the modules are loaded:

```bash
lsmod | grep -E 'k10temp|amdgpu'
```

### Service repeatedly restarts

Stop manual copies of the controller so only the service owns the HID device:

```bash
pkill -f '[p]c_display_control.py --live'
systemctl --user restart pc-display-control.service
journalctl --user -u pc-display-control.service -n 50
```
