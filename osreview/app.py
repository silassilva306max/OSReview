"""OSReview 0.3 — Tk dark dashboard, local diagnostics and voluntary benchmarks."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import json
import os
import webbrowser
import platform
import queue
import threading
import time
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from typing import Any

from osreview import __version__
from osreview.services.benchmark import cpu_benchmark, memory_benchmark, BenchmarkCancelled
from osreview.services.configuration import ConfigStore, configure_system_startup, get_system_startup_status
from osreview.services.diagnostics import DiagnosticsEngine
from osreview.services.history import HistoryStore
from osreview.services.system_monitor import SystemMonitor
from osreview.services.tray import TrayController
from osreview.services.windows_health import collect_windows_health
from osreview.services.windows_inventory import collect_inventory
from osreview.services.event_intelligence import collect_events
from osreview.services.software_updates import scan_upgrades
from osreview.services.windows_update_agent import scan_pending_windows_updates
from osreview.services.safe_cleanup import preview_cleanup, clean_category
from osreview.services.online_ai import analyze_event, build_sanitized_event_payload

BG = '#0F131A'
SIDEBAR = '#151A22'
PANEL = '#1A212B'
PANEL2 = '#202A36'
EDGE = '#2E3946'
WHITE = '#F3F6FA'
MUTED = '#93A2B3'
RED = '#F16A64'
GREEN = '#6ED6A5'
BLUE = '#64B5FF'
PURPLE = '#B79AF7'
YELLOW = '#F2C16D'
FONT = 'Segoe UI'


def ui_label(parent, text='', size=11, color=WHITE, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=kwargs.pop('bg', PANEL), fg=color,
                    font=(FONT, size, 'bold' if bold else 'normal'), **kwargs)


def ui_button(parent, text, action, accent=False, width=None):
    options = {'width': width} if width else {}
    return tk.Button(parent, text=text, command=action, font=(FONT, 10, 'bold'),
                     bg=RED if accent else PANEL2, fg='#11151A' if accent else WHITE,
                     activebackground='#FD8580' if accent else EDGE, activeforeground=WHITE,
                     relief='flat', bd=0, highlightthickness=0, padx=14, pady=9, cursor='hand2', **options)


def text_area(parent, height=8):
    t = ScrolledText(parent, height=height, wrap='word', bg=BG, fg=WHITE,
                     insertbackground=WHITE, selectbackground=EDGE,
                     borderwidth=0, relief='flat', font=(FONT, 10), padx=12, pady=10)
    t.configure(state='disabled')
    return t


def set_text(widget, text):
    widget.configure(state='normal')
    widget.delete('1.0', 'end')
    widget.insert('end', text)
    widget.configure(state='disabled')


class OSReviewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'OSReview | Monitoramento & Diagnóstico — {__version__}')
        self.geometry('1390x865')
        self.minsize(1130, 770)
        self.configure(bg=BG)
        try:
            base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
            self.window_icon = tk.PhotoImage(file=str(base / 'assets' / 'osreview.png'))
            self.iconphoto(True, self.window_icon)
        except (OSError, tk.TclError):
            pass
        self.protocol('WM_DELETE_WINDOW', self.close_or_hide)
        self.config_store = ConfigStore()
        self.store = HistoryStore()
        self.engine = DiagnosticsEngine()
        self.monitor = SystemMonitor()
        self.events: queue.Queue = queue.Queue()
        self.shutdown = threading.Event()
        self.bench_stop = threading.Event()
        self.bench_running = False
        self.latest: dict[str, Any] | None = None
        self.procs: list[dict[str, Any]] = []
        self.health: dict[str, Any] | None = None
        self.inventory: dict[str, Any] | None = None
        self.event_data: dict[str, Any] | None = None
        self.upgrade_data: dict[str, Any] | None = None
        self.pending_windows_updates = None
        self.selected_event = None
        self.findings = []
        self.cpu_history: deque[float] = deque(maxlen=65)
        self.ram_history: deque[float] = deque(maxlen=65)
        self.last_alert: dict[str, float] = {}
        self.alert_streak: dict[str, int] = {}
        self.last_finding_hash = ''
        self.selected = 'dashboard'
        self.tabs: dict[str, tk.Frame] = {}
        self.navbuttons: dict[str, tk.Button] = {}
        self.metrics: dict[str, tuple[tk.Label, tk.Label, tk.Canvas]] = {}
        self.tray = TrayController(self.events)

        self._style_tree()
        self._layout()
        self.switch('dashboard')
        safe_mode = os.environ.get('OSREVIEW_SAFE_MODE') == '1'
        if not safe_mode:
            self.tray.start()
        threading.Thread(target=self._sampling_worker, daemon=True, name='osreview-monitor').start()
        if not safe_mode:
            threading.Thread(target=self._health_worker, daemon=True, name='osreview-health').start()
            threading.Thread(target=self._inventory_worker, daemon=True, name='osreview-inventory').start()
            threading.Thread(target=self._event_worker, daemon=True, name='osreview-eventlog').start()
        self.after(120, self._process_events)

    def _style_tree(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('OS.Treeview', background=PANEL, fieldbackground=PANEL, foreground=WHITE,
                        borderwidth=0, relief='flat', rowheight=30, font=(FONT, 10))
        style.configure('OS.Treeview.Heading', background=PANEL2, foreground=WHITE,
                        relief='flat', borderwidth=0, font=(FONT, 10, 'bold'))
        style.map('OS.Treeview', background=[('selected', '#34465A')], foreground=[('selected', WHITE)])

    def _layout(self):
        self.root_grid = tk.Frame(self, bg=BG)
        self.root_grid.pack(fill='both', expand=True)
        sidebar = tk.Frame(self.root_grid, bg=SIDEBAR, width=220)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        logo = tk.Frame(sidebar, bg=SIDEBAR)
        logo.pack(fill='x', padx=19, pady=(22, 4))
        ui_label(logo, '●', 24, RED, bold=True, bg=SIDEBAR).pack(side='left')
        ui_label(logo, 'OSReview', 24, WHITE, bold=True, bg=SIDEBAR).pack(side='left', padx=6)
        ui_label(sidebar, f'SYSTEM INTELLIGENCE  ·  v{__version__}', 8, MUTED, bg=SIDEBAR).pack(anchor='w', padx=24, pady=(0, 10))
        nav = [
            ('▦', 'Visão geral', 'dashboard'),
            ('◈', 'Diagnóstico', 'diagnostics'),
            ('▥', 'Benchmark', 'benchmark'),
            ('▣', 'Hardware / GPUs', 'hardware'),
            ('⚠', 'Eventos / IA', 'events'),
            ('◆', 'Segurança', 'security'),
            ('↻', 'Atualizações', 'updates'),
            ('✚', 'Central de soluções', 'solutions'),
            ('≡', 'Processos', 'processes'),
            ('⊞', 'Windows / Serviços', 'windows'),
            ('◷', 'Histórico', 'history'),
            ('⚙', 'Configurações', 'settings'),
        ]
        for glyph, label, key in nav:
            b = tk.Button(sidebar, text=f'   {glyph}     {label}', anchor='w', relief='flat', bd=0,
                          bg=SIDEBAR, fg=MUTED, font=(FONT, 10, 'bold'), padx=12, pady=8,
                          activebackground=PANEL2, activeforeground=WHITE, highlightthickness=0,
                          cursor='hand2', command=lambda k=key: self.switch(k))
            b.pack(fill='x', padx=9, pady=1)
            self.navbuttons[key] = b
        tk.Frame(sidebar, bg=EDGE, height=1).pack(fill='x', padx=18, pady=(8, 8))
        ui_label(sidebar, 'PERFIL ATIVO', 9, MUTED, bold=True, bg=SIDEBAR).pack(anchor='w', padx=22)
        self.profile_badge = ui_label(sidebar, '●  DIAGNÓSTICO GERAL', 10, BLUE, bold=True, bg=SIDEBAR)
        self.profile_badge.pack(anchor='w', padx=22, pady=(5, 9))
        self.left_status = ui_label(sidebar, '●  Iniciando sensores...', 9, MUTED, bg=SIDEBAR,
                                    wraplength=175, justify='left')
        self.left_status.pack(side='bottom', anchor='w', padx=20, pady=24)

        body = tk.Frame(self.root_grid, bg=BG)
        body.pack(side='left', fill='both', expand=True)
        head = tk.Frame(body, bg=BG)
        head.pack(fill='x', padx=24, pady=(18, 12))
        ui_label(head, 'Centro de diagnóstico', 22, WHITE, bold=True, bg=BG).pack(side='left')
        self.notice = ui_label(head, 'ANÁLISE LOCAL • SEM ENVIO DE DADOS', 9, GREEN, bold=True, bg=BG)
        self.notice.pack(side='right', padx=(12, 3))

        metric_row = tk.Frame(body, bg=BG, height=112)
        metric_row.pack(fill='x', padx=18, pady=(0, 12))
        metric_row.pack_propagate(False)
        for key, title, color in [
            ('cpu', 'PROCESSADOR', RED), ('ram', 'MEMÓRIA RAM', BLUE),
            ('disk', 'ARMAZENAMENTO', YELLOW), ('gpu', 'GPU / VRAM', PURPLE),
            ('network', 'REDE', GREEN),
        ]:
            outer = tk.Frame(metric_row, bg=PANEL, width=150, highlightbackground=EDGE, highlightthickness=1)
            outer.pack(side='left', fill='both', expand=True, padx=5)
            outer.pack_propagate(False)
            ui_label(outer, title, 9, MUTED, bold=True).pack(anchor='w', padx=14, pady=(10, 3))
            val = ui_label(outer, '—', 19, color, bold=True)
            val.pack(anchor='w', padx=14)
            detail = ui_label(outer, 'Aguardando...', 9, MUTED)
            detail.pack(anchor='w', padx=14, pady=(0, 4))
            bar = tk.Canvas(outer, height=5, bg=EDGE, bd=0, highlightthickness=0)
            bar.pack(fill='x', padx=14, pady=(0, 11))
            self.metrics[key] = (val, detail, bar)
            target = 'hardware' if key == 'gpu' else 'diagnostics'
            for widget in (outer, val, detail, bar):
                widget.bind('<Button-1>', lambda _evt, t=target: self.switch(t))

        self.content = tk.Frame(body, bg=BG)
        self.content.pack(fill='both', expand=True, padx=23, pady=(0, 18))
        self._make_dashboard()
        self._make_diagnostics()
        self._make_benchmark()
        self._make_processes()
        self._make_hardware()
        self._make_events()
        self._make_security()
        self._make_updates()
        self._make_solutions()
        self._make_windows()
        self._make_history()
        self._make_settings()

    def _page(self, key, heading, subtitle):
        page = tk.Frame(self.content, bg=BG)
        self.tabs[key] = page
        top = tk.Frame(page, bg=BG)
        top.pack(fill='x', pady=(0, 14))
        ui_label(top, heading, 18, WHITE, bold=True, bg=BG).pack(anchor='w')
        ui_label(top, subtitle, 10, MUTED, bg=BG).pack(anchor='w', pady=(3, 0))
        return page

    def _panel(self, parent, title, subtitle=''):
        panel = tk.Frame(parent, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
        ui_label(panel, title, 13, WHITE, bold=True).pack(anchor='w', padx=16, pady=(14, 4))
        if subtitle:
            ui_label(panel, subtitle, 9, MUTED, wraplength=540, justify='left').pack(anchor='w', padx=16, pady=(0, 7))
        return panel

    def _make_dashboard(self):
        page = self._page('dashboard', 'Visão geral do dispositivo',
                          'Os mesmos dados da área avançada, explicados para todos os níveis de conhecimento.')
        action = tk.Frame(page, bg=BG)
        action.pack(fill='x', pady=(0, 14))
        ui_button(action, 'Executar diagnóstico', self.request_analysis, True).pack(side='left', padx=(0, 10))
        ui_button(action, 'Salvar leitura', self.save_snapshot).pack(side='left', padx=(0, 10))
        ui_button(action, 'Abrir benchmark', lambda: self.switch('benchmark')).pack(side='left')
        ui_button(action, 'Central de soluções', lambda: self.switch('solutions')).pack(side='left', padx=8)
        cols = tk.Frame(page, bg=BG)
        cols.pack(fill='both', expand=True)
        graph_panel = self._panel(cols, 'MONITORAMENTO EM TEMPO REAL',
                                  'CPU e RAM ao longo das últimas leituras, sem dados simulados.')
        graph_panel.pack(side='left', fill='both', expand=True, padx=(0, 7))
        self.graph = tk.Canvas(graph_panel, bg=BG, height=245, highlightthickness=0)
        self.graph.pack(fill='both', expand=True, padx=16, pady=(4, 12))
        legend = tk.Frame(graph_panel, bg=PANEL)
        legend.pack(fill='x', padx=16, pady=(0, 15))
        ui_label(legend, '● CPU', 10, RED).pack(side='left')
        ui_label(legend, '● RAM', 10, BLUE).pack(side='left', padx=20)
        self.graph_note = ui_label(graph_panel, 'Coletando informações...', 10, MUTED)
        self.graph_note.pack(anchor='w', padx=16, pady=(0, 13))
        right = self._panel(cols, 'DIAGNÓSTICO EXPLICADO', 'Prioridades e ações sugeridas para o uso atual.')
        right.configure(width=390)
        right.pack(side='left', fill='both', padx=(7, 0))
        right.pack_propagate(False)
        self.summary = text_area(right, 18)
        self.summary.pack(fill='both', expand=True, padx=14, pady=(4, 14))
        self.dashboard_modules = {}
        hub = tk.Frame(page, bg=BG)
        hub.pack(fill='x', pady=(10, 0))
        for key, heading, target in [('security', 'SEGURANÇA', 'security'),
                                     ('drivers', 'DISPOSITIVOS', 'hardware'),
                                     ('events', 'EVENTOS', 'events'),
                                     ('apps', 'PROGRAMAS', 'updates')]:
            widget = ui_button(hub, heading + '\nAguardando diagnóstico',
                               lambda t=target: self.switch(t))
            widget.configure(justify='left', anchor='w', wraplength=170, height=2,
                             font=(FONT, 9, 'bold'))
            widget.pack(side='left', fill='x', expand=True, padx=4)
            self.dashboard_modules[key] = widget
        bottom = tk.Frame(page, bg=BG)
        bottom.pack(fill='x', pady=(8, 0))
        ui_label(bottom, 'SIMPLIFICADO', 9, GREEN, bold=True, bg=BG).pack(side='left')
        ui_label(bottom, '    •    ', 9, MUTED, bg=BG).pack(side='left')
        ui_label(bottom, 'AVANÇADO: CPU, GPU, E/S, processos e serviços', 9, PURPLE, bold=True, bg=BG).pack(side='left')

    def _make_diagnostics(self):
        page = self._page('diagnostics', 'Diagnóstico e recomendações',
                          'Indícios e ações sugeridas. Um alerta isolado não confirma defeito físico.')
        tool = tk.Frame(page, bg=BG)
        tool.pack(fill='x', pady=(0, 8))
        ui_button(tool, 'Nova verificação', self.request_analysis, True).pack(side='left')
        ui_button(tool, 'Exportar snapshot', self.save_snapshot).pack(side='left', padx=10)
        self.diag_text = text_area(page, 25)
        self.diag_text.pack(fill='both', expand=True)
        self.diag_text.tag_configure('critical', foreground=RED)
        self.diag_text.tag_configure('warning', foreground=YELLOW)
        self.diag_text.tag_configure('ok', foreground=GREEN)
        self.diag_text.tag_configure('info', foreground=BLUE)
        self.diag_text.tag_configure('title', font=(FONT, 12, 'bold'))

    def _make_benchmark(self):
        page = self._page('benchmark', 'Benchmark integrado',
                          'Testes sintéticos voluntários, com limites de duração e sem estresse prolongado.')
        outer = tk.Frame(page, bg=BG)
        outer.pack(fill='both', expand=True)
        rail = self._panel(outer, 'TIPO DE TESTE')
        rail.configure(width=245)
        rail.pack(side='left', fill='y', padx=(0, 12))
        rail.pack_propagate(False)
        self.bench_type = tk.StringVar(value='CPU — núcleo único')
        for option in ('CPU — núcleo único', 'Memória RAM', 'GPU / VRAM (futuro)', 'Disco SMART (futuro)'):
            tk.Radiobutton(rail, text=option, variable=self.bench_type, value=option,
                           bg=PANEL, fg=WHITE, selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=WHITE, font=(FONT, 10), anchor='w', padx=10,
                           command=self._benchmark_type_changed).pack(fill='x', padx=9, pady=8)
        self.bench_start = ui_button(rail, '▶ Iniciar teste', self.start_benchmark, True)
        self.bench_start.pack(fill='x', padx=12, pady=(22, 9))
        ui_button(rail, '■ Interromper', self.stop_benchmark).pack(fill='x', padx=12, pady=(0, 9))
        ui_button(rail, '↺ Limpar resultado', self.reset_benchmark).pack(fill='x', padx=12)
        ui_label(rail, 'Testes de hardware não provam integridade física.', 9, MUTED,
                 wraplength=202, justify='left').pack(anchor='w', padx=13, pady=25)
        center = self._panel(outer, 'CONFIGURAÇÃO E RESULTADOS',
                             'Escolha uma duração. Todos os controles abaixo alteram o teste de verdade.')
        center.pack(side='left', fill='both', expand=True)
        cfg = tk.Frame(center, bg=PANEL)
        cfg.pack(fill='x', padx=17, pady=(8, 16))
        ui_label(cfg, 'CARGA', 9, MUTED, bold=True).pack(side='left', padx=(0, 10))
        self.bench_size = tk.StringVar(value='Pequena')
        for value in ('Pequena', 'Média', 'Grande'):
            tk.Radiobutton(cfg, text=value, variable=self.bench_size, value=value, bg=PANEL,
                           fg=WHITE, selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=WHITE, font=(FONT, 10), padx=8).pack(side='left', padx=4)
        self.bench_status = ui_label(center, 'Pronto para iniciar', 12, GREEN, bold=True)
        self.bench_status.pack(anchor='w', padx=18, pady=(8, 12))
        self.bench_result = text_area(center, 15)
        self.bench_result.pack(fill='both', expand=True, padx=17, pady=(0, 17))

    def _make_processes(self):
        page = self._page('processes', 'Aplicativos e processos',
                          'Todos os processos acessíveis via sistema, com pesquisa e classificação. Processos protegidos podem ter dados limitados.')
        filters=tk.Frame(page,bg=BG);filters.pack(fill='x',pady=(0,10))
        ui_label(filters,'Filtrar:',10,MUTED,bg=BG).pack(side='left')
        self.proc_search=tk.StringVar(value='')
        search=tk.Entry(filters,textvariable=self.proc_search,width=28,bg=PANEL,fg=WHITE,insertbackground=WHITE)
        search.pack(side='left',padx=(8,18))
        self.proc_search.trace_add('write',lambda *_:self._refresh_processes())
        ui_label(filters,'Ordenar:',10,MUTED,bg=BG).pack(side='left')
        self.proc_sort=tk.StringVar(value='CPU')
        sort=ttk.Combobox(filters,textvariable=self.proc_sort,values=('CPU','RAM','Nome','PID'),state='readonly',width=12)
        sort.pack(side='left',padx=8)
        sort.bind('<<ComboboxSelected>>',lambda _evt:self._refresh_processes())
        self.proc_counter=ui_label(filters,'0 processos',10,MUTED,bg=BG)
        self.proc_counter.pack(side='right')
        cols = ('pid', 'cpu', 'ram', 'state')
        table = tk.Frame(page, bg=BG)
        table.pack(fill='both', expand=True)
        self.proc_tree = ttk.Treeview(table, columns=cols, show='tree headings', style='OS.Treeview')
        self.proc_tree.heading('#0', text='Processo')
        for key, label in [('pid','PID'),('cpu','CPU % total'),('ram','RAM %'),('state','Estado')]:
            self.proc_tree.heading(key, text=label)
        self.proc_tree.column('#0', width=330, minwidth=200)
        for col, width in [('pid',65),('cpu',115),('ram',100),('state',140)]:
            self.proc_tree.column(col, width=width, anchor='center')
        scrollbar = ttk.Scrollbar(table, orient='vertical', command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.proc_tree.pack(side='left', fill='both', expand=True)
        self.proc_note = ui_label(page, 'A porcentagem de CPU dos processos é normalizada pelo número de CPUs lógicas.',
                                   10, MUTED, bg=BG)
        self.proc_note.pack(anchor='w', pady=12)

    def _make_hardware(self):
        page = self._page('hardware', 'Inventário de hardware e GPU integrada',
                          'Intel UHD / Iris, AMD Radeon integrada e NVIDIA. Detecção não é medição de sensores.')
        tools = tk.Frame(page, bg=BG); tools.pack(fill='x', pady=(0, 10))
        ui_button(tools, 'Atualizar inventário', self.request_inventory, True).pack(side='left')
        ui_button(tools, 'Drivers Intel oficiais', lambda: webbrowser.open('https://www.intel.com/content/www/us/en/support/detect.html')).pack(side='left', padx=7)
        ui_button(tools, 'Drivers AMD', lambda: webbrowser.open('https://www.amd.com/pt/support/download/drivers.html')).pack(side='left', padx=7)
        ui_button(tools, 'Drivers NVIDIA', lambda: webbrowser.open('https://www.nvidia.com/pt-br/drivers/')).pack(side='left', padx=7)
        self.hardware_text = text_area(page, 24)
        self.hardware_text.pack(fill='both', expand=True)
        set_text(self.hardware_text, 'Consultando controladores gráficos via WMI...')

    def _make_events(self):
        page = self._page('events', 'Eventos do Windows explicados',
                          'Últimos 7 dias: somente erros e eventos críticos de Sistema e Aplicativo (até 120 registros).')
        tools = tk.Frame(page, bg=BG); tools.pack(fill='x', pady=(0, 9))
        ui_button(tools, 'Recarregar eventos', self.request_events, True).pack(side='left')
        ui_button(tools, 'Interpretar selecionado com IA (opt-in)', self.request_online_ai).pack(side='left', padx=9)
        self.event_status = ui_label(tools, 'Aguardando eventos...', 9, MUTED, bg=BG)
        self.event_status.pack(side='left', padx=6)
        cols = ('time','severity','source','id','title')
        self.event_tree = ttk.Treeview(page, columns=cols, show='headings', height=8, style='OS.Treeview')
        for col, title, width in [('time','Hora',150),('severity','Prioridade',100),('source','Origem',230),('id','ID',55),('title','Interpretação',330)]:
            self.event_tree.heading(col, text=title)
            self.event_tree.column(col, width=width, minwidth=55)
        self.event_tree.pack(fill='both', expand=True)
        self.event_tree.bind('<<TreeviewSelect>>', self._show_selected_event)
        self.event_explain = text_area(page, 11)
        self.event_explain.pack(fill='both', expand=True, pady=(10, 0))
        set_text(self.event_explain, 'Selecione um evento para ler o significado em linguagem simples e recomendações.')

    def _make_security(self):
        page = self._page('security', 'Segurança do computador',
                          'Antivírus detectado, estado do Microsoft Defender e dispositivos com erro.')
        tools = tk.Frame(page, bg=BG); tools.pack(fill='x', pady=(0, 9))
        ui_button(tools, 'Atualizar segurança', self.request_inventory, True).pack(side='left')
        ui_button(tools, 'Abrir Segurança do Windows', lambda: self._open_windows('ms-settings:windowsdefender')).pack(side='left', padx=9)
        ui_button(tools, 'Saiba mais: Microsoft Defender', lambda: webbrowser.open('https://support.microsoft.com/pt-br/windows/security/windows-security/stay-protected-with-the-windows-security-app')).pack(side='left')
        ui_label(page, 'Coleta local: WMI/COM e APIs de eventos; sem execução de PowerShell. '
                 'Assinatura digital: verifique nas propriedades do arquivo distribuído.',
                 9, MUTED, bg=BG, wraplength=980, justify='left').pack(anchor='w', pady=(0, 8))
        self.security_text = text_area(page, 25)
        self.security_text.pack(fill='both', expand=True)
        set_text(self.security_text, 'Verificação de segurança em andamento. Status desconhecido não significa ausência de antivírus.')

    def _make_updates(self):
        page = self._page('updates', 'Atualizações e drivers',
                          'WinGet lista atualizações de programas. Drivers críticos exigem verificação do fabricante.')
        tool = tk.Frame(page, bg=BG); tool.pack(fill='x', pady=(0, 9))
        ui_button(tool, 'Consultar programas (WinGet)', self.request_upgrades, True).pack(side='left')
        ui_button(tool, 'Abrir Windows Update', lambda: self._open_windows('ms-settings:windowsupdate')).pack(side='left', padx=9)
        ui_button(tool, 'Gerenciador de Dispositivos', lambda: self._open_windows('devmgmt.msc')).pack(side='left')
        ui_button(tool, 'Buscar KBs/drivers ofertados', self.request_pending_windows_updates).pack(side='left', padx=9)
        self.updates_text = text_area(page, 24)
        self.updates_text.pack(fill='both', expand=True)
        set_text(self.updates_text, 'Clique em Consultar para verificar atualizações disponíveis de programas. Nenhuma atualização será instalada automaticamente.')

    def _make_solutions(self):
        page = self._page('solutions', 'Central de soluções',
                          'Inspecione primeiro. Ações de limpeza sempre exigem sua confirmação.')
        bar = tk.Frame(page, bg=BG); bar.pack(fill='x', pady=(0, 8))
        ui_button(bar, 'Eventos', lambda: self.switch('events')).pack(side='left')
        ui_button(bar, 'Hardware / drivers', lambda: self.switch('hardware')).pack(side='left', padx=7)
        ui_button(bar, 'Segurança', lambda: self.switch('security')).pack(side='left')
        ui_button(bar, 'Atualizações', lambda: self.switch('updates')).pack(side='left', padx=7)
        p = self._panel(page, 'LIMPEZA SEGURA DE ARQUIVOS TEMPORÁRIOS',
                        'Temp do usuário (somente arquivos com mais de 48h) e cache dos navegadores FECHADOS. Não remove senhas, cookies ou perfis.')
        p.pack(fill='x', pady=(5, 10))
        row = tk.Frame(p, bg=PANEL); row.pack(fill='x', padx=15, pady=12)
        self.cleanup_kind = tk.StringVar(value='Temp (usuário)')
        tk.OptionMenu(row, self.cleanup_kind, 'Temp (usuário)', 'Chrome', 'Edge', 'Firefox').pack(side='left')
        ui_button(row, 'Analisar antes de limpar', self.request_cleanup_preview, True).pack(side='left', padx=10)
        self.cleanup_status = ui_label(p, 'Selecione a categoria e veja quanto espaço poderá ser liberado.', 10, MUTED)
        self.cleanup_status.pack(anchor='w', padx=15, pady=(0, 16))
        self.solutions_text = text_area(page, 13)
        self.solutions_text.pack(fill='both', expand=True)
        set_text(self.solutions_text, 'Diagnósticos e ações sugeridas:\n\n'
                 '• GPU não identificada: abra Hardware e verifique modelo/driver.\n'
                 '• Vídeo genérico ou falhas PnP: consulte o fabricante do dispositivo.\n'
                 '• Falhas de disco: faça backup antes de qualquer reparo.\n'
                 '• Segurança desconhecida: verifique Segurança do Windows.\n'
                 '• Apps desatualizados: abra Atualizações e confirme cada instalação.\n'
                 '• Lentidão: confira Processos, eventos e atualizações em andamento.\n\n'
                 'Nunca desative serviços, apague arquivos de perfil ou baixe drivers de sites de terceiros para corrigir alertas.')

    @staticmethod
    def _open_windows(uri):
        if platform.system() != 'Windows':
            messagebox.showinfo('OSReview', 'Esta ação está disponível no Windows.')
            return
        try:
            if uri == 'devmgmt.msc':
                import subprocess
                subprocess.Popen(['mmc.exe', 'devmgmt.msc'])
            else:
                os.startfile(uri)
        except OSError as exc:
            messagebox.showwarning('Windows', f'Não foi possível abrir: {exc}')

    def request_inventory(self):
        threading.Thread(target=lambda: self.events.put(('inventory', collect_inventory())), daemon=True).start()

    def request_events(self):
        threading.Thread(target=lambda: self.events.put(('eventlogs', collect_events())), daemon=True).start()

    def _inventory_worker(self):
        while not self.shutdown.is_set():
            self.events.put(('inventory', collect_inventory()))
            self.shutdown.wait(170)

    def _event_worker(self):
        while not self.shutdown.is_set():
            self.events.put(('eventlogs', collect_events()))
            self.shutdown.wait(190)

    def request_upgrades(self):
        set_text(self.updates_text, 'Consultando WinGet... Isso pode utilizar a internet e demorar alguns segundos.')
        threading.Thread(target=lambda: self.events.put(('upgrades', scan_upgrades())), daemon=True).start()

    def request_pending_windows_updates(self):
        if not messagebox.askyesno('Consulta Windows Update',
              'Esta consulta pode acessar Windows Update ou WSUS e demorar até 75 segundos. '
              'Apenas pesquisa e lista ofertas; NÃO instala ou baixa atualizações. Continuar?'):
            return
        set_text(self.updates_text, 'Consultando atualizações ofertadas pelo Windows Update/WSUS...')
        threading.Thread(target=lambda: self.events.put(('wua-results', scan_pending_windows_updates())), daemon=True).start()

    def request_cleanup_preview(self):
        kind = self.cleanup_kind.get()
        self.cleanup_status.configure(text='Analisando cache/temp sem apagar arquivos...')
        def worker():
            try:
                self.events.put(('cleanup-preview', kind, preview_cleanup(kind)))
            except Exception as exc:
                self.events.put(('cleanup-error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _cleanup_confirm(self, kind, preview):
        self.cleanup_status.configure(text=f"{kind}: {preview['count']} arquivos / {preview['mb']} MB candidatos (estimativa).")
        if not preview['count']:
            return
        if not messagebox.askyesno('OSReview - confirmar limpeza',
            f"Categoria: {kind}\nArquivos: {preview['count']}\nEspaço estimado: {preview['mb']} MB\n\n"
            'Apenas arquivos do cache permitido serão apagados. A ação não tem desfazer. Confirmar?'):
            return
        def worker():
            try:
                self.events.put(('cleanup-done', kind, clean_category(kind)))
            except Exception as exc:
                self.events.put(('cleanup-error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _recompute_diagnostics(self):
        if not self.latest:
            return
        self.findings = self.engine.analyze(self.latest, self.procs, self.health,
                                            self.inventory, self.event_data, self.pending_windows_updates)
        self._update_diagnostics()

    def _refresh_dashboard_modules(self):
        if not hasattr(self, 'dashboard_modules'):
            return
        d = self.inventory or {}
        defender = d.get('defender') or {}
        protected = defender.get('RealTimeProtectionEnabled') is True
        av_count = len(d.get('antivirus', []))
        sec = 'Proteção ativa' if protected else (f'{av_count} produto(s) detectado(s)' if av_count else 'Status não confirmado')
        errors = len(d.get('devices_with_errors', []))
        drivers = f'{errors} dispositivo(s) com alerta' if errors else ('Sem alertas PnP' if d.get('pnp_query_ok') else 'Aguardando consulta PnP')
        ev = self.event_data
        count = len(ev.get('events', [])) if ev else None
        event_text = f'{count} eventos no período' if count is not None else 'Aguardando logs'
        apps = 'Lista consultada' if self.upgrade_data and self.upgrade_data.get('lines') else 'Verificar atualizações'
        for key, title, value in [('security','SEGURANÇA',sec),('drivers','DISPOSITIVOS',drivers),
                                   ('events','EVENTOS',event_text),('apps','PROGRAMAS',apps)]:
            self.dashboard_modules[key].configure(text=title + '\n' + value)

    def _refresh_hardware(self):
        data = self.inventory or {}
        lines = ['CONTROLADORES DE VÍDEO IDENTIFICADOS PELO WINDOWS (WMI):\n']
        for gpu in data.get('gpus', []):
            lines.extend([f"● {gpu['name']}  [{gpu['type']}]",
                          f"  Fabricante: {gpu['vendor']} | Driver: {gpu['driver_version']}",
                          f"  Estado: {gpu['status']} | Código do dispositivo: {gpu['error_code']}",
                          f"  Resolução atual: {gpu['resolution']}",
                          f"  {gpu['vram_note']}\n"])
        if not data.get('gpus'):
            lines.append('Não foi possível ler as GPUs. Verifique se há driver genérico, falha de WMI ou hardware desativado.')
        if self.latest:
            s = self.latest
            lines += ['\nTELEMETRIA REAL (NVIDIA, se suportada):',
                      f"  Nome lido por NVIDIA SMI: {s['gpu_name']}",
                      f"  Uso: {s['gpu_percent'] if s['gpu_percent'] is not None else 'Indisponível'}",
                      f"  Temperatura: {s['gpu_temp_c'] if s['gpu_temp_c'] is not None else 'Indisponível'}",
                      f"  Potência: {s['gpu_power_w'] if s['gpu_power_w'] is not None else 'Indisponível'}",
                      '  Em GPUs Intel/AMD, uso/temperatura/energia permanecem indisponíveis até integração confiável de sensores.']
        lines += ['\nDISPOSITIVOS COM ESTADO NÃO OK (não significa driver desatualizado):']
        lines += [f"• {x['name']}: {x['status']} [{x['class']}]" for x in data.get('devices_with_errors', [])]
        if not data.get('devices_with_errors'):
            lines.append('Nenhum dispositivo com erro retornado / consulta sem resultado.')
        set_text(self.hardware_text, '\n'.join(lines))

    def _refresh_security(self):
        d = self.inventory or {}
        lines = ['ANTIVÍRUS REGISTRADO NO WINDOWS SECURITY CENTER:']
        av = d.get('antivirus', [])
        if av:
            lines += [f"• {x['name']} (estado bruto {x['state_raw']}; consulte Segurança do Windows para o status efetivo)" for x in av]
        else:
            lines.append('• Nenhum produto retornado. Isso NÃO prova que o sistema está sem antivírus.')
        defender = d.get('defender')
        lines += ['\nMICROSOFT DEFENDER:']
        if defender:
            for field, label in [('AMRunningMode','Modo'),('AntivirusEnabled','Antivírus habilitado'),
                                 ('RealTimeProtectionEnabled','Proteção em tempo real'),
                                 ('AntivirusSignatureAge','Idade da definição (dias)'),
                                 ('AntivirusSignatureVersion','Versão das definições')]:
                lines.append(f"• {label}: {defender.get(field, 'Indisponível')}")
        else:
            lines.append('• Não foi possível consultar Defender: verifique na Segurança do Windows.')
        lines += ['\nRECOMENDAÇÃO:',
                  '• Para a maioria dos usuários, Microsoft Defender integrado e atualizado é uma opção sólida.',
                  '• Evite instalar dois antivírus em tempo real simultaneamente.',
                  '• Atualize o Windows, navegador, programas e mantenha backups.',
                  '• O app não avalia a qualidade de um antivírus apenas pelo nome ou presença.']
        set_text(self.security_text, '\n'.join(lines))

    def _refresh_events(self):
        for child in self.event_tree.get_children():
            self.event_tree.delete(child)
        events = (self.event_data or {}).get('events', [])
        for index, e in enumerate(events):
            self.event_tree.insert('', 'end', iid=str(index), values=(e['time'][:22],e['severity'],e['provider'][:34],e['id'],e['title'][:65]))
        info = (self.event_data or {}).get('error')
        self.event_status.configure(text=f'{len(events)} erros/críticos nos últimos 7 dias | ' + (info or 'Leitura concluída'))

    def _show_selected_event(self, _event=None):
        selected = self.event_tree.selection()
        rows = (self.event_data or {}).get('events', [])
        if not selected:
            return
        idx = int(selected[0])
        if idx >= len(rows):
            return
        self.selected_event = rows[idx]
        e = self.selected_event
        set_text(self.event_explain, f"Evento {e['id']} | {e['provider']} | {e['time']}\n"
                 f"PRIORIDADE: {e['severity'].upper()}\n\n{e['title']}\n\n"
                 f"O que significa: {e['meaning']}\n\nO que fazer: {e['action']}\n\n"
                 f"Mensagem original (apenas local):\n{e['message']}\n\n"
                 'Importante: um único evento não é diagnóstico definitivo. Consulte ocorrências e contexto.')

    def request_online_ai(self):
        e = self.selected_event
        if not e:
            messagebox.showinfo('OSReview', 'Selecione um evento antes de pedir análise online.')
            return
        payload = build_sanitized_event_payload(e)
        if not messagebox.askyesno('Privacidade — consulta opcional de IA',
            'Será enviada pela internet APENAS esta informação, sem o texto original do log, IP ou nome do PC:\n\n'
            + payload + '\n\nA API pode gerar custo. Deseja continuar?'):
            return
        key = simpledialog.askstring('API de IA', 'Cole sua chave de API OpenAI (não será salva):', show='*', parent=self)
        if not key:
            return
        self.event_status.configure(text='Consultando IA após consentimento...')
        self.notice.configure(text='IA ONLINE COM CONSENTIMENTO', fg=YELLOW)
        def worker():
            try:
                answer = analyze_event(key, e)
                self.events.put(('ai-result', e, answer))
            except Exception as exc:
                self.events.put(('ai-error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _make_windows(self):
        page = self._page('windows', 'Windows Update, serviços e eventos',
                          'Consultas locais em modo leitura. Não altera políticas, serviços ou drivers.')
        tools = tk.Frame(page, bg=BG)
        tools.pack(fill='x', pady=(0, 12))
        ui_button(tools, 'Atualizar diagnóstico do Windows', self.request_analysis, True).pack(side='left')
        self.windows_at = ui_label(tools, 'Aguardando verificação...', 10, MUTED, bg=BG)
        self.windows_at.pack(side='left', padx=13)
        self.windows_text = text_area(page, 24)
        self.windows_text.pack(fill='both', expand=True)

    def _make_history(self):
        page = self._page('history', 'Histórico e evolução',
                          'Registros ficam neste computador e incluem versão, métricas e processos observados.')
        tools = tk.Frame(page, bg=BG)
        tools.pack(fill='x', pady=(0, 12))
        ui_button(tools, 'Salvar nova análise', self.save_snapshot, True).pack(side='left')
        ui_button(tools, 'Atualizar lista', self.refresh_history).pack(side='left', padx=10)
        self.history_text = text_area(page, 25)
        self.history_text.pack(fill='both', expand=True)
        self.refresh_history()

    def _make_settings(self):
        page = self._page('settings', 'Preferências e privacidade',
                          'Dados locais por padrão. Somente a consulta opcional de IA envia metadados de evento após consentimento.')
        options = self._panel(page, 'OPÇÕES DO SISTEMA')
        options.pack(fill='x')
        self.var_alert = tk.BooleanVar(value=self.config_store.data['notifications'])
        self.var_tray = tk.BooleanVar(value=self.config_store.data['close_to_tray'])
        self.var_start = tk.BooleanVar(value=get_system_startup_status())
        options_entries = [
            ('Alertas críticos (notificações do sistema quando disponíveis)', self.var_alert, self.set_alert),
            ('Iniciar junto com o sistema — usuário atual', self.var_start, self.set_startup),
        ]
        if platform.system() == 'Windows':
            options_entries.insert(1, ('Minimizar para a bandeja ao fechar (Windows)', self.var_tray, self.set_close_tray))
        for label, var, callback in options_entries:
            tk.Checkbutton(options, text=label, variable=var, command=callback,
                           bg=PANEL, fg=WHITE, selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=WHITE, font=(FONT, 11), anchor='w', padx=16, pady=13).pack(fill='x')
        self.settings_status = ui_label(options, '', 10, MUTED)
        self.settings_status.pack(anchor='w', padx=18, pady=(8, 16))
        meta = self._panel(page, 'INFORMAÇÕES DA VERSÃO')
        meta.pack(fill='x', pady=18)
        ui_label(meta, f'v{__version__} • Diagnóstico local • IA opt-in • Python / Tkinter',
                 10, WHITE).pack(anchor='w', padx=17, pady=(5, 8))
        ui_label(meta, 'Pendente: FPS/frametime, SMART, sensores universais, checagem automática de versões de drivers e apps macOS.',
                 10, MUTED, wraplength=700, justify='left').pack(anchor='w', padx=17, pady=(0, 20))

    def switch(self, key: str):
        for child in self.tabs.values():
            child.pack_forget()
        self.tabs[key].pack(fill='both', expand=True)
        self.selected = key
        for tab, b in self.navbuttons.items():
            b.configure(bg=PANEL2 if tab == key else SIDEBAR,
                        fg=WHITE if tab == key else MUTED)
        if key == 'history':
            self.refresh_history()
        if key == 'windows':
            self.refresh_windows()
        if key == 'hardware':
            self._refresh_hardware()
        if key == 'security':
            self._refresh_security()
        if key == 'events':
            self._refresh_events()

    def _sampling_worker(self):
        while not self.shutdown.is_set():
            try:
                sample = self.monitor.collect().to_dict()
                processes = self.monitor.get_process_snapshot()
                self.events.put(('sample', sample, processes))
            except Exception as exc:
                self.events.put(('error', 'Coleta de sensores', str(exc)))
            self.shutdown.wait(float(self.config_store.data.get('sample_seconds', 3)))

    def _health_worker(self):
        while not self.shutdown.is_set():
            try:
                result = collect_windows_health()
                self.events.put(('windows', result))
            except Exception as exc:
                self.events.put(('error', 'Diagnóstico do Windows', str(exc)))
            self.shutdown.wait(65)

    def request_analysis(self):
        self.notice.configure(text='VERIFICAÇÃO EM ANDAMENTO...', fg=YELLOW)
        threading.Thread(target=lambda: self.events.put(('windows', collect_windows_health())),
                         daemon=True, name='osreview-on-demand').start()

    def _process_events(self):
        for _ in range(30):
            try:
                msg = self.events.get_nowait()
            except queue.Empty:
                break
            kind = msg[0]
            if kind == 'sample':
                self.latest, self.procs = msg[1], msg[2]
                self.cpu_history.append(float(self.latest['cpu_percent']))
                self.ram_history.append(float(self.latest['memory_percent']))
                self.findings = self.engine.analyze(self.latest, self.procs, self.health, self.inventory, self.event_data, self.pending_windows_updates)
                self._update_telemetry()
                self._update_diagnostics()
                self._check_alerts()
            elif kind == 'windows':
                self.health = msg[1]
                self.notice.configure(text='ANÁLISE LOCAL • SEM ENVIO DE DADOS', fg=GREEN)
                self.refresh_windows()
                if self.latest:
                    self.findings = self.engine.analyze(self.latest, self.procs, self.health, self.inventory, self.event_data, self.pending_windows_updates)
                    self._update_diagnostics()
            elif kind == 'inventory':
                self.inventory = msg[1]
                self._refresh_hardware()
                self._refresh_security()
                self._recompute_diagnostics()
                self._refresh_dashboard_modules()
                # Graphics card shows detected adapter even without performance sensors.
                if self.latest:
                    self._update_telemetry()
            elif kind == 'eventlogs':
                self.event_data = msg[1]
                self._refresh_events()
                self._recompute_diagnostics()
                self._refresh_dashboard_modules()
            elif kind == 'upgrades':
                self.upgrade_data = msg[1]
                self._refresh_dashboard_modules()
                d = msg[1]
                set_text(self.updates_text, d.get('status', '') + '\n\n' + '\n'.join(d.get('lines', [])) +
                    '\n\nPara atualizar, confira o fabricante ou execute WinGet manualmente. Nenhuma instalação foi efetuada.')
            elif kind == 'wua-results':
                self.pending_windows_updates = msg[1]
                self._recompute_diagnostics()
                d = msg[1]
                if not d.get('ok'):
                    set_text(self.updates_text, 'Windows Update Agent indisponível: ' + str(d.get('error')))
                else:
                    rows = [f"{d.get('total',0)} atualização(ões) ofertada(s) pelo provedor configurado.",
                            'Não é uma auditoria exaustiva de drivers instalados. Não indica instalação automática.\n']
                    for update in d.get('updates', []):
                        severity = update.get('severity') or 'não definida'
                        rows.append(f"• {update.get('title')} | Tipo: {update.get('type')} | Severidade Microsoft: {severity}")
                    set_text(self.updates_text, '\n'.join(rows))
            elif kind == 'cleanup-preview':
                self._cleanup_confirm(msg[1], msg[2])
            elif kind == 'cleanup-done':
                x = msg[2]
                self.cleanup_status.configure(text=f"{msg[1]}: {x['deleted']} removidos; {x['freed_mb']} MB liberados; {x['errors']} inacessíveis.")
            elif kind == 'cleanup-error':
                self.cleanup_status.configure(text='Falha ou proteção: ' + msg[1], fg=YELLOW)
            elif kind == 'ai-result':
                e, answer = msg[1], msg[2]
                self.event_status.configure(text='Análise online recebida.')
                self.notice.configure(text='CONSULTA ONLINE CONCLUÍDA', fg=GREEN)
                set_text(self.event_explain, f"IA ONLINE • evento {e['id']} / {e['provider']}\n\n{answer}\n\n"
                         'Essa orientação não substitui testes locais nem prova a causa da falha.')
            elif kind == 'ai-error':
                self.event_status.configure(text='Falha na IA online: ' + msg[1], fg=YELLOW)
                self.notice.configure(text='IA ONLINE INDISPONÍVEL', fg=YELLOW)
            elif kind == 'bench-result':
                self.bench_running = False
                self.bench_status.configure(text='Teste concluído', fg=GREEN)
                set_text(self.bench_result, json.dumps(msg[1], ensure_ascii=False, indent=2))
                self.store.append({'type': 'benchmark', 'timestamp_readable': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                                   'result': msg[1], 'version': __version__})
            elif kind == 'bench-stop':
                self.bench_running = False
                self.bench_status.configure(text='Teste interrompido', fg=YELLOW)
            elif kind == 'bench-error':
                self.bench_running = False
                self.bench_status.configure(text='Falha durante o benchmark', fg=RED)
                set_text(self.bench_result, msg[1])
            elif kind == 'error':
                self.left_status.configure(text=f'Falha: {msg[1]}. Consulte o terminal/log.', fg=YELLOW)
            elif kind == 'show':
                self.deiconify()
                self.lift()
                self.focus_force()
            elif kind == 'toggle_alerts':
                self.var_alert.set(not self.var_alert.get())
                self.set_alert()
            elif kind == 'exit':
                self.exit_app()
        if not self.shutdown.is_set():
            self.after(160, self._process_events)

    def _update_telemetry(self):
        s = self.latest
        def fmt(x, unit=''):
            return f'{x:.1f}{unit}' if isinstance(x, (float, int)) else 'Indisp.'
        vals = {
            'cpu': (fmt(s['cpu_percent'], '%'), f"{fmt(s['cpu_freq_mhz'], ' MHz')}  •  {fmt(s['cpu_temp_c'], '°C')}", s['cpu_percent'], RED),
            'ram': (fmt(s['memory_percent'], '%'), f"{s['memory_used_gb']} / {s['memory_total_gb']} GB", s['memory_percent'], BLUE),
            'disk': (fmt(s['disk_percent'], '%'), f"E/S: ↓{s['disk_read_mb_s']} ↑{s['disk_write_mb_s']} MB/s", s['disk_percent'], YELLOW),
            'gpu': (fmt(s['gpu_percent'], '%') if s['gpu_percent'] is not None else ('Detectada' if self.inventory and self.inventory.get('gpus') else '—'), (self.inventory['gpus'][0]['name'][:24] if self.inventory and self.inventory.get('gpus') else 'Sem inventário gráfico'), s['gpu_percent'] or 0, PURPLE),
            'network': (f"↓ {s['net_recv_mb']:.2f}", f"↑ {s['net_sent_mb']:.2f} MB/s", min(s['net_recv_mb'] * 6, 100), GREEN),
        }
        for key, (value, label, pct, color) in vals.items():
            v, d, bar = self.metrics[key]
            v.configure(text=value)
            d.configure(text=label)
            bar.delete('all')
            width = max(bar.winfo_width(), 70)
            bar.create_rectangle(0, 0, width * min(max(pct, 0), 100) / 100, 5,
                                 fill=color, outline='')
        self._draw_graph()
        self._refresh_processes()
        self.left_status.configure(text='●  Monitoramento ativo\n' + datetime.now().strftime('%H:%M:%S'), fg=GREEN)

    def _draw_graph(self):
        c = self.graph
        c.delete('all')
        w, h = max(c.winfo_width(), 120), max(c.winfo_height(), 90)
        x0, x1, y0, y1 = 35, w-12, 12, h-25
        for v in (0, 25, 50, 75, 100):
            y = y1 - (y1-y0) * v / 100
            c.create_line(x0, y, x1, y, fill=EDGE, dash=(2, 4))
            c.create_text(25, y, text=str(v), fill=MUTED, font=(FONT, 8))
        for series, color in ((self.cpu_history, RED), (self.ram_history, BLUE)):
            points = list(series)
            if len(points) < 2:
                continue
            coords = []
            for i, value in enumerate(points):
                coords.extend([x0 + (x1-x0)*i/max(len(points)-1, 1),
                               y1 - (y1-y0)*min(max(value, 0), 100)/100])
            c.create_line(*coords, fill=color, width=2.5, smooth=True)
        if self.latest:
            self.graph_note.configure(text=f"Última leitura: CPU {self.latest['cpu_percent']:.1f}%  |  RAM {self.latest['memory_percent']:.1f}%  |  Swap {self.latest['swap_percent']:.1f}%")

    def _update_diagnostics(self):
        if not self.latest:
            return
        concise = []
        for finding in self.findings:
            if finding.level in ('critical', 'warning', 'info'):
                concise.append(f'● {finding.title}\n{finding.summary}\n\nAção: {finding.action}\n')
        if not concise:
            concise = ['Nenhuma condição crítica identificada pelas métricas disponíveis.\nIsso não descarta falhas ocultas de hardware.']
        set_text(self.summary, '\n'.join(concise[:4]))
        fingerprint = repr([(f.level, f.title, f.summary) for f in self.findings])
        if fingerprint == self.last_finding_hash:
            return
        self.last_finding_hash = fingerprint
        t = self.diag_text
        t.configure(state='normal')
        t.delete('1.0', 'end')
        for f in self.findings:
            t.insert('end', f'● {f.title}\n', (f.level, 'title'))
            t.insert('end', f'{f.summary}\n\n')
            t.insert('end', f'Detalhe técnico: {f.technical}\n')
            t.insert('end', f'O que fazer: {f.action}\n\n' + '─'*68 + '\n\n')
        t.configure(state='disabled')

    def _check_alerts(self):
        critical = {f.title for f in self.findings if f.level == 'critical'}
        for title in list(self.alert_streak):
            if title not in critical:
                self.alert_streak.pop(title, None)
        for title in critical:
            count = self.alert_streak.get(title, 0) + 1
            self.alert_streak[title] = count
            if count >= 3 and self.var_alert.get() and time.time() - self.last_alert.get(title, 0) > 600:
                self.last_alert[title] = time.time()
                self.notice.configure(text=f'ALERTA: {title[:40]}', fg=RED)
                self.tray.notify('OSReview: atenção necessária', title)

    def _refresh_processes(self):
        query=self.proc_search.get().casefold().strip() if hasattr(self,'proc_search') else ''
        rows=[p for p in self.procs if query in str(p.get('name','')).casefold() or query in str(p.get('pid',''))]
        order=self.proc_sort.get() if hasattr(self,'proc_sort') else 'CPU'
        rows.sort(key={'CPU':lambda p:p.get('cpu',0),'RAM':lambda p:p.get('memory',0),
            'Nome':lambda p:p.get('name','').casefold(),'PID':lambda p:p.get('pid',0)}.get(order,lambda p:p.get('cpu',0)),
            reverse=order in ('CPU','RAM'))
        tree=self.proc_tree
        position=tree.yview()[0]
        selected=set(tree.selection())
        focused=tree.focus()
        existing=set(tree.get_children())
        wanted={str(p['pid']) for p in rows}
        for item in existing-wanted:
            tree.delete(item)
        for index,p in enumerate(rows):
            iid=str(p['pid'])
            values=(p['pid'], f"{p['cpu']:.1f}", f"{p['memory']:.1f}", p['status'])
            if iid in existing:
                tree.item(iid,text=p['name'],values=values)
                tree.move(iid,'',index)
            else:
                tree.insert('',index,iid=iid,text=p['name'],values=values)
        surviving=selected & wanted
        if surviving:
            tree.selection_set(*surviving)
        if focused in wanted:
            tree.focus(focused)
        tree.yview_moveto(position)
        if hasattr(self,'proc_counter'):
            self.proc_counter.configure(text=f'{len(rows)} de {len(self.procs)} processos visíveis')

    def refresh_windows(self):
        if not self.health:
            set_text(self.windows_text, 'Aguardando primeira verificação...')
            return
        h = self.health
        if not h.get('supported'):
            set_text(self.windows_text, h.get('message', 'Disponível no Windows 10/11.'))
            return
        lines = [f"Verificado em: {h.get('collected_at','?')}",
                 f"Reinicialização pendente: { {True:'SIM', False:'NÃO', None:'Indisponível'}[h.get('pending_reboot')]}",
                 '\nSERVIÇOS DO SISTEMA (não é obrigatório estarem todos em execução):']
        for s in h.get('services', []):
            lines.append(f"  • {s['label']}: {s['state']}  |  inicialização: {s['start_type']}")
        lines.append('\nPROCESSOS ASSOCIADOS A ATUALIZAÇÕES/MANUTENÇÃO:')
        lines.extend(f"  • {p['name']} (PID {p['pid']})" for p in h.get('update_processes', []))
        if not h.get('update_processes'):
            lines.append('  Nenhum dos processos monitorados foi identificado.')
        lines.append('  Atenção: presença/ausência desses processos NÃO confirma status do Windows Update.')
        lines.append('\nCORREÇÕES INSTALADAS MAIS RECENTES (histórico parcial):')
        for entry in h.get('recent_hotfixes', []):
            lines.append(f"  • {entry.get('HotFixID','?')}  {entry.get('Description','')}")
        if not h.get('recent_hotfixes'):
            lines.append('  Sem informação disponível para esta consulta.')
        lines.append('\nERROS RECENTES NO LOG SYSTEM (últimas 24 horas; até 7 eventos):')
        for e in h.get('errors', []):
            lines.append(f"  • Evento {e.get('Id','?')} / {e.get('ProviderName','?')}: {e.get('Message','').replace(chr(10),' ')[:220]}")
        if not h.get('errors'):
            lines.append('  Nenhum erro retornado (ou leitura não permitida).')
        lines.append('\nPróximos passos: confira Configurações > Windows Update e o Visualizador de Eventos para detalhes.')
        set_text(self.windows_text, '\n'.join(lines))
        self.windows_at.configure(text=f"Última leitura: {h.get('collected_at', '?')}")

    def save_snapshot(self):
        if not self.latest:
            messagebox.showinfo('OSReview', 'Ainda não há leitura disponível.')
            return
        self.store.append({'type': 'snapshot', 'timestamp_readable': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                           'sample': self.latest, 'processes': self.procs,
                           'findings': [vars(f) for f in self.findings], 'gpus': (self.inventory or {}).get('gpus', []),
                           'events_summary': [dict(id=e.get('id'), provider=e.get('provider'), title=e.get('title')) for e in (self.event_data or {}).get('events', [])[:20]],
                           'version': __version__})
        self.notice.configure(text='SNAPSHOT SALVO NO COMPUTADOR', fg=GREEN)
        self.refresh_history()

    def refresh_history(self):
        try:
            records = self.store.load()
        except (OSError, ValueError):
            records = []
        lines = [f'{len(records)} registro(s) local(is) no histórico.\n']
        for rec in records[-25:][::-1]:
            typ = rec.get('type', 'snapshot')
            lines.append(f"[{rec.get('timestamp_readable','?')}]  {typ.upper()} • versão {rec.get('version', '?')}")
            if typ == 'benchmark':
                result = rec.get('result', {})
                lines.append(f"  {result.get('type','Teste')} | {result.get('score_primes_s',result.get('copy_mb_s','?'))} pontos / MB/s")
            else:
                sample = rec.get('sample', {})
                lines.append(f"  CPU {sample.get('cpu_percent','?')}% | RAM {sample.get('memory_percent','?')}%")
        set_text(self.history_text, '\n'.join(lines))

    def _benchmark_type_changed(self):
        self.bench_status.configure(text=f'Selecionado: {self.bench_type.get()}', fg=BLUE)

    def start_benchmark(self):
        if self.bench_running:
            self.bench_status.configure(text='Já existe um teste em andamento.', fg=YELLOW)
            return
        kind = self.bench_type.get()
        if '(futuro)' in kind:
            self.bench_status.configure(text='Este módulo não está implementado na v0.3.0.', fg=YELLOW)
            return
        size = self.bench_size.get()
        self.bench_stop.clear()
        self.bench_running = True
        self.bench_status.configure(text='Teste em execução. Evite iniciar durante trabalho importante.', fg=YELLOW)
        set_text(self.bench_result, f'Teste selecionado: {kind}\nCarga: {size}\n')
        def worker():
            try:
                if kind.startswith('CPU'):
                    result = cpu_benchmark({'Pequena':3, 'Média':5, 'Grande':8}[size], self.bench_stop)
                else:
                    result = memory_benchmark({'Pequena':32, 'Média':64, 'Grande':128}[size], self.bench_stop)
                self.events.put(('bench-result', result))
            except BenchmarkCancelled:
                self.events.put(('bench-stop',))
            except Exception as exc:
                self.events.put(('bench-error', str(exc)))
        threading.Thread(target=worker, daemon=True, name='osreview-benchmark').start()

    def stop_benchmark(self):
        self.bench_stop.set()
        if self.bench_running:
            self.bench_status.configure(text='Interrompendo teste...', fg=YELLOW)

    def reset_benchmark(self):
        if self.bench_running:
            self.stop_benchmark()
        else:
            self.bench_status.configure(text='Pronto para iniciar', fg=GREEN)
            set_text(self.bench_result, '')

    def set_alert(self):
        self.config_store.set('notifications', self.var_alert.get())
        self.settings_status.configure(text='Preferência de alertas salva.')

    def set_close_tray(self):
        self.config_store.set('close_to_tray', self.var_tray.get())
        self.settings_status.configure(text='Preferência de minimização salva.')

    def set_startup(self):
        desired = self.var_start.get()
        ok, msg = configure_system_startup(desired)
        self.settings_status.configure(text=msg, fg=GREEN if ok else YELLOW)
        if not ok:
            self.var_start.set(get_system_startup_status())
        else:
            self.config_store.set('start_with_system', desired)

    def close_or_hide(self):
        if self.tray.available and self.tray.icon and self.var_tray.get():
            self.withdraw()
            return
        self.exit_app()

    def exit_app(self):
        if self.shutdown.is_set():
            return
        self.shutdown.set()
        self.bench_stop.set()
        self.tray.stop()
        self.destroy()


def main():
    OSReviewApp().mainloop()
