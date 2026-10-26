"""Read-only hardware telemetry: trustworthy sensor values or explicit 'indisponível'.

Windows: optional LibreHardwareMonitor WMI namespace; never installs drivers or modifies sensors.
Works without LHM, although some categories will remain unavailable. """
from __future__ import annotations
import math
import time
import platform
import json
import sys
import subprocess
from pathlib import Path
import re
from datetime import datetime
from typing import Any
import psutil
from .windows_inventory import native_windows_query, _list
from .startup_logging import LOG

_LAST_SUMMARY = None
_LAST_SUMMARY_LOG_AT = 0.0

SENSOR_CATEGORIES = ('CPU', 'GPU', 'VRM', 'Placa-mãe / chipset', 'SSD / HD', 'Memória RAM', 'Fonte / PSU', 'Outros')
SENSOR_TYPES = ('Temperature', 'Power', 'Voltage', 'Fan', 'Clock', 'Load', 'Current', 'Energy', 'Data', 'Throughput')

def classify_sensor(name: str, identifier: str, parent: str = '') -> str:
    n = (name or '').lower()
    ident = (identifier or '').lower()
    p = (parent or '').lower()
    if re.search(r'\b(psu|power supply|fonte de alimenta)\b', p):
        return 'Fonte / PSU'
    if re.search(r'\b(vrm|vr mos|mosfet|vcore vr|voltage regulator)\b', n):
        return 'VRM'
    if re.search(r'\b(dim(m)?\d*|ddr\d*|dram|ram module|memory stick)\b', n) and 'gpu' not in ident:
        return 'Memória RAM'
    if any(x in ident for x in ('/hdd/', '/storage/', '/nvme/', '/ssd/')) or re.search(r'\b(nvme|ssd|hard disk|hdd)\b', p):
        return 'SSD / HD'
    if any(x in ident for x in ('/gpu-', '/gpu/', '/integratedgpu/')) or 'gpu' in p or re.search(r'\b(gpu|graphics card)\b', n):
        return 'GPU'
    if any(x in ident for x in ('/intelcpu/', '/amdcpu/', '/cpu/')) or re.search(r'\b(cpu|processor|package|tctl|tdie|ccd\d*)\b', n):
        return 'CPU'
    if any(x in ident for x in ('/lpc/', '/mainboard/', '/motherboard/', '/superio/', '/chipset/')) or re.search(r'\b(mainboard|motherboard|system|chipset|pch|super i/o)\b', n):
        return 'Placa-mãe / chipset'
    if any(x in ident for x in ('/ram/', '/memory/')):
        return 'Memória RAM'
    return 'Outros'


def classify_by_hardware_type(raw: dict) -> str:
    """LibreHardwareMonitor reports hardware owner explicitly: use it before name heuristics."""
    kind = str(raw.get('HardwareType') or '').casefold()
    if kind in ('cpu',): return 'CPU'
    if kind.startswith('psu') or kind in ('powermonitor',): return 'Fonte / PSU'
    if kind.startswith('gpu'): return 'GPU'
    if kind in ('storage',): return 'SSD / HD'
    if kind in ('memory',): return 'Memória RAM'
    if kind in ('motherboard', 'superio', 'embeddedcontroller'): return 'Placa-mãe / chipset'
    # Keep every unsupported hardware type visible under 'Outros'.
    return ''


def sensor_inventory(groups: dict) -> dict:
    """A full sensor count does not imply a working thermal probe."""
    by_type = {}
    thermal_by_group = {}
    for cat, readings in groups.items():
        for r in readings:
            t = str(r.get('type') or '').casefold()
            by_type[t] = by_type.get(t, 0) + 1
            if t == 'temperature':
                from .sensor_analysis import is_real_temperature
                if is_real_temperature(r):
                    thermal_by_group[cat] = thermal_by_group.get(cat, 0) + 1
    return {'types': by_type, 'thermal_by_group': thermal_by_group,
            'thermal_count': sum(thermal_by_group.values()),
            'thermal_metadata_count': by_type.get('temperature',0)-sum(thermal_by_group.values())}


def normalize_sensor(raw: dict, source: str = 'LibreHardwareMonitor/WMI') -> dict | None:
    kind = str(raw.get('SensorType') or '').strip()
    name = str(raw.get('Name') or '').strip()
    ident = str(raw.get('Identifier') or '').strip()
    try:
        value = float(raw.get('Value'))
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value) or not name or not kind:
        return None
    # Discard unrealistic temp values; invalid sensors often report placeholders.
    if kind.lower() == 'temperature' and not (-30 <= value <= 180):
        return None
    # Windows battery capacity APIs normally report mWh; LHM 0.9.6 forwards
    # those raw numbers as SensorType.Energy. Do not label 42009 as 42009 Wh.
    battery_energy = kind.casefold() == 'energy' and (str(raw.get('HardwareType') or '').casefold() == 'battery' or '/battery/' in ident.lower())
    if battery_energy and 1000 <= value <= 1000000:
        value /= 1000.0
    labels = {'temperature':'°C', 'power':'W', 'voltage':'V', 'fan':'RPM',
              'clock':'MHz', 'load':'%', 'current':'A', 'energy':'Wh'}
    return {'category':(classify_by_hardware_type(raw) or classify_sensor(name, ident, str(raw.get('Parent') or ''))),
            'type':kind, 'name':name, 'value':round(value, 2),
            'unit':labels.get(kind.lower(), ''), 'identifier':ident, 'source':source,
            'min':raw.get('Min'), 'max':raw.get('Max'),
            'hardware_type':str(raw.get('HardwareType') or ''),
            'device':str(raw.get('Device') or raw.get('Parent') or '')}


def organize_sensors(items: Any, source: str = 'LibreHardwareMonitor/WMI') -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {cat: [] for cat in SENSOR_CATEGORIES}
    for raw in _list(items):
        if not isinstance(raw, dict):
            continue
        row = normalize_sensor(raw, source)
        if row:
            groups[row['category']].append(row)
    return groups


def _bundled_sensor_bridge() -> tuple[Any, str | None]:
    """Take the latest sample from our long-running, integrity-checked reader.

    Returns no readings until the first valid sample is delivered; never makes
    up values from the component inventory.
    """
    if platform.system() != 'Windows':
        return None, None
    from .sensor_runtime import runtime
    data = runtime.snapshot()
    if data['available']:
        return data['rows'], 'LibreHardwareMonitorLib 0.9.6 (ponte íntegra)'
    return None, None


def _fallback_storage_sensors() -> list[dict]:
    """Read native Windows reliability counters if the thermal bridge is absent.

    Storage controllers may omit these fields; absent readings stay unavailable.
    """
    from .windows_native import query_wmi
    rows = query_wmi('MSFT_StorageReliabilityCounter',
                     ('DeviceId', 'Temperature', 'Wear', 'PowerOnHours',
                      'ReadErrorsUncorrected', 'WriteErrorsUncorrected'),
                     namespace=r'root\Microsoft\Windows\Storage', limit=50)
    sensors = []
    for row in rows or []:
        name = str(row.get('DeviceId') or '?')
        temperature = row.get('Temperature')
        if isinstance(temperature, (int, float)) and 0 < temperature < 110:
            sensors.append({'Name': f'Disco {name}: temperatura',
                            'SensorType': 'Temperature', 'Value': temperature,
                            'Identifier': f'/storage/{name}/temperature'})
        wear = row.get('Wear')
        if isinstance(wear, (int, float)) and 0 <= wear <= 100:
            sensors.append({'Name': f'Disco {name}: desgaste informado',
                            'SensorType': 'Load', 'Value': wear,
                            'Identifier': f'/storage/{name}/wear'})
    return sensors


def _fallback_acpi_thermal_zones() -> list[dict]:
    """ACPI thermal-zone reading is not CPU temperature; OEMs may expose none."""
    from .windows_native import query_wmi
    try:
        zones=query_wmi('MSAcpi_ThermalZoneTemperature',
                        ('InstanceName','CurrentTemperature'),
                        namespace=r'root\wmi',limit=12)
    except Exception:
        return []
    readings=[]
    for zone in zones or []:
        try:
            c=float(zone.get('CurrentTemperature'))/10.-273.15
        except (ValueError, TypeError):continue
        if 0 <= c <= 110:
            name=str(zone.get('InstanceName') or 'Zona ACPI')[:140]
            readings.append({'Name':f'Zona térmica ACPI — {name}',
                    'SensorType':'Temperature','Value':round(c,1),
                    'Identifier':f'/acpi/thermal/{name}',
                    'Parent':'Zona térmica do sistema, NÃO temperatura da CPU'})
    return readings


def collect_energy_sensors() -> dict:
    """No PSU wall wattage claim. Unavailable readings are never replaced with guesses."""
    raw,source = _bundled_sensor_bridge()
    runtime_status = None
    if platform.system() == 'Windows':
        from .sensor_runtime import runtime
        runtime_status = runtime.snapshot()
    if platform.system() == 'Windows' and raw is None:
        raw = native_windows_query(
            "Get-CimInstance -Namespace 'root/LibreHardwareMonitor' -ClassName Sensor -ErrorAction Stop | "
            "Select-Object Name,SensorType,Value,Identifier,Parent | ConvertTo-Json -Compress -Depth 3", 15)
    if raw is None and platform.system() == 'Windows':
        # Passive WMI fallback: only if an authorized Open Hardware Monitor
        # instance is ALREADY exposing root\OpenHardwareMonitor.
        # No binary download, driver install or application execution.
        try:
            from .windows_native import query_wmi
            passive = query_wmi('Sensor', ('Name', 'SensorType', 'Value', 'Identifier', 'Parent'),
                namespace=r'root\OpenHardwareMonitor', limit=600)
            if passive:
                raw, source = passive, 'Open Hardware Monitor / WMI (terceiros, leitura passiva)'
        except (OSError, ValueError):
            pass
    if raw is not None and not source: source='LibreHardwareMonitor/WMI'
    groups = organize_sensors(raw,source=source or 'LibreHardwareMonitor/WMI')
    # Independent, Windows-native fallback for SSD/HDD temperature and wear.
    # This remains available even when third-party sensor drivers are blocked.
    if platform.system() == 'Windows':
        try:
            storage = organize_sensors(_fallback_storage_sensors(), 'Windows Storage Reliability')
            known = {r['identifier'] for rows in groups.values() for r in rows}
            for category, readings in storage.items():
                groups[category].extend(r for r in readings if r['identifier'] not in known)
        except Exception:
            pass

    if platform.system() == 'Windows':
        # ACPI fallback is labelled as a separate system thermal zone.
        # It must never be silently substituted for an Intel/AMD CPU package reading.
        try:
            for sensor in _fallback_acpi_thermal_zones():
                row=normalize_sensor(sensor,'Windows ACPI (zona térmica ≠ CPU)')
                if row:
                    row['category']='Outros'
                    if row['identifier'] not in {x['identifier'] for cat in groups.values() for x in cat}:
                        groups['Outros'].append(row)
        except Exception:
            pass
    if platform.system() != 'Windows':
        try:
            temps = psutil.sensors_temperatures() or {}
        except (OSError, AttributeError, NotImplementedError):
            temps = {}
        for chip, values in temps.items():
            for val in values:
                sensor = normalize_sensor({'Name':val.label or chip, 'SensorType':'Temperature',
                                           'Value':val.current, 'Identifier':chip}, 'psutil/sistema')
                if sensor:
                    groups[sensor['category']].append(sensor)
    mac_telemetry = None
    if platform.system() == 'Darwin':
        from .mac_power import collect_mac_power
        mac_telemetry = collect_mac_power()
    battery = None
    try:
        b = psutil.sensors_battery()
        if b is not None:
            battery = {'percent':b.percent, 'plugged':b.power_plugged,
                       'remaining_seconds':b.secsleft if b.secsleft >= 0 else None}
    except (AttributeError, OSError, NotImplementedError):
        pass
    counts = sensor_inventory(groups)
    # Log only sensor counts and availability automatically (not identifying
    # machine details or individual readings). Detailed data are export opt-in.
    global _LAST_SUMMARY, _LAST_SUMMARY_LOG_AT
    fingerprint = (sum(len(rows) for rows in groups.values()),
                   counts['thermal_count'], counts['types'].get('power', 0),
                   bool(runtime_status and runtime_status.get('available')))
    now = time.monotonic()
    if fingerprint != _LAST_SUMMARY or now - _LAST_SUMMARY_LOG_AT > 90:
        LOG.info('Cobertura sensores: leituras=%s termicos=%s potencia=%s ponte_ativa=%s', *fingerprint)
        _LAST_SUMMARY, _LAST_SUMMARY_LOG_AT = fingerprint, now
    windows_admin = None
    if platform.system() == 'Windows':
        try:
            import ctypes
            windows_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            pass
    if runtime_status is not None:
        runtime_status = dict(runtime_status)
        runtime_status['summary'] = counts
    return {'collected_at':datetime.now().isoformat(timespec='seconds'),
            'groups':groups, 'sensor_count':sum(map(len,groups.values())), 'sensor_inventory':counts,
            'windows_admin':windows_admin,
            'lhm_connected':raw is not None,
            'sensor_source':source or 'Não conectado',
            'battery':battery, 'mac_electrical':mac_telemetry,
            'engine_status':runtime_status,
            'psu_total_w':None, 'psu_voltage':None,
            'note': 'Fonte ATX: potência total real e tensões não são oferecidas pelo Windows. Sensores de componentes não comprovam a entrega total da fonte.',
            'integration': ('Ponte interna LibreHardwareMonitorLib conferida por SHA-256' if source and 'ponte íntegra' in source else ('Motor ainda sem leituras. ' + (runtime_status.get('error') or 'Aguardando dados...') if runtime_status else 'Sem ponte Windows; usando sensores do sistema.'))}


def psu_budget(cpu_w: float | None, gpu_w: float | None, disks: int = 1) -> dict:
    """Estimate only when user supplies credible maximum sustained CPU/GPU power in W.
    65 W board/memory/peripherals and 25 W fans/USB are conservative placeholders,
    not observed measurements. 35% headroom; no PSU quality/connector guarantee.
    """
    if cpu_w is None or gpu_w is None:
        return {'ok':False, 'reason':'Informe o consumo máximo documentado de CPU e GPU em watts (GPU integrada: 0 W adicional se incluída no consumo total da CPU).'}
    if not (10 <= cpu_w <= 600 and 0 <= gpu_w <= 800 and 0 <= disks <= 24):
        return {'ok':False, 'reason':'Valores fora da faixa admitida. Consulte os dados oficiais do fabricante.'}
    baseline = cpu_w + gpu_w + 65 + disks * 12 + 25
    suggested = math.ceil(baseline * 1.35 / 50) * 50
    return {'ok':True, 'estimated_demand_w':round(baseline), 'recommended_nominal_w':max(350, suggested),
            'headroom_percent':35, 'method':'CPU + GPU máximos fornecidos + 65 W plataforma + 12 W/disco + 25 W extras + 35% folga',
            'warning':'Estimativa para seleção preliminar: verifique ATX/SFX, conectores 24 pinos/EPS/PCIe, tensão de entrada 100–240 V, picos de carga e testes independentes. Não comprova defeito elétrico.'}
