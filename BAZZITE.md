# Bazzite Installation, Running, and Autostart

This guide is specifically for
[Bazzite](https://docs.bazzite.gg/), including desktop and HTPC/gaming-mode
installations.

PC Display Control runs directly on the Bazzite host because it needs access to
USB `hidraw` and Linux `hwmon`. It does not require Display Driver,
LibreHardwareMonitor, HWiNFO, or another sensor application.

The Linux kernel provides the sensor data:

- Ryzen temperature: `k10temp`
- Radeon temperature, utilization, power, clock, and fan: `amdgpu`
- CPU and memory utilization: `psutil`

> [!IMPORTANT]
> Bazzite is an immutable Fedora Atomic system. This guide does not use
> `rpm-ostree install` or modify the immutable system image. It follows
> Bazzite's recommendation to use Homebrew for command-line tools.

## 1. Switch to Desktop Mode

On a Bazzite HTPC or handheld installation, switch to Desktop Mode before
starting. Open a terminal such as Konsole.

## 2. Install `uv` with Homebrew

Homebrew is included with standard Bazzite installations. Install `uv`, which
will create and manage an isolated Python environment:

```bash
brew install uv
```

Confirm it works:

```bash
uv --version
```

If `brew` is not available, open Bazzite Portal and enable the Homebrew/Bold
Brew tooling first. See the official
[Bazzite Homebrew documentation](https://docs.bazzite.gg/Installing_and_Managing_Software/Homebrew/).

## 3. Clone PC Display Control

Git is normally available on Bazzite. Clone the repository into your home
directory:

```bash
cd "$HOME"
git clone https://github.com/georgiPavlov/pc-display-control.git
cd pc-display-control
```

If the repository is already present, update it instead:

```bash
cd "$HOME/pc-display-control"
git pull --ff-only
```

## 4. Create the Python environment

Create a local virtual environment and install the project requirements:

```bash
cd "$HOME/pc-display-control"
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

The Windows-only `pythonnet` dependency is automatically skipped on Bazzite.

## 5. Install the USB HID permission rule

The Bazzite system image is immutable, but `/etc` is writable and is the
correct location for a local udev rule.

```bash
cd "$HOME/pc-display-control"
sudo install -m 0644 99-pc-display-control.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and reconnect the display after installing the rule.

Verify that the display is visible:

```bash
lsusb -d 5131:2007
./.venv/bin/python pc_display_control.py --list
```

## 6. Verify Ryzen and Radeon sensors

Show the available `hwmon` drivers:

```bash
grep . /sys/class/hwmon/hwmon*/name
```

For an AMD Ryzen CPU and Radeon GPU, the results should normally include:

```text
k10temp
amdgpu
```

Print a live snapshot without opening the HID display:

```bash
cd "$HOME/pc-display-control"
./.venv/bin/python pc_display_control.py --show-sensors
```

Expected fields include `temp`, `gpu`, `cpu_util`, `gpu_util`, `gpu_power`, and
`memory_util`.

## 7. Test the display manually

Start continuous updates:

```bash
cd "$HOME/pc-display-control"
./.venv/bin/python pc_display_control.py --live
```

Confirm that the display updates, then press `Ctrl+C` before configuring the
background service. Only one controller instance should run at a time.

## 8. Configure Bazzite autostart

Create a systemd user service:

```bash
mkdir -p "$HOME/.config/systemd/user"
nano "$HOME/.config/systemd/user/pc-display-control.service"
```

Paste this configuration:

```ini
[Unit]
Description=PC Display Control for HID 5131:2007
After=graphical-session.target

[Service]
Type=simple
WorkingDirectory=%h/pc-display-control
ExecStart=%h/pc-display-control/.venv/bin/python %h/pc-display-control/pc_display_control.py --live
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

Save the file, reload the user service manager, and enable the service:

```bash
systemctl --user daemon-reload
systemctl --user enable --now pc-display-control.service
```

The controller will now start automatically with your Bazzite user session.
On Bazzite systems configured for automatic gaming-mode login, it starts as
part of that user session as well.

## 9. Start, stop, and inspect the service

Show status:

```bash
systemctl --user status pc-display-control.service
```

Start it:

```bash
systemctl --user start pc-display-control.service
```

Stop it while retaining autostart:

```bash
systemctl --user stop pc-display-control.service
```

Restart it:

```bash
systemctl --user restart pc-display-control.service
```

Disable autostart and stop it:

```bash
systemctl --user disable --now pc-display-control.service
```

Enable autostart and start it again:

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

## 10. Update PC Display Control

Stop the service, pull the latest code, synchronize the dependencies, and
restart:

```bash
systemctl --user stop pc-display-control.service
cd "$HOME/pc-display-control"
git pull --ff-only
uv pip install --python .venv/bin/python -r requirements.txt
systemctl --user start pc-display-control.service
```

Check the logs after updating:

```bash
journalctl --user -u pc-display-control.service -n 50
```

## 11. Remove autostart

Disable and remove the systemd user service:

```bash
systemctl --user disable --now pc-display-control.service
rm "$HOME/.config/systemd/user/pc-display-control.service"
systemctl --user daemon-reload
systemctl --user reset-failed
```

These commands remove only autostart. They do not delete the repository or
Python environment.

## 12. Complete removal

After removing autostart, remove the udev rule and project files if desired:

```bash
sudo rm /etc/udev/rules.d/99-pc-display-control.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
rm -rf "$HOME/pc-display-control"
```

The last command permanently deletes the local repository and its virtual
environment. Confirm the path before running it.

## Troubleshooting

### `brew` is not found

Use Bazzite Portal to enable Homebrew/Bold Brew, then open a new terminal. The
official Bazzite software guide recommends Homebrew for command-line tools:

- [Installing Software on Bazzite](https://docs.bazzite.gg/Installing_and_Managing_Software/software-intro/)
- [Bazzite Homebrew](https://docs.bazzite.gg/Installing_and_Managing_Software/Homebrew/)

### HID permission denied

Reinstall the udev rule and reconnect the display:

```bash
cd "$HOME/pc-display-control"
sudo install -m 0644 99-pc-display-control.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then check:

```bash
./.venv/bin/python pc_display_control.py --list
```

### CPU or GPU values are zero

Inspect the kernel drivers and sensor nodes:

```bash
lsmod | grep -E 'k10temp|amdgpu'
grep . /sys/class/hwmon/hwmon*/name
find /sys/class/hwmon -name 'temp*_input' -o -name 'gpu_busy_percent'
```

No external sensor application is necessary. If `k10temp` or `amdgpu` is
absent, investigate the kernel/driver state before changing the Python setup.

### Service keeps restarting

Ensure no manually started copy owns the HID interface:

```bash
pkill -f '[p]c_display_control.py --live'
systemctl --user restart pc-display-control.service
journalctl --user -u pc-display-control.service -n 50
```

### Bazzite update considerations

The repository, virtual environment, user service, and `/etc/udev/rules.d`
rule persist across normal Bazzite image updates. No package layering is used,
so the setup does not require rebuilding an `rpm-ostree` deployment.

