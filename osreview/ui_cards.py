"""Scrollable human-readable hardware/network specification cards, Tkinter only."""
from __future__ import annotations
import tkinter as tk
import math
from tkinter import ttk
from typing import Any
from osreview import app as base


def fmt(value, unit: str = '') -> str:
    if value is None or value == '': return 'Indisponível'
    if isinstance(value,bool): return 'Sim' if value else 'Não'
    if isinstance(value,(list,tuple)):return ', '.join(fmt(v) for v in value) or 'Indisponível'
    return f'{value}{unit}'


class SpecCards(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent,bg=base.BG)
        self.canvas=tk.Canvas(self,bg=base.BG,highlightthickness=0,bd=0)
        self.vbar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.vbar.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        self.body=tk.Frame(self.canvas,bg=base.BG)
        self.window=self.canvas.create_window((0,0),window=self.body,anchor='nw')
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.body.bind('<Configure>',lambda _e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.window,width=e.width))
        # The application routes wheel events from nested card labels to this canvas.
        self.current=[]
        self._pending_scroll=None

    def render(self, cards:list[dict]):
        previous = self.canvas.yview()[0] if self.canvas.winfo_exists() else 0.0
        self.current=cards
        if self._pending_scroll is not None:
            try:self.after_cancel(self._pending_scroll)
            except tk.TclError:pass
            self._pending_scroll=None
        for w in self.body.winfo_children():w.destroy()
        for card in cards:
            panel=tk.Frame(self.body,bg=base.PANEL,highlightbackground=base.EDGE,highlightthickness=1)
            panel.pack(fill='x',padx=7,pady=6)
            tk.Label(panel,text=card.get('title','COMPONENTE'),bg=base.PANEL,fg=base.WHITE,
                anchor='w',font=(base.FONT,12,'bold')).pack(fill='x',padx=16,pady=(12,5))
            if card.get('hint'):
                tk.Label(panel,text=card['hint'],bg=base.PANEL,fg=base.MUTED,anchor='w',
                    wraplength=860,justify='left',font=(base.FONT,9)).pack(fill='x',padx=16,pady=(0,5))
            for label,value in card.get('rows',[]):
                row=tk.Frame(panel,bg=base.PANEL);row.pack(fill='x',padx=16,pady=2)
                tk.Label(row,text=label,bg=base.PANEL,fg=base.MUTED,anchor='w',
                    width=25,font=(base.FONT,10)).pack(side='left')
                tk.Label(row,text=fmt(value),bg=base.PANEL,fg=base.WHITE,anchor='w',
                    wraplength=780,justify='left',font=(base.FONT,10,'bold')).pack(side='left',fill='x',expand=True)
            tk.Frame(panel,bg=base.PANEL,height=9).pack()
        # Redraw can change scrollregion asynchronously. Restore after layout,
        # never jump to the beginning during background updates.
        def restore():
            self._pending_scroll=None
            if self.canvas.winfo_exists():self.canvas.yview_moveto(previous)
        self._pending_scroll=self.after_idle(restore)


def hardware_cards(data:dict) -> list[dict]:
    cards=[]
    for i,c in enumerate(data.get('cpus') or []):
        cards.append({'title':f'PROCESSADOR {i+1} — {fmt(c.get("name"))}',
            'rows': [('Fabricante',c.get('manufacturer')),('Núcleos físicos',c.get('cores')),
            ('Processadores lógicos',c.get('threads')),('Frequência informada',fmt(c.get('reported_mhz'),' MHz')),
            ('Frequência máxima declarada',fmt(c.get('max_mhz'),' MHz')),('Soquete',c.get('socket')),
            ('Cache L2',fmt(c.get('l2_kb'),' KB')),('Cache L3',fmt(c.get('l3_kb'),' KB'))]})
    cards.append({'title':'MEMÓRIA RAM — INSTALADA', 'rows':[
        ('Total físico',fmt(data.get('ram_total_gb'),' GB')),
        ('Slots informados pelo BIOS',data.get('ram_slots_reported'))]})
    for i,m in enumerate(data.get('ram_sticks') or []):
        cards.append({'title':f'MÓDULO DE MEMÓRIA {i+1}', 'rows':[
            ('Fabricante',m.get('manufacturer')),('Modelo / Part number',m.get('model')),
            ('Capacidade',fmt(m.get('capacity_gb'),' GB')),('Tecnologia',m.get('technology')),
            ('Frequência nominal',fmt(m.get('speed_mhz'),' MHz')),
            ('Frequência configurada',fmt(m.get('configured_mhz'),' MHz')),
            ('Slot',m.get('slot')),('Banco',m.get('bank'))]})
    for i,d in enumerate(data.get('disks') or []):
        cards.append({'title':f'ARMAZENAMENTO FÍSICO {i+1} — {fmt(d.get("model"))}',
            'rows':[('Número',d.get('number')),('Tecnologia',d.get('technology')),
            ('Capacidade',fmt(d.get('size_gb'),' GB')),('Barramento',d.get('bus')),
            ('Mídia',d.get('media')),('RPM',d.get('rpm') if d.get('rpm') else 'Não informado / não aplicável'),
            ('Saúde reportada',d.get('health')),('Removível',d.get('removable'))]})
    for i,d in enumerate(data.get('volumes') or []):
        cards.append({'title':f'VOLUME {fmt(d.get("letter"))}', 'rows':[
            ('Nome',d.get('name') or 'Sem rótulo'),('Sistema de arquivos',d.get('fs')),
            ('Capacidade',fmt(d.get('size_gb'),' GB')),('Livre',fmt(d.get('free_gb'),' GB'))]})
    for i,d in enumerate(data.get('removable') or []):
        cards.append({'title':f'UNIDADE REMOVÍVEL {i+1}', 'rows':[
            ('Letra',d.get('letter')),('Nome',d.get('name')),('Capacidade',fmt(d.get('size_gb'),' GB'))]})
    for i,d in enumerate(data.get('usb_devices') or []):
        cards.append({'title':f'USB {i+1} — {fmt(d.get("name"))}','rows':[('Estado',d.get('status'))]})
    if not cards: cards=[{'title':'Inventário indisponível','rows':[('Situação','Windows: confira WMI, CIM e permissões')]}]
    if data.get('warnings'):cards.append({'title':'AVISOS SOBRE OS DADOS','rows':[('Observação',x) for x in data['warnings']]})
    return cards


def board_cards(data:dict) -> list[dict]:
    return [{'title':'PLACA-MÃE E CHIPSET','rows':[
            ('Fabricante',data.get('manufacturer')),('Modelo',data.get('model')),
            ('Revisão',data.get('revision')),('Chipset',data.get('chipset')),
            ('Soquete informado',data.get('socket'))],
            'hint':'A compatibilidade com CPUs e RAM deve ser conferida na lista oficial do fabricante para esta revisão.'},
            {'title':'BIOS / UEFI', 'rows':[
            ('Fabricante',data.get('bios_vendor')),('Versão instalada',data.get('bios_version')),
            ('Data',data.get('bios_date')),('Orientação',data.get('note'))]}]


def power_cards(data:dict) -> list[dict]:
    from .services.sensor_analysis import temperature_readings, power_readings, temperature_thresholds, is_real_temperature
    temps=temperature_readings(data)
    energy=power_readings(data)
    limits=temperature_thresholds(data)
    def read(r,unit):return r.display(unit) if r else 'Indisponível'
    cards=[{'title':'MONITORAMENTO ENERGÉTICO',
        'rows':[('Sensores disponíveis',data.get('sensor_count',0)),
                ('Biblioteca acessível','Sim' if data.get('lhm_connected') else 'Não'),
                ('CPU Package — medição',read(energy['cpu_package'],'W')),
                ('CPU Platform — domínio separado',read(energy['cpu_platform'],'W')),
                ('GPU — medição',read(energy['gpu'],'W')),
                ('Fonte — watts totais',read(energy['psu_total'],'W')),
                ('Aviso',data.get('note'))],
        'hint':'Potências de CPU Package, Platform e GPU podem incluir domínios sobrepostos. Não somar para obter consumo total da fonte.'},
        {'title':'TEMPERATURAS ATUAIS · LEITURAS CONFIRMADAS',
         'rows':[(f'{key} — sensor atual',read(temps[key],'°C')+' · '+(temps[key].provenance() if temps[key] else 'Sem sensor'))
                 for key in ('CPU','GPU','Disco','Geral')]+
                [('SSD — limite de alerta',f"{limits['warning']:.0f} °C • REFERÊNCIA, não é temperatura atual" if 'warning' in limits else 'Indisponível'),
                 ('SSD — limite crítico',f"{limits['critical']:.0f} °C • REFERÊNCIA, não é temperatura atual" if 'critical' in limits else 'Indisponível')],
         'hint':'Maior temperatura pode coincidir com CPU, disco ou GPU porque destaca o sensor real mais quente. Limites NVMe e Distância para TjMax são excluídos.'}]
    status = data.get('engine_status') or {}
    inventory = data.get('sensor_inventory') or {}
    count = inventory.get('thermal_count', 0)
    sensor_types = inventory.get('types') or {}
    cards.insert(1, {'title':'COBERTURA TÉRMICA REAL',
        'rows':[('Total de sensores lidos',data.get('sensor_count',0)),
                ('Permissão no Windows',('Elevada' if data['windows_admin'] else 'Padrão (alguns sensores de baixo nível podem não responder)') if data.get('windows_admin') is not None else 'Não verificada / outro sistema'),
                ('Sensores térmicos disponíveis',count),
                ('Tipos detectados',', '.join(f'{key}: {val}' for key,val in sorted(sensor_types.items())) or 'Nenhum'),
                ('Interpretação',('Temperaturas válidas listadas abaixo.' if count else
                    'Há telemetria, mas nenhuma temperatura física foi exposta. Possíveis restrições de permissões, driver bloqueado ou sensores não suportados.'))],
        'hint':'Uso de CPU, frequências e potência não substituem medição de temperatura. A zona ACPI do Windows, quando existente, não é necessariamente o sensor da CPU.'})
    cards.insert(2, {'title':'SENSORES SEM CATEGORIA • INSPEÇÃO',
        'rows':[(r.get('name','Sensor'),f"{r.get('value')} {r.get('unit','')} | Dispositivo: {r.get('device') or 'desconhecido'} | Tipo HW: {r.get('hardware_type') or 'não informado'}")
                for r in (data.get('groups') or {}).get('Outros', [])[:80]] or [('Situação','Nenhum sensor sem categoria')],
        'hint':'Exibe leituras válidas que ainda não correspondem a uma classe de hardware conhecida, sem omiti-las.'})
    absent = status.get('unavailable') or []
    if absent:
        cards.append({'title':'SENSORES ENUMERADOS SEM LEITURA',
            'rows':[(str(x.get('Hardware') or 'Dispositivo')+' · '+str(x.get('Sensor') or 'Sensor'),
                     str(x.get('SensorType') or '?')+' — '+str(x.get('Reason') or 'valor indisponível'))
                    for x in absent[:30]],
            'hint':'A biblioteca enumerou estes sensores mas não forneceu um valor. O relatório exportado contém a lista completa disponível (até 240 itens). Esta condição não demonstra defeito físico.'})
    cards.insert(1, {'title':'DIAGNÓSTICO DO MOTOR DE SENSORES',
              'rows':[('Situação','Recebendo dados' if status.get('available') else 'Sem leituras'),
                      ('Detalhe',status.get('error') or 'Motor operacional'),
                      ('Dispositivos enumerados',status.get('devices')),
                      ('Última leitura',str(status.get('age_seconds'))+' s' if status.get('age_seconds') is not None else 'Ainda não recebida'),
                      ('Avisos','; '.join(status.get('warnings') or []) or 'Nenhum'),
                      ('Sensores sem valor',status.get('missing_count', 0)),
                      ('Dispositivos na biblioteca',len(status.get('hardware') or [])),
                      ('Última mensagem',status.get('status') or 'Indisponível'),
                      ('Falhas do processo','; '.join((status.get('stderr') or [])[-3:]) or 'Nenhuma')],
              'hint':'Fonte local LibreHardwareMonitorLib. Se nenhum sensor chegar, verifique o diagnóstico abaixo e o motor da instalação.'})
    mac = data.get('mac_electrical') or {}
    battery_elec = mac.get('battery_electrical')
    if battery_elec:
        cards.append({'title':'BATERIA MAC — MEDIÇÃO ELÉTRICA',
                     'rows':[('Tensão da bateria',fmt(battery_elec.get('voltage_v'),' V')),
                             ('Corrente instantânea',fmt(battery_elec.get('current_a'),' A')),
                             ('Potência da bateria',fmt(battery_elec.get('power_w'),' W'))],
                     'hint':battery_elec.get('scope','')})
    elif mac:
        cards.append({'title':'BATERIA MAC',
                      'rows':[('Medição elétrica','Indisponível (IOKit não expôs sensor)')],
                      'hint':mac.get('note','')})
    for label, sensors in (data.get('groups') or {}).items():
        if sensors:
            cards.append({'title':label.upper(), 'rows':[
                (str(s.get('name') or s.get('type')),
                 fmt(s.get('value'),(' '+str(s.get('unit') or ''))) +
                 ('  •  LIMITE/REFERÊNCIA, não medição atual' if
                  (str(s.get('type','')).casefold()=='temperature' and not is_real_temperature(s)) else '') +
                 (f"  |  mín {s['min']} / máx {s['max']}" if s.get('min') is not None and s.get('max') is not None else ''))
                for s in sensors]})
        else:
            cards.append({'title':label.upper(), 'rows':[('Medição','Indisponível (sensor não exposto)')]})
    cards.append({'title':'ALTERNATIVA DE CONSULTA (TERCEIROS)',
                  'rows':[('Projeto','Open Hardware Monitor — projeto original'),
                          ('Integração','WMI local, somente leitura, quando um coletor já está ativo'),
                          ('Repositório','https://github.com/openhardwaremonitor/openhardwaremonitor'),
                          ('Autoria','Open Hardware Monitor e contribuidores')],
                  'hint':'Não instala nem abre programas externos automaticamente. Bibliotecas e direitos pertencem a seus autores.'})
    cards.append({'title':'CRÉDITOS DO MOTOR DE SENSORES (TERCEIROS)',
                  'rows':[('Biblioteca','LibreHardwareMonitorLib 0.9.6'),
                          ('Desenvolvimento','LibreHardwareMonitor e contribuidores'),
                          ('Licença','Mozilla Public License 2.0 (MPL-2.0)'),
                          ('Projeto oficial','https://github.com/LibreHardwareMonitor/LibreHardwareMonitor'),
                          ('Relação com OSReview','Biblioteca de terceiros; OSReview é independente')],
                  'hint':'O código e os direitos da biblioteca pertencem ao projeto original; créditos e licença estão incluídos no pacote.'})
    return cards


def network_cards(data: dict, connectivity: dict | None = None,
                  dns_comparison: dict | None = None, isp: dict | None = None) -> list[dict]:
    from osreview.services.network_diagnostics import DNS_PROVIDERS, adapter_findings, analyze_network
    cards=[]
    overview=analyze_network(data.get('interfaces',[]),data.get('dns',{}),data.get('gateways',{}),connectivity)
    warnings=(overview.get('issues') or [])+(overview.get('adapter_warnings') or [])
    cards.append({'title':'SITUAÇÃO DA REDE',
                  'hint':'O estado local, o DNS e a conexão à Internet são avaliados separadamente.',
                  'rows':[('Situação',overview.get('status')),
                          ('Indícios encontrados',len(warnings)),
                          ('Validação externa','Executada' if connectivity else 'Não executada'),
                          ('Orientação', 'Verifique alertas dos adaptadores abaixo; não altere DNS antes de corrigir IP/DHCP.'
                           if warnings else 'Execute os testes de conexão e DNS para validar o acesso externo.') ]})
    if isp:
        if isp.get('ok'):
            cards.append({'title':'IP PÚBLICO / OPERADORA IDENTIFICADA',
                'rows':[('IP externo',isp.get('ip')),('Organização / rede anunciadora',isp.get('organization')),
                        ('ASN',isp.get('asn')),('Serviço de consulta',isp.get('source'))],
                'hint':isp.get('disclaimer')})
        else:
            cards.append({'title':'IDENTIFICAÇÃO DA OPERADORA NÃO CONCLUÍDA',
                'rows':[('Erro da consulta',isp.get('error')),('Fonte',isp.get('source'))],
                'hint':'Falha neste serviço de identificação não prova defeito na Internet.'})
    if warnings:
        cards.append({'title':'ALERTAS E PRÓXIMOS PASSOS',
                      'rows':[(f'Observação {i+1}',txt) for i,txt in enumerate(warnings[:12])],
                      'hint':'Um Wi-Fi desconectado pode coexistir com Ethernet funcionando. Um endereço APIPA aponta problema no DHCP daquela interface.'})
    for nic in data.get('interfaces') or []:
        name=nic.get('name') or 'Não identificado'
        issue=adapter_findings(nic,data.get('dns'),data.get('gateways'))
        ipv4=[str(x.get('ip')) for x in (nic.get('ipv4') or [])]
        cards.append({'title':f'ADAPTADOR DE REDE — {name}',
                      'hint':issue.get('description'),
                      'rows':[
                          ('Estado físico','Conectado' if nic.get('up') else 'Desconectado'),
                          ('Endereço IPv4',fmt(ipv4)),('Endereço IPv6',fmt(nic.get('ipv6'))),
                          ('Endereço MAC',nic.get('mac')),
                          ('Link negociado',fmt(nic.get('speed_mbps'),' Mbps')),
                          ('Gateway IPv4',fmt(data.get('gateways',{}).get(name))),
                          ('DNS do adaptador',fmt(data.get('dns',{}).get(name))),
                          ('Erros recebidos',nic.get('errors_in')),
                          ('Erros enviados',nic.get('errors_out'))]})
    if connectivity:
        tests=[('Resposta ICMP do gateway',connectivity.get('gateway')),
               ('Latência do gateway',fmt(connectivity.get('gateway_rtt_ms'),' ms')),
               ('Resolução de nomes (DNS)',connectivity.get('dns')),
               ('Tempo para resolver DNS',fmt(connectivity.get('dns_resolution_ms'),' ms')),
               ('Acesso HTTPS (TCP 443)',connectivity.get('internet')),
               ('Tempo de conexão TCP',fmt(connectivity.get('tcp_443_ms'),' ms')),
               ('Servidor de teste',connectivity.get('test_host'))]
        cards.append({'title':'TESTES DE CONECTIVIDADE',
                      'rows':tests,
                      'hint':'DNS resolve nomes; TCP 443 verifica alcance. Um gateway pode ignorar ping sem estar defeituoso.'})
    provider_rows=[]
    lookup={x.get('name'):x for x in (dns_comparison or {}).get('providers',[])}
    for provider in DNS_PROVIDERS:
        test=lookup.get(provider['name'])
        timing=(f"{test['median_ms']:.1f} ms (UDP DNS)" if test and test.get('ok') else
                'Sem resposta / bloqueado' if test else 'Não medido')
        provider_rows.append((provider['name'],f"{provider['primary']} / {provider['secondary']}  •  {provider['feature']}  •  {timing}"))
    cards.append({'title':'SERVIDORES DNS RECOMENDADOS', 'rows':provider_rows,
                  'hint':'Latência menor no teste não garante o melhor DNS em toda situação. Para domínio interno, VPN e Active Directory, preserve o DNS da organização.'})
    if dns_comparison:
        fastest=dns_comparison.get('fastest')
        cards.append({'title':'RESULTADO DA COMPARAÇÃO DE DNS',
                      'rows':[('Menor latência observada',fastest or 'Nenhuma resposta válida'),
                              ('Leitura',dns_comparison.get('note'))],
                      'hint':'Comparação iniciada manualmente; nenhum DNS foi alterado.'})
    return cards


def activity_cards(result:dict) -> list[dict]:
    if not result.get('supported'):
        return [{'title':'ATIVIDADE DE FUNDO','rows':[('Estado',result.get('status','Somente Windows'))]}]
    cards=[{'title':'DIAGNÓSTICO DE INSTALAÇÕES E ATUALIZAÇÕES',
        'rows':[('Situação',result.get('status')),('Grau de confirmação',result.get('confidence')),
                ('Disco — leitura/gravação',fmt(result.get('disk_mb_s'),' MB/s')),
                ('Rede — tráfego total',fmt(result.get('network_mb_s'),' MB/s')),
                ('Leitura em',result.get('checked_at'))],
        'hint':'Aumento de uso durante instalações pode ser normal. Compare amostras antes de concluir que há problema.'}]
    for i,p in enumerate(result.get('processes',[])[:30]):
        cards.append({'title':f'PROCESSO {i+1} — {p.get("name")}', 'rows':[
            ('Atividade provável',p.get('description')),('PID',p.get('pid')),
            ('CPU (todos os núcleos)',fmt(p.get('cpu_percent'),' %')),
            ('RAM',fmt(p.get('ram_mb'),' MB')),
            ('Leitura',fmt(p.get('read_mb_s'),' MB/s')),
            ('Gravação',fmt(p.get('write_mb_s'),' MB/s')),
            ('Confiança',p.get('certainty'))]})
    if result.get('events'):
        cards.append({'title':'EVENTOS DE ATUALIZAÇÃO NAS ÚLTIMAS 20 MINUTOS',
                      'rows':[(f"Evento {x['id']} — {x['time']}",x['description']) for x in result['events']]})
    for message in result.get('impact_notes',[]):
        cards.append({'title':'ORIENTAÇÃO DE DIAGNÓSTICO','rows':[('Interpretação',message)]})
    return cards

class SpeedGauge(tk.Frame):
    """Semicircular meter fed only by the voluntary network test."""
    def __init__(self,parent,label:str,color:str):
        super().__init__(parent,bg=base.PANEL)
        self.label=label;self.color=color;self.current=None;self.fraction=0.;self.stage='Aguardando teste'
        self.scale=100.;self.needle=0.;self._animation=None
        self.canvas=tk.Canvas(self,width=250,height=205,bg=base.PANEL,bd=0,highlightthickness=0)
        self.canvas.pack(fill='x',expand=True,padx=7,pady=(4,2))
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.draw()

    def update_value(self,mbps:float,progress:float,state:str):
        self.current=max(0.,float(mbps)) if mbps is not None else None;self.fraction=max(0.,min(1.,float(progress)))
        self.stage=state
        for limit in (100,250,500,1000,2500,5000,10000):
            if self.current is not None and self.current>self.scale and self.current<=limit:
                self.scale=float(limit);break
        if self.current is not None and self.current>self.scale:
            self.scale=float(math.ceil(self.current/1000)*1000)
        target=min((self.current or 0.)/self.scale,1.)
        if self._animation is not None:
            self.after_cancel(self._animation)
        def step():
            self.needle+=0.34*(target-self.needle)
            self.draw()
            if abs(target-self.needle)>0.004:
                self._animation=self.after(25,step)
            else:
                self.needle=target;self._animation=None;self.draw()
        step()

    def draw(self):
        c=self.canvas;c.delete('all')
        w=max(190,c.winfo_width());cx=w/2;cy=91;r=64
        box=(cx-r,cy-r,cx+r,cy+r)
        c.create_arc(*box,start=210,extent=-240,style='arc',outline=base.EDGE,width=12)
        if self.needle>0:
            c.create_arc(*box,start=210,extent=-240*self.needle,style='arc',outline=self.color,width=12)
        for i in range(11):
            angle=math.radians(210-24*i)
            inner=47 if i%2==0 else 51
            x1=cx+inner*math.cos(angle);y1=cy-inner*math.sin(angle)
            x2=cx+56*math.cos(angle);y2=cy-56*math.sin(angle)
            c.create_line(x1,y1,x2,y2,fill=base.MUTED,width=2 if i%2==0 else 1)
        angle=math.radians(210-240*self.needle)
        c.create_line(cx,cy,cx+42*math.cos(angle),cy-42*math.sin(angle),
                      fill=self.color,width=3,capstyle='round')
        c.create_oval(cx-5,cy-5,cx+5,cy+5,fill=self.color,outline='')
        c.create_text(cx,17,text=self.label,fill=base.MUTED,font=(base.FONT,10,'bold'))
        c.create_text(cx,144,text=f'{self.current:,.1f} Mbps' if self.current is not None else '— Mbps',
                      fill=base.WHITE,font=(base.FONT,19,'bold'))
        c.create_text(cx,165,text=f'Escala 0–{self.scale:g} Mbps',fill=base.MUTED,font=(base.FONT,9))
        c.create_text(cx,185,text=self.stage[:46],fill=base.MUTED,font=(base.FONT,9))
        c.create_rectangle(12,198,w-12,202,fill=base.EDGE,outline='')
        if self.fraction:
            c.create_rectangle(12,198,12+(w-24)*self.fraction,202,fill=self.color,outline='')


def local_devices_cards(data: dict) -> list[dict]:
    """User-friendly scanner view, without raw JSON or invented device identity."""
    if not data:
        return [{'title':'DISPOSITIVOS DA REDE','rows':[('Situação','Nenhuma descoberta foi executada ainda.')]}]
    devices=data.get('devices') or []
    cards=[{'title':'RESUMO DA VARREDURA LOCAL',
        'rows':[('Adaptador',data.get('interface')),('Sub-rede',data.get('subnet')),
                ('Endereços consultados',data.get('tested')),
                ('Registros encontrados',len(devices)),
                ('Nomes identificados',sum(bool(d.get('hostname')) for d in devices))],
        'hint':'O programa só verifica a rede local autorizada; dispositivos que bloqueiam ping podem não aparecer.'}]
    for i,device in enumerate(devices):
        state=('Este computador' if device.get('is_local') else
               'Respondeu ao ping' if device.get('responds') else
               'Encontrado apenas no cache ARP (presença atual não confirmada)')
        cards.append({'title':f"DISPOSITIVO {i+1} — {device.get('hostname') or device.get('ip','Endereço desconhecido')}",
                      'rows':[('Situação',state),('Nome do computador',device.get('hostname') or 'Não identificado'),
                              ('Origem do nome',device.get('hostname_source') or 'Não identificado'),
                              ('IP',device.get('ip')),
                              ('MAC',device.get('mac')),
                              ('Latência',fmt(device.get('rtt_ms'),' ms')),
                              ('Cache de vizinhos',device.get('neighbor_state'))]})
    if not devices:
        cards.append({'title':'NENHUMA RESPOSTA IDENTIFICADA',
                      'rows':[('Interpretação','Nenhum dos endereços consultados respondeu à técnica de descoberta.')],
                      'hint':'Isso não prova que a sub-rede está vazia. Wi-Fi com isolamento, antivírus e firewall podem impedir respostas.'})
    return cards
