"""Portable local-only telemetry. Values absent from sensors remain None."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import os
import platform
import shutil
import socket
import subprocess
import time
from typing import Any

import psutil


def gb(n: float) -> float:
    return round(n / (1024 ** 3), 2)


def mb(n: float) -> float:
    return round(n / (1024 ** 2), 2)


@dataclass
class Sample:
    timestamp: float
    cpu_percent: float
    cpu_freq_mhz: float | None
    cpu_temp_c: float | None
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    swap_percent: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_read_mb_s: float
    disk_write_mb_s: float
    gpu_name: str
    gpu_percent: float | None
    gpu_temp_c: float | None
    gpu_memory_used_mb: float | None
    gpu_memory_total_mb: float | None
    gpu_power_w: float | None
    net_sent_mb: float
    net_recv_mb: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SystemMonitor:
    def __init__(self):
        psutil.cpu_percent(None)
        self.boot_time = psutil.boot_time()
        self.last_net = psutil.net_io_counters()
        self.last_io = psutil.disk_io_counters()
        self.last_time = time.monotonic()
        self.first_procs: set[int] = set()

    def get_static_info(self) -> dict[str, Any]:
        return {
            "hostname": socket.gethostname(), "os": platform.platform(),
            "processor": platform.processor() or "Nome indisponível",
            "cpu_cores_physical": psutil.cpu_count(logical=False),
            "cpu_cores_logical": psutil.cpu_count(logical=True),
            "memory_total_gb": gb(psutil.virtual_memory().total),
            "uptime_hours": round((time.time() - self.boot_time) / 3600, 2),
        }

    def get_process_snapshot(self, limit=None):
        rows = []
        count = max(psutil.cpu_count(logical=True) or 1, 1)
        for p in psutil.process_iter(["pid", "name", "memory_percent", "status"]):
            try:
                raw = p.cpu_percent(interval=None)
                rows.append({"pid": p.pid, "name": p.info.get("name") or "desconhecido",
                             "cpu": round(raw / count, 1),
                             "memory": round(p.info.get("memory_percent") or 0.0, 1),
                             "status": p.info.get("status") or "?"})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        rows.sort(key=lambda p: (p["cpu"], p["memory"]), reverse=True)
        return rows[:max(1, limit)] if limit is not None else rows

    @staticmethod
    def _temp():
        try:
            sensors = psutil.sensors_temperatures()
        except (AttributeError, OSError):
            return None
        priority = []
        all_temps = []
        for sensor_name, values in sensors.items():
            for item in values:
                n = (sensor_name + " " + (item.label or "")).lower()
                if not isinstance(item.current, (int, float)):
                    continue
                if not 0 < item.current < 140:
                    continue
                if any(k in n for k in ("cpu", "package", "coretemp", "k10temp", "tctl", "tdie")):
                    priority.append(item.current)
                all_temps.append(item.current)
        return round(max(priority), 1) if priority else None

    @staticmethod
    def _optional_float(v):
        try:
            return float(v) if str(v).strip().upper() not in ("N/A", "[NOT SUPPORTED]") else None
        except (ValueError, TypeError):
            return None

    @classmethod
    def _nvidia_gpu(cls):
        result = dict(gpu_name="Não disponível", gpu_percent=None, gpu_temp_c=None,
                      gpu_memory_used_mb=None, gpu_memory_total_mb=None, gpu_power_w=None)
        executable = shutil.which("nvidia-smi")
        if not executable and os.name == "nt":
            p = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                             "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
            if os.path.exists(p):
                executable = p
        if not executable:
            return result
        try:
            completed = subprocess.run([
                executable, "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw",
                "--format=csv,noheader,nounits"], text=True, capture_output=True,
                timeout=2.5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if completed.returncode:
                return result
            parts = [part.strip() for part in completed.stdout.splitlines()[0].split(",")]
            if len(parts) < 6:
                return result
            result.update(gpu_name=parts[0], gpu_percent=cls._optional_float(parts[1]),
                          gpu_temp_c=cls._optional_float(parts[2]),
                          gpu_memory_used_mb=cls._optional_float(parts[3]),
                          gpu_memory_total_mb=cls._optional_float(parts[4]),
                          gpu_power_w=cls._optional_float(parts[5]))
        except (subprocess.TimeoutExpired, OSError, IndexError):
            pass
        return result

    def collect(self) -> Sample:
        cpu = psutil.cpu_percent(interval=0.15)
        frequency = psutil.cpu_freq()
        vm = psutil.virtual_memory()
        disk = shutil.disk_usage(os.path.expanduser("~"))
        now = time.monotonic()
        seconds = max(now - self.last_time, 0.01)
        net = psutil.net_io_counters()
        io = psutil.disk_io_counters()
        values = dict(net_sent_mb=0.0, net_recv_mb=0.0, disk_read_mb_s=0.0, disk_write_mb_s=0.0)
        if net is not None and self.last_net is not None:
            values["net_sent_mb"] = round(max(net.bytes_sent - self.last_net.bytes_sent, 0) / seconds / 1048576, 2)
            values["net_recv_mb"] = round(max(net.bytes_recv - self.last_net.bytes_recv, 0) / seconds / 1048576, 2)
        if io is not None and self.last_io is not None:
            values["disk_read_mb_s"] = round(max(io.read_bytes - self.last_io.read_bytes, 0) / seconds / 1048576, 2)
            values["disk_write_mb_s"] = round(max(io.write_bytes - self.last_io.write_bytes, 0) / seconds / 1048576, 2)
        self.last_net = net
        self.last_io = io
        self.last_time = now
        gpu = self._nvidia_gpu()
        return Sample(timestamp=time.time(), cpu_percent=round(cpu, 1),
                      cpu_freq_mhz=round(frequency.current, 0) if frequency else None,
                      cpu_temp_c=self._temp(), memory_percent=round(vm.percent, 1),
                      memory_used_gb=gb(vm.used), memory_total_gb=gb(vm.total),
                      swap_percent=round(psutil.swap_memory().percent, 1),
                      disk_percent=round(100 * disk.used / disk.total, 1),
                      disk_used_gb=gb(disk.used), disk_total_gb=gb(disk.total), **gpu, **values)
