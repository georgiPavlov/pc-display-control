"""Cross-platform live system monitor for VID 5131 / PID 2007 displays.

This controller targets VID 5131 / PID 2007 and implements its 64-byte
Display Driver-compatible HID report.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import sys
import time

import hid


VID = 0x5131
PID = 0x2007
REPORT_LENGTH = 64


def read_number(path: Path, scale: float = 1.0) -> float | None:
    try:
        return float(path.read_text(encoding="ascii").strip()) / scale
    except (OSError, ValueError):
        return None


class LiveSensors:
    """Cross-platform AMD sensor reader."""

    def __init__(self) -> None:
        try:
            import psutil
        except ImportError as error:
            raise RuntimeError("Live mode needs psutil: py -m pip install psutil") from error
        self.psutil = psutil
        self.windows = platform.system() == "Windows"
        self.lhm_computer = self._open_lhm() if self.windows else None
        self.last_hardware_read = 0.0
        self.windows_values: dict[str, float | None] = {}

    @staticmethod
    def _open_lhm():
        folder = Path(os.environ.get("LOCALAPPDATA", "")) / "PCDisplayControl" / "LibreHardwareMonitor"
        assembly = folder / "LibreHardwareMonitorLib.dll"
        if not assembly.is_file():
            raise RuntimeError(
                "LibreHardwareMonitor is not installed. Run install_windows_startup.ps1 first."
            )
        try:
            sys.path.insert(0, str(folder))
            previous_directory = Path.cwd()
            os.chdir(folder)
            try:
                import clr
                clr.AddReference(str(assembly))
                from LibreHardwareMonitor.Hardware import Computer

                computer = Computer()
                computer.IsCpuEnabled = True
                computer.IsGpuEnabled = True
                computer.IsMotherboardEnabled = True
                computer.Open()
            finally:
                os.chdir(previous_directory)
            time.sleep(1.0)
            return computer
        except Exception as error:
            raise RuntimeError(
                "Could not initialize LibreHardwareMonitor. Run Windows setup as administrator: "
                f"{error}"
            ) from error

    def _lhm_sensors(self) -> list[tuple[str, str, str, float]]:
        sensors: list[tuple[str, str, str, float]] = []

        def visit(hardware, group: str) -> None:
            hardware.Update()
            for sensor in hardware.Sensors:
                if sensor.Value is not None:
                    sensors.append((group, str(sensor.Name), str(sensor.SensorType), float(sensor.Value)))
            for child in hardware.SubHardware:
                visit(child, group)

        for hardware in self.lhm_computer.Hardware:
            hardware_type = str(hardware.HardwareType).lower()
            if "cpu" in hardware_type:
                group = "cpu"
            elif "gpu" in hardware_type:
                group = "gpu"
            else:
                group = "board"
            visit(hardware, group)
        return sensors

    @staticmethod
    def _lhm_value(
        sensors: list[tuple[str, str, str, float]],
        group: str,
        sensor_type: str,
        preferred: tuple[str, ...],
    ) -> float | None:
        matching = [item for item in sensors if item[0] == group and item[2].lower() == sensor_type.lower()]
        for needle in preferred:
            for _, name, _, value in matching:
                if needle.lower() in name.lower():
                    return value
        return matching[0][3] if matching else None

    @staticmethod
    def _hwmon_devices() -> list[tuple[str, Path]]:
        devices = []
        for folder in Path("/sys/class/hwmon").glob("hwmon*"):
            try:
                devices.append(((folder / "name").read_text().strip().lower(), folder))
            except OSError:
                pass
        return devices

    @staticmethod
    def _labelled_value(folder: Path, prefix: str, labels: tuple[str, ...], scale: float) -> float | None:
        for input_path in folder.glob(f"{prefix}*_input"):
            label_path = input_path.with_name(input_path.name.replace("_input", "_label"))
            try:
                label = label_path.read_text().strip().lower()
            except OSError:
                label = ""
            if any(item in label for item in labels):
                value = read_number(input_path, scale)
                if value is not None:
                    return value
        inputs = list(folder.glob(f"{prefix}*_input"))
        return read_number(inputs[0], scale) if inputs else None

    def read(self) -> dict[str, int]:
        values: dict[str, float | None] = {
            "temp": None, "gpu": None, "cpu_util": self.psutil.cpu_percent(),
            "gpu_util": None, "cpu_power": None, "gpu_power": None,
            "cpu_clock": None, "gpu_clock": None, "gpu_fan": None, "fan": None,
            "memory_util": self.psutil.virtual_memory().percent,
        }
        cpu_freq = self.psutil.cpu_freq()
        if cpu_freq:
            values["cpu_clock"] = cpu_freq.current

        if self.windows:
            if time.monotonic() - self.last_hardware_read >= 1.0:
                sensors = self._lhm_sensors()
                self.windows_values = {
                    "temp": self._lhm_value(sensors, "cpu", "Temperature", ("tctl/tdie", "package", "core")),
                    "gpu": self._lhm_value(sensors, "gpu", "Temperature", ("gpu core", "gpu temperature", "hot spot")),
                    "gpu_util": self._lhm_value(sensors, "gpu", "Load", ("gpu core", "d3d 3d", "total")),
                    "cpu_power": self._lhm_value(sensors, "cpu", "Power", ("package", "cores")),
                    "gpu_power": self._lhm_value(sensors, "gpu", "Power", ("gpu package", "total")),
                    "gpu_clock": self._lhm_value(sensors, "gpu", "Clock", ("gpu core",)),
                    "gpu_fan": self._lhm_value(sensors, "gpu", "Fan", ("gpu fan",)),
                    "fan": self._lhm_value(sensors, "board", "Fan", ("system", "chassis", "cpu")),
                }
                self.last_hardware_read = time.monotonic()
            values.update(self.windows_values)
        else:
            for name, folder in self._hwmon_devices():
                if name == "k10temp":
                    values["temp"] = self._labelled_value(folder, "temp", ("tctl", "tdie"), 1000)
                elif name == "amdgpu":
                    values["gpu"] = self._labelled_value(folder, "temp", ("edge", "junction"), 1000)
                    values["gpu_util"] = read_number(folder / "device" / "gpu_busy_percent")
                    values["gpu_power"] = read_number(folder / "power1_average", 1_000_000)
                    values["gpu_clock"] = read_number(folder / "freq1_input", 1_000_000)
                    fan = read_number(folder / "fan1_input")
                    values["gpu_fan"] = fan

        # Missing sensors remain zero; values are bounded to the packet fields.
        return {key: max(0, min(9999 if "clock" in key or "fan" in key else 255, round(value or 0)))
                for key, value in values.items()}

    def close(self) -> None:
        if self.lhm_computer is not None:
            self.lhm_computer.Close()


def byte_value(value: int, name: str) -> int:
    if not 0 <= value <= 255:
        raise ValueError(f"{name} must be between 0 and 255")
    return value


def split_hundreds(value: int) -> tuple[int, int]:
    return value // 100, value % 100


def make_packet(args: argparse.Namespace) -> bytearray:
    packet = bytearray(REPORT_LENGTH)

    # Exact default header from the PID 2007 branch in device_hid.js.
    packet[0:4] = bytes((1, 0, 1, 2))
    packet[4] = byte_value(args.temp, "--temp")
    packet[5] = 0  # CPU temperature fractional hundredths
    packet[6] = 0  # 0 = Celsius, 1 = Fahrenheit
    packet[7] = byte_value(args.cpu_util, "--cpu-util")

    cpu_power_hi, cpu_power_lo = split_hundreds(args.cpu_power)
    packet[8] = byte_value(cpu_power_lo, "CPU power low byte")
    packet[9] = 0  # CPU power fractional hundredths

    cpu_clock_hi, cpu_clock_lo = split_hundreds(args.cpu_clock)
    packet[10] = byte_value(cpu_clock_hi, "CPU clock high part")
    packet[11] = byte_value(cpu_clock_lo, "CPU clock low part")

    packet[14] = byte_value(args.gpu, "--gpu")
    packet[15] = 0  # GPU temperature fractional hundredths
    packet[16] = 0  # 0 = Celsius, 1 = Fahrenheit
    packet[17] = byte_value(args.gpu_util, "--gpu-util")

    gpu_power_hi, gpu_power_lo = split_hundreds(args.gpu_power)
    packet[18] = byte_value(gpu_power_lo, "GPU power low byte")
    packet[19] = 0  # GPU power fractional hundredths

    gpu_clock_hi, gpu_clock_lo = split_hundreds(args.gpu_clock)
    packet[20] = byte_value(gpu_clock_hi, "GPU clock high part")
    packet[21] = byte_value(gpu_clock_lo, "GPU clock low part")

    gpu_fan_hi, gpu_fan_lo = split_hundreds(args.gpu_fan)
    packet[22] = byte_value(gpu_fan_hi, "GPU fan high part")
    packet[23] = byte_value(gpu_fan_lo, "GPU fan low part")

    fan_hi, fan_lo = split_hundreds(args.fan)
    packet[24] = byte_value(fan_hi, "fan high part")
    packet[25] = byte_value(fan_lo, "fan low part")

    now = datetime.now()
    packet[26] = now.year // 100
    packet[27] = now.year % 100
    packet[28] = now.month
    packet[29] = now.day
    packet[30] = now.hour
    packet[31] = now.minute
    packet[32] = now.second
    # JavaScript getDay(): Sunday=0 through Saturday=6.
    packet[33] = (now.weekday() + 1) % 7

    packet[34] = byte_value(args.memory_util, "--memory-util")
    packet[35] = byte_value(cpu_power_hi, "CPU power high part")
    packet[36] = byte_value(gpu_power_hi, "GPU power high part")
    packet[38] = 5  # DisplayDriver's default cycle interval
    return packet


def matching_devices() -> list[dict]:
    return hid.enumerate(VID, PID)


def describe_device(index: int, info: dict) -> str:
    return (
        f"[{index}] path={info['path']!r} "
        f"usage_page=0x{info.get('usage_page', 0):04X} "
        f"interface={info.get('interface_number', -1)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one DisplayDriver-compatible report to VID 5131 / PID 2007."
    )
    parser.add_argument("--live", action="store_true", help="fetch live Ryzen/Radeon sensor values")
    parser.add_argument(
        "--show-sensors", action="store_true",
        help="print one live sensor snapshot as JSON without opening the HID device",
    )
    parser.add_argument("--temp", type=int, help="CPU temperature override in Celsius")
    parser.add_argument("--gpu", type=int, help="GPU temperature override in Celsius")
    parser.add_argument("--cpu-util", type=int, help="CPU utilization override")
    parser.add_argument("--gpu-util", type=int, help="GPU utilization override")
    parser.add_argument("--cpu-power", type=int, help="CPU power override in watts")
    parser.add_argument("--gpu-power", type=int, help="GPU power override in watts")
    parser.add_argument("--cpu-clock", type=int, help="CPU clock override in MHz")
    parser.add_argument("--gpu-clock", type=int, help="GPU clock override in MHz")
    parser.add_argument("--gpu-fan", type=int, help="GPU fan speed override in RPM")
    parser.add_argument("--fan", type=int, help="System fan speed override in RPM")
    parser.add_argument("--memory-util", type=int, help="Memory utilization override")
    parser.add_argument("--device", type=int, default=0, help="Matching HID device index")
    parser.add_argument(
        "--interval", type=float, default=0.2,
        help="seconds between reports (default: 0.2, matching DisplayDriver)",
    )
    parser.add_argument(
        "--duration", type=float, default=0,
        help="seconds to run; 0 means until Ctrl+C (default: 0)",
    )
    parser.add_argument("--once", action="store_true", help="send one report and exit")
    parser.add_argument("--list", action="store_true", help="List matching HID interfaces and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print the packet without sending it")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.show_sensors:
        try:
            sensors = LiveSensors()
            print(json.dumps(sensors.read(), indent=2))
            sensors.close()
            return 0
        except RuntimeError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2

    devices = matching_devices()
    metric_names = (
        "temp", "gpu", "cpu_util", "gpu_util", "cpu_power", "gpu_power",
        "cpu_clock", "gpu_clock", "gpu_fan", "fan", "memory_util",
    )
    overrides = {name: getattr(args, name) for name in metric_names if getattr(args, name) is not None}
    for name in metric_names:
        if getattr(args, name) is None:
            setattr(args, name, 0)

    if args.list:
        if not devices:
            print("No VID 5131 / PID 2007 HID interfaces found")
            return 1
        for index, info in enumerate(devices):
            print(describe_device(index, info))
        return 0

    try:
        packet = make_packet(args)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(packet.hex(" "))
        return 0

    if not devices:
        print("Device VID 5131 / PID 2007 not found", file=sys.stderr)
        return 1
    if not 0 <= args.device < len(devices):
        print(f"Device index {args.device} does not exist; use --list", file=sys.stderr)
        return 2
    if args.interval <= 0 or args.duration < 0:
        print("--interval must be positive and --duration cannot be negative", file=sys.stderr)
        return 2

    sensors = None
    if args.live:
        try:
            sensors = LiveSensors()
        except RuntimeError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2

    device = hid.device()
    try:
        device.open_path(devices[args.device]["path"])
        started = time.monotonic()
        reports = 0
        last_status = 0.0
        while True:
            if sensors:
                live = sensors.read()
                for name in metric_names:
                    setattr(args, name, overrides.get(name, live[name]))
            packet = make_packet(args)
            written = device.write(packet)
            # On Windows, hidapi commonly returns 65 for this 64-byte report:
            # the count includes the report-ID byte/padded output report.
            if written < len(packet):
                print(f"Short HID write: {written} of at least {len(packet)} bytes", file=sys.stderr)
                return 1
            reports += 1
            if sensors and time.monotonic() - last_status >= 1:
                print(
                    f"CPU {args.temp:3d} C {args.cpu_util:3d}% | "
                    f"GPU {args.gpu:3d} C {args.gpu_util:3d}% | "
                    f"RAM {args.memory_util:3d}%",
                    end="\r", flush=True,
                )
                last_status = time.monotonic()
            if args.once or (args.duration and time.monotonic() - started >= args.duration):
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped")
        return 0
    except OSError as error:
        print(
            f"HID write failed: {error}. Close the Thermaltake/DisplayDriver app "
            "if it currently owns the interface.",
            file=sys.stderr,
        )
        return 1
    finally:
        device.close()
        if sensors:
            sensors.close()

    print(f"Sent {reports} report(s) to VID 5131 / PID 2007")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
