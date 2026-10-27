"""Rule-based, explainable event-log interpretations; never assert a diagnosis from one log."""
from __future__ import annotations
import platform
from datetime import datetime
from typing import Any
from osreview.services.windows_inventory import native_windows_query, _list


RULES = [
    ('Microsoft-Windows-WHEA-Logger', {18}, 'crítico', 'Falha de hardware reportada pelo Windows',
     'O Windows recebeu indicação de erro de hardware. Pode envolver CPU, RAM, placa-mãe ou barramento.',
     'Verifique reincidência, temperatura, drivers e estabilidade. Se persistir, teste componentes separadamente.'),
    ('Microsoft-Windows-WHEA-Logger', {17, 19}, 'atenção', 'Erro de hardware corrigido',
     'Houve um erro de hardware que o sistema reportou como corrigido; recorrência pode afetar estabilidade.',
     'Observe frequência e hardware associado. Verifique drivers, BIOS e conexões antes de trocar peças.'),
    ('Microsoft-Windows-Kernel-Power', {41}, 'atenção', 'Reinicialização/desligamento inesperado',
     'O Windows iniciou após um desligamento que não foi concluído corretamente. Não aponta, sozinho, a causa.',
     'Investigue energia, aquecimento, travamentos e eventos anteriores no mesmo horário.'),
    ('EventLog', {6008}, 'atenção', 'Desligamento anterior inesperado',
     'O registro indica que a sessão anterior terminou sem desligamento normal.',
     'Compare a hora com falhas de drivers, energia ou travamentos.'),
    ('Disk', {7, 51, 153, 157}, 'atenção', 'Erro ou atraso de armazenamento',
     'O subsistema registrou problemas de leitura/escrita, comunicação ou disponibilidade de disco.',
     'Faça backup dos dados, verifique SMART com ferramenta confiável, cabos e conexões.'),
    ('storahci', {129}, 'atenção', 'Reinicialização do controlador de armazenamento',
     'O driver solicitou recuperação do dispositivo/controlador; pode provocar lentidão ou congelamentos.',
     'Confira drivers do controlador, cabos e integridade do SSD/HD. Não altere modo SATA sem planejamento.'),
    ('stornvme', {129}, 'atenção', 'Reinicialização de dispositivo NVMe',
     'Foi necessário recuperar a comunicação com a unidade NVMe.',
     'Faça backup e verifique firmware do SSD, temperatura e atualizações oficiais.'),
    ('Display', {4101}, 'atenção', 'Driver de vídeo reinicializado',
     'O Windows recuperou o driver gráfico após o sistema de vídeo deixar de responder.',
     'Verifique versão oficial do driver e estabilidade em aplicações gráficas; um evento isolado não prova defeito da GPU.'),
    ('Application Error', {1000}, 'atenção', 'Aplicativo encerrou com falha',
     'Um programa sofreu falha. A mensagem detalhada pode conter o executável e o módulo envolvidos.',
     'Atualize ou repare o programa afetado e confira sua compatibilidade.'),
    ('Service Control Manager', {7031, 7034, 7000, 7009, 7011}, 'atenção', 'Falha ou demora em serviço',
     'Um serviço do Windows ou de aplicativo parou, não iniciou ou demorou a responder.',
     'Verifique nome do serviço e recorrência; não desative serviços desconhecidos.'),
    ('Ntfs', {55}, 'crítico', 'Possível corrupção no sistema de arquivos',
     'O Windows identificou indícios de estrutura NTFS inconsistente.',
     'Faça backup dos dados e avalie a integridade da unidade antes de reparar o volume.'),
    ('Microsoft-Windows-DistributedCOM', {10016}, 'informativo', 'Permissão DCOM registrada',
     'Esse evento é frequente em sistemas saudáveis e, isoladamente, costuma não exigir correção.',
     'Evite modificar permissões DCOM apenas para eliminar esse evento.'),
]


def explain_event(source: str, event_id: int, message: str = '') -> dict[str, str]:
    source_low = str(source).lower()
    for provider, ids, level, title, meaning, action in RULES:
        if int(event_id) in ids and provider.lower() in source_low:
            return {'severity': level, 'title': title, 'meaning': meaning, 'action': action}
    if int(event_id) == 1001 and 'bugcheck' in (source_low + str(message).lower()):
        return {'severity': 'atenção', 'title': 'Falha grave do Windows (BugCheck)',
                'meaning': 'Foi registrado um erro associado à tela azul ou reinicialização após falha.',
                'action': 'Anote o código de parada, verifique drivers e examine o despejo de memória com ferramenta apropriada.'}
    return {'severity': 'informativo', 'title': 'Evento sem interpretação específica',
            'meaning': 'Este registro sozinho não permite determinar se há um defeito. O contexto e a recorrência importam.',
            'action': 'Correlacione horário, origem, mensagem e comportamento percebido no PC.'}


def normalize_events(raw: Any) -> list[dict[str, Any]]:
    records = []
    for item in _list(raw):
        if not isinstance(item, dict):
            continue
        try:
            eid = int(item.get('Id') or 0)
        except (TypeError, ValueError):
            continue
        provider = str(item.get('ProviderName') or 'Não informado')
        msg = str(item.get('Message') or '')[:1400]
        explanation = explain_event(provider, eid, msg)
        if explanation['severity'] == 'informativo' and item.get('Level') in (1, 2, '1', '2'):
            explanation['severity'] = 'crítico' if str(item['Level']) == '1' else 'erro'
            explanation['title'] = 'Erro registrado (causa não determinada)'
            explanation['meaning'] = 'O Windows classificou este registro como erro, mas não há uma interpretação local específica para sua origem.'
        records.append({'id': eid, 'provider': provider,
                        'log': str(item.get('LogName') or '?'), 'time': str(item.get('TimeCreated') or ''),
                        'message': msg, **explanation})
    return records


def collect_events(max_events: int = 120) -> dict[str, Any]:
    if platform.system() != 'Windows':
        return {'supported': False, 'events': [], 'error': 'Leitura de eventos disponível somente no Windows.'}
    count = min(max(int(max_events), 1), 200)
    # Logs System/Application, only Critical=1 and Error=2, up to 7 days.
    script = (
        "$from=(Get-Date).AddDays(-7); "
        "$base=Get-WinEvent -FilterHashtable @{LogName=@('System','Application');Level=@(1,2);StartTime=$from} "
        f"-MaxEvents {count} -ErrorAction SilentlyContinue; "
        "$base | Where-Object { $_ -ne $null } | Sort-Object TimeCreated -Descending | "
        f"Select-Object -First {count} "
        "@{N='TimeCreated';E={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}},LogName,ProviderName,Id,Level,Message | "
        "ConvertTo-Json -Depth 3 -Compress"
    )
    raw = native_windows_query(script, 25)
    return {'supported': True, 'events': normalize_events(raw),
            'error': None if raw is not None else 'Consulta indisponível. Verifique o serviço Log de Eventos do Windows e as permissões.',
            'collected_at': datetime.now().isoformat(timespec='seconds')}
