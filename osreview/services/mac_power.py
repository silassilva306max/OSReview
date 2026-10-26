"""macOS native, read-only energy readings. Never requests sudo privileges.

Apple does not provide a general-purpose public sensor API covering all
models. IOKit battery measurements are provided only if that machine exposes
these keys. Readings can be signed and can be stale depending on firmware.
"""
from __future__ import annotations

import platform
import plistlib
import subprocess


def _run(command: list[str], timeout: float = 6.0) -> bytes | None:
    try:
        done = subprocess.run(command, capture_output=True, timeout=timeout, check=True)
        return done.stdout
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return None


def _battery_from_iokit(payload) -> dict | None:
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, dict):
            continue
        mv = item.get('Voltage')
        ma = item.get('Amperage')
        try:
            voltage_v = float(mv) / 1000
            current_a = float(ma) / 1000
        except (ValueError, TypeError):
            continue
        if not (0.1 <= voltage_v <= 50 and -30 <= current_a <= 30):
            continue
        return {
            'voltage_v':round(voltage_v, 3),
            'current_a':round(current_a, 3),
            'power_w':round(voltage_v * current_a, 2),
            'source':'IOKit AppleSmartBattery',
            'scope':'Apenas bateria (não representa fonte/tomada nem consumo total do computador)',
        }
    return None


def collect_mac_power() -> dict:
    if platform.system() != 'Darwin':
        return {'ok':False,'error':'Requer macOS'}
    raw = _run(['/usr/sbin/ioreg','-r','-c','AppleSmartBattery','-a'], timeout=8)
    try:
        battery = _battery_from_iokit(plistlib.loads(raw)) if raw else None
    except (ValueError, TypeError, plistlib.InvalidFileException):
        battery = None
    return {'ok':bool(battery), 'battery_electrical':battery,
            'note':'Temperaturas de CPU/VRM/GPU podem não ser acessíveis sem APIs privadas ou permissões especiais. '
                   'Nenhum acesso privilegiado será solicitado automaticamente.'}
