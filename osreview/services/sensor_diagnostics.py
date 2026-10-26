"""User-triggered, locally generated diagnostics for unavailable sensors.

Contains no network transmissions; strips identifying local paths, email addresses,
IPv4/IPv6 and MAC addresses before writing a report. The report may still
contain hardware models/identifiers. User chooses where to save and share it.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import ipaddress
import os
from pathlib import Path
import platform
import re
from typing import Any

from .bridge_integrity import find_trusted_bridge
from .sensor_triage import triage
from .sensor_analysis import is_real_temperature, temperature_readings, temperature_thresholds, power_readings
from osreview import __version__


def redact(text: str) -> str:
    for root in (os.environ.get('USERPROFILE'), os.environ.get('HOME')):
        if root:
            text = re.sub(re.escape(root), '<PASTA_USUARIO>', text, flags=re.IGNORECASE)
    # Avoid spilling Windows account names from stack traces and program paths.
    text = re.sub(r'(?i)[A-Z]:\\Users\\[^\\\s\"\']+', r'<USUARIO_WINDOWS>', text)
    text = re.sub(r'(?i)/Users/[^/\s\"\']+', '<USUARIO_MAC>', text)
    text = re.sub(r'(?i)/home/[^/\s\"\']+', '<USUARIO_LINUX>', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '<EMAIL>', text)
    text = re.sub(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '<IPV4>', text)
    def mask_ipv6(m):
        value=m.group(0)
        try:
            ipaddress.IPv6Address(value.split('%')[0])
            return '<IPV6>'
        except ValueError:
            return value
    text=re.sub(r'(?<![A-Za-z0-9:])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:%]+', mask_ipv6, text)
    text = re.sub(r'\b(?:[A-Fa-f0-9]{2}[:-]){5}[A-Fa-f0-9]{2}\b', '<MAC>', text)
    return text


def advice(data: dict) -> list[str]:
    status = data.get('engine_status') or {}
    counts = data.get('sensor_inventory') or {}
    notes: list[str] = []
    if platform.system() == 'Windows' and data.get('windows_admin') is False:
        notes.append('Alguns sensores físicos exigem privilégios elevados. Confirme o fabricante e a assinatura dos drivers antes de autorizar qualquer elevação; não desative o antivírus.')
    if not status.get('available'):
        notes.append('Ponte não está entregando leituras atuais. Confira a integridade do executável, sua compilação e as mensagens de erro antes de alterar configurações de segurança.')
    elif not counts.get('thermal_count'):
        notes.append('A ponte entrega medições, mas nenhuma foi classificada como temperatura válida. Revise os sensores sem valor, os dispositivos e as mensagens do coletor.')
    else:
        notes.append('Existem sensores de temperatura válidos. Caso não apareçam na CPU/GPU, compare HardwareType, SensorType e identificador com as regras de classificação.')
    if not counts.get('types', {}).get('power'):
        notes.append('Nenhuma leitura de potência foi identificada. Potência total da fonte ATX não pode ser inferida de sensores de CPU/GPU isolados.')
    if status.get('missing_count',0):
        notes.append(f"Há {status['missing_count']} sensores enumerados que não forneceram valor; isso não comprova defeito físico.")
    if status.get('stderr'):
        notes.append('O coletor informou erros de execução; verifique os detalhes no relatório antes de intervir.')
    return notes


def build_report(data: dict) -> dict[str, Any]:
    """Consume existing snapshot; do not start hardware probes or require elevation."""
    status = data.get('engine_status') or {}
    groups = data.get('groups') or {}
    _, integrity = find_trusted_bridge()
    bridge_state = {k: integrity.get(k) for k in ('present','integrity','allowed','reason','sha256')}
    # Do not include the absolute executable path or PID: not needed for reporting.
    device_sensors = []
    for group, sensors in groups.items():
        for s in sensors:
            device_sensors.append({
                'group': group, 'device': s.get('device'), 'name': s.get('name'),
                'type': s.get('type'), 'hardware_type': s.get('hardware_type'),
                'value': s.get('value'), 'unit': s.get('unit'),
                'is_current_temperature':is_real_temperature(s) if str(s.get('type','')).casefold()=='temperature' else None,
                'identifier': s.get('identifier'), 'source': s.get('source')
            })
    grouped = Counter(r.get('group') for r in device_sensors)
    report = {
        'app': 'OSReview', 'version': __version__,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'environment': {
            'os': platform.system(), 'os_release': platform.release(),
            'architecture': platform.machine(), 'admin_windows': data.get('windows_admin')
        },
        'bridge_integrity': bridge_state,
        'motor': {k: status.get(k) for k in (
            'available','age_seconds','error','status','devices',
            'missing_count','exit_code','warnings','stderr','started_seconds_ago','automatic_retry_paused')},
        'inventory': data.get('sensor_inventory'),
        'sensors_by_group': dict(grouped),
        'hardware': status.get('hardware') or [],
        'no_value_sensors': status.get('unavailable') or [],
        'valid_sensors': device_sensors,
        'recommendations': advice(data),
        'technical_triage': triage(data),
        'validated_temperature_summary': {key:{'value_c':v.value,'sensor':v.name,'group':v.group} if v else None
            for key,v in temperature_readings(data).items()},
        'nvme_temperature_limits_c':temperature_thresholds(data),
        'power_domains_notice':'Potências CPU Package, CPU Platform, GPU e bateria não devem ser somadas como consumo total do computador.',
        'privacy_notice': 'Exportação local voluntária; verifique o conteúdo antes de compartilhar. Pode conter nomes e modelos de componentes.'
    }
    # Redact in serialized representation so even nested warnings are protected.
    return json.loads(redact(json.dumps(report, ensure_ascii=False, default=str)))


def write_report(data: dict, path: str | Path) -> Path:
    output = Path(path)
    if output.suffix.lower() != '.json':
        raise ValueError('O diagnóstico só pode ser salvo como JSON.')
    if not output.parent.is_dir():
        raise ValueError('Pasta de destino inexistente.')
    payload = build_report(data)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return output
