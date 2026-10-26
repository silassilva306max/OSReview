"""Read-only native Windows diagnostics without spawning PowerShell.

Uses official WMI/COM interfaces via pywin32. Every supported query is an
explicitly coded operation; strings are NOT executed as shell commands.
Unknown queries return None (never executed), preventing arbitrary code paths.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import os
import platform
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Any


def _com():
    if platform.system() != 'Windows':
        return None
    try:
        import win32com.client
        return win32com.client
    except ImportError:
        return None


def available() -> bool:
    return _com() is not None


def _value(v):
    if v is None:
        return None
    if isinstance(v, (str, bool, int, float)):
        return v
    if isinstance(v, (tuple, list)):
        return [_value(x) for x in v]
    try:
        return list(map(_value, v))
    except (TypeError, ValueError):
        return str(v)


def query_wmi(classname: str, fields: tuple[str, ...], namespace: str = r'root\cimv2',
              where: str | None = None, limit: int = 100) -> list[dict[str, Any]] | None:
    """Only trusted classnames/fieldnames from literals should reach this function."""
    client = _com()
    if not client:
        return None
    try:
        import pythoncom
        pythoncom.CoInitialize()  # WMI collectors are called on background threads.
    except ImportError:
        return None
    try:
        service = client.GetObject('winmgmts:{impersonationLevel=impersonate}!\\\\.\\' + namespace)
        sql = f'SELECT {", ".join(fields)} FROM {classname}'
        if where:
            sql += ' WHERE ' + where
        result = []
        for obj in service.ExecQuery(sql):
            row = {}
            for field in fields:
                try:
                    row[field] = _value(getattr(obj, field))
                except Exception:
                    row[field] = None
            result.append(row)
            if len(result) >= limit:
                break
        return result
    except Exception:
        return None
    finally:
        pythoncom.CoUninitialize()


def query_pnp(only_errors: bool = False, only_usb: bool = False) -> list[dict] | None:
    fields = ('Name', 'PNPDeviceID', 'ConfigManagerErrorCode', 'Status', 'PNPClass', 'Present')
    rows = query_wmi('Win32_PnPEntity', fields, limit=500)
    if rows is None:
        return None
    items = []
    for row in rows:
        pnp = str(row.get('PNPDeviceID') or '')
        code = row.get('ConfigManagerErrorCode')
        if only_usb and not (pnp.upper().startswith('USB\\') or str(row.get('PNPClass') or '').upper() == 'USB'):
            continue
        if only_errors and (code in (0, None, '0')):
            continue
        items.append({
            'FriendlyName': row.get('Name'), 'Class': row.get('PNPClass'),
            'Status': 'ERROR' if code not in (0, None, '0') else (row.get('Status') or 'OK'),
            'InstanceId': pnp,
        })
    return items[:35 if only_errors else 30]


def collect_network_configuration() -> list[dict] | None:
    rows = query_wmi('Win32_NetworkAdapterConfiguration',
        ('Description', 'InterfaceIndex', 'IPAddress', 'DefaultIPGateway', 'DNSServerSearchOrder'),
        where='IPEnabled=True', limit=80)
    if rows is None:
        return None
    # Match InterfaceAlias from psutil via registry GUID mapping; best effort.
    index_to_name: dict[int, str] = {}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r'SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}') as root:
            count = winreg.QueryInfoKey(root)[0]
            for i in range(count):
                guid = winreg.EnumKey(root, i)
                try:
                    with winreg.OpenKey(root, guid + r'\Connection') as conn:
                        alias = winreg.QueryValueEx(conn, 'Name')[0]
                except OSError:
                    continue
                index_to_name[guid.lower()] = alias
    except OSError:
        pass
    adapters = query_wmi('Win32_NetworkAdapter', ('InterfaceIndex', 'GUID', 'NetConnectionID'), limit=300) or []
    index_to_alias = {}
    for a in adapters:
        idx = a.get('InterfaceIndex')
        alias = a.get('NetConnectionID') or index_to_name.get(str(a.get('GUID') or '').lower(), '')
        if idx is not None and alias:
            index_to_alias[idx] = alias
    result = []
    for r in rows:
        index = r.get('InterfaceIndex')
        result.append({
            'InterfaceAlias':index_to_alias.get(index, r.get('Description') or str(index)),
            'InterfaceIndex':index,
            'IPv4DefaultGateway': [x for x in (r.get('DefaultIPGateway') or []) if ':' not in x],
            'IPv6DefaultGateway': [x for x in (r.get('DefaultIPGateway') or []) if ':' in x],
            'DNSServers': r.get('DNSServerSearchOrder') or [],
            'NetProfile': None,
        })
    return result


def collect_adapters() -> list[dict] | None:
    rows = query_wmi('Win32_NetworkAdapter',
        ('Name','NetConnectionID','Speed','NetEnabled','MACAddress','InterfaceIndex'), limit=250)
    if rows is None:
        return None
    return [{'Name':r.get('NetConnectionID') or r.get('Name'),
             'InterfaceDescription':r.get('Name'),
             'LinkSpeed':f'{int(r["Speed"])/1_000_000:g} Mbps' if r.get('Speed') is not None else None,
             'Status':'Up' if r.get('NetEnabled') else 'Disconnected',
             'MacAddress':r.get('MACAddress'), 'InterfaceIndex':r.get('InterfaceIndex')}
            for r in rows]


def collect_neighbors() -> list[dict] | None:
    """ARP table reader, no port scanning and no shell interpreter."""
    try:
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(['arp.exe', '-a'], capture_output=True, text=True,
                                timeout=7, creationflags=creationflags)
        if result.returncode:
            return None
        entries = []
        for match in re.finditer(r'\b(\d{1,3}(?:\.\d{1,3}){3})\s+([a-fA-F0-9-]{17})\s+(\S+)',result.stdout):
            ip, mac, kind = match.groups()
            try:
                ipaddress.IPv4Address(ip)
            except ValueError:
                continue
            entries.append({'IPAddress': ip, 'LinkLayerAddress':mac, 'State':'Reachable' if 'dynamic' in kind.lower() else 'Permanent', 'InterfaceAlias':None})
        return entries
    except (OSError, subprocess.TimeoutExpired):
        return None


def collect_events(max_events: int = 120, logs: tuple[str, ...] = ('System', 'Application'),
                   days: int = 7) -> list[dict] | None:
    """Vista Event Log API. Message may be unavailable unless provider formatting is accessible."""
    if platform.system() != 'Windows':
        return None
    try:
        import win32evtlog
        max_events = max(1, min(max_events, 200))
        rows = []
        filter_ms = max(days, 1) * 24 * 3600 * 1000
        query = f'*[System[(Level=1 or Level=2) and TimeCreated[timediff(@SystemTime) <= {filter_ms}]]]'
        for logname in logs:
            handle = win32evtlog.EvtQuery(logname, win32evtlog.EvtQueryReverseDirection, query)
            try:
                while len(rows) < max_events:
                    batch = win32evtlog.EvtNext(handle, min(20, max_events-len(rows)), 0, 0)
                    if not batch:
                        break
                    for event_handle in batch:
                        xml = win32evtlog.EvtRender(event_handle, win32evtlog.EvtRenderEventXml)
                        el = ET.fromstring(xml)
                        ns = {'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
                        sys = el.find('e:System', ns)
                        if sys is None:
                            continue
                        e_id = sys.find('e:EventID', ns)
                        level = sys.find('e:Level', ns)
                        provider = sys.find('e:Provider', ns)
                        time_el = sys.find('e:TimeCreated', ns)
                        data = el.find('e:EventData', ns)
                        desc = '; '.join((node.text or '')[:160] for node in data) if data is not None else ''
                        rows.append({
                            'TimeCreated':(time_el.attrib.get('SystemTime','') if time_el is not None else ''),
                            'LogName':logname, 'ProviderName': provider.attrib.get('Name') if provider is not None else None,
                            'Id':int(e_id.text or 0) if e_id is not None else 0,
                            'Level':int(level.text or 2) if level is not None else 2,
                            'Message':desc or 'O log não forneceu mensagem legível; verifique o Visualizador de Eventos para detalhes.'
                        })
            finally:
                win32evtlog.EvtClose(handle)
        rows.sort(key=lambda r: r['TimeCreated'], reverse=True)
        return rows[:max_events]
    except Exception:
        return None


def collect_updates(max_updates: int = 80) -> dict:
    """User-triggered COM Windows Update scan. Reads available updates, installs nothing."""
    client = _com()
    if not client:
        return {'ok':False, 'updates':[], 'error':'pywin32/COM indisponível'}
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        return {'ok':False, 'updates':[], 'error':'pythoncom indisponível'}
    try:
        session = client.Dispatch('Microsoft.Update.Session')
        searcher = session.CreateUpdateSearcher()
        result = searcher.Search('IsInstalled=0 and IsHidden=0')
        total = int(result.Updates.Count)
        updates = []
        for i in range(min(total,max_updates)):
            u = result.Updates.Item(i)
            updates.append({'title':str(u.Title), 'severity':str(u.MsrcSeverity),
                            'type':str(u.Type), 'mandatory':bool(u.IsMandatory),
                            'downloaded':bool(u.IsDownloaded)})
        return {'ok':True, 'updates':updates, 'total':total}
    except Exception as exc:
        return {'ok':False, 'updates':[], 'error':f'Windows Update Agent não respondeu: {type(exc).__name__}'}
    finally:
        pythoncom.CoUninitialize()


def get_av() -> list[dict] | None:
    return query_wmi('AntiVirusProduct',('displayName','productState','pathToSignedProductExe'),
                     namespace=r'root\SecurityCenter2', limit=20)


def get_defender() -> list[dict] | None:
    return query_wmi('MSFT_MpComputerStatus',
            ('AMRunningMode','AntivirusEnabled','RealTimeProtectionEnabled',
             'AntivirusSignatureAge','AntivirusSignatureVersion'),
             namespace=r'root\Microsoft\Windows\Defender', limit=2)


def resolve_legacy_readonly_query(script: str, timeout: int = 18) -> Any:
    """Compatibility with existing UI collectors: fixed allowlisted Windows APIs.

    No supplied script is interpreted/executed or forwarded to a shell.
    Unknown requests return None and will be displayed as unavailable.
    """
    s = script.lower()
    if 'get-winipconfiguration' in s or 'get-netipconfiguration' in s:
        return collect_network_configuration()
    if 'get-netadapter' in s:
        return collect_adapters()
    if 'get-netneighbor' in s:
        return collect_neighbors()
    if 'get-winevent' in s and 'windowsupdateclient/operational' in s:
        return collect_update_events()
    if 'get-winevent' in s:
        count = re.search(r'-maxevents\s+(\d+)',s)
        return collect_events(min(int(count.group(1)),200) if count else 100)
    if 'microsoft.update.session' in s:
        return collect_updates()
    if 'get-mpcomputerstatus' in s:
        rows = get_defender()
        return rows[0] if rows else None
    if 'get-pnpdevice' in s:
        return query_pnp('status error' in s or '-status' in s,
                         '-class usb' in s)
    if 'get-physicaldisk' in s:
        return query_wmi('MSFT_PhysicalDisk',('DeviceId','FriendlyName','MediaType','BusType',
                         'SpindleSpeed','HealthStatus','Size'),
                         namespace=r'root\Microsoft\Windows\Storage')
    if re.search(r'\bget-disk\b',s):
        return query_wmi('MSFT_Disk',('Number','FriendlyName','BusType','Size'),
                         namespace=r'root\Microsoft\Windows\Storage')
    if 'get-hotfix' in s:
        return query_wmi('Win32_QuickFixEngineering',('HotFixID','InstalledOn','Description'),limit=15)
    if 'get-ciminstance' not in s:
        return None
    if 'librehardwaremonitor' in s:
        return query_wmi('Sensor', ('Name','SensorType','Value','Identifier','Parent'),
                         namespace=r'root\LibreHardwareMonitor', limit=1000)
    if 'securitycenter2' in s:
        rows = get_av()
        return rows
    mapping = {
        'win32_videocontroller': ('Win32_VideoController', ('Name','AdapterCompatibility','PNPDeviceID','DriverVersion',
                                'Status','ConfigManagerErrorCode','CurrentHorizontalResolution','CurrentVerticalResolution')),
        'win32_processor': ('Win32_Processor',('Name','Manufacturer','NumberOfCores','NumberOfLogicalProcessors',
                            'MaxClockSpeed','CurrentClockSpeed','SocketDesignation','L2CacheSize','L3CacheSize')),
        'win32_physicalmemoryarray': ('Win32_PhysicalMemoryArray',('MemoryDevices',)),
        'win32_physicalmemory': ('Win32_PhysicalMemory',('Manufacturer','PartNumber','Capacity','Speed',
                                 'ConfiguredClockSpeed','SMBIOSMemoryType','MemoryType','DeviceLocator','BankLabel')),
        'win32_diskdrive': ('Win32_DiskDrive',('Index','Model','Size','InterfaceType','MediaType','PNPDeviceID')),
        'win32_logicaldisk': ('Win32_LogicalDisk',('DeviceID','VolumeName','Size','FreeSpace','FileSystem','DriveType')),
        'win32_baseboard': ('Win32_BaseBoard',('Manufacturer','Product','Version')),
        'win32_bios': ('Win32_BIOS',('Manufacturer','SMBIOSBIOSVersion','ReleaseDate')),
        'win32_computersystem': ('Win32_ComputerSystem',('Manufacturer','Model')),
    }
    for needle, (classname, fields) in mapping.items():
        if re.search(r'\b'+re.escape(needle)+r'\b',s):
            where = None
            if needle == 'win32_logicaldisk':
                where = 'DriveType=2' if 'drivetype=2' in s else 'DriveType=3' if 'drivetype=3' in s else None
            return query_wmi(classname, fields, where=where)
    return None


def collect_update_events() -> list[dict] | None:
    """Query official WindowsUpdateClient log without launching a shell."""
    if platform.system() != 'Windows':
        return None
    try:
        import win32evtlog
        log = 'Microsoft-Windows-WindowsUpdateClient/Operational'
        query = '*[System[(EventID=17 or EventID=19 or EventID=20 or EventID=26 or EventID=43 or EventID=44) and TimeCreated[timediff(@SystemTime) <= 1200000]]]'
        handle = win32evtlog.EvtQuery(log, win32evtlog.EvtQueryReverseDirection, query)
        rows = []
        try:
            while len(rows) < 15:
                batch = win32evtlog.EvtNext(handle, min(15 - len(rows), 10), 0, 0)
                if not batch:
                    break
                for event in batch:
                    xml = win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml)
                    el = ET.fromstring(xml)
                    ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
                    e_id = el.find('e:System/e:EventID',ns)
                    time_el = el.find('e:System/e:TimeCreated',ns)
                    values = el.findall('e:EventData/e:Data',ns)
                    rows.append({'TimeCreated':time_el.attrib.get('SystemTime','') if time_el is not None else '',
                                 'Id': int(e_id.text or 0) if e_id is not None else 0,
                                 'Message':'; '.join((v.text or '')[:200] for v in values)})
        finally:
            win32evtlog.EvtClose(handle)
        return rows
    except Exception:
        return None
