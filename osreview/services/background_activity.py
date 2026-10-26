"""Correlate background setup/update activity and resource pressure, read-only.

Processes are only INDICATORS. A recent event is EVIDENCE OF A TRANSITION,
not proof an installation remains active. No automatic service manipulation.
"""
from __future__ import annotations
import datetime as dt
import platform
import time
from typing import Any
import psutil
from .windows_inventory import native_windows_query, _list

# Normalize executable basenames. Do not infer installation from generic svchost.exe.
PROCESSES = {
    'tiworker.exe': ('Componentes do Windows / manutenção', 'atualização'),
    'trustedinstaller.exe': ('Instalador de módulos do Windows', 'atualização'),
    'mousocoreworker.exe': ('Windows Update Orchestrator', 'atualização'),
    'usoclient.exe': ('Cliente Windows Update', 'atualização'),
    'wuauclt.exe': ('Windows Update legado', 'atualização'),
    'dosvc.exe': ('Otimização de entrega', 'transferência'),
    'msiexec.exe': ('Windows Installer (MSI)', 'instalação'),
    'winget.exe': ('WinGet', 'instalação'),
    'appinstaller.exe': ('App Installer', 'instalação'),
    'choco.exe': ('Chocolatey', 'instalação'),
    'scoop.exe': ('Scoop', 'instalação'),
    'dism.exe': ('Manutenção de imagem Windows', 'manutenção'),
    'dismhost.exe': ('DISM Host', 'manutenção'),
    'setuphost.exe': ('Instalador / atualização do Windows', 'instalação'),
    'setup.exe': ('Instalador genérico (nome não é prova)', 'instalação'),
    'msmpeng.exe': ('Verificação do Microsoft Defender', 'antivírus'),
    'searchindexer.exe': ('Indexação do Windows Search', 'indexação'),
    'onedrive.exe': ('Sincronização OneDrive', 'sincronização'),
}

def _snapshot() -> dict[int, dict[str, Any]]:
    result = {}
    for p in psutil.process_iter(['pid','name','memory_info','cpu_times','io_counters']):
        try:
            x = p.info
            name = (x.get('name') or '').casefold()
            if name not in PROCESSES:
                continue
            cpu = x.get('cpu_times')
            io = x.get('io_counters')
            result[x['pid']] = {
                'pid':x['pid'], 'name': x['name'], 'cpu_time':(cpu.user+cpu.system) if cpu else None,
                'read':getattr(io,'read_bytes',None),'write':getattr(io,'write_bytes',None),
                'rss':getattr(x.get('memory_info'), 'rss', None),
            }
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            pass
    return result


def calculate_activity(first: dict, second: dict, seconds: float, cpu_count: int = 1) -> list[dict]:
    """Process CPU% normalized against ALL logical processors, not a single core."""
    rows = []
    seconds = max(seconds, .1)
    count = max(cpu_count,1)
    for pid, second_p in second.items():
        old = first.get(pid, {})
        key = (second_p.get('name') or '').casefold()
        description, category = PROCESSES.get(key, ('Processo','outro'))
        cpu_delta = None
        if old.get('cpu_time') is not None and second_p.get('cpu_time') is not None:
            cpu_delta = max(0,second_p['cpu_time']-old['cpu_time'])/seconds/count*100
        def mb_per_sec(field):
            a,b=old.get(field),second_p.get(field)
            return round(max(0,b-a)/seconds/1048576,2) if a is not None and b is not None else None
        rows.append({'pid':pid,'name':second_p.get('name'), 'description':description, 'category':category,
            'cpu_percent':round(cpu_delta,1) if cpu_delta is not None else None,
            'read_mb_s':mb_per_sec('read'), 'write_mb_s':mb_per_sec('write'),
            'ram_mb':round(second_p['rss']/1048576,1) if second_p.get('rss') is not None else None,
            'certainty':'Indício: processo em execução; NÃO confirma atualização ou instalação ativa'})
    return sorted(rows,key=lambda p: ((p['cpu_percent'] or 0),(p['read_mb_s'] or 0)+(p['write_mb_s'] or 0)),reverse=True)


def parse_update_events(raw: Any) -> list[dict]:
    rows = []
    for e in _list(raw):
        if not isinstance(e,dict):continue
        try:eid = int(e.get('Id'))
        except (ValueError,TypeError):continue
        meaning = {
            43:'Início de instalação relatado', 44:'Início de download relatado',
            19:'Instalação concluída', 20:'Falha de instalação',
            17:'Download concluído', 26:'Reinicialização solicitada',
        }.get(eid)
        if not meaning:continue
        rows.append({'id':eid,'time':str(e.get('TimeCreated') or ''), 'description':meaning,
             'message':str(e.get('Message') or '')[:240],
             'status':'início recente (não confirma atividade atual)' if eid in (43,44) else 'evento de conclusão/falha'})
    return rows


def interpret_background_activity(processes:list[dict], events:list[dict], disk_mbps:float|None, network_mbps:float|None,
                                  cpu_total:float|None=None) -> dict:
    active = [p for p in processes if (p.get('cpu_percent') or 0)>=1.0 or
              ((p.get('read_mb_s') or 0)+(p.get('write_mb_s') or 0))>=.5]
    update_processes = [p for p in active if p.get('category') in ('atualização','instalação')]
    # Events are returned newest-first. A later completion/failure removes the
    # evidence of a currently unfinished operation; events still remain visible.
    recent_ids = [e.get('id') for e in events]
    start_events = [e for e in events if e['id'] in (43,44)] if recent_ids and recent_ids[0] in (43,44) else []
    if update_processes and start_events:
        status='Possível atualização/instalação com atividade observada'
        confidence='moderada — correlação de processo ativo e evento recente; não confirma o mesmo pacote'
    elif active:
        status='Atividade de manutenção em segundo plano detectada'
        confidence='limitada — processo está consumindo recursos, mas pode não estar instalando nada'
    elif start_events:
        status='Eventos recentes de atualização, sem atividade relevante observada na amostra'
        confidence='limitada — o download ou a instalação podem já ter terminado'
    else:
        status='Sem indícios relevantes nesta amostra'
        confidence='limitada — tarefas transitórias podem escapar de uma única leitura'
    notes=[]
    if disk_mbps is not None and disk_mbps>=10 and active:
        notes.append('Há tráfego de leitura/gravação e processos de fundo ativos; verifique o uso de disco antes de atribuir a lentidão ao SSD/HD.')
    if network_mbps is not None and network_mbps>=5 and active:
        notes.append('Há tráfego de rede e atividade de fundo; compare download/upload por processo antes de culpar a conexão.')
    if cpu_total is not None and cpu_total>=75 and active:
        notes.append('Uso global da CPU elevado juntamente com tarefas em segundo plano: pode afetar a responsividade.')
    notes.append('Processos de atualização NÃO devem ser encerrados ou serviços desativados automaticamente.')
    return {'status':status,'confidence':confidence,'observed_active':len(active),
            'processes':processes,'events':events,'impact_notes':notes}


def collect_background_activity(sample_seconds:float=1.0) -> dict:
    if platform.system()!='Windows':
        return {'supported':False, 'status':'Diagnóstico de instaladores disponível no Windows',
                'processes':[], 'events':[], 'impact_notes':[],'confidence':'indisponível'}
    t0=time.monotonic();before=_snapshot();before_disk=psutil.disk_io_counters();before_net=psutil.net_io_counters()
    time.sleep(min(3.,max(.5,float(sample_seconds))))
    elapsed=max(.1,time.monotonic()-t0)
    after=_snapshot();after_disk=psutil.disk_io_counters();after_net=psutil.net_io_counters()
    procs=calculate_activity(before,after,elapsed,psutil.cpu_count() or 1)
    disk=None
    if before_disk and after_disk:
        disk=max(0,after_disk.read_bytes-before_disk.read_bytes+after_disk.write_bytes-before_disk.write_bytes)/elapsed/1048576
    net=None
    if before_net and after_net:
        net=max(0,after_net.bytes_recv-before_net.bytes_recv+after_net.bytes_sent-before_net.bytes_sent)/elapsed/1048576
    cmd = (
        "$from=(Get-Date).AddMinutes(-20); "
        "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-WindowsUpdateClient/Operational';StartTime=$from;Id=@(17,19,20,26,43,44)} "
        "-MaxEvents 15 -ErrorAction SilentlyContinue | "
        "Select-Object @{N='TimeCreated';E={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}},Id,Message | "
        "ConvertTo-Json -Compress -Depth 3")
    events=parse_update_events(native_windows_query(cmd,12))
    result=interpret_background_activity(procs,events,round(disk,2) if disk is not None else None,
        round(net,2) if net is not None else None,psutil.cpu_percent(interval=.2))
    result.update({'supported':True,'checked_at':dt.datetime.now().isoformat(timespec='seconds'),
                   'disk_mb_s':round(disk,2) if disk is not None else None,
                   'network_mb_s':round(net,2) if net is not None else None,
                   'recent_update_event_count':len(events)})
    return result
