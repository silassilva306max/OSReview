"""Windows inventory in read-only mode. No driver installation or service changes."""
from __future__ import annotations

import json
import platform
import subprocess
from typing import Any


def _list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def native_windows_query(script: str, timeout: int = 18) -> Any:
    """Compatibility shim for old collectors. Does NOT launch PowerShell.

    New OSReview builds use explicitly mapped WMI/COM read-only operations.
    Unmapped collectors return None and show "Indisponível" in the UI.
    """
    from .windows_native import resolve_legacy_readonly_query
    return resolve_legacy_readonly_query(script, timeout)


def gpu_kind(name: str, pnp: str = '') -> str:
    """Heuristic category, not a verified hardware architecture property."""
    n = name.lower()
    if any(s in n for s in ('microsoft basic display', 'basic render', 'remote display')):
        return 'driver genérico/virtual'
    if 'intel' in n or 'ven_8086' in pnp.lower():
        if any(s in n for s in ('uhd', 'hd graphics', 'iris', 'arc graphics')):
            return 'integrada/provável'
        return 'Intel (tipo não confirmado)'
    if 'amd' in n or 'radeon' in n or 'ven_1002' in pnp.lower():
        if ('radeon graphics' in n or 'radeon(tm) graphics' in n) and not any(s in n for s in ('rx ', 'pro w')):
            return 'integrada/provável'
        return 'AMD (tipo não confirmado)'
    if 'nvidia' in n or 'geforce' in n or 'ven_10de' in pnp.lower():
        return 'NVIDIA (dedicada/provável)'
    return 'não determinado'


def normalize_gpus(payload: Any) -> list[dict[str, Any]]:
    devices = []
    for d in _list(payload):
        if not isinstance(d, dict):
            continue
        name = str(d.get('Name') or d.get('Caption') or '').strip()
        if not name:
            continue
        pnp = str(d.get('PNPDeviceID') or '')
        devices.append({
            'name': name, 'vendor': str(d.get('AdapterCompatibility') or 'Não informado'),
            'type': gpu_kind(name, pnp), 'driver_version': str(d.get('DriverVersion') or 'Indisponível'),
            'status': str(d.get('Status') or 'Não informado'),
            'error_code': d.get('ConfigManagerErrorCode'),
            'resolution': ' × '.join(map(str, [d.get('CurrentHorizontalResolution'), d.get('CurrentVerticalResolution')]))
                          if d.get('CurrentHorizontalResolution') and d.get('CurrentVerticalResolution') else 'Indisponível',
            'pnp_id': pnp,
            'vram_note': 'Memória compartilhada/dedicada não estimada pelo WMI; AdapterRAM pode ser incorreto.'
        })
    return devices


def _mac_gpus() -> list[dict[str, Any]]:
    try:
        output = subprocess.run(['system_profiler', 'SPDisplaysDataType', '-json'],
                                text=True, capture_output=True, timeout=18, check=True)
        sections = json.loads(output.stdout).get('SPDisplaysDataType', [])
    except (OSError, ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return []
    rows = []
    for item in sections:
        name = str(item.get('sppci_model') or item.get('_name') or 'GPU sem nome')
        rows.append({'name': name, 'vendor': item.get('spdisplays_vendor', '?'),
                     'type': gpu_kind(name), 'driver_version': 'Gerenciado pelo macOS',
                     'status': 'Detectado no System Profiler', 'error_code': None,
                     'resolution': 'Indisponível', 'pnp_id': '',
                     'vram_note': 'Compartilhamento e VRAM dependem do modelo; não estimados.'})
    return rows


def collect_inventory() -> dict[str, Any]:
    response = {'supported': platform.system() == 'Windows', 'gpus': [], 'antivirus': [],
                'defender': None, 'devices_with_errors': [], 'error': None}
    if not response['supported']:
        if platform.system() == 'Darwin':
            response['gpus'] = _mac_gpus()
            response['error'] = 'Inventário gráfico via system_profiler; segurança/PnP do Windows indisponíveis no macOS.'
        else:
            response['error'] = 'Inventário WMI e segurança somente no Windows.'
        return response
    query = ("Get-CimInstance -ClassName Win32_VideoController -ErrorAction SilentlyContinue | "
             "Select-Object Name,AdapterCompatibility,PNPDeviceID,DriverVersion,Status,ConfigManagerErrorCode,CurrentHorizontalResolution,CurrentVerticalResolution | "
             "ConvertTo-Json -Compress -Depth 4")
    devices = native_windows_query(query, 20)
    response['gpus'] = normalize_gpus(devices)
    if devices is None:
        response['error'] = 'Consulta de GPUs não retornou dados; verifique WMI e privilégios.'
    av = native_windows_query(
        "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction SilentlyContinue | "
        "Select-Object displayName,productState,pathToSignedProductExe | ConvertTo-Json -Compress -Depth 3", 15)
    response['antivirus'] = [
        {'name': str(x.get('displayName')), 'state_raw': x.get('productState')}
        for x in _list(av) if isinstance(x, dict) and x.get('displayName')]
    # A missing SecurityCenter2 result is unknown, NOT proof of no antivirus.
    response['antivirus_query_ok'] = av is not None
    defender = native_windows_query(
        "Get-MpComputerStatus -ErrorAction SilentlyContinue | "
        "Select-Object AMRunningMode,AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureAge,AntivirusSignatureVersion | ConvertTo-Json -Compress", 15)
    if isinstance(defender, dict):
        response['defender'] = defender
    pnp = native_windows_query(
        "Get-PnpDevice -PresentOnly -Status ERROR,DEGRADED,UNKNOWN -ErrorAction SilentlyContinue | "
        "Select-Object -First 35 FriendlyName,Class,Status,InstanceId | ConvertTo-Json -Compress -Depth 3", 20)
    response['devices_with_errors'] = [
        {'name': x.get('FriendlyName') or 'Dispositivo sem nome',
         'class': x.get('Class') or '?', 'status': x.get('Status') or '?',
         'instance_id': x.get('InstanceId') or '?'}
        for x in _list(pnp) if isinstance(x, dict)]
    response['pnp_query_ok'] = pnp is not None
    return response
