"""Interpret local sensor coverage conservatively; do not infer hardware damage."""
from __future__ import annotations


def triage(data: dict) -> dict:
    status = data.get('engine_status') or {}
    inventory = data.get('sensor_inventory') or {}
    from .sensor_analysis import is_real_temperature
    valid_temp = sum(is_real_temperature(sensor) for readings in (data.get('groups') or {}).values() for sensor in readings)
    missing = list(status.get('unavailable') or [])
    missing_temp = [x for x in missing if str(x.get('SensorType', '')).lower() == 'temperature']
    groups = data.get('groups') or {}
    zeros = [x for rows in groups.values() for x in rows
             if str(x.get('type', '')).lower() == 'power' and x.get('value') == 0]
    admin = data.get('windows_admin')
    hardware = status.get('hardware') or []
    devices = ', '.join(str(h.get('Hardware', '?')) for h in hardware[:6]) or 'Não informado'
    findings = []
    if not status.get('available'):
        findings.append('Ponte sem amostra atual: verifique integridade, mensagem de erro e log de inicialização.')
    elif valid_temp == 0 and missing_temp:
        findings.append('O coletor identificou sensores de temperatura, mas todos os enumerados ficaram sem valor. Isso indica falha de acesso/compatibilidade da leitura, não uma temperatura zero.')
    elif valid_temp == 0:
        findings.append('Nenhum sensor térmico válido foi fornecido. O equipamento pode não expor essa informação pelo coletor atual.')
    else:
        findings.append(f'{valid_temp} temperatura(s) físicas/zonas térmicas disponíveis. Limites NVMe e margens TjMax não representam temperatura atual.')
    if admin is False and missing_temp:
        findings.append('A coleta foi executada sem elevação. Alguns sensores requerem acesso de baixo nível; testar pontualmente com permissão administrativa pode ajudar, sem desativar proteções.')
    if zeros:
        findings.append(f'{len(zeros)} leitura(s) de potência indicaram 0 W; esses números não confirmam consumo real nulo e devem ser marcados como não confiáveis até validação.')
    if missing_temp:
        findings.append('Confira os registros de integridade de código e proteção do antivírus para identificar driver legítimo bloqueado. Não crie exclusões gerais nem desative Integridade da Memória.')
    findings.append('Se outra ferramenta mostrar temperaturas no mesmo PC, compare a origem/sensor; ela pode usar interface de hardware diferente.')
    return {
        'valid_temperatures': valid_temp,
        'missing_temperatures': len(missing_temp),
        'invalid_power_zero': len(zeros),
        'hardware_count': len(hardware),
        'devices': devices,
        'status': 'Temperaturas não fornecidas pelo coletor' if valid_temp == 0 else 'Há temperaturas disponíveis',
        'findings': findings,
    }
