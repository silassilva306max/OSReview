"""Coverage report for trusted read-only diagnostics, never installs/drivers.

A missing sensor is not a failed diagnosis, but absence must be visible.
No silent downgrade: show provider, measured/available/unavailable and recovery.
"""
from __future__ import annotations

import platform
from datetime import datetime
from typing import Any

import psutil

from .bridge_integrity import find_trusted_bridge


def row(name: str, source: str, state: str, detail: str, action: str = '') -> dict[str, str]:
    return {'name': name, 'source': source, 'status': state, 'detail': detail, 'action': action}


def diagnose_collection(psutil_module=psutil, os_name: str | None = None) -> dict[str, Any]:
    system = os_name or platform.system()
    checks = []
    try:
        cpu = psutil_module.cpu_percent(interval=0.05)
        freq = psutil_module.cpu_freq()
        checks.append(row('CPU / frequência', 'psutil / APIs do SO', 'OK',
                          f'CPU: {cpu:.1f}%; frequência: {round(freq.current)} MHz' if freq else
                          f'CPU: {cpu:.1f}%; frequência indisponível'))
    except Exception as exc:
        checks.append(row('CPU / frequência', 'psutil', 'INDISPONÍVEL', type(exc).__name__))
    try:
        vm = psutil_module.virtual_memory()
        checks.append(row('Memória RAM', 'psutil', 'OK', f'{vm.percent:.1f}% utilizada'))
    except Exception as exc:
        checks.append(row('Memória RAM', 'psutil', 'INDISPONÍVEL', type(exc).__name__))
    try:
        counters = psutil_module.net_io_counters()
        checks.append(row('Rede: tráfego local', 'psutil', 'OK' if counters else 'INDISPONÍVEL',
                          'Contadores de envio/recebimento de bytes disponíveis' if counters else 'Sem contadores'))
    except Exception as exc:
        checks.append(row('Rede: tráfego local', 'psutil', 'INDISPONÍVEL', type(exc).__name__))

    if system == 'Windows':
        from .windows_native import available, query_wmi, collect_events
        if available():
            for title, cls, fields, namespace in [
                ('CPU e placa-mãe', 'Win32_Processor', ('Name','MaxClockSpeed'), r'root\cimv2'),
                ('Memória por módulo', 'Win32_PhysicalMemory', ('Capacity','Speed'), r'root\cimv2'),
                ('Placa de vídeo integrada/dedicada', 'Win32_VideoController', ('Name','DriverVersion'), r'root\cimv2'),
                ('Armazenamento físico', 'MSFT_PhysicalDisk', ('FriendlyName','MediaType','BusType'), r'root\Microsoft\Windows\Storage'),
                ('SMART: confiabilidade dos discos', 'MSFT_StorageReliabilityCounter',
                 ('DeviceId','Temperature','Wear','PowerOnHours'), r'root\Microsoft\Windows\Storage'),
            ]:
                values = query_wmi(cls, fields, namespace=namespace, limit=25)
                if values is None:
                    status, detail = 'INDISPONÍVEL', 'Consulta não respondeu; não equivale a ausência de hardware'
                elif not values:
                    status, detail = 'SEM DADOS', 'Controlador não retornou valores para este dispositivo'
                else:
                    status, detail = 'OK', f'{len(values)} registro(s) retornado(s) via WMI'
                checks.append(row(title, 'Windows WMI/COM', status, detail,
                                  'Verifique os drivers ou permissões de leitura se ficar indisponível.'))
            events = collect_events(max_events=3, days=7)
            checks.append(row('Erros e eventos críticos', 'Windows Event Log API',
                              'OK' if events is not None else 'INDISPONÍVEL',
                              f'{len(events)} evento(s) recentes retornado(s)' if events is not None else
                              'Acesso ao log não disponível'))
        else:
            checks.append(row('Inventário WMI/COM', 'pywin32 / Windows', 'INDISPONÍVEL',
                              'pywin32 ou serviço WMI indisponível; coleta básica continua',
                              'Instale as dependências oficiais e verifique o serviço WMI.'))
        path, status = find_trusted_bridge()
        checks.append(row('Ponte térmica avançada', 'LibreHardwareMonitorLib 0.9.6',
                          'PRONTA' if path else 'INDISPONÍVEL', status['reason'],
                          'Não permita exceções gerais de antivírus. Use distribuição íntegra e assinada.'))
    elif system == 'Darwin':
        checks.append(row('Sensores de bateria', 'IOKit / sistema macOS', 'SUPORTE PARCIAL',
                          'Capacidade, corrente, tensão disponíveis somente se o hardware permitir'))
        checks.append(row('Temperaturas internas', 'macOS / psutil', 'SUPORTE PARCIAL',
                          'APIs públicas de sensores não cobrem todos os modelos Apple'))
    else:
        checks.append(row('Sensores térmicos', 'psutil / sistema', 'SUPORTE PARCIAL',
                          'Cobertura depende do kernel, drivers e permissões'))
    ok = sum(c['status'] in ('OK','PRONTA') for c in checks)
    return {'date': datetime.now().isoformat(timespec='seconds'), 'os': system,
            'checks': checks, 'ok': ok, 'total': len(checks),
            'notice': 'Auditoria de disponibilidade e integridade; não é certificação antivírus nem prova da ausência de malware.'}
