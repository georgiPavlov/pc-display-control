#!/usr/bin/env bash

set -Eeuo pipefail

TASK_NAME="pc-display-control.service"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER="$SCRIPT_DIR/pc_display_control.py"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
UDEV_RULE="$SCRIPT_DIR/99-pc-display-control.rules"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/$TASK_NAME"
FORCE=0

if [[ "${1:-}" == "--force" ]]; then
    FORCE=1
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--force]" >&2
    exit 2
fi

log() {
    printf '\n==> %s\n' "$*"
}

fail() {
    printf '\nERROR: %s\n' "$*" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if [[ ! -r /etc/os-release ]]; then
    fail "Cannot read /etc/os-release."
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "bazzite" && "${VARIANT_ID:-}" != *"bazzite"* ]]; then
    if [[ $FORCE -ne 1 ]]; then
        fail "This installer is intended for Bazzite. Use --force to continue on another compatible system."
    fi
    echo "Warning: Bazzite was not detected; continuing because --force was supplied."
fi

[[ -f "$CONTROLLER" ]] || fail "Missing $CONTROLLER"
[[ -f "$REQUIREMENTS" ]] || fail "Missing $REQUIREMENTS"
[[ -f "$UDEV_RULE" ]] || fail "Missing $UDEV_RULE"
command_exists systemctl || fail "systemctl is required."
command_exists sudo || fail "sudo is required to install the udev rule."

log "Installing uv with Homebrew"
if ! command_exists brew; then
    fail "Homebrew is not available. Enable Homebrew/Bold Brew in Bazzite Portal, open a new terminal, and run this installer again."
fi

if ! command_exists uv; then
    brew install uv
fi
UV_BIN="$(command -v uv)"
echo "Using $UV_BIN"

log "Creating the Python environment"
if [[ ! -x "$PYTHON" ]]; then
    "$UV_BIN" venv "$VENV_DIR"
fi
"$UV_BIN" pip install --python "$PYTHON" -r "$REQUIREMENTS"

log "Installing HID permissions for VID 5131 / PID 2007"
sudo install -m 0644 "$UDEV_RULE" /etc/udev/rules.d/99-pc-display-control.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw

log "Checking AMD sensor drivers"
if [[ -d /sys/class/hwmon ]]; then
    HWMON_NAMES="$(grep -h . /sys/class/hwmon/hwmon*/name 2>/dev/null || true)"
    if grep -qx "k10temp" <<<"$HWMON_NAMES"; then
        echo "Found Ryzen k10temp sensors."
    else
        echo "Warning: k10temp was not found; CPU temperature may show 0."
    fi
    if grep -qx "amdgpu" <<<"$HWMON_NAMES"; then
        echo "Found Radeon amdgpu sensors."
    else
        echo "Warning: amdgpu was not found; GPU values may show 0."
    fi
fi

log "Installing the systemd user service"
mkdir -p "$SERVICE_DIR"
TEMP_SERVICE="$(mktemp)"
trap 'rm -f -- "$TEMP_SERVICE"' EXIT

printf '%s\n' \
    '[Unit]' \
    'Description=PC Display Control for HID 5131:2007' \
    '# Bazzite may start directly in Gamescope/Gaming Mode.' \
    '' \
    '[Service]' \
    'Type=simple' \
    "WorkingDirectory=$SCRIPT_DIR" \
    "ExecStart=\"$PYTHON\" \"$CONTROLLER\" --live --wait-for-device" \
    'Environment=PYTHONUNBUFFERED=1' \
    'Restart=always' \
    'RestartSec=3' \
    '' \
    '[Install]' \
    'WantedBy=default.target' >"$TEMP_SERVICE"

install -m 0644 "$TEMP_SERVICE" "$SERVICE_FILE"
systemctl --user daemon-reload
systemctl --user enable --now "$TASK_NAME"

log "Enabling user lingering for Gaming Mode"
sudo loginctl enable-linger "$USER"

log "Installation result"
sleep 2
if systemctl --user is-active --quiet "$TASK_NAME"; then
    echo "PC Display Control is installed, running, and enabled at login."
    systemctl --user --no-pager --full status "$TASK_NAME" || true
else
    echo "The service is installed and enabled but is not currently running." >&2
    echo "Reconnect the USB display, then run:" >&2
    echo "  systemctl --user restart $TASK_NAME" >&2
    echo "  journalctl --user -u $TASK_NAME -n 50" >&2
    exit 1
fi

cat <<'EOF'

Useful commands:
  systemctl --user status pc-display-control.service
  systemctl --user stop pc-display-control.service
  systemctl --user restart pc-display-control.service
  systemctl --user disable --now pc-display-control.service
  journalctl --user -u pc-display-control.service -f
EOF
