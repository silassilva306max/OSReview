"""Inventário físico detalhado. Windows: CIM/Storage (leitura apenas); macOS: system_profiler.

Nunca infere NVMe, RPM, DDR ou slots livres a partir de nomes comerciais.
Dados omitidos pelo fabricante/driver ficam como indisponíveis.
"""
from __future__ import annotations

import json
import platform
import subprocess
from typing import Any

import psutil
from .windows_inventory import native_windows_query, _list

MEMORY_TYPES = {20: 'DDR', 21: 'DDR2', 24: 'DDR3', 26: 'DDR4', 34: 'DDR5',
                30: 'LPDDR3', 31: 'LPDDR4', 35: 'LPDDR5', 36: 'LPDDR5X'}
BUS_TYPES = {0:'Desconhecido',1:'SCSI',2:'ATAPI',3:'ATA',7:'USB',8:'RAID',10:'SAS',11:'SATA',
             12:'SD',13:'MMC',16:'Storage Spaces',17:'NVMe'}
MEDIA_TYPES = {0:'Não informada',3:'HDD',4:'SSD',5:'SCM'}


def _gb(value: Any) -> float | None:
    try:
        return round(int(value) / 1024**3, 2) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text(v, default='Não informado'):
    return str(v).strip() if v not in (None, '') else default


def normalize_disks(wmi: Any, physical: Any, windows_disks: Any = None) -> list[dict[str, Any]]:
    """Merge by explicit disk number/DeviceId; avoids merging similarly named disks."""
    physical_by_number: dict[int, dict] = {}
    for item in _list(physical):
        if isinstance(item, dict) and _int(item.get('DeviceId')) is not None:
            physical_by_number[int(item['DeviceId'])] = item
    disk_by_number: dict[int, dict] = {}
    for item in _list(windows_disks):
        if isinstance(item, dict) and _int(item.get('Number')) is not None:
            disk_by_number[int(item['Number'])] = item
    results = []
    for raw in _list(wmi):
        if not isinstance(raw, dict):
            continue
        number = _int(raw.get('Index'))
        provider = physical_by_number.get(number, {})
        disk = disk_by_number.get(number, {})
        bus_raw = provider.get('BusType') if provider.get('BusType') is not None else disk.get('BusType')
        media_raw = provider.get('MediaType')
        bus = BUS_TYPES.get(_int(bus_raw), _text(bus_raw, 'Desconhecido'))
        media = MEDIA_TYPES.get(_int(media_raw), _text(media_raw, 'Não informada'))
        speed = _int(provider.get('SpindleSpeed'))
        rpm = speed if media == 'HDD' and speed is not None and 60 <= speed < 100000 else None
        if media == 'SSD' and bus == 'NVMe':
            technology = 'SSD NVMe'
        elif media == 'SSD':
            technology = f'SSD ({bus})' if bus not in ('Desconhecido', 'Não informado') else 'SSD (interface não identificada)'
        elif media == 'HDD':
            technology = f'HDD ({bus})' if bus != 'Desconhecido' else 'HDD (interface não identificada)'
        else:
            technology = f'Tipo não confirmado (barramento {bus})'
        results.append({
            'number': number, 'model': _text(raw.get('Model')),
            'size_gb': _gb(raw.get('Size')),
            'technology': technology, 'media': media, 'bus': bus, 'rpm': rpm,
            'rpm_note': ('RPM não informado pelo controlador' if media == 'HDD' and rpm is None else None),
            'interface_wmi': _text(raw.get('InterfaceType')),
            'health': _text(provider.get('HealthStatus'), 'Indisponível'),
            'removable': bus == 'USB' or 'removable' in _text(raw.get('MediaType'), '').lower(),
        })
    return results


def normalize_memory(items: Any) -> list[dict[str, Any]]:
    rows = []
    for d in _list(items):
        if not isinstance(d, dict):
            continue
        typ = _int(d.get('SMBIOSMemoryType'))
        if typ not in MEMORY_TYPES:
            typ = _int(d.get('MemoryType'))
        rows.append({
            'manufacturer': _text(d.get('Manufacturer')), 'model': _text(d.get('PartNumber')),
            'capacity_gb': _gb(d.get('Capacity')),
            'technology': MEMORY_TYPES.get(typ, 'DDR não identificado'),
            'speed_mhz': _int(d.get('Speed')),
            'configured_mhz': _int(d.get('ConfiguredClockSpeed')),
            'slot': _text(d.get('DeviceLocator')),
            'bank': _text(d.get('BankLabel')),
        })
    return rows


def memory_frequency_summary(inventory: dict | None) -> str:
    """Summarize firmware-reported module speeds without inventing a system clock."""
    sticks = [row for row in ((inventory or {}).get('ram_sticks') or []) if isinstance(row, dict)]
    if not sticks:
        return 'Não informada'
    for field, suffix in (('configured_mhz', 'config.'), ('speed_mhz', 'nominal')):
        speeds = [row.get(field) for row in sticks]
        valid = [int(value) for value in speeds if isinstance(value, (int, float)) and
                 not isinstance(value, bool) and value > 0]
        if not valid:
            continue
        unique = sorted(set(valid))
        if len(unique) > 1:
            return f'{unique[0]}–{unique[-1]} MHz (módulos)'
        qualifier = suffix if len(valid) == len(sticks) else 'parcial'
        return f'{unique[0]} MHz ({qualifier})'
    return 'Não informada'


def _collect_windows() -> dict:
    cpu = native_windows_query("Get-CimInstance Win32_Processor | Select-Object Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed,SocketDesignation,L2CacheSize,L3CacheSize | ConvertTo-Json -Compress -Depth 3", 20)
    mem = native_windows_query("Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer,PartNumber,Capacity,Speed,ConfiguredClockSpeed,SMBIOSMemoryType,MemoryType,DeviceLocator,BankLabel | ConvertTo-Json -Compress -Depth 3", 20)
    slots = native_windows_query("Get-CimInstance Win32_PhysicalMemoryArray | Select-Object MemoryDevices | ConvertTo-Json -Compress -Depth 2", 12)
    disks = native_windows_query("Get-CimInstance Win32_DiskDrive | Select-Object Index,Model,Size,InterfaceType,MediaType,PNPDeviceID | ConvertTo-Json -Compress -Depth 4", 22)
    physical = native_windows_query("Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object DeviceId,FriendlyName,MediaType,BusType,SpindleSpeed,HealthStatus,Size | ConvertTo-Json -Compress -Depth 4", 22)
    get_disk = native_windows_query("Get-Disk -ErrorAction SilentlyContinue | Select-Object Number,FriendlyName,BusType,Size | ConvertTo-Json -Compress -Depth 3", 22)
    removable = native_windows_query("Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=2' | Select-Object DeviceID,VolumeName,Size,FreeSpace,FileSystem | ConvertTo-Json -Compress -Depth 3", 14)
    volumes = native_windows_query("Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,VolumeName,Size,FreeSpace,FileSystem | ConvertTo-Json -Compress -Depth 3", 14)
    usb = native_windows_query("Get-PnpDevice -PresentOnly -Class USB -ErrorAction SilentlyContinue | Select-Object -First 30 FriendlyName,Status,Class | ConvertTo-Json -Compress -Depth 3", 15)
    cpus = []
    for item in _list(cpu):
        if not isinstance(item, dict):
            continue
        cpus.append({
            'name': _text(item.get('Name')), 'manufacturer': _text(item.get('Manufacturer')),
            'cores': _int(item.get('NumberOfCores')), 'threads': _int(item.get('NumberOfLogicalProcessors')),
            'max_mhz': _int(item.get('MaxClockSpeed')), 'reported_mhz': _int(item.get('CurrentClockSpeed')),
            'socket': _text(item.get('SocketDesignation')),
            'l2_kb': _int(item.get('L2CacheSize')), 'l3_kb': _int(item.get('L3CacheSize')),
        })
    total_slots = sum(_int(a.get('MemoryDevices')) or 0 for a in _list(slots) if isinstance(a, dict)) or None
    def vol(row):
        return {'letter': row.get('DeviceID'), 'name': row.get('VolumeName') or '',
                'size_gb': _gb(row.get('Size')), 'free_gb': _gb(row.get('FreeSpace')),
                'fs': row.get('FileSystem') or ''}
    return {
        'platform': 'Windows', 'cpus': cpus, 'ram_sticks': normalize_memory(mem),
        'ram_total_gb': round(psutil.virtual_memory().total / 1024**3, 2),
        'ram_slots_reported': total_slots,
        'disks': normalize_disks(disks, physical, get_disk),
        'volumes': [vol(d) for d in _list(volumes) if isinstance(d, dict)],
        'removable': [vol(d) for d in _list(removable) if isinstance(d, dict)],
        'usb_devices': [{'name': _text(x.get('FriendlyName')), 'status': _text(x.get('Status'))}
                        for x in _list(usb) if isinstance(x, dict)],
        'warnings': (["Dados de discos não retornados pelo Windows; serviço Storage/CIM pode estar indisponível."] if disks is None else []) +
                    (["Tipo de mídia, barramento ou RPM podem depender da controladora e do driver."] if physical is None else []),
    }


def _collect_mac() -> dict:
    try:
        out = subprocess.run(['system_profiler', 'SPHardwareDataType', 'SPMemoryDataType', 'SPStorageDataType', 'SPUSBDataType', '-json'],
                             capture_output=True, text=True, timeout=30, check=True)
        payload = json.loads(out.stdout)
        return {'platform': 'macOS', 'profiler': payload,
                'cpus': [], 'ram_sticks': [], 'ram_total_gb': round(psutil.virtual_memory().total / 1024**3, 2),
                'disks': [], 'volumes': [], 'removable': [], 'usb_devices': [],
                'warnings': ['Informações originais do System Profiler; campos ausentes não foram estimados.']}
    except (OSError, ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return {'platform':'macOS','cpus': [], 'ram_sticks':[], 'ram_total_gb':round(psutil.virtual_memory().total/1024**3,2),
                'disks':[], 'volumes':[], 'removable':[], 'usb_devices':[],
                'warnings':['System Profiler não respondeu.']}


def collect_hardware_deep() -> dict:
    if platform.system() == 'Windows':
        return _collect_windows()
    if platform.system() == 'Darwin':
        return _collect_mac()
    return {'platform':platform.system(), 'cpus':[], 'ram_sticks':[],
            'ram_total_gb':round(psutil.virtual_memory().total / 1024**3, 2),
            'disks':[], 'volumes':[], 'removable':[], 'usb_devices':[],
            'warnings':['Inventário físico detalhado disponibilizado para Windows e parcialmente macOS.']}
