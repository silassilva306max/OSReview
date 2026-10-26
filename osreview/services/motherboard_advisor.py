"""Board/BIOS inventory with fact-based official lookup links; never guesses CPU compatibility."""
from __future__ import annotations
from datetime import datetime
import platform
import urllib.parse
from .windows_inventory import native_windows_query, _list


def collect_board() -> dict:
    out = {'supported':platform.system() == 'Windows', 'manufacturer':None, 'model':None,
           'revision':None, 'chipset':None, 'bios_vendor':None, 'bios_version':None,
           'bios_date':None, 'socket':None, 'links':{}, 'note':''}
    if not out['supported']:
        out['note'] = 'Modelo/BIOS via CIM disponível apenas no Windows. Em macOS confira Ajustes > Geral > Sobre.'
        return out
    board = native_windows_query("Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version | ConvertTo-Json -Compress", 12)
    bios = native_windows_query("Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | ConvertTo-Json -Compress", 12)
    cpu = native_windows_query("Get-CimInstance Win32_Processor | Select-Object SocketDesignation | ConvertTo-Json -Compress", 12)
    system = native_windows_query("Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model | ConvertTo-Json -Compress", 12)
    board = _list(board)[0] if _list(board) else {}
    bios = _list(bios)[0] if _list(bios) else {}
    cpu = _list(cpu)[0] if _list(cpu) else {}
    system = _list(system)[0] if _list(system) else {}
    out.update({'manufacturer': board.get('Manufacturer') or system.get('Manufacturer'),
                'model':board.get('Product') or system.get('Model'), 'revision':board.get('Version'),
                'bios_vendor':bios.get('Manufacturer'), 'bios_version':bios.get('SMBIOSBIOSVersion'),
                'bios_date':str(bios.get('ReleaseDate'))[:19] if bios.get('ReleaseDate') else None,
                'socket':cpu.get('SocketDesignation')})
    # Chipset ID requires dedicated PCI topology enumeration and cross-referencing:
    # Win32_BaseBoard does not provide a reliable chipset field.
    manuf = out['manufacturer'] or ''
    model = out['model'] or ''
    if manuf and model:
        for label, suffix in [('support','official support drivers BIOS'), ('cpu','official CPU support list BIOS revision'),
                              ('memory','official memory QVL RAM'), ('pcie','official PCIe GPU compatibility')]:
            out['links'][label] = 'https://www.google.com/search?q=' + urllib.parse.quote_plus(f'{manuf} {model} {suffix}')
    out['note'] = ('Chipset: indisponível sem identificação confiável da controladora PCI. '
                   'Modelo OEM pode substituir modelo da placa. Verifique revisão física e BIOS antes de upgrades. '
                   'Links abrem pesquisas, NÃO listas oficialmente verificadas.')
    return out
