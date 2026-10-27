"""OSReview 0.6 — painéis legíveis, velocidade visual e tarefas em segundo plano.

All Tk operations stay on the main UI thread. Potentially slow diagnostics
run in background threads. Internet traffic and scans require a click.
"""
from __future__ import annotations

import json
from collections import deque
import os
import platform
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from typing import Any

from osreview import __version__
from osreview import app as base
from osreview.services.hardware_deep import collect_hardware_deep
from osreview.services.network_diagnostics import (
    collect_network, test_connectivity, discover_local_hosts, run_speedtest, compare_public_dns)
from osreview.services.energy_sensors import collect_energy_sensors, psu_budget
from osreview.services.sensor_diagnostics import write_report
from osreview.services.support_bundle import export_support_zip
from osreview.services.startup_logging import LOG, log_tk_error
from osreview.energy_meter import SensorMeter, representative_temperatures
from osreview.sensor_explorer import SensorExplorer
from osreview.services.sensor_triage import triage
from osreview.services.sensor_analysis import (temperature_readings, power_readings, clock_readings,
    sensor_overview, temperature_thresholds, timestamp_of)
from osreview.services.diagnostics import Finding
from osreview.services.motherboard_advisor import collect_board
from osreview.services.gemini_questions import ask_gemini
from osreview.services.fps_live import fps_session, bundled_presentmon_path, verify_presentmon
from osreview.services.fps_targets import graphical_processes, desktop_refresh_hz
from osreview.services.isp_lookup import fetch_isp
from osreview.services.background_activity import collect_background_activity
from osreview.services.collection_integrity import diagnose_collection
from osreview.ui_cards import (SpecCards, SpeedGauge, hardware_cards, board_cards, network_cards, power_cards, activity_cards, local_devices_cards)
from osreview.ui_theme import THEMES, palette

THEME_KEYS = tuple(palette('dark', 'graphite'))


def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def clean_summary(data: dict, keys: tuple[str, ...]) -> str:
    return '\n'.join(f'{key}: {data.get(key) if data.get(key) is not None else "Indisponível"}' for key in keys)


class OSReviewAppV5(base.OSReviewApp):
    def __init__(self):
        self.hardware_detail = None
        self.board_detail = None
        self.net_detail = None
        self.connection_detail = None
        self.dns_comparison = None
        self.speed_result = None
        self.isp_detail = None
        self.power_detail = None
        self._sensor_detail_frozen = True
        self._sensor_details_initialized = False
        self.sensor_explorer_window = None
        self.background_detail = None
        self.integrity_detail = None
        self.speedtest_running = False
        self._compact = False
        self._full_geometry = '1390x865'
        self._hover_last = 0.0
        self._hover_shown_at = 0.0
        self._hover_active = False
        self._cpu_clock_samples = deque(maxlen=30)
        # Existing UI creates most components before super() returns.
        super().__init__()
        self.title(f'OSReview | Hardware, Rede e Diagnóstico — {__version__}' +
                   (' [MODO SEGURO]' if os.environ.get('OSREVIEW_SAFE_MODE')=='1' else ''))
        self.apply_theme(self.config_store.data.get('theme', 'dark'), save=False)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('hardware_deep', collect_hardware_deep)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('network', collect_network)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('power', collect_energy_sensors)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('board', collect_board)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('background', collect_background_activity)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('integrity', diagnose_collection)
        self.after(65000, self._periodic_background)
        self.after(170, self._poll_v05)
        self._sensor_refresh_running=False
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self.after(6500, self._live_sensor_tick)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self.after(1100, self._live_fps_tick)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self.after(900, self.refresh_fps_processes)
        if self.config_store.data.get('compact_mode'):
            self.after(500, lambda: self.set_compact(True))

    def _layout(self):
        # Tray menu callbacks and hover events must use a separate queue because
        # original v0.4 event handler does not recognize new events.
        self.tray_events = queue.Queue()
        self.v05_events = queue.Queue()
        self.tray.commands = self.tray_events
        super()._layout()
        self._make_v05_pages()
        self._enhance_dashboard_cards()
        self._rebuild_navigation()
        self._add_quick_buttons()
        self._build_compact()
        self._build_hover_popup()

    def _make_diagnostics(self):
        """Modern, status-based diagnostic cards share the validated thermal engine."""
        super()._make_diagnostics()
        page=self.tabs['diagnostics']
        self.diag_text.pack_forget()  # preserve backwards compatible field
        self.diagnostic_state=base.ui_label(page,'AGUARDANDO COLETA · Os sensores térmicos são verificados separadamente.',
                  10,base.BLUE,True,bg=base.BG)
        self.diagnostic_state.pack(fill='x',anchor='w',pady=(5,8))
        self.diag_cards=SpecCards(page)
        self.diag_cards.pack(fill='both',expand=True)
        self.diag_cards.render([{'title':'STATUS DO DIAGNÓSTICO','rows':[('Estado','Aguardando métricas e sensores')]}])
        self._diagnosis_signature=None
        self._diagnosis_last_render=0.

    def _enhance_dashboard_cards(self):
        """Eight additional live cards; existing top 5 remain visible on every tab."""
        action=self.dashboard_action
        self.dash_sensor_area=tk.Frame(self.dashboard_scroll.body,bg=base.BG)
        self.dash_sensor_area.pack(fill='x',after=action,pady=(0,10))
        self.dash_sensor_values={}
        self.dash_sensor_subtitles={}
        self.dash_sensor_boxes=[]
        titles=[('temp_cpu','CPU · TEMPERATURA'),('temp_gpu','GPU · TEMPERATURA'),
                ('temp_disco','SSD / HD · TEMPERATURA'),('temp_geral','MAIOR TEMPERATURA REAL'),
                ('power_cpu','CPU · POTÊNCIA MEDIDA'),('power_gpu','GPU · POTÊNCIA MEDIDA'),
                ('power_bateria','BATERIA · POTÊNCIA'),('power_fonte','ENERGIA · USO GERAL')]
        for i,(key,title) in enumerate(titles):
            box=tk.Frame(self.dash_sensor_area,bg=base.PANEL,highlightbackground=base.EDGE,
                         highlightthickness=1,cursor='hand2')
            box.grid(row=i//4,column=i%4,sticky='nsew',padx=4,pady=4)
            self.dash_sensor_boxes.append(box)
            base.ui_label(box,title,9,base.MUTED,True).pack(anchor='w',padx=10,pady=(7,2))
            val=base.ui_label(box,'Aguardando...',15,base.BLUE,True)
            val.pack(anchor='w',padx=10)
            desc=base.ui_label(box,'Clique para detalhes',8,base.MUTED,wraplength=180,justify='left')
            desc.pack(anchor='w',padx=10,pady=(1,7))
            self.dash_sensor_values[key]=val
            self.dash_sensor_subtitles[key]=desc
            for w in (box,val,desc):
                w.bind('<Button-1>',lambda _e:self.switch('power'))
        for i in range(4):self.dash_sensor_area.grid_columnconfigure(i,weight=1)

    def _layout_sensor_meters(self, width):
        columns = 2 if width < 900 else 4
        if getattr(self, '_sensor_meter_columns', None) == columns:
            return False
        self._sensor_meter_columns = columns
        for index, widget in enumerate(self.sensor_meters.values()):
            widget.grid(row=index // columns, column=index % columns)
        for column in range(4):
            self.sensor_meter_row.grid_columnconfigure(column,
                                                        weight=1 if column < columns else 0)
        return True

    def _rebuild_navigation(self):
        sidebar = self.root_grid.winfo_children()[0]
        self.nav_sidebar = sidebar
        # Preserve original status label, replace navigation with scrollable list.
        for child in sidebar.winfo_children():
            if child is not self.left_status:
                child.destroy()
        for key, button in list(self.navbuttons.items()):
            self.navbuttons.pop(key, None)
        logo = tk.Frame(sidebar, bg=base.SIDEBAR)
        logo.pack(side='top', fill='x', pady=(12, 2))
        base.ui_label(logo, '●  OSReview', 21, base.WHITE, bold=True, bg=base.SIDEBAR).pack(anchor='w', padx=17)
        base.ui_label(sidebar, 'SYSTEM INTELLIGENCE  v'+__version__, 8, base.MUTED,
                      bg=base.SIDEBAR).pack(side='top', anchor='w', padx=20, pady=(0, 10))
        shell = tk.Frame(sidebar, bg=base.SIDEBAR)
        shell.pack(side='top', fill='both', expand=True, padx=(4, 0))
        canvas = tk.Canvas(shell, bg=base.SIDEBAR, bd=0, highlightthickness=0)
        self.nav_canvas = canvas
        scroll = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        nav = tk.Frame(canvas, bg=base.SIDEBAR)
        winid = canvas.create_window((0,0), window=nav, anchor='nw')
        nav.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(winid, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        items = [
            ('▦','Visão geral','dashboard'), ('◈','Diagnóstico','diagnostics'),
            ('▣','Inventário do hardware','hardware_deep'), ('⊞','Placa-mãe e BIOS','motherboard'),
            ('◉','Energia / temperaturas','power'), ('▣','GPU / drivers','hardware'),
            ('◇','Rede e Internet','network'), ('◎','Scanner de IPs','ipscanner'),
            ('▥','Benchmark','benchmark'), ('◴','FPS / Frametime','fps'),
            ('?','Pergunte à IA','questions'), ('⚠','Eventos / IA','events'),
            ('◆','Segurança','security'), ('↻','Atualizações','updates'),
            ('✚','Central de soluções','solutions'), ('≡','Processos','processes'),
            ('⊞','Windows / Serviços','windows'), ('◌','Atividades de fundo','background'), ('◷','Histórico','history'),
            ('◈','Fontes e integridade','integrity'), ('⚙','Configurações','settings'),
        ]
        for glyph, title, key in items:
            button = tk.Button(nav, text=f' {glyph}   {title}', anchor='w', relief='flat', bd=0,
                               bg=base.SIDEBAR, fg=base.MUTED, font=(base.FONT, 10, 'bold'),
                               padx=10, pady=7, activebackground=base.PANEL2,
                               activeforeground=base.WHITE, highlightthickness=0,
                               cursor='hand2', command=lambda k=key: self.switch(k))
            button.pack(fill='x', padx=6, pady=1)
            self.navbuttons[key] = button
        self.left_status.pack_forget()
        self.left_status.pack(side='bottom', padx=14, pady=10, anchor='w')

    def _add_quick_buttons(self):
        controls = tk.Frame(self.main_body, bg=base.BG)
        controls.pack(fill='x', padx=24, pady=(0, 8), after=self.main_header)
        base.ui_button(controls, 'Sair do OSReview', self.exit_app, True).pack(side='right', padx=(6, 0))
        base.ui_button(controls, '☾ / ☀', self.toggle_theme).pack(side='right', padx=6)
        base.ui_button(controls, '▣ Modo compacto', lambda: self.set_compact(True)).pack(side='right', padx=6)

    def _page_v5(self, name, title, subtitle):
        return self._page(name, title, subtitle)

    def _make_v05_pages(self):
        # Inventory separated from network, with reusable informational views.
        hw = self._page_v5('hardware_deep', 'Inventário físico detalhado',
                           'CPU e frequência, RAM por módulo, SSD NVMe/SATA, HDD/RPM, volumes e dispositivos removíveis.')
        top = tk.Frame(hw, bg=base.BG); top.pack(fill='x', pady=(0,9))
        base.ui_button(top,'Atualizar hardware',lambda:self._start_v05_job('hardware_deep',collect_hardware_deep), True).pack(side='left')
        base.ui_button(top,'Placa-mãe / BIOS',lambda:self.switch('motherboard')).pack(side='left',padx=8)
        self.hw_text = base.text_area(hw,5)  # suporte a mensagens de erro
        self.hw_cards=SpecCards(hw); self.hw_cards.pack(fill='both',expand=True)
        self.hw_cards.render([{'title':'INVENTÁRIO FÍSICO','rows':[('Status','Coletando dados do dispositivo...')]}])

        bd = self._page_v5('motherboard','Placa-mãe, chipset e BIOS',
                           'Modelo, revisão e BIOS. Compatibilidade depende da lista oficial e versão exata do equipamento.')
        top = tk.Frame(bd,bg=base.BG);top.pack(fill='x',pady=(0,8))
        base.ui_button(top,'Ler placa-mãe / BIOS',lambda:self._start_v05_job('board',collect_board),True).pack(side='left')
        self.board_links = {}
        for label, key in [('CPU compatível','cpu'), ('Memória QVL','memory'), ('BIOS e drivers','support'), ('PCIe / GPU','pcie')]:
            base.ui_button(top,label,lambda k=key:self.open_board_link(k)).pack(side='left',padx=3)
        self.board_text = base.text_area(bd,5)
        self.board_cards=SpecCards(bd); self.board_cards.pack(fill='both',expand=True)
        self.board_cards.render([{'title':'PLACA-MÃE','rows':[('Status','Coletando dados...')]}])
        base.ui_label(bd, 'As consultas abrem pesquisas na web, não uma certificação de compatibilidade.\n'
                          'BIOS mais nova não é necessariamente mais estável; compare suporte oficial, revisão e relatos verificáveis.',
                      10,base.MUTED,bg=base.BG,justify='left',wraplength=850).pack(anchor='w',pady=8)

        nw = self._page_v5('network','Rede e Internet — Diagnóstico do dispositivo',
                           'Conexão, IP/DHCP, gateway, DNS, download, upload e próximos passos.')
        top=tk.Frame(nw,bg=base.BG);top.pack(fill='x',pady=(0,8))
        base.ui_button(top,'Atualizar interfaces',lambda:self._start_v05_job('network',collect_network),True).pack(side='left')
        base.ui_button(top,'Testar Internet / DNS',self.run_connectivity).pack(side='left',padx=6)
        base.ui_button(top,'Medir download / upload',self.confirm_speedtest).pack(side='left')
        top_more = tk.Frame(nw,bg=base.BG);top_more.pack(fill='x',pady=(0,8))
        base.ui_button(top_more,'Scanner de IPs',lambda:self.switch('ipscanner')).pack(side='left')
        base.ui_button(top_more,'Identificar provedor',self.confirm_isp).pack(side='left',padx=6)
        status_panel=tk.Frame(nw,bg=base.PANEL,highlightthickness=1,highlightbackground=base.EDGE)
        status_panel.pack(fill='x',pady=(2,8))
        self.network_status=base.ui_label(status_panel,'REDE  •  Aguardando diagnóstico',12,base.BLUE,True)
        self.network_status.pack(anchor='w',padx=15,pady=(10,4))
        self.network_hint=base.ui_label(status_panel,'Identificação do adaptador não equivale a teste de Internet.',10,
                                        base.MUTED,wraplength=880,justify='left')
        self.network_hint.pack(anchor='w',padx=15,pady=(0,10))
        speedbar=tk.Frame(nw,bg=base.PANEL)
        speedbar.pack(fill='x',pady=(0,2))
        self.gauge_download=SpeedGauge(speedbar,'DOWNLOAD',base.GREEN)
        self.gauge_upload=SpeedGauge(speedbar,'UPLOAD',base.BLUE)
        self.gauge_download.pack(side='left',fill='x',expand=True)
        self.gauge_upload.pack(side='left',fill='x',expand=True)
        tools=tk.Frame(nw,bg=base.BG);tools.pack(fill='x',pady=(6,3))
        base.ui_label(tools,'Motor de teste:',10,base.MUTED,bg=base.BG).pack(side='left')
        self.speed_provider=tk.StringVar(value='Automático')
        ttk.Combobox(tools,textvariable=self.speed_provider,values=['Automático','Speedtest.net','Cloudflare'],
                     state='readonly',width=16).pack(side='left',padx=7)
        base.ui_label(tools,'Tempo por sentido:',10,base.MUTED,bg=base.BG).pack(side='left',padx=(7,2))
        self.speed_duration=tk.StringVar(value='10 s')
        ttk.Combobox(tools,textvariable=self.speed_duration,values=['10 s','20 s'],
                     state='readonly',width=6).pack(side='left',padx=(2,7))
        dns_tools=tk.Frame(nw,bg=base.BG);dns_tools.pack(fill='x',pady=(0,3))
        base.ui_button(dns_tools,'Comparar DNS públicos',self.start_dns_comparison).pack(side='left',padx=(0,6))
        self.dns_doc_choice=tk.StringVar(value='Cloudflare')
        ttk.Combobox(dns_tools,textvariable=self.dns_doc_choice,values=['Cloudflare','Google Public DNS','Quad9 (protegido)'],
                     state='readonly',width=19).pack(side='left',padx=(5,3))
        base.ui_button(dns_tools,'Site oficial DNS',self.open_dns_documentation).pack(side='left')
        self.isp_note=base.ui_label(nw,'Provedor/ASN: Não consultado (consulta externa opcional).',10,base.BLUE,bg=base.BG,wraplength=980,justify='left')
        self.isp_note.pack(anchor='w',pady=(3,3))
        self.speed_note=base.ui_label(nw,'Aguardando teste. O medidor usa dados transferidos, não a velocidade da placa.',
                                     10,base.MUTED,bg=base.BG,wraplength=980,justify='left')
        self.speed_note.pack(anchor='w',pady=(2,8))
        self.net_text = base.text_area(nw,2)  # usado somente para registrar falhas técnicas
        self.net_cards=SpecCards(nw);self.net_cards.pack(fill='both',expand=True)
        self.net_cards.render([{'title':'REDE E CONECTIVIDADE','rows':[('Status','Coletando adaptadores...')]}])

        sc = self._page_v5('ipscanner','Descoberta de IPs locais',
                            'Descoberta na sub-rede privada conectada: até 254 endereços utilizáveis em uma rede /24. Sem varredura de portas.')
        tools = tk.Frame(sc,bg=base.BG);tools.pack(fill='x',pady=(0,10))
        base.ui_label(tools,'Interface:',10,base.MUTED,bg=base.BG).pack(side='left')
        self.nic_choice = tk.StringVar(value='Aguardando interfaces...')
        self.nic_combo = ttk.Combobox(tools,textvariable=self.nic_choice,state='readonly',width=31)
        self.nic_combo.pack(side='left',padx=8)
        base.ui_label(tools,'Limite de IPs:',10,base.MUTED,bg=base.BG).pack(side='left',padx=(12,5))
        self.scan_limit_choice = tk.StringVar(value='254')
        ttk.Combobox(tools,textvariable=self.scan_limit_choice,state='readonly',
                     values=['64','128','254'],width=5).pack(side='left',padx=(0,8))
        base.ui_button(tools,'Pesquisar dispositivos',self.confirm_ipscan,True).pack(side='left')
        self.ip_text = base.text_area(sc,3)  # diagnóstico técnico oculto
        self.ip_cards=SpecCards(sc)
        self.ip_cards.pack(fill='both',expand=True)
        self.ip_cards.render(local_devices_cards({}))

        pw = self._page_v5('power','Temperaturas, energia e fonte',
                           'VRM, placa-mãe, RAM, CPU, GPU, SSD e HDD: sensores reais, ou “Indisponível”.')
        top = tk.Frame(pw,bg=base.BG);top.pack(fill='x',pady=(0,10))
        base.ui_button(top,'Atualizar sensores',lambda:self._start_v05_job('power',collect_energy_sensors),True).pack(side='left')
        base.ui_button(top,'Exportar log dos sensores',self.export_sensor_log).pack(side='left',padx=5)
        base.ui_button(top,'Pacote de suporte (.zip)',self.export_support_bundle).pack(side='left',padx=5)
        base.ui_button(top,'Reiniciar motor',self.restart_sensor_motor).pack(side='left',padx=4)
        credits=tk.Frame(pw,bg=base.BG)
        credits.pack(fill='x',pady=(0,6))
        base.ui_button(credits,'Projeto LibreHardwareMonitor (autor)',lambda:webbrowser.open('https://github.com/LibreHardwareMonitor/LibreHardwareMonitor')).pack(side='left')
        base.ui_button(credits,'Licença MPL 2.0',lambda:webbrowser.open('https://www.mozilla.org/en-US/MPL/2.0/')).pack(side='left',padx=7)
        base.ui_label(pw, 'MOTOR DE SENSORES DE TERCEIROS: LibreHardwareMonitorLib 0.9.6 | © LibreHardwareMonitor e contribuidores | MPL 2.0.\nO OSReview não é afiliado ao projeto original. A leitura usa a biblioteca original quando disponível.',
                      9,base.MUTED,bg=base.BG,justify='left',wraplength=1000).pack(anchor='w',pady=(0,9))
        meter_row = tk.Frame(pw, bg=base.BG)
        self.sensor_meter_row = meter_row
        meter_row.pack(fill='x', pady=(0, 10))
        self.sensor_meters = {}
        for index, title in enumerate(('CPU','GPU','Disco','Geral')):
            widget=SensorMeter(meter_row, ('Maior temp. real' if title=='Geral' else title + ' · temperatura'))
            widget.grid(row=0, column=index, sticky='nsew', padx=5, pady=4)
            self.sensor_meters[title]=widget
        for column in range(4):
            meter_row.grid_columnconfigure(column, weight=1)
        self.energy_live_status=base.ui_label(pw,
            'Maior temperatura real: apenas valores medidos; os limites de alerta do NVMe não entram no cálculo.',
            9,base.MUTED,bg=base.BG)
        self.energy_live_status.pack(anchor='w',pady=(0,8))
        self.energy_row=tk.Frame(pw,bg=base.BG)
        self.energy_row.pack(fill='x',pady=(0,10))
        self.energy_labels={}
        for key,title in [('cpu_package','CPU · Pacote'),('cpu_platform','CPU · Plataforma'),
                          ('gpu','GPU · Potência'),('psu_total','Fonte · Total')]:
            cell=tk.Frame(self.energy_row,bg=base.PANEL,highlightthickness=1,highlightbackground=base.EDGE)
            cell.pack(side='left',fill='both',expand=True,padx=(0,7))
            base.ui_label(cell,title,9,base.MUTED,True).pack(anchor='w',padx=10,pady=(8,2))
            val=base.ui_label(cell,'Indisponível',14,base.BLUE,True)
            val.pack(anchor='w',padx=10,pady=(0,8))
            self.energy_labels[key]=val
        detailbar=tk.Frame(pw,bg=base.BG)
        detailbar.pack(fill='x',pady=(0,7))
        self.sensor_freeze_button=base.ui_button(detailbar,'▶ Atualizar detalhes automaticamente',self.toggle_sensor_details)
        self.sensor_freeze_button.pack(side='left',padx=(0,8))
        base.ui_button(detailbar,'Capturar detalhes agora',self.capture_sensor_details).pack(side='left',padx=(0,8))
        base.ui_button(detailbar,'Explorar sensores (janela)',self.open_sensor_explorer).pack(side='left',padx=(0,8))
        self.sensor_refresh_note=base.ui_label(pw,'Detalhes congelados; os medidores seguem ativos.',
                                             9,base.MUTED,bg=base.BG)
        self.sensor_refresh_note.pack(anchor='w',pady=(0,7))
        filterrow=tk.Frame(pw,bg=base.BG)
        filterrow.pack(fill='x',pady=(0,8))
        base.ui_label(filterrow,'Visualizar detalhes:',10,base.MUTED,bg=base.BG).pack(side='left',padx=(0,9))
        self.sensor_section_var=tk.StringVar(value='Resumo')
        self.sensor_section_combo=ttk.Combobox(filterrow,textvariable=self.sensor_section_var,
            state='readonly',width=22,values=['Resumo','CPU','GPU','SSD / HD','Fonte / energia','Todos os sensores'])
        self.sensor_section_combo.pack(side='left')
        self.sensor_section_combo.bind('<<ComboboxSelected>>',lambda _event:self.capture_sensor_details())
        base.ui_label(pw,'Atualização: medidores ao vivo; detalhes só mediante captura ou opção automática.',
                      9,base.MUTED,bg=base.BG,wraplength=650).pack(anchor='w',pady=(0,7))
        self.power_text = base.text_area(pw,5)
        self.power_cards=SpecCards(pw);self.power_cards.pack(fill='both',expand=True)
        self.power_cards.render([{'title':'SENSORES','rows':[('Status','Consultando sensores...')]}])
        calc = self._panel(pw,'DIMENSIONAMENTO DA FONTE (ESTIMATIVA, NÃO MEDIÇÃO)')
        calc.pack(fill='x',pady=(12,0))
        row = tk.Frame(calc,bg=base.PANEL);row.pack(fill='x',padx=12,pady=8)
        self.w_cpu = tk.StringVar(value='65');self.w_gpu=tk.StringVar(value='0');self.w_disks=tk.StringVar(value='1')
        for label,var in [('CPU W documentados',self.w_cpu),('GPU W documentados',self.w_gpu),('Discos',self.w_disks)]:
            base.ui_label(row,label,9,base.MUTED).pack(side='left',padx=5)
            tk.Entry(row,textvariable=var,width=6,bg=base.BG,fg=base.WHITE,insertbackground=base.WHITE).pack(side='left',padx=(0,12))
        base.ui_button(row,'Estimar watts da fonte',self.calculate_psu,True).pack(side='left')
        self.psu_result=base.ui_label(calc,'Informe valores máximos oficiais; nunca interpretados como watts medidos.',10,base.MUTED,wraplength=800,justify='left')
        self.psu_result.pack(anchor='w',padx=14,pady=(0,12))

        fps = self._page_v5('fps','FPS e frametime (modo gamer)',
                            'Captura real de quadros via motor Intel PresentMon CLI embutido (MIT), sem instalar outro programa.')
        top=tk.Frame(fps,bg=base.BG);top.pack(fill='x',pady=(0,8))
        self.target_process=tk.StringVar(value='dwm.exe')
        self.fps_overlay_var=tk.BooleanVar(value=True)
        base.ui_label(top,'Aplicativo / processo:',10,base.MUTED,bg=base.BG).pack(side='left')
        self.fps_combo=ttk.Combobox(top,textvariable=self.target_process,width=26)
        self.fps_combo.pack(side='left',padx=8)
        base.ui_button(top,'Atualizar lista',self.refresh_fps_processes).pack(side='left',padx=3)
        base.ui_button(top,'▶ Ativar FPS',self.confirm_fps,True).pack(side='left',padx=3)
        base.ui_button(top,'■ Desativar',self.stop_fps).pack(side='left',padx=3)
        fps_options=tk.Frame(fps,bg=base.BG);fps_options.pack(fill='x',pady=(0,8))
        tk.Checkbutton(fps_options,text='Mostrar janela FPS sobreposta',variable=self.fps_overlay_var,
            bg=base.BG,fg=base.WHITE,selectcolor=base.PANEL,activebackground=base.BG,
            activeforeground=base.WHITE).pack(side='left')
        base.ui_label(fps,'Motor de captura: Intel PresentMon (GameTechDev), código aberto MIT. '
            'OSReview é independente. Site: https://github.com/GameTechDev/PresentMon',
            10,base.MUTED,bg=base.BG,wraplength=650).pack(anchor='w',pady=(0,9))
        self.display_refresh_note=base.ui_label(fps,'Desktop Windows: consultando taxa de atualização...',10,base.BLUE,bg=base.BG,wraplength=950,justify='left')
        self.display_refresh_note.pack(anchor='w',pady=(1,7))
        base.ui_label(fps,'dwm.exe = compositor do Windows; explorer.exe = shell/barra de tarefas. Não existe um executável universal que represente todos os FPS da tela. A frequência em Hz não é FPS. PresentMon poderá ou não reportar quadros do DWM.',
                      10,base.MUTED,bg=base.BG,wraplength=650,justify='left').pack(anchor='w',pady=(0,8))
        self.fps_text=base.text_area(fps,12);self.fps_text.pack(fill='both',expand=True)
        base.set_text(self.fps_text,'Clique Ativar FPS depois de abrir o jogo. O OSReview usa o motor '
            'PresentMon CLI 2.6.0 empacotado e verificado por SHA-256. Se o motor estiver ausente, '
            'reinstale o OSReview a partir do instalador oficial. '
            'Contadores podem não funcionar em todos os jogos e exigem Windows.')
        self.fps_overlay=None
        self.fps_overlay_label=None

        ia=self._page_v5('questions','Pergunte ao Assistente',
                          'Consulta online opt-in à API Gemini; requer chave própria. Busca Google sujeita a cotas e cobrança.')
        row=tk.Frame(ia,bg=base.BG);row.pack(fill='x',pady=8)
        base.ui_label(row,'Chave API (somente sessão)',10,base.MUTED,bg=base.BG).pack(side='left')
        self.gemini_key=tk.StringVar(value='')
        tk.Entry(row,textvariable=self.gemini_key,show='•',width=40,bg=base.PANEL,fg=base.WHITE,insertbackground=base.WHITE).pack(side='left',padx=9)
        self.use_web=tk.BooleanVar(value=False)
        tk.Checkbutton(row,text='Pesquisa Google (se disponível)',variable=self.use_web,bg=base.BG,fg=base.WHITE,
                       activebackground=base.BG,activeforeground=base.WHITE,selectcolor=base.PANEL2).pack(side='left')
        base.ui_label(ia,'Sua pergunta:',10,base.MUTED,bg=base.BG).pack(anchor='w')
        self.question=tk.Text(ia,height=4,bg=base.PANEL,fg=base.WHITE,insertbackground=base.WHITE,wrap='word',relief='flat')
        self.question.pack(fill='x',pady=(5,10))
        row2=tk.Frame(ia,bg=base.BG);row2.pack(fill='x')
        base.ui_button(row2,'Consultar IA pela Internet',self.confirm_gemini,True).pack(side='left')
        base.ui_button(row2,'Obter chave da API',lambda:webbrowser.open('https://aistudio.google.com/apikey')).pack(side='left',padx=8)
        # Independent collector health / trust page. A failed optional sensor never
        # becomes an unreported 'zero' measurement or a security exception.
        it = self._page_v5('integrity', 'Integridade das fontes de diagnóstico',
            'Mostra quais leituras foram obtidas, de qual API vieram e quando uma fonte está indisponível.')
        ib = tk.Frame(it,bg=base.BG); ib.pack(fill='x',pady=(0,9))
        base.ui_button(ib, 'Verificar fontes agora',
                       lambda: self._start_v05_job('integrity',diagnose_collection),True).pack(side='left')
        base.ui_button(ib,'Abrir Energia / sensores',lambda:self.switch('power')).pack(side='left',padx=8)
        self.integrity_summary = base.ui_label(it,
            'Conferindo os coletores locais. Nenhum antivírus será desativado.',
            10,base.MUTED,bg=base.BG,wraplength=880,justify='left')
        self.integrity_summary.pack(anchor='w',pady=(0,9))
        self.integrity_cards = SpecCards(it); self.integrity_cards.pack(fill='both',expand=True)
        self.integrity_cards.render([{'title':'COBERTURA', 'rows':[('Status','Aguardando verificação...')]}])

        # Background activity: separate from hardware/network, linked on dashboard.
        bg=self._page_v5('background','Instalações e atualizações em segundo plano',
            'Correlaciona processos ativos, eventos recentes e uso de CPU, disco e Internet. Diagnóstico somente leitura.')
        bar=tk.Frame(bg,bg=base.BG);bar.pack(fill='x',pady=(0,10))
        base.ui_button(bar,'Verificar atividade agora',lambda:self._start_v05_job('background',collect_background_activity),True).pack(side='left')
        base.ui_button(bar,'Windows Update',lambda:self.switch('updates')).pack(side='left',padx=9)
        self.bg_cards=SpecCards(bg);self.bg_cards.pack(fill='both',expand=True)
        self.bg_cards.render([{'title':'DIAGNÓSTICO DE FUNDO','rows':[('Status','Aguardando verificação...')]}])
        base.ui_button(self.dashboard_action,'Atividade em segundo plano',
                       lambda:self.switch('background')).pack(side='left',padx=7)
        self.activity_summary=base.ui_label(self.dashboard_scroll.body,
            'Atividades de fundo: verificando...',10,base.MUTED,bg=base.BG)
        self.activity_summary.pack(anchor='w',pady=(0,6),before=self.dashboard_columns)
        self.ai_answer=base.text_area(ia,14);self.ai_answer.pack(fill='both',expand=True,pady=(10,0))
        base.set_text(self.ai_answer,'Nunca compartilhe senhas, chaves, logs completos ou dados pessoais.\n'
                      'A pergunta enviada não inclui automaticamente inventário, rede, eventos ou chaves.')

    def _make_settings(self):
        super()._make_settings()
        settings=self.tabs['settings']
        panel=self._panel(settings,'APARÊNCIA E JANELAS')
        panel.pack(fill='x',pady=(0,8),before=settings.winfo_children()[1])
        row=tk.Frame(panel,bg=base.PANEL);row.pack(fill='x',padx=14,pady=9)
        base.ui_label(row,'Tema:',10,base.MUTED).pack(side='left')
        self.theme_var=tk.StringVar(value=self.config_store.data.get('theme','dark'))
        for value,label in [('dark','● Escuro'),('light','○ Claro')]:
            tk.Radiobutton(row,text=label,value=value,variable=self.theme_var,command=lambda:self.apply_theme(self.theme_var.get()),
                           bg=base.PANEL,fg=base.WHITE,selectcolor=base.PANEL2,
                           activebackground=base.PANEL,activeforeground=base.WHITE).pack(side='left',padx=14)
        palette_row=tk.Frame(panel,bg=base.PANEL);palette_row.pack(fill='x',padx=14,pady=(0,8))
        base.ui_label(palette_row,'Paleta:',10,base.MUTED).pack(side='left',padx=(5,8))
        self.accent_var=tk.StringVar(value=self.config_store.data.get('accent_theme','graphite'))
        choices=[f'{key} · {value[0]}' for key,value in THEMES.items()]
        self.accent_choice=ttk.Combobox(palette_row,values=choices,state='readonly',width=28)
        self.accent_choice.set(next((choice for choice in choices if choice.startswith(self.accent_var.get()+' ·')),choices[0]))
        self.accent_choice.bind('<<ComboboxSelected>>',lambda _e:self.apply_theme(
            self.theme_var.get(),self.accent_choice.get().split(' · ',1)[0]))
        self.accent_choice.pack(side='left',padx=5)
        base.ui_button(panel,'Alternar compacto / completo',self.toggle_compact).pack(anchor='w',padx=18,pady=(0,8))
        self.hover_var=tk.BooleanVar(value=self.config_store.data.get('tray_hover_popup',True))
        tk.Checkbutton(panel,text='Mostrar mini cartão ao passar mouse no ícone da bandeja (Windows)',
                       variable=self.hover_var,command=self.save_hover_option,bg=base.PANEL,
                       fg=base.WHITE,selectcolor=base.PANEL2,activebackground=base.PANEL,
                       activeforeground=base.WHITE,font=(base.FONT,10)).pack(anchor='w',padx=18,pady=(2,12))
        # Replace outdated version labels created by base.
        for parent in settings.winfo_children():
            for w in parent.winfo_children():
                if isinstance(w,tk.Label):
                    txt=w.cget('text')
                    if txt.startswith('v0.4.0'):
                        w.configure(text=f'v{__version__} • Inventário, rede, energia, consulta IA opt-in e tema dinâmico')

    def _build_compact(self):
        self.compact=tk.Frame(self,bg=base.BG)
        bar=tk.Frame(self.compact,bg=base.PANEL);bar.pack(fill='x',padx=12,pady=(12,8))
        base.ui_label(bar,'● OSReview  |  Mini painel',14,base.WHITE,True).pack(side='left',padx=8,pady=9)
        base.ui_button(bar,'Abrir completo',lambda:self.set_compact(False)).pack(side='right',padx=6,pady=4)
        inner=tk.Frame(self.compact,bg=base.BG);inner.pack(fill='both',expand=True,padx=14,pady=6)
        self.mini_labels={}
        for i,(key,title) in enumerate([('cpu','CPU'),('ram','RAM'),('temp','Temperatura CPU'),('gpu','GPU'),('net','Rede')]):
            box=tk.Frame(inner,bg=base.PANEL,highlightthickness=1,highlightbackground=base.EDGE)
            box.grid(row=i//2,column=i%2,sticky='nsew',padx=5,pady=5)
            base.ui_label(box,title,9,base.MUTED).pack(anchor='w',padx=11,pady=(9,2))
            label=base.ui_label(box,'Indisponível',14,base.BLUE,True)
            label.pack(anchor='w',padx=11,pady=(0,9))
            self.mini_labels[key]=label
        for i in (0,1):inner.grid_columnconfigure(i,weight=1)
        for i in range(3):inner.grid_rowconfigure(i,weight=1)

    def _build_hover_popup(self):
        self.popup=tk.Toplevel(self)
        self.popup.withdraw();self.popup.overrideredirect(True)
        self.popup.attributes('-topmost',True)
        self.popup.configure(bg=base.EDGE)
        surface=tk.Frame(self.popup,bg=base.PANEL,highlightbackground=base.EDGE,highlightthickness=1)
        surface.pack(fill='both',expand=True,padx=1,pady=1)
        base.ui_label(surface,'●  OSReview — Status atual',12,base.WHITE,True).pack(anchor='w',padx=14,pady=(11,7))
        self.hover_values={}
        for k,caption in [('cpu','CPU'),('ram','Memória RAM'),('temp','Temperatura CPU'),
                          ('gpu','GPU'),('disk','Armazenamento'),('net','Rede ↓/↑')]:
            row=tk.Frame(surface,bg=base.PANEL);row.pack(fill='x',padx=14,pady=2)
            base.ui_label(row,caption,10,base.MUTED).pack(side='left')
            value=base.ui_label(row,'Indisponível',10,base.BLUE,True)
            value.pack(side='right')
            self.hover_values[k]=value
        base.ui_label(surface,'Duplo clique no ícone para abrir.',9,base.MUTED).pack(anchor='w',padx=14,pady=(8,12))
        self.popup.geometry('310x236+0+0')

    def _start_v05_job(self, kind, func, *args):
        def worker():
            try:
                self.v05_events.put((kind,func(*args),None))
            except Exception as exc:
                self.v05_events.put((kind,None,str(exc)))
        threading.Thread(target=worker,daemon=True,name='osreview-'+kind).start()

    def _poll_v05(self):
        for _ in range(18):
            try:kind,result,error=self.v05_events.get_nowait()
            except queue.Empty:break
            if error:
                if kind=='scan':
                    self.ip_cards.render([{'title':'VARREDURA NÃO CONCLUÍDA','rows':[('Erro',str(error))]}])
                if kind in ('connectivity','dns-comparison'):
                    self.speed_note.configure(text='Falha na consulta: '+str(error))
                if kind=='speedtest':
                    self.speedtest_running=False
                    self.speed_note.configure(text='Teste indisponível: '+str(error))
                    self.gauge_download.update_value(None,0,'INDISPONÍVEL')
                    self.gauge_upload.update_value(None,0,'INDISPONÍVEL')
                label={'network':'rede','board':'placa-mãe','power':'sensores','hardware_deep':'hardware'}.get(kind,kind)
                self._text_for_job(kind,f'Falha ao consultar {label}: {error}')
                continue
            if kind=='hardware_deep':
                self.hardware_detail=result
                lines=['INVENTÁRIO (somente leituras identificadas pelo sistema)',
                       '\nCPU:',pretty(result.get('cpus',[])), '\nMEMÓRIAS / MÓDULOS:',pretty(result.get('ram_sticks',[])),
                       '\nDISCOS FÍSICOS:',pretty(result.get('disks',[])), '\nVOLUMES:',pretty(result.get('volumes',[])),
                       '\nREMOVÍVEIS:',pretty(result.get('removable',[])), '\nUSB:',pretty(result.get('usb_devices',[])),
                       '\nAVISOS:',pretty(result.get('warnings',[]))]
                if result.get('profiler'):
                    lines += ['\nMACOS / SYSTEM PROFILER',pretty(result['profiler'])]
                self.hw_cards.render(hardware_cards(result))
            elif kind=='board':
                self.board_detail=result
                self.board_cards.render(board_cards(result))
            elif kind=='network':
                self.net_detail=result
                self.net_cards.render(network_cards(self.net_detail,self.connection_detail,self.dns_comparison,self.isp_detail))
                self.update_network_status()
                names=[x['name'] for x in result.get('interfaces',[]) if x.get('up') and
                       any(z.get('kind')=='privado' for z in x.get('ipv4',[]))]
                self.nic_combo.configure(values=names)
                if names:self.nic_choice.set(names[0])
            elif kind=='connectivity':
                self.connection_detail=result
                self.net_cards.render(network_cards(self.net_detail,self.connection_detail,self.dns_comparison,self.isp_detail))
                dns_txt='DNS: OK' if result.get('dns') else 'DNS: falhou'
                ext_txt='TCP externo: OK' if result.get('internet') else 'TCP externo: falhou'
                self.speed_note.configure(text=f"Conectividade concluída • {dns_txt} • {ext_txt}. Veja detalhes nos cartões.")
                self.update_network_status()
            elif kind=='dns-comparison':
                self.dns_comparison=result
                self.net_cards.render(network_cards(self.net_detail or {},self.connection_detail,self.dns_comparison,self.isp_detail))
                best=result.get('fastest')
                self.speed_note.configure(text=('Comparação DNS concluída. Menor latência: '+best if best else
                                                 'Nenhum servidor DNS público respondeu via UDP 53; pode haver bloqueio na rede.'))
            elif kind=='scan':
                self.ip_cards.render(local_devices_cards(result))
            elif kind=='isp':
                self.isp_detail = result
                if result.get('ok'):
                    self.isp_note.configure(text=f"Rede do IP público: {result['organization']} • ASN: {result['asn'] or 'não informado'} • IP: {result['ip']} (fonte: {result['source']}). Pode ser VPN/operadora upstream.")
                else:
                    self.isp_note.configure(text='Não foi possível identificar a operadora nesta consulta: '+str(result.get('error')))
                self.net_cards.render(network_cards(self.net_detail or {},self.connection_detail,self.dns_comparison,self.isp_detail))
            elif kind=='speedtest':
                self.speedtest_running=False
                self.speed_result=result
                source=result.get('server','servidor desconhecido')
                if result.get('ok'):
                    self.speed_note.configure(text=f"Teste concluído via {source} • Download: {result['download_mbps']:.2f} Mbps • Upload: {result['upload_mbps']:.2f} Mbps.")
                    self.gauge_download.update_value(result['download_mbps'],1.,'CONCLUÍDO')
                    self.gauge_upload.update_value(result['upload_mbps'],1.,'CONCLUÍDO')
                else:
                    self.speed_note.configure(text='Teste indisponível: '+str(result.get('error'))+
                                              ' • Um HTTP 403 indica recusa do servidor, não necessariamente falha da sua Internet.')
                    for g,key in [(self.gauge_download,'download_mbps'),(self.gauge_upload,'upload_mbps')]:
                        value=result.get(key)
                        if isinstance(value,(float,int)) and value>0:
                            g.update_value(value,1.,'PARCIAL — NÃO VALIDADO')
                        else:
                            g.update_value(None,0.,'INDISPONÍVEL')
            elif kind=='power':
                self.power_detail=result
                self._update_sensor_widgets()
                self._update_diagnostics()  # same sensor source as the dedicated panel
                lines=['FONTE ATX — W REAL CONSUMIDOS: INDISPONÍVEL', result.get('note',''),
                       '\nIntegração: '+result.get('integration',''), '\nBateria:',pretty(result.get('battery'))]
                for k,sensors in result.get('groups',{}).items():
                    lines.extend(['\n'+k.upper()+':',pretty(sensors) if sensors else 'Indisponível (sem sensor acessível)'])
                if not self._sensor_detail_frozen or not self._sensor_details_initialized:
                    self.capture_sensor_details()
                else:
                    self.sensor_refresh_note.configure(text='Detalhes congelados • leitura mais recente recebida; clique Capturar detalhes agora para atualizar a lista.')
                self._update_mini()
            elif kind=='speed-progress':
                stage=result['stage']
                if stage in ('download','upload'):
                    gauge=self.gauge_download if stage=='download' else self.gauge_upload
                    gauge.update_value(result['mbps'],result['progress'],f'Medindo {stage} • {result["progress"]*100:.0f}%')
                    self.speed_note.configure(text=f'Medindo {stage}: {result["mbps"]:.1f} Mbps — conexão externa em uso')
                elif stage=='fallback':
                    self.speed_note.configure(text='O primeiro serviço falhou. Tentando servidor alternativo...')
                    self.gauge_download.update_value(0,0,'TROCANDO SERVIDOR')
                    self.gauge_upload.update_value(0,0,'AGUARDANDO')
                elif stage=='preparing':
                    self.speed_note.configure(text='Procurando servidor de teste disponível...')
            elif kind=='background':
                self.background_detail=result
                self.bg_cards.render(activity_cards(result))
                self.activity_summary.configure(text='Atividades de fundo: '+result.get('status','indisponível'))
                if result.get('supported') and result.get('observed_active'):
                    self.left_status.configure(text='Atividade de fundo: '+str(result.get('observed_active'))+' processo(s) ativo(s)')
            elif kind=='integrity':
                self.integrity_detail = result
                self.integrity_summary.configure(text=(f"Fontes disponíveis: {result['ok']} de "
                    f"{result['total']}. Ausência de sensores é registrada, nunca inventada. "
                    "SHA-256 local não substitui assinatura digital do editor."))
                self.integrity_cards.render([
                    {'title': 'FONTE • ' + item['name'],
                     'rows': [('Situação', item['status']),('Provedor',item['source']),
                              ('Resultado',item['detail']),('Próxima ação',item['action'] or 'Nenhuma')]}
                    for item in result['checks']])
            elif kind=='fps':
                base.set_text(self.fps_text, pretty(result))
            elif kind=='gemini':
                answer=result.get('answer','')
                sources='\n'.join(f"• {x.get('title','Fonte')}: {x.get('url','')}" for x in result.get('sources',[]))
                base.set_text(self.ai_answer,answer+'\n\nFONTES\n'+(sources or 'Nenhuma fonte retornada; verifique a resposta.')+
                              '\n\n'+result.get('warning',''))
        for _ in range(30):
            try:msg=self.tray_events.get_nowait()
            except queue.Empty:break
            action=msg[0]
            if action=='tray-hover' and self.config_store.data.get('tray_hover_popup',True):
                self._hover_last=time.monotonic()
                if not self._hover_active:
                    self._show_hover()
            elif action=='tray-hide-popup':self._hide_hover()
            elif action=='show':
                self._hide_hover();self.deiconify();self.lift();self.focus_force()
            elif action=='exit':self.exit_app();return
            elif action=='toggle_alerts':
                self.var_alert.set(not self.var_alert.get());self.set_alert()
        if self._hover_active and time.monotonic()-self._hover_last>1.8:
            # Auto-hide when no hover callback received, unless pointing at popup.
            x,y=self.winfo_pointerxy()
            px,py=self.popup.winfo_rootx(),self.popup.winfo_rooty()
            if not (px<=x<=px+310 and py<=y<=py+236):self._hide_hover()
        if not self.shutdown.is_set():self.after(180,self._poll_v05)

    def _text_for_job(self,kind,msg):
        widget={'hardware_deep':self.hw_text,'board':self.board_text,'network':self.net_text,
                'power':self.power_text,'scan':self.ip_text,'speedtest':self.net_text,
                'connectivity':self.net_text,'dns-comparison':self.net_text,'fps':self.fps_text,'gemini':self.ai_answer}.get(kind)
        if widget:base.set_text(widget,msg)
        if kind in ('hardware_deep','board','network','power','background'):
            attr={'hardware_deep':'hw_cards','board':'board_cards','network':'net_cards','power':'power_cards','background':'bg_cards'}[kind]
            target=getattr(self,attr,None)
            if target:target.render([{'title':'CONSULTA NÃO CONCLUÍDA','rows':[('Mensagem',msg)]}])

    def _network_report(self):
        data=self.net_detail or {}
        lines=['DIAGNÓSTICO DE REDE — SEPARADO DO HARDWARE','\nESTADO:',pretty(data.get('overview',{})),
               '\nINTERFACES:',pretty(data.get('interfaces',[])), '\nGATEWAYS:',pretty(data.get('gateways',{})),
               '\nDNS:',pretty(data.get('dns',{})), '\nADAPTADORES:',pretty(data.get('adapter_details',[])),
               '\nAVISO:',data.get('note','')]
        if self.connection_detail:
            lines.extend(['\nTESTE DE CONECTIVIDADE (resultado pontual):',pretty(self.connection_detail)])
        return '\n'.join(lines)

    def update_network_status(self):
        from osreview.services.network_diagnostics import analyze_network
        if not self.net_detail:
            return
        d=self.net_detail
        report=analyze_network(d.get('interfaces',[]),d.get('dns',{}),d.get('gateways',{}),self.connection_detail)
        primary=report.get('primary_interface')
        link=report.get('primary_link_mbps')
        adapter=(f'{primary} • link {link:g} Mbps' if primary and link else primary or '')
        issues=report.get('issues') or []
        secondary=report.get('adapter_warnings') or []
        self.network_status.configure(text='REDE  •  '+report.get('status','Estado desconhecido'),
                                      fg=base.YELLOW if issues else base.GREEN)
        self.network_hint.configure(text=' • '.join(filter(None, [adapter, *issues[:2],
            f'{len(secondary)} aviso(s) em adaptadores; consulte os cartões' if secondary else '',
            'Link da placa não é velocidade da Internet' if link else ''])))

    def start_dns_comparison(self):
        if not messagebox.askyesno('Comparação de DNS',
                'Consultar example.com usando UDP 53 diretamente nos servidores públicos da Cloudflare, Google e Quad9?\n'
                'Isto envia pequenas consultas externas, não modifica sua configuração.\n'
                'Em redes empresariais ou VPN, consultas diretas podem ser bloqueadas. Continuar?'):
            return
        self.speed_note.configure(text='Comparando latências de servidores DNS públicos...')
        self._start_v05_job('dns-comparison',compare_public_dns)

    def open_dns_documentation(self):
        from osreview.services.network_diagnostics import DNS_PROVIDERS
        name=self.dns_doc_choice.get()
        url=next((p['official_url'] for p in DNS_PROVIDERS if p['name']==name),DNS_PROVIDERS[0]['official_url'])
        webbrowser.open(url)

    def run_connectivity(self):
        if not self.net_detail:
            messagebox.showinfo('Rede','Atualize a lista de interfaces primeiro.');return
        self.connection_detail=None
        self._start_v05_job('connectivity',test_connectivity,self.net_detail)
        # Provider lookup is separate and initiated by the same explicit Internet test.
        self._start_v05_job('isp',fetch_isp)
        self.speed_note.configure(text='Testando gateway, DNS e TCP 443 (sem transferir arquivos)...')

    def confirm_isp(self):
        if messagebox.askyesno('Identificação do provedor',
            'Consultar a organização e o ASN do seu IP público via HTTPS (ipapi.co)?\n\nO serviço receberá seu IP público. Nenhum log local será enviado. Em redes com VPN, proxy ou CGNAT, o resultado pode não refletir o contrato.\n\nContinuar?'):
            self.isp_note.configure(text='Consultando ASN e organização do IP público...')
            self._start_v05_job('isp',fetch_isp)

    def refresh_fps_processes(self):
        names=graphical_processes()
        available=['dwm.exe']+[name for name in names if name.casefold() != 'dwm.exe']
        self.fps_combo.configure(values=available)
        hz=desktop_refresh_hz()
        self.display_refresh_note.configure(text=(f'Tela principal: {hz} Hz configurados (não representa FPS renderizado).' if hz is not None else
            'Taxa de atualização da tela: indisponível; não substitui uma medição de FPS.'))
        if not self.target_process.get().strip():
            self.target_process.set(available[0])

    def confirm_speedtest(self):
        if self.speedtest_running:return
        provider_name=self.speed_provider.get()
        provider={'Automático':'auto','Speedtest.net':'ookla','Cloudflare':'cloudflare'}.get(provider_name,'auto')
        duration=20 if self.speed_duration.get()=='20 s' else 10
        if not messagebox.askyesno('Medição de Internet',
                f'O teste procura medir cerca de {duration} segundos de download e {duration} de upload. '
                'Em conexão de 1 Gb/s pode transferir vários GB; a amostra HTTP tem limite de dados.\n'
                'Seu IP público também será consultado em ipapi.co para identificar ASN/provedor provável. O tráfego pode afetar outros dispositivos da rede.\n\n'
                'Iniciar agora?'):
            return
        self.speedtest_running=True
        self.gauge_download.update_value(0,0,'INICIANDO')
        self.gauge_upload.update_value(0,0,'AGUARDANDO')
        self.speed_note.configure(text='Teste iniciado; aguardando servidor. Isto não mede o link físico da placa.')
        def callback(stage,mbps,progress):
            self.v05_events.put(('speed-progress',{'stage':stage,'mbps':mbps,'progress':progress},None))
        self._start_v05_job('speedtest',run_speedtest,callback,provider,duration)
        self._start_v05_job('isp',fetch_isp)

    def confirm_ipscan(self):
        if not self.net_detail:
            messagebox.showinfo('Scanner de IPs', 'Aguardando leitura das interfaces de rede.')
            return
        nic=self.nic_choice.get()
        try:
            limit=int(self.scan_limit_choice.get())
            if limit not in (64,128,254): raise ValueError
        except ValueError:
            messagebox.showerror('Scanner de IPs','Escolha 64, 128 ou 254 endereços.')
            return
        if not messagebox.askyesno('Scanner IP local',
                f'Pesquisar até {limit} endereços na rede privada diretamente conectada à interface “{nic}”?\n\n'
                'A consulta usa ping, cache ARP e resolução local de nomes.\n'
                'Uma rede /24 possui até 254 IPs utilizáveis; alguns dispositivos não respondem.\n'
                'Use apenas em redes próprias ou com autorização.'):
            return
        self.ip_cards.render([{'title':'CONSULTA EM ANDAMENTO','rows':[
            ('Situação',f'Pesquisando até {limit} endereços IPv4 e consultando nomes disponíveis...'),
            ('Aviso','A varredura pode levar algum tempo. Hosts que bloqueiam ping podem não ser detectados.')]}])
        self._start_v05_job('scan',discover_local_hosts,self.net_detail,nic,limit)

    def open_board_link(self,key):
        if not self.board_detail:
            messagebox.showinfo('Placa-mãe','Aguarde a identificação da placa-mãe.');return
        url=self.board_detail.get('links',{}).get(key)
        if not url:messagebox.showinfo('Consulta','Fabricante/modelo não identificado.');return
        webbrowser.open(url)

    def calculate_psu(self):
        try:result=psu_budget(float(self.w_cpu.get()),float(self.w_gpu.get()),int(self.w_disks.get()))
        except ValueError:result={'ok':False,'reason':'Preencha watts e quantidade de discos com números válidos.'}
        if result.get('ok'):
            msg=(f"Demanda de referência (não medida): {result['estimated_demand_w']} W. "
                 f"Fonte nominal sugerida como ponto de partida: {result['recommended_nominal_w']} W, com 35% de folga. "
                 f"Confira marca, qualidade, conectores, fator ATX/SFX e entrada AC. {result['warning']}")
        else:msg=result['reason']
        self.psu_result.configure(text=msg)

    def confirm_fps(self):
        name=self.target_process.get().strip()
        if not messagebox.askyesno('OSReview — Ativar FPS',
            f'Capturar quadros reais do processo {name}?\n\n'
            'Utiliza o motor Intel PresentMon incluído no OSReview. Não injeta código no jogo nem altera o executável.\nO compositor dwm.exe pode não expor apresentações utilizáveis; o valor em Hz da tela não é FPS.'):
            return
        try:
            fps_session.start(name)
        except (RuntimeError,ValueError) as exc:
            base.set_text(self.fps_text,'FPS não iniciado: '+str(exc))
            messagebox.showwarning('Motor FPS',str(exc))
            return
        if self.fps_overlay_var.get():self._create_fps_overlay()
        base.set_text(self.fps_text,'Motor de FPS ativado. Aguardando apresentação de quadros pelo jogo...')

    def stop_fps(self):
        fps_session.stop()
        if self.fps_overlay:
            self.fps_overlay.destroy()
            self.fps_overlay=None
            self.fps_overlay_label=None
        base.set_text(self.fps_text,'Contador FPS desativado. Nenhuma captura em andamento.')

    def _create_fps_overlay(self):
        if self.fps_overlay:return
        win=tk.Toplevel(self)
        win.title('OSReview FPS')
        win.geometry('230x72+55+55')
        win.configure(bg='#0D1725')
        win.attributes('-topmost',True)
        win.overrideredirect(True)
        label=tk.Label(win,text='FPS: aguardando | Frametime: —',font=('Segoe UI',12,'bold'),
            bg='#0D1725',fg='#4EE6C4',padx=14,pady=18)
        label.pack(fill='both',expand=True)
        # Overlay can be moved using standard mouse dragging; never inject into games.
        def drag_start(ev):win._drag_x=ev.x_root-win.winfo_x();win._drag_y=ev.y_root-win.winfo_y()
        def drag(ev):win.geometry(f'+{ev.x_root-win._drag_x}+{ev.y_root-win._drag_y}')
        label.bind('<ButtonPress-1>',drag_start)
        label.bind('<B1-Motion>',drag)
        label.bind('<Double-Button-1>',lambda _:self.stop_fps())
        self.fps_overlay=win
        self.fps_overlay_label=label

    def _live_fps_tick(self):
        if not self.shutdown.is_set():
            state=fps_session.snapshot()
            if state['enabled']:
                v=state.get('fps');m=state.get('frametime_ms')
                txt=(f'FPS: {v:.1f}   |   {m:.2f} ms' if v is not None
                     else 'FPS: aguardando quadro...')
                if self.fps_overlay_label:
                    self.fps_overlay_label.configure(text=txt)
                base.set_text(self.fps_text,txt+'\nProcesso: '+state['target']+
                    '\nQuadros recentes: '+str(state['frames'])+'\nEstado: '+state['status']+
                    '\n\nMotor Intel PresentMon v2.6.0 • MIT • licença e créditos no pacote.')
                if self.fps_overlay_var.get() and self.fps_overlay is None:self._create_fps_overlay()
                if not self.fps_overlay_var.get() and self.fps_overlay is not None:
                    self.fps_overlay.destroy();self.fps_overlay=None;self.fps_overlay_label=None
            self.after(1100,self._live_fps_tick)

    def toggle_sensor_details(self):
        self._sensor_detail_frozen = not self._sensor_detail_frozen
        self.sensor_freeze_button.configure(text=('▶ Atualizar detalhes automaticamente' if self._sensor_detail_frozen
                                                    else '❚❚ Congelar detalhes e rolagem'))
        if not self._sensor_detail_frozen:
            self.capture_sensor_details()
        else:
            self.sensor_refresh_note.configure(text='Detalhes congelados: a rolagem fica estável; os medidores seguem ativos.')

    def _update_sensor_widgets(self):
        if not self.power_detail:return
        data=self.power_detail
        temps=temperature_readings(data)
        watts=power_readings(data)
        for name,reading in temps.items():
            meter=self.sensor_meters.get(name)
            if meter is not None:
                meter.show_temperature(reading.value if reading else None,
                    reading.provenance() if reading else 'Sensor térmico não exposto')
        for key,label in getattr(self,'energy_labels',{}).items():
            reading=watts.get(key)
            label.configure(text=reading.display('W') if reading else 'Não medido',
                            fg=base.GREEN if reading else base.MUTED)
        general=temps['Geral']
        self.energy_live_status.configure(text=(
            f"Última leitura {timestamp_of(data)} · Maior temperatura atual: " +
            (f"{general.display()} ({general.provenance()}). " if general else 'indisponível. ')+
            'O valor geral pode coincidir com outro card porque destaca a maior leitura; '
            'limites NVMe e margens TjMax são excluídos.'),wraplength=1030)
        if hasattr(self,'dash_sensor_values'):
            for item in sensor_overview(data):
                card_key=item['key'].replace('temp_disco','temp_disco').replace('temp_geral','temp_geral')
                if card_key in self.dash_sensor_values:
                    self.dash_sensor_values[card_key].configure(text=item['value'],
                        fg=base.GREEN if item['reading'] else base.MUTED)
                    self.dash_sensor_subtitles[card_key].configure(text=item['description'][:70])
            misc={'power_gpu':watts.get('gpu'),'power_bateria':watts.get('battery'),
                  'power_fonte':watts.get('psu_total')}
            for key,reading in misc.items():
                self.dash_sensor_values[key].configure(text=reading.display('W') if reading else 'Não medido',
                    fg=base.GREEN if reading else base.MUTED)
                descriptions={'power_gpu':'Potência reportada pela GPU',
                    'power_bateria':'Carga/descarga da bateria (se reportada)',
                    'power_fonte':'Potência total só com fonte digital compatível'}
                if key=='power_gpu' and reading is not None and reading.value==0:
                    descriptions[key]='Sensor reportou 0 W nesta amostra; não prova GPU desligada'
                if key=='power_fonte' and reading is None:
                    domains=[f'CPU {watts["cpu_package"].value:.1f} W' for _ in (0,) if watts.get('cpu_package')]
                    if watts.get('gpu'):domains.append(f'GPU {watts["gpu"].value:.2f} W')
                    descriptions[key]=(' / '.join(domains)+' (não somar)' if domains else descriptions[key])
                self.dash_sensor_subtitles[key].configure(text=descriptions[key])
            # Replace the old CPU subtitle with a short, clear source label.
            for key,actual in [('power_cpu','cpu_package')]:
                reading=watts.get(actual)
                self.dash_sensor_subtitles[key].configure(text='CPU Package · não equivale ao consumo da fonte')

    def _update_diagnostics(self):
        """Consistent live diagnostics using the *same* validated sensor snapshot."""
        if not getattr(self,'latest',None) or not hasattr(self,'diag_cards'):return
        import datetime as _dt
        snapshot=dict(self.latest)
        temps=temperature_readings(self.power_detail)
        power=power_readings(self.power_detail)
        cpu=temps.get('CPU')
        # No stale reading masquerades as live evidence. A slow/blocked bridge
        # leaves standard system diagnostics available.
        recent=False
        if self.power_detail:
            try:
                since=_dt.datetime.fromisoformat(str(self.power_detail.get('collected_at','')))
                recent=0 <= (_dt.datetime.now()-since).total_seconds() < 50
            except (ValueError,TypeError):pass
        if recent and cpu:
            snapshot['cpu_temp_c']=cpu.value
        # Preserve native platform temperature when no recent LibreHardwareMonitor
        # reading is available; never fabricate an unavailable value.
        items=list(self.engine.analyze(snapshot,self.procs,self.health,self.inventory,
                                      self.event_data,self.pending_windows_updates))
        if recent and cpu and cpu.value < 85:
            items.append(Finding('ok','Temperatura da CPU monitorada',
                f'Leitura do processador: {cpu.display()}.',
                f'Sensor {cpu.name}; dispositivo {cpu.device}.',
                'Sem indicação de alerta térmico nesta medição isolada.'))
        if recent and not temps.get('GPU') and self.power_detail:
            items.append(Finding('info','Temperatura da GPU indisponível',
                'O coletor ainda não recebeu um sensor térmico para a GPU, embora possa identificá-la.',
                'Isso é frequente em determinadas GPUs integradas; não prova defeito.',
                'Mantenha a indicação Indisponível; consulte os sensores válidos antes de concluir falha.'))
        disk=temps.get('Disco') if recent else None
        limits=temperature_thresholds(self.power_detail)
        if disk:
            if disk.value >= limits.get('critical',85):
                severity='critical'; title='Temperatura crítica do SSD'
            elif disk.value >= limits.get('warning',70):
                severity='warning'; title='Temperatura elevada do SSD'
            else:
                severity='ok'; title='SSD com temperatura normal'
            items.append(Finding(severity,title,
                f'Temperatura real {disk.display()} no {disk.device or "armazenamento"}.',
                f'Sensor: {disk.name}. Limites NVMe: aviso {limits.get("warning", "não informado")} °C; '
                f'crítico {limits.get("critical", "não informado")} °C. Esses limites NÃO são medições.',
                'Nenhuma intervenção térmica necessária.' if severity=='ok' else
                'Verifique ventilação, temperatura durante carga e o estado do SSD.'))
        if recent and power.get('cpu_package'):
            p=power['cpu_package']
            items.append(Finding('ok','Potência da CPU sendo medida',
                f'Pacote CPU: {p.display("W")}.',
                'Potência de pacote reportada; não é consumo total do computador.',
                'Acompanhe em Energia / temperaturas; domínios CPU não são somados.'))
        elif self.power_detail:
            items.append(Finding('info','Potência da CPU não disponível',
                'O coletor não forneceu uma leitura recente válida do pacote CPU.',
                '0 W isolado não confirma consumo real nulo.',
                'Confira fontes de sensores e nível de acesso autorizado.'))
        if self.power_detail and not recent:
            items.append(Finding('info','Leitura de hardware desatualizada',
                'O coletor de sensores não entregou dados recentes.',
                f'Última amostra registrada: {timestamp_of(self.power_detail)}.',
                'Verifique o estado da ponte antes de interpretar temperaturas.'))
        self.findings=items
        # Update summary on the dashboard only when status changes or manually.
        self._update_diag_cards(items)

    def _update_diag_cards(self, items, force=False):
        importance={'critical':0,'warning':1,'info':2,'ok':3}
        counts={key:sum(x.level==key for x in items) for key in importance}
        severity='CRÍTICO' if counts['critical'] else 'ATENÇÃO' if counts['warning'] else 'SEM ALERTAS CRÍTICOS'
        ts=time.strftime('%H:%M:%S')
        self.diagnostic_state.configure(
            text=f"STATUS: {severity}  ·  {counts['critical']} crítico(s)  ·  {counts['warning']} atenção  ·  "
                 f"{counts['info']} informação(ões)  ·  Dados coletados {ts}" ,
            fg=base.RED if counts['critical'] else (base.YELLOW if counts['warning'] else base.GREEN))
        sig=tuple((x.level,x.title) for x in items)
        now=time.monotonic()
        if force or sig!=self._diagnosis_signature or now-self._diagnosis_last_render>25:
            cards=[]
            for finding in sorted(items,key=lambda x:importance.get(x.level,4)):
                label={'critical':'CRÍTICO','warning':'ATENÇÃO','info':'INFORMATIVO','ok':'NORMAL'}.get(finding.level,'STATUS')
                cards.append({'title':f'{label}  •  {finding.title}',
                     'rows':[('O que foi observado',finding.summary),
                             ('Evidência técnica',finding.technical),
                             ('Recomendação',finding.action)]})
            self.diag_cards.render(cards)
            self._diagnosis_signature=sig
            self._diagnosis_last_render=now
            self.last_finding_hash=repr(sig)
            summary=[x for x in items if x.level in ('critical','warning')]
            if not summary:summary=[x for x in items if x.level in ('info','ok')]
            base.set_text(self.summary,'\n\n'.join(f'● {x.title}\n{x.summary}' for x in summary[:5]) or
                          'Sem alterações identificadas nos indicadores disponíveis.')

    def capture_sensor_details(self):
        result = self.power_detail
        if not result:return
        try:
            from osreview.ui_cards import power_cards
            current = power_cards(result)
            summary = triage(result)
            temps=temperature_readings(result); power=power_readings(result)
            thresholds=temperature_thresholds(result)
            introduction={'title':'RESUMO DA COLETA VALIDADA',
                'rows':[('Situação',summary['status']),
                        ('Última captura',timestamp_of(result)),
                        ('Temperatura CPU',temps['CPU'].display() if temps['CPU'] else 'Indisponível'),
                        ('Temperatura SSD',temps['Disco'].display() if temps['Disco'] else 'Indisponível'),
                        ('Maior valor real', (temps['Geral'].display()+' — '+temps['Geral'].provenance()) if temps['Geral'] else 'Indisponível'),
                        ('Limite de aviso SSD',f"{thresholds['warning']:.0f} °C (não é leitura atual)" if 'warning' in thresholds else 'Indisponível'),
                        ('Limite crítico SSD',f"{thresholds['critical']:.0f} °C (não é leitura atual)" if 'critical' in thresholds else 'Indisponível'),
                        ('Potência CPU Package',power['cpu_package'].display('W') if power['cpu_package'] else 'Indisponível'),
                        ('Temperaturas reais disponíveis',summary['valid_temperatures'])] +
                        [('Orientação',x) for x in summary['findings'][:2]],
                'hint':'Limites de aviso/crítico do NVMe e Distance to TjMax não entram nos medidores de temperatura atual.'}
            view=getattr(self,'sensor_section_var',None)
            choice=view.get() if view else 'Resumo'
            if choice=='Resumo':
                current=[card for card in current if card['title'] in ('MONITORAMENTO ENERGÉTICO','COBERTURA TÉRMICA REAL','DIAGNÓSTICO DO MOTOR DE SENSORES')]
            elif choice=='CPU':
                current=[card for card in current if card['title']=='CPU']
            elif choice=='GPU':
                current=[card for card in current if card['title']=='GPU']
            elif choice=='SSD / HD':
                current=[card for card in current if card['title']=='SSD / HD']
            elif choice=='Fonte / energia':
                current=[card for card in current if any(token in card['title'] for token in ('ENERGÉTICO','BATERIA','FONTE','PSU'))]
            self.power_cards.render([introduction]+current)
            self._sensor_details_initialized=True
            self.sensor_refresh_note.configure(text=('Detalhes capturados; a posição de rolagem é preservada.' if self._sensor_detail_frozen
                                                     else 'Detalhes em atualização automática; posição de rolagem preservada.'))
        except Exception:
            LOG.exception('Falha renderizando detalhes térmicos')

    def open_sensor_explorer(self):
        explorer=self.sensor_explorer_window
        if explorer is not None and explorer.winfo_exists():
            explorer.lift();explorer.focus_force();return
        self.sensor_explorer_window=SensorExplorer(self,lambda:self.power_detail)

    def _live_sensor_tick(self):
        if not self.shutdown.is_set():
            if not self._sensor_refresh_running:
                self._sensor_refresh_running=True
                def worker():
                    try:self.v05_events.put(('power',collect_energy_sensors(),None))
                    except Exception as exc:self.v05_events.put(('power',None,str(exc)))
                    finally:self._sensor_refresh_running=False
                threading.Thread(target=worker,daemon=True,name='osreview-energy-refresh').start()
            self.after(5500,self._live_sensor_tick)

    def report_callback_exception(self, exc, value, tb):
        """Keep the GUI open and capture failures in after()/button callbacks."""
        log_tk_error(exc, value, tb)
        try:
            self.left_status.configure(text='Falha de interface registrada em osreview.log')
        except Exception:
            pass

    def export_support_bundle(self):
        if not messagebox.askyesno('Pacote de suporte OSReview',
            'Criar ZIP local com log de abertura e estado dos sensores?\n'
            'O relatório será mascarado automaticamente, mas revise antes de enviar.'):
            return
        path = filedialog.asksaveasfilename(title='Salvar pacote de suporte',
            defaultextension='.zip', filetypes=[('Pacote de suporte','*.zip')],
            initialfile='OSReview_suporte.zip')
        if not path:
            return
        try:
            out = export_support_zip(path, self.power_detail)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Falha ao exportar',str(exc))
            return
        messagebox.showinfo('Pacote criado',f'Arquivo criado em:\n{out}\n\nRevise o conteúdo antes de compartilhar.')

    def export_sensor_log(self):
        # Never upload automatically. The user chooses a local location and may
        # inspect the report before sharing with a technician.
        if not self.power_detail:
            messagebox.showinfo('OSReview — Sensores',
                'Ainda não há uma leitura para exportar. Clique Atualizar sensores.'); return
        if not messagebox.askyesno('Exportar log local de sensores',
            'O relatório contém nomes e modelos dos componentes, leituras e erros do coletor. '
            'Caminhos de usuário, IPs e MACs serão mascarados. '
            'Revise o arquivo antes de compartilhar. Continuar?'):
            return
        path = filedialog.asksaveasfilename(title='Salvar diagnóstico dos sensores OSReview',
            defaultextension='.json',filetypes=[('Diagnóstico JSON','*.json')],
            initialfile='OSReview_diagnostico_sensores.json')
        if not path: return
        try:
            out=write_report(self.power_detail,path)
        except (OSError,ValueError) as exc:
            messagebox.showerror('Falha ao salvar log',str(exc));return
        messagebox.showinfo('Diagnóstico salvo',
            f'Relatório criado em:\n{out}\n\nRevise o conteúdo antes de compartilhar.')

    def restart_sensor_motor(self):
        if not messagebox.askyesno('Reiniciar coletor de sensores',
            'Reiniciar apenas a ponte local do OSReview? Nenhum serviço ou driver do Windows será alterado.'):
            return
        def work():
            try:
                from osreview.services.sensor_runtime import runtime
                runtime.stop()
                runtime.start()
                import time
                time.sleep(3)
                result=collect_energy_sensors()
                self.v05_events.put(('power',result,None))
            except (OSError,RuntimeError,ValueError) as exc:
                self.v05_events.put(('power',None,str(exc)))
        threading.Thread(target=work,daemon=True,name='osreview-sensors-restart').start()

    def confirm_gemini(self):
        question=self.question.get('1.0','end').strip()
        if len(question)<4:
            messagebox.showwarning('Pergunta','Digite uma pergunta antes de consultar.');return
        if not messagebox.askyesno('Enviar pergunta para Gemini',
                'Enviar SOMENTE sua pergunta à API Gemini? Nenhum evento, inventário ou informação da rede será incluído automaticamente.\n\nA API pode ter limites ou cobranças.'):
            return
        base.set_text(self.ai_answer,'Consultando IA (pode demorar conforme serviço e conexão)...')
        self._start_v05_job('gemini',ask_gemini,self.gemini_key.get(),question,'',self.use_web.get())

    def request_analysis(self):
        super().request_analysis()
        if hasattr(self,'diagnostic_state'):
            self.diagnostic_state.configure(text='ANÁLISE EM ANDAMENTO · Atualizando métricas, serviços e sensores...',fg=base.BLUE)
        self._start_v05_job('background',collect_background_activity)
        if os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('power',collect_energy_sensors)

    def _periodic_background(self):
        if not self.shutdown.is_set() and os.environ.get('OSREVIEW_SAFE_MODE') != '1':
            self._start_v05_job('background',collect_background_activity)
            self.after(65000,self._periodic_background)

    def toggle_theme(self):
        self.apply_theme('light' if self.config_store.data.get('theme','dark')=='dark' else 'dark')

    def apply_theme(self, mode='dark', accent=None, save=True):
        mode='light' if mode=='light' else 'dark'
        accent=accent or self.config_store.data.get('accent_theme','graphite')
        if accent not in THEMES:accent='graphite'
        old={k:getattr(base,k) for k in THEME_KEYS}
        new=palette(mode,accent)
        mapping={old[k].lower():new[k] for k in old}
        for k,v in new.items():setattr(base,k,v)
        self._recolor_widget(self, mapping)
        try:
            self._style_tree()
            style=ttk.Style(self)
            style.map('OS.Treeview',
                      background=[('selected',new['PANEL2'])],
                      foreground=[('selected',new['WHITE'])])
            style.configure('Vertical.TScrollbar',background=new['PANEL2'],troughcolor=new['BG'],
                            arrowcolor=new['MUTED'],bordercolor=new['EDGE'],relief='flat')
            style.map('Vertical.TScrollbar',background=[('active',new['ACCENT'])])
            style.configure('TCombobox',fieldbackground=new['PANEL2'],background=new['PANEL2'],
                            foreground=new['WHITE'],arrowcolor=new['MUTED'])
        except tk.TclError:pass
        if getattr(self,'theme_var',None):self.theme_var.set(mode)
        if getattr(self,'accent_var',None):self.accent_var.set(accent)
        if save:
            self.config_store.set('theme',mode)
            self.config_store.set('accent_theme',accent)
        for widget in ('hw_cards','board_cards','net_cards','power_cards','bg_cards'):
            view=getattr(self,widget,None)
            if view and view.current:view.render(view.current)
        for gauge in ('gauge_download','gauge_upload'):
            g=getattr(self,gauge,None)
            if g:
                g.color=new['GREEN'] if gauge=='gauge_download' else new['BLUE']
                g.draw()
        if self.latest:
            self._draw_graph()
            self._update_telemetry()

    def _recolor_widget(self, widget, mapping):
        if widget.winfo_class() not in ('TCombobox','Treeview','Treeview.Heading'):
            for key in ('background','foreground','activebackground','activeforeground',
                        'selectcolor','highlightbackground','insertbackground','selectbackground',
                        'troughcolor'):
                try:
                    color=widget.cget(key)
                    if isinstance(color,str) and color.lower() in mapping:
                        widget.configure(**{key:mapping[color.lower()]})
                except (tk.TclError,KeyError,ValueError):pass
        for child in widget.winfo_children():self._recolor_widget(child,mapping)

    def set_compact(self, enabled: bool):
        enabled=bool(enabled)
        if enabled==self._compact:return
        self._compact=enabled
        if enabled:
            self._full_geometry=self.geometry()
            self.root_grid.pack_forget()
            self.compact.pack(fill='both',expand=True)
            self.minsize(350,230)
            self.geometry('430x345')
        else:
            self.compact.pack_forget()
            self.root_grid.pack(fill='both',expand=True)
            self.minsize(980,600)
            self.geometry(self._full_geometry)
        self.config_store.set('compact_mode',enabled)
        self._update_mini()

    def toggle_compact(self):self.set_compact(not self._compact)

    def save_hover_option(self):
        val=bool(self.hover_var.get())
        self.config_store.set('tray_hover_popup',val)
        if not val:self._hide_hover()

    def _show_hover(self):
        # Only emitted by the actual Windows tray icon callback.
        if platform.system()!='Windows':return
        self._hover_active=True
        self._hover_shown_at=time.monotonic()
        self._hover_last=self._hover_shown_at
        self._update_mini()
        x,y=self.winfo_pointerxy()
        screen_w, screen_h=self.winfo_screenwidth(),self.winfo_screenheight()
        x=min(max(0,x-288),max(0,screen_w-318))
        y=min(max(0,y-249),max(0,screen_h-243))
        self.popup.geometry(f'310x236+{x}+{y}')
        self.popup.deiconify()
        self.popup.lift()

    def _hide_hover(self):
        self._hover_active=False
        if hasattr(self,'popup'):self.popup.withdraw()

    def _update_mini(self):
        s=self.latest or {}
        def pct(key):
            n=s.get(key)
            return f'{n:.0f}%' if isinstance(n,(int,float)) else 'Indisponível'
        def temp(value):
            return f'{value:.1f} °C' if isinstance(value,(int,float)) else 'Indisponível'
        cpu_temp=s.get('cpu_temp_c')
        if cpu_temp is None and self.power_detail:
            from datetime import datetime
            try:
                age=(datetime.now()-datetime.fromisoformat(
                    str(self.power_detail.get('collected_at','')))).total_seconds()
            except (TypeError,ValueError):
                age=float('inf')
            if 0 <= age <= 50:
                measured=temperature_readings(self.power_detail)['CPU']
                if measured:
                    cpu_temp=measured.value
        result={'cpu':pct('cpu_percent'),'ram':pct('memory_percent'), 'temp':temp(cpu_temp),
                'gpu':pct('gpu_percent'), 'disk':pct('disk_percent'),
                'net':f"↓{s.get('net_recv_mb',0):.1f} / ↑{s.get('net_sent_mb',0):.1f} MB/s"}
        for key,label in getattr(self,'mini_labels',{}).items():label.configure(text=result.get(key,'Indisponível'))
        for key,label in getattr(self,'hover_values',{}).items():label.configure(text=result.get(key,'Indisponível'))

    def _update_telemetry(self):
        super()._update_telemetry()
        # A source that reports a fixed frequency is labelled as such; no
        # artificial variation or unmeasured power is inserted.
        from datetime import datetime
        try:
            freshness=(datetime.now()-datetime.fromisoformat(
                str((self.power_detail or {}).get('collected_at','')))).total_seconds()
        except (TypeError,ValueError):freshness=float('inf')
        recent=0<=freshness<=50
        clocks=clock_readings(self.power_detail) if recent else {'CPU':None,'GPU':None}
        temps=temperature_readings(self.power_detail) if recent else {'CPU':None}
        watts=power_readings(self.power_detail) if recent else {'gpu':None}
        mhz=clocks['CPU'].value if clocks['CPU'] else self.latest.get('cpu_freq_mhz')
        if isinstance(mhz,(int,float)) and mhz>0:
            self._cpu_clock_samples.append(float(mhz))
            low,high=min(self._cpu_clock_samples),max(self._cpu_clock_samples)
            trend=(f'Faixa {low:.0f}–{high:.0f} MHz' if high-low>=max(50,mhz*.03) else
                   'Sem variação observada' if len(self._cpu_clock_samples)>=3 else
                   'Amostrando frequência')
            source='sensor' if clocks['CPU'] else 'API do Windows'
            freq=f'{mhz:.0f} MHz'
        else:
            trend='Frequência indisponível';source='';freq='Clock n/d'
        temperature=temps['CPU'].value if temps['CPU'] else self.latest.get('cpu_temp_c')
        thermal=f'{temperature:.1f} °C' if isinstance(temperature,(int,float)) else 'Temp. n/d'
        self.metrics['cpu'][1].configure(text=f'{freq} · {thermal}\n{trend} · {source}'.strip(' ·'))
        if recent and self.latest.get('gpu_percent') is None:
            rows=(self.power_detail.get('groups') or {}).get('GPU',[])
            observed=next((r for r in rows if r.get('name','').casefold()=='d3d 3d' and
                r.get('type','').casefold()=='load' and isinstance(r.get('value'),(int,float))),None)
            if observed:self.metrics['gpu'][0].configure(text=f'{observed["value"]:.1f}%')
        gpu_clock=f'{clocks["GPU"].value:.0f} MHz' if clocks['GPU'] else 'n/d'
        gpu_power=watts['gpu'].display('W') if watts['gpu'] else (
            f"{self.latest['gpu_power_w']:.1f} W" if isinstance(self.latest.get('gpu_power_w'),(int,float)) else 'Não medido')
        gpu_name=(self.inventory['gpus'][0]['name'] if self.inventory and self.inventory.get('gpus') else
                  self.latest.get('gpu_name','GPU'))
        self.metrics['gpu'][1].configure(text=f'{str(gpu_name)[:24]}\nClock {gpu_clock} · {gpu_power}')
        self._update_mini()

    def exit_app(self):
        if hasattr(self,'popup'):self._hide_hover()
        fps_session.stop()
        from osreview.services.sensor_runtime import runtime
        runtime.stop()
        super().exit_app()


def main():
    OSReviewAppV5().mainloop()
