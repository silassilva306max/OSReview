"""OSReview 0.3 — Tk dark dashboard, local diagnostics and voluntary benchmarks."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import json
import os
import webbrowser
import platform
import queue
import subprocess
import threading
import time
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from typing import Any

from osreview import __version__
from osreview.services.benchmark import timed_benchmark, BenchmarkCancelled
from osreview.services.configuration import ConfigStore, configure_system_startup, get_system_startup_status
from osreview.services.diagnostics import DiagnosticsEngine
from osreview.services.history import HistoryStore
from osreview.services.hardware_deep import memory_frequency_summary
from osreview.services.system_monitor import SystemMonitor
from osreview.services.tray import TrayController
from osreview.services.windows_health import collect_windows_health
from osreview.services.windows_inventory import collect_inventory
from osreview.services.event_intelligence import collect_events
from osreview.services.event_web_search import BROWSERS, SEARCH_ENGINES, open_event_search
from osreview.services.software_updates import scan_upgrades
from osreview.services.windows_update_agent import scan_pending_windows_updates
from osreview.services.safe_cleanup import preview_cleanup, clean_category
from osreview.services.online_ai import analyze_event, build_sanitized_event_payload
from osreview.services.local_controls import (list_services, change_service,
    close_process_window, terminate_process, process_still_running, reopen_executable)
from osreview.services.app_updates import (check_for_updates, download_installer,
    verify_installer, ReleaseInfo, UpdateCancelled)

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
ACCENT = '#75A9BD'
ACCENT_FG = '#08121A'
ACTIVE_ACCENT = '#A9B8C5'
FONT = 'Segoe UI'


def ui_label(parent, text='', size=11, color=WHITE, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=kwargs.pop('bg', PANEL), fg=color,
                    font=(FONT, size, 'bold' if bold else 'normal'), **kwargs)


def ui_button(parent, text, action, accent=False, width=None):
    options = {'width': width} if width else {}
    return tk.Button(parent, text=text, command=action, font=(FONT, 10, 'bold'),
                     bg=ACCENT if accent else PANEL2, fg=ACCENT_FG if accent else WHITE,
                     activebackground=ACTIVE_ACCENT if accent else EDGE,
                     activeforeground=ACCENT_FG if accent else WHITE,
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


def ram_card_detail(sample: dict[str, Any], inventory: dict | None) -> str:
    available = sample.get('memory_available_gb')
    total = sample.get('memory_total_gb')
    capacity = (f'{available:.1f} / {total:.1f} GB'
                if isinstance(available, (int, float)) and isinstance(total, (int, float))
                else 'Indisponível')
    return f'Disponível: {capacity}\nFreq.: {memory_frequency_summary(inventory)}'


class ScrollablePageContent(tk.Frame):
    """Keep tall page content accessible when the window has little height."""

    def __init__(self, parent, horizontal=False):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, bd=0, highlightthickness=0)
        if horizontal:
            self.hscrollbar = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
            self.canvas.configure(xscrollcommand=self.hscrollbar.set)
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = tk.Frame(self.canvas, bg=BG)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.body.bind('<Configure>', self._update_region)
        self.canvas.bind('<Configure>', self._resize_body)
        self.on_width_change = None

    def _update_region(self, _event=None):
        bounds = self.canvas.bbox('all')
        if bounds is not None:
            self.canvas.configure(scrollregion=bounds)

    def _resize_body(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        if self.on_width_change is not None:
            self.on_width_change(event.width)


class OSReviewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'OSReview | Monitoramento & Diagnóstico — {__version__}')
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f'{min(1390, max(980, screen_width - 40))}x'
                      f'{min(865, max(600, screen_height - 80))}')
        self.minsize(980, 600)
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
        self.bench_samples: list[dict] = []
        self.bench_chart_duration = 180
        self.latest: dict[str, Any] | None = None
        self.procs: list[dict[str, Any]] = []
        self._last_process_scan = 0.0
        self._cached_processes: list[dict[str, Any]] = []
        self._last_closed_app: dict | None = None
        self.service_rows: dict[str, dict] = {}
        self.service_loading = False
        self.app_update_release: ReleaseInfo | None = None
        self.app_update_path: Path | None = None
        self.app_update_checking = False
        self.app_update_downloading = False
        self.app_update_cancel = threading.Event()
        self._app_update_notified = False
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
        self.bind('<Unmap>', self._on_unmap, add='+')

        self._style_tree()
        self._layout()
        self.switch('dashboard')
        self._wheel_targets_cache: dict[str, list[tk.Widget]] = {}
        self._wheel_target: tk.Widget | None = None
        self._wheel_remainder = 0
        self.bind_all('<MouseWheel>', self._route_mouse_wheel, add='+')
        self.bind_all('<Button-4>', self._route_mouse_wheel, add='+')
        self.bind_all('<Button-5>', self._route_mouse_wheel, add='+')
        safe_mode = os.environ.get('OSREVIEW_SAFE_MODE') == '1'
        if not safe_mode:
            self.tray.start()
        threading.Thread(target=self._sampling_worker, daemon=True, name='osreview-monitor').start()
        if not safe_mode:
            threading.Thread(target=self._health_worker, daemon=True, name='osreview-health').start()
            threading.Thread(target=self._inventory_worker, daemon=True, name='osreview-inventory').start()
            threading.Thread(target=self._event_worker, daemon=True, name='osreview-eventlog').start()
        self.after(120, self._process_events)
        if platform.system() == 'Windows' and not safe_mode and self.config_store.data.get('check_app_updates', True):
            self.after(4500, self.check_app_update)

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
        self.main_body = body
        body.pack(side='left', fill='both', expand=True)
        head = tk.Frame(body, bg=BG)
        self.main_header = head
        head.pack(fill='x', padx=24, pady=(18, 12))
        ui_label(head, 'Centro de diagnóstico', 22, WHITE, bold=True, bg=BG).pack(side='left')
        self.notice = ui_label(head, 'MÉTRICAS LOCAIS • ATUALIZAÇÕES OPCIONAIS', 9, GREEN, bold=True, bg=BG)
        self.notice.pack(side='right', padx=(12, 3))

        metric_row = tk.Frame(body, bg=BG, height=112)
        self.metric_row = metric_row
        metric_row.pack(fill='x', padx=18, pady=(0, 12))
        metric_row.pack_propagate(False)
        self.metric_cards = []
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
            outer.bind('<Configure>', lambda event, item=detail:
                       item.configure(wraplength=max(82, event.width - 30), justify='left'))
            self.metric_cards.append((outer, detail))
            bar = tk.Canvas(outer, height=5, bg=EDGE, bd=0, highlightthickness=0)
            bar.pack(fill='x', padx=14, pady=(0, 11))
            self.metrics[key] = (val, detail, bar)
            target = 'hardware' if key == 'gpu' else 'diagnostics'
            for widget in (outer, val, detail, bar):
                widget.bind('<Button-1>', lambda _evt, t=target: self.switch(t))
        metric_row.bind('<Configure>', self._resize_metric_cards)

        self.content_viewport = ScrollablePageContent(body, horizontal=True)
        self.content_viewport.pack(fill='both', expand=True, padx=23, pady=(0, 18))
        self.content_viewport.on_width_change = lambda _width: self._fit_content_page()
        self.content = self.content_viewport.body
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

    def _resize_metric_cards(self, event):
        compact = event.width < 850
        height = 132 if compact else 112
        if int(self.metric_row.cget('height')) != height:
            self.metric_row.configure(height=height)
        for card, detail in self.metric_cards:
            detail.configure(wraplength=max(82, card.winfo_width() - 30),
                             justify='left')

    def _page(self, key, heading, subtitle):
        page = tk.Frame(self.content, bg=BG)
        page.bind('<Configure>', lambda _event: self.after_idle(self._fit_content_page), add='+')
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
        self.dashboard_scroll = ScrollablePageContent(page)
        self.dashboard_scroll.pack(fill='both', expand=True)
        self.dashboard_scroll.on_width_change = self._dashboard_width_changed
        body = self.dashboard_scroll.body
        action = tk.Frame(body, bg=BG)
        self.dashboard_action = action
        action.pack(fill='x', pady=(0, 14))
        ui_button(action, 'Executar diagnóstico', self.request_analysis, True).pack(side='left', padx=(0, 10))
        ui_button(action, 'Salvar leitura', self.save_snapshot).pack(side='left', padx=(0, 10))
        ui_button(action, 'Abrir benchmark', lambda: self.switch('benchmark')).pack(side='left')
        ui_button(action, 'Central de soluções', lambda: self.switch('solutions')).pack(side='left', padx=8)
        cols = tk.Frame(body, bg=BG)
        self.dashboard_columns = cols
        cols.pack(fill='both', expand=True)
        graph_panel = self._panel(cols, 'MONITORAMENTO EM TEMPO REAL',
                                  'CPU e RAM ao longo das últimas leituras, sem dados simulados.')
        self.dashboard_graph_panel = graph_panel
        graph_panel.pack(side='left', fill='both', expand=True, padx=(0, 7))
        self.graph = tk.Canvas(graph_panel, bg=BG, height=245, highlightthickness=0)
        self.graph.pack(fill='both', expand=True, padx=16, pady=(4, 12))
        self.graph.bind('<Configure>', lambda _event: self._draw_graph())
        legend = tk.Frame(graph_panel, bg=PANEL)
        legend.pack(fill='x', padx=16, pady=(0, 15))
        ui_label(legend, '● CPU', 10, RED).pack(side='left')
        ui_label(legend, '● RAM', 10, BLUE).pack(side='left', padx=20)
        self.graph_note = ui_label(graph_panel, 'Coletando informações...', 10, MUTED)
        self.graph_note.pack(anchor='w', padx=16, pady=(0, 13))
        right = self._panel(cols, 'DIAGNÓSTICO EXPLICADO', 'Prioridades e ações sugeridas para o uso atual.')
        self.dashboard_summary_panel = right
        right.configure(width=390)
        right.pack(side='left', fill='both', padx=(7, 0))
        right.pack_propagate(False)
        self.summary = text_area(right, 18)
        self.summary.pack(fill='both', expand=True, padx=14, pady=(4, 14))
        self.dashboard_modules = {}
        hub = tk.Frame(body, bg=BG)
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
        bottom = tk.Frame(body, bg=BG)
        bottom.pack(fill='x', pady=(8, 0))
        ui_label(bottom, 'SIMPLIFICADO', 9, GREEN, bold=True, bg=BG).pack(side='left')
        ui_label(bottom, '    •    ', 9, MUTED, bg=BG).pack(side='left')
        ui_label(bottom, 'AVANÇADO: CPU, GPU, E/S, processos e serviços', 9, PURPLE, bold=True, bg=BG).pack(side='left')

    def _dashboard_width_changed(self, width: int):
        stacked = width < 850
        if getattr(self, '_dashboard_stacked', None) == stacked:
            return
        self._dashboard_stacked = stacked
        graph = self.dashboard_graph_panel
        summary = self.dashboard_summary_panel
        graph.pack_forget()
        summary.pack_forget()
        if stacked:
            graph.pack(fill='x', pady=(0, 8))
            summary.pack(fill='x')
            summary.pack_propagate(True)
        else:
            graph.pack(side='left', fill='both', expand=True, padx=(0, 7))
            summary.configure(width=390)
            summary.pack(side='left', fill='both', padx=(7, 0))
            summary.pack_propagate(False)
        boxes = getattr(self, 'dash_sensor_boxes', ())
        columns = 2 if stacked else 4
        for index, box in enumerate(boxes):
            box.grid(row=index // columns, column=index % columns)
        if boxes:
            for column in range(4):
                self.dash_sensor_area.grid_columnconfigure(column,
                                                            weight=1 if column < columns else 0)

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
                          'CPU de um núcleo ou cópia de RAM, por 3, 5 ou 10 minutos. Compare somente resultados do mesmo método.')
        self.benchmark_scroll = ScrollablePageContent(page)
        self.benchmark_scroll.pack(fill='both', expand=True)
        self.benchmark_scroll.on_width_change = self._benchmark_width_changed
        outer = tk.Frame(self.benchmark_scroll.body, bg=BG)
        outer.pack(fill='both', expand=True)
        rail = self._panel(outer, 'TIPO DE TESTE')
        self.benchmark_rail = rail
        rail.configure(width=245)
        rail.pack(side='left', fill='y', padx=(0, 12))
        rail.pack_propagate(False)
        self.bench_type = tk.StringVar(value='CPU — núcleo único')
        for option in ('CPU — núcleo único', 'Memória RAM'):
            tk.Radiobutton(rail, text=option, variable=self.bench_type, value=option,
                           bg=PANEL, fg=WHITE, selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=WHITE, font=(FONT, 10), anchor='w', padx=10,
                           command=self._benchmark_type_changed).pack(fill='x', padx=9, pady=8)
        self.bench_start = ui_button(rail, '▶ Iniciar teste', self.start_benchmark, True)
        self.bench_start.pack(fill='x', padx=12, pady=(22, 9))
        ui_button(rail, '■ Interromper', self.stop_benchmark).pack(fill='x', padx=12, pady=(0, 9))
        ui_button(rail, '↺ Limpar resultado', self.reset_benchmark).pack(fill='x', padx=12)
        ui_label(rail, 'Teste voluntário e cancelável. Pontuação interna: mediana do desempenho medido; não equivale a Geekbench ou PassMark.',
                 9, MUTED, wraplength=202, justify='left').pack(anchor='w', padx=13, pady=25)
        center = self._panel(outer, 'DESEMPENHO E ESTABILIDADE',
                             'A duração define o tempo real de execução. O gráfico registra a taxa em cada intervalo.')
        self.benchmark_center = center
        center.pack(side='left', fill='both', expand=True)
        cfg = tk.Frame(center, bg=PANEL)
        cfg.pack(fill='x', padx=17, pady=(8, 8))
        ui_label(cfg, 'DURAÇÃO', 9, MUTED, bold=True).pack(side='left', padx=(0, 8))
        self.bench_duration=tk.StringVar(value='3 min')
        ttk.Combobox(cfg,textvariable=self.bench_duration,values=('3 min','5 min','10 min'),
                     state='readonly',width=9).pack(side='left',padx=(0,20))
        ui_label(cfg, 'BLOCO RAM', 9, MUTED, bold=True).pack(side='left', padx=(0, 8))
        self.bench_size=tk.StringVar(value='64 MB')
        ttk.Combobox(cfg,textvariable=self.bench_size,values=('32 MB','64 MB','128 MB'),
                     state='readonly',width=9).pack(side='left')
        self.bench_status = ui_label(center, 'Pronto para iniciar', 12, GREEN, bold=True)
        self.bench_status.pack(anchor='w', padx=18, pady=(3, 7))
        self.bench_progress=ttk.Progressbar(center,mode='determinate',maximum=100)
        self.bench_progress.pack(fill='x',padx=18,pady=(0,10))
        cards=tk.Frame(center,bg=PANEL);cards.pack(fill='x',padx=16)
        self.bench_metrics={}
        for key,title in [('score','PONTUAÇÃO'),('stability','ESTABILIDADE'),
                          ('range','FAIXA MEDIDA'),('duration','TEMPO')]:
            card=tk.Frame(cards,bg=PANEL2,highlightbackground=EDGE,highlightthickness=1)
            card.pack(side='left',fill='x',expand=True,padx=3)
            ui_label(card,title,8,MUTED,True,bg=PANEL2).pack(anchor='w',padx=9,pady=(6,2))
            value=ui_label(card,'—',13,BLUE,True,bg=PANEL2)
            value.pack(anchor='w',padx=9,pady=(0,7))
            self.bench_metrics[key]=value
        self.bench_chart=tk.Canvas(center,height=135,bg=PANEL2,highlightthickness=1,
                                   highlightbackground=EDGE)
        self.bench_chart.pack(fill='x',padx=19,pady=(10,8))
        self.bench_chart.bind('<Configure>',lambda _e:self._draw_bench_chart())
        ui_label(center,'HISTÓRICO DE TESTES LOCAIS',9,MUTED,True).pack(anchor='w',padx=18,pady=(2,4))
        columns=('date','kind','duration','score','stability')
        self.bench_history=ttk.Treeview(center,columns=columns,show='headings',height=4,style='OS.Treeview')
        for key,title,width in [('date','DATA',135),('kind','TESTE',130),('duration','TEMPO',75),
                                ('score','RESULTADO',125),('stability','ESTABILIDADE',95)]:
            self.bench_history.heading(key,text=title)
            self.bench_history.column(key,width=width,anchor='center')
        self.bench_history.pack(fill='x',padx=18,pady=(0,7))
        self.bench_result = text_area(center, 3)
        self.bench_result.pack(fill='both',expand=True,padx=17,pady=(0,12))
        set_text(self.bench_result,'Escolha o teste e a duração. Nenhum benchmark começa automaticamente.')
        self.refresh_bench_history()

    def _benchmark_width_changed(self, width: int):
        stacked = width < 850
        if getattr(self, '_benchmark_stacked', None) == stacked:
            return
        self._benchmark_stacked = stacked
        rail, center = self.benchmark_rail, self.benchmark_center
        rail.pack_forget()
        center.pack_forget()
        if stacked:
            rail.pack(fill='x', pady=(0, 8))
            rail.pack_propagate(True)
            center.pack(fill='x')
        else:
            rail.configure(width=245)
            rail.pack(side='left', fill='y', padx=(0, 12))
            rail.pack_propagate(False)
            center.pack(side='left', fill='both', expand=True)

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
        self.proc_note.pack(anchor='w', pady=(7,3))
        actions=tk.Frame(page,bg=BG);actions.pack(fill='x',pady=(0,3))
        ui_button(actions,'Fechar janela',lambda:self._process_action('close')).pack(side='left',padx=(0,5))
        ui_button(actions,'Forçar encerrar',lambda:self._process_action('terminate')).pack(side='left',padx=5)
        ui_button(actions,'Reabrir último aplicativo',self._reopen_last_app).pack(side='left',padx=5)
        self.proc_action_status=ui_label(page,'Selecione um aplicativo seu. Processos do sistema são protegidos.',
                                         9,MUTED,bg=BG)
        self.proc_action_status.pack(anchor='w')

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
        ui_button(tools, '⛶ Ampliar eventos', self.open_events_expanded).pack(side='left', padx=6)
        search=tk.Frame(page,bg=BG);search.pack(fill='x',pady=(0,5))
        ui_label(search,'Busca:',9,MUTED,bg=BG).pack(side='left')
        self.event_search_engine=tk.StringVar(value='Google')
        ttk.Combobox(search,textvariable=self.event_search_engine,values=list(SEARCH_ENGINES),
                     state='readonly',width=14).pack(side='left',padx=(5,9))
        ui_label(search,'Abrir em:',9,MUTED,bg=BG).pack(side='left')
        self.event_search_browser=tk.StringVar(value='Navegador padrão')
        ttk.Combobox(search,textvariable=self.event_search_browser,values=list(BROWSERS),
                     state='readonly',width=18).pack(side='left',padx=(5,9))
        ui_button(search,'Pesquisar erro selecionado',self.search_selected_event).pack(side='left')
        ui_label(page,'A pesquisa envia apenas ID, origem e interpretação resumida. A mensagem original do log permanece local.',
                 9,MUTED,bg=BG,wraplength=900,justify='left').pack(anchor='w',pady=(0,5))
        self.event_status = ui_label(page, 'Aguardando eventos...', 9, MUTED, bg=BG,
                                     wraplength=900, justify='left')
        self.event_status.pack(anchor='w', pady=(0,5))
        cols = ('time','severity','source','id','title')
        event_frame=tk.Frame(page,bg=BG)
        event_frame.pack(fill='both',expand=True)
        self.event_tree = ttk.Treeview(event_frame, columns=cols, show='headings', height=8, style='OS.Treeview')
        for col, title, width in [('time','Hora',150),('severity','Prioridade',100),('source','Origem',230),('id','ID',55),('title','Interpretação',330)]:
            self.event_tree.heading(col, text=title)
            self.event_tree.column(col, width=width, minwidth=55)
        event_vbar=ttk.Scrollbar(event_frame,orient='vertical',command=self.event_tree.yview)
        event_hbar=ttk.Scrollbar(event_frame,orient='horizontal',command=self.event_tree.xview)
        self.event_tree.configure(yscrollcommand=event_vbar.set,xscrollcommand=event_hbar.set)
        event_vbar.pack(side='right',fill='y')
        event_hbar.pack(side='bottom',fill='x')
        self.event_tree.pack(side='left',fill='both', expand=True)
        self.event_tree.bind('<<TreeviewSelect>>', self._show_selected_event)
        self.event_explain = text_area(page, 11)
        self.event_explain.pack(fill='both', expand=True, pady=(10, 0))
        set_text(self.event_explain, 'Selecione um evento para ler o significado em linguagem simples e recomendações.')

    def open_events_expanded(self):
        popup=tk.Toplevel(self)
        popup.title('OSReview • Eventos do Windows')
        popup.configure(bg=BG)
        popup.geometry('1100x700')
        popup.attributes('-fullscreen',True)
        head=tk.Frame(popup,bg=BG);head.pack(fill='x',padx=16,pady=8)
        ui_label(head,'EVENTOS DO WINDOWS • ERROS E CRÍTICOS',13,WHITE,True,bg=BG).pack(side='left')
        ui_button(head,'Fechar • Esc',popup.destroy).pack(side='right')
        search=tk.Frame(popup,bg=BG);search.pack(fill='x',padx=16,pady=(0,8))
        ui_label(search,'Buscar em:',10,MUTED,bg=BG).pack(side='left')
        ttk.Combobox(search,textvariable=self.event_search_engine,values=list(SEARCH_ENGINES),
                     state='readonly',width=14).pack(side='left',padx=(5,10))
        ttk.Combobox(search,textvariable=self.event_search_browser,values=list(BROWSERS),
                     state='readonly',width=18).pack(side='left',padx=(0,10))
        ui_button(search,'Pesquisar evento selecionado',self.search_selected_event).pack(side='left')
        frame=tk.Frame(popup,bg=BG);frame.pack(fill='both',expand=True,padx=16)
        columns=self.event_tree['columns']
        tree=ttk.Treeview(frame,columns=columns,show='headings',style='OS.Treeview')
        for col in columns:
            tree.heading(col,text=self.event_tree.heading(col,'text'))
            tree.column(col,width=self.event_tree.column(col,'width'),minwidth=55)
        for iid in self.event_tree.get_children():
            tree.insert('','end',iid=iid,values=self.event_tree.item(iid,'values'))
        vbar=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        hbar=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=vbar.set,xscrollcommand=hbar.set)
        vbar.pack(side='right',fill='y')
        hbar.pack(side='bottom',fill='x')
        tree.pack(side='left',fill='both',expand=True)
        detail=text_area(popup,9)
        detail.pack(fill='x',padx=16,pady=(8,14))
        set_text(detail,'Selecione um evento para ler a interpretação.')
        def selected(_event=None):
            ids=tree.selection()
            if ids:
                self.event_tree.selection_set(ids[0])
                self._show_selected_event()
                set_text(detail,self.event_explain.get('1.0','end-1c'))
        tree.bind('<<TreeviewSelect>>',selected)
        popup.bind('<Escape>',lambda _e:popup.destroy())
        popup.focus_force()

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
        own = self._panel(page, 'VERSÃO DO OSREVIEW',
                          'Verifica novas versões. O download e a instalação dependem da sua escolha.')
        own.pack(fill='x', pady=(0, 12))
        self.app_update_status = ui_label(own, f'Versão instalada: {__version__} · Aguardando consulta',
                                          11, MUTED)
        self.app_update_status.pack(anchor='w', padx=16, pady=(5, 8))
        update_actions = tk.Frame(own, bg=PANEL)
        update_actions.pack(fill='x', padx=16, pady=(0, 10))
        ui_button(update_actions, 'Verificar agora', lambda: self.check_app_update(manual=True), True).pack(side='left')
        self.app_update_button = ui_button(update_actions, 'Nenhuma atualização disponível',
                                           self.download_or_install_update)
        self.app_update_button.configure(state='disabled')
        self.app_update_button.pack(side='left', padx=8)
        self.app_update_progress = ttk.Progressbar(own, mode='determinate', maximum=100)
        self.app_update_progress.pack(fill='x', padx=16, pady=(0, 12))
        tool = tk.Frame(page, bg=BG); tool.pack(fill='x', pady=(0, 9))
        ui_button(tool, 'Consultar programas (WinGet)', self.request_upgrades, True).pack(side='left')
        ui_button(tool, 'Abrir Windows Update', lambda: self._open_windows('ms-settings:windowsupdate')).pack(side='left', padx=9)
        ui_button(tool, 'Gerenciador de Dispositivos', lambda: self._open_windows('devmgmt.msc')).pack(side='left')
        tool_more = tk.Frame(page, bg=BG); tool_more.pack(fill='x', pady=(0, 9))
        ui_button(tool_more, 'Buscar KBs/drivers ofertados', self.request_pending_windows_updates).pack(side='left')
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

    def check_app_update(self, manual=False):
        if platform.system() != 'Windows' or self.app_update_checking or self.app_update_downloading:
            return
        self.app_update_checking = True
        self.app_update_button.configure(state='disabled')
        self.app_update_status.configure(text='Verificando novas versões do OSReview...', fg=BLUE)
        def worker():
            try:
                result = check_for_updates(self.config_store.data.get('update_prereleases', True))
                self.events.put(('app-update-check', result, manual))
            except Exception as exc:
                self.events.put(('app-update-error', 'Não foi possível verificar atualizações: ' + str(exc)))
        threading.Thread(target=worker, daemon=True, name='osreview-update-check').start()

    def download_or_install_update(self):
        release = self.app_update_release
        if self.app_update_downloading and self.app_update_path is None:
            self.app_update_cancel.set()
            self.app_update_button.configure(state='disabled')
            self.app_update_status.configure(text='Cancelando download...', fg=YELLOW)
            return
        if release is None or self.app_update_downloading:
            return
        self.app_update_downloading = True
        self.app_update_button.configure(state='disabled')
        if self.app_update_path is None:
            self.app_update_cancel.clear()
            self.app_update_button.configure(text='Cancelar download', state='normal')
            self.app_update_status.configure(text=f'Baixando a versão {release.tag}...', fg=BLUE)
            def worker():
                try:
                    path = download_installer(release, progress=lambda done, total:
                        self.events.put(('app-update-progress', done, total)), stop=self.app_update_cancel)
                    self.events.put(('app-update-ready', path))
                except UpdateCancelled:
                    self.events.put(('app-update-cancelled',))
                except Exception as exc:
                    self.events.put(('app-update-error', 'Download não concluído: ' + str(exc)))
            threading.Thread(target=worker, daemon=True, name='osreview-update-download').start()
        else:
            path = self.app_update_path
            def worker():
                try:
                    if not verify_installer(path, release):
                        raise ValueError('O instalador mudou após o download; baixe novamente.')
                    self.events.put(('app-update-confirm-install', path))
                except Exception as exc:
                    self.events.put(('app-update-error', 'Verificação falhou: ' + str(exc)))
            threading.Thread(target=worker, daemon=True, name='osreview-update-verify').start()

    @staticmethod
    def _is_installed_copy() -> bool:
        if platform.system() != 'Windows' or not getattr(sys, 'frozen', False):
            return False
        try:
            import winreg
            key_path = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\OSReview.Diagnostics_is1'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                folder = winreg.QueryValueEx(key, 'InstallLocation')[0]
            return Path(folder).resolve() == Path(sys.executable).resolve().parent
        except (OSError, ValueError):
            return False

    def _confirm_and_launch_update(self, path: Path):
        release = self.app_update_release
        if release is None:
            return
        extra = ('' if self._is_installed_copy() else
                 '\nEsta cópia parece portátil ou iniciada pelo código-fonte. O instalador não substituirá essa pasta; ele criará ou atualizará uma instalação do OSReview.\n')
        if not messagebox.askyesno('OSReview · instalar atualização',
                f'Instalador {release.tag} baixado e SHA-256 conferido.\n{extra}\n'
                'Aguarde o Avast terminar a análise do arquivo. Você confirma que a análise terminou e deseja abrir o instalador agora?'):
            self.app_update_status.configure(text='Instalador pronto. Aguarde o Avast e clique em Instalar agora.', fg=YELLOW)
            return
        try:
            subprocess.Popen([str(path)], cwd=str(path.parent))
        except OSError as exc:
            self.app_update_status.configure(text=f'Não foi possível abrir o instalador: {exc}', fg=YELLOW)
            return
        self.exit_app()

    def set_app_update_check(self):
        self.config_store.set('check_app_updates', self.var_app_updates.get())
        self.settings_status.configure(text='Consulta de versões na abertura salva. Métricas de hardware permanecem no dispositivo.')

    def set_update_prereleases(self):
        self.config_store.set('update_prereleases', self.var_update_prereleases.get())
        self.settings_status.configure(text='Preferência de versões de teste salva.')

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

    def search_selected_event(self):
        if not self.event_tree.selection():
            messagebox.showinfo('Pesquisar evento', 'Selecione um erro ou evento crítico na lista primeiro.')
            return
        self._show_selected_event()
        try:
            terms=open_event_search(self.selected_event, self.event_search_engine.get(),
                                    self.event_search_browser.get())
        except (OSError, ValueError) as exc:
            messagebox.showwarning('Pesquisar evento', str(exc))
            return
        self.event_status.configure(text=f'Pesquisa aberta: {terms}', fg=BLUE)

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
                          'Diagnóstico local. Serviços de terceiros podem ser iniciados ou parados após confirmação, sem alterar sua configuração.')
        tools = tk.Frame(page, bg=BG)
        tools.pack(fill='x', pady=(0, 12))
        ui_button(tools, 'Atualizar diagnóstico do Windows', self.request_analysis, True).pack(side='left')
        ui_button(tools, 'Listar serviços', self.request_services).pack(side='left',padx=7)
        ui_button(tools, 'Aplicativos e processos', lambda:self.switch('processes')).pack(side='left',padx=7)
        self.windows_at = ui_label(tools, 'Aguardando verificação...', 10, MUTED, bg=BG)
        self.windows_at.pack(side='left', padx=13)
        services=tk.Frame(page,bg=BG);services.pack(fill='both',expand=True)
        cols=('display','status','start_type','manageable')
        self.service_tree=ttk.Treeview(services,columns=cols,show='headings',height=8,style='OS.Treeview')
        for key,title,width in [('display','SERVIÇO',310),('status','ESTADO',110),
                                ('start_type','INÍCIO',100),('manageable','CONTROLE',120)]:
            self.service_tree.heading(key,text=title)
            self.service_tree.column(key,width=width,anchor='w' if key=='display' else 'center')
        self.service_tree.pack(side='left',fill='both',expand=True)
        service_scroll=ttk.Scrollbar(services,orient='vertical',command=self.service_tree.yview)
        service_scroll.pack(side='right',fill='y')
        self.service_tree.configure(yscrollcommand=service_scroll.set)
        actions=tk.Frame(page,bg=BG);actions.pack(fill='x',pady=6)
        ui_button(actions,'Parar serviço selecionado',lambda:self._service_action('stop')).pack(side='left',padx=(0,6))
        ui_button(actions,'Iniciar serviço selecionado',lambda:self._service_action('start')).pack(side='left')
        self.service_action_status=ui_label(page,'Serviços do Windows e de segurança ficam protegidos.',9,MUTED,bg=BG)
        self.service_action_status.pack(anchor='w',pady=(0,5))
        self.windows_text = text_area(page, 8)
        self.windows_text.pack(fill='both',expand=True)

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
                          'Métricas locais. A busca de versões usa a internet ao abrir, se ativada; IA online exige consentimento.')
        options = self._panel(page, 'OPÇÕES DO SISTEMA')
        options.pack(fill='x')
        self.var_alert = tk.BooleanVar(value=self.config_store.data['notifications'])
        self.var_tray = tk.BooleanVar(value=self.config_store.data['close_to_tray'])
        self.var_start = tk.BooleanVar(value=get_system_startup_status())
        self.var_app_updates = tk.BooleanVar(value=self.config_store.data.get('check_app_updates', True))
        self.var_update_prereleases = tk.BooleanVar(value=self.config_store.data.get('update_prereleases', True))
        options_entries = [
            ('Alertas críticos (notificações do sistema quando disponíveis)', self.var_alert, self.set_alert),
            ('Iniciar junto com o sistema — usuário atual', self.var_start, self.set_startup),
            ('Avisar ao abrir sobre novas versões do OSReview',
             self.var_app_updates, self.set_app_update_check),
            ('Incluir versões de teste (release candidates)',
             self.var_update_prereleases, self.set_update_prereleases),
        ]
        if platform.system() == 'Windows':
            options_entries.insert(1, ('Minimizar ou fechar para a bandeja (Windows)', self.var_tray, self.set_close_tray))
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
                 10, MUTED, wraplength=600, justify='left').pack(anchor='w', padx=17, pady=(0, 20))

    def switch(self, key: str):
        for child in self.tabs.values():
            child.pack_forget()
        self.tabs[key].pack(fill='both', expand=True)
        self.selected = key
        self.after_idle(self._show_content_page)
        for tab, b in self.navbuttons.items():
            b.configure(bg=PANEL2 if tab == key else SIDEBAR,
                        fg=WHITE if tab == key else MUTED)
        if key == 'history':
            self.refresh_history()
        if key == 'benchmark':
            self.refresh_bench_history()
            self._draw_bench_chart()
        if key == 'dashboard' and self.latest:
            self._draw_graph()
        if key == 'processes':
            self._refresh_processes()
        if key == 'windows':
            self.refresh_windows()
            if not self.service_rows:self.request_services()
        if key == 'hardware':
            self._refresh_hardware()
        if key == 'security':
            self._refresh_security()
        if key == 'events':
            self._refresh_events()

    def _show_content_page(self):
        self._fit_content_page()
        self.content_viewport.canvas.xview_moveto(0)
        self.content_viewport.canvas.yview_moveto(0)

    def _fit_content_page(self):
        page = self.tabs.get(self.selected)
        if page is None or not page.winfo_exists():
            return
        viewport = self.content_viewport
        canvas = viewport.canvas
        if self.selected == 'power':
            layout_meters = getattr(self, '_layout_sensor_meters', None)
            if layout_meters is not None and layout_meters(canvas.winfo_width()):
                self.after_idle(self._fit_content_page)
        width = max(canvas.winfo_width(), page.winfo_reqwidth())
        height = max(canvas.winfo_height(), page.winfo_reqheight())
        hbar = viewport.hscrollbar
        if width > canvas.winfo_width() + 1:
            if not hbar.winfo_manager():
                hbar.pack(side='bottom', fill='x')
        elif hbar.winfo_manager():
            hbar.pack_forget()
        canvas.itemconfigure(viewport.window, width=width, height=height)
        viewport._update_region()

    @staticmethod
    def _descends_from(widget: tk.Widget, ancestor: tk.Widget) -> bool:
        while widget is not None:
            if widget is ancestor:
                return True
            widget = widget.master
        return False

    @staticmethod
    def _scrollable(widget: tk.Widget) -> bool:
        try:
            first, last = widget.yview()
            return last - first < 0.999
        except (AttributeError, tk.TclError):
            return False

    def _page_wheel_targets(self, key: str) -> list[tk.Widget]:
        cached = self._wheel_targets_cache.get(key)
        if cached is not None and all(item.winfo_exists() for item in cached):
            return cached
        targets: list[tk.Widget] = []
        def collect(widget: tk.Widget):
            canvas = getattr(widget, 'canvas', None)
            if isinstance(canvas, tk.Canvas) and canvas.cget('yscrollcommand') and canvas not in targets:
                targets.append(canvas)
            if isinstance(widget, (tk.Text, ttk.Treeview)):
                targets.append(widget)
                return
            if isinstance(widget, tk.Canvas) and widget.cget('yscrollcommand') and widget not in targets:
                targets.append(widget)
            for child in widget.winfo_children():
                collect(child)
        collect(self.tabs[key])
        outer = getattr(getattr(self, 'content_viewport', None), 'canvas', None)
        if outer is not None:
            targets.append(outer)
        self._wheel_targets_cache[key] = targets
        return targets

    @staticmethod
    def _wheel_distance(widget: tk.Widget, x: int, y: int) -> int:
        left, top = widget.winfo_rootx(), widget.winfo_rooty()
        right, bottom = left + widget.winfo_width(), top + widget.winfo_height()
        dx = max(left - x, 0, x - right)
        dy = max(top - y, 0, y - bottom)
        return dx * dx + dy * dy

    @staticmethod
    def _wheel_ancestor_distance(widget: tk.Widget, target: tk.Widget) -> int:
        distance = 0
        while widget is not None:
            if widget is target:
                return distance
            widget = widget.master
            distance += 1
        return 100000

    def _route_mouse_wheel(self, event):
        widget = event.widget
        if widget.winfo_toplevel() is not self:
            return
        sidebar = getattr(self, 'nav_sidebar', None)
        if sidebar is not None and self._descends_from(widget, sidebar):
            target = getattr(self, 'nav_canvas', None)
        else:
            page = self.tabs.get(self.selected)
            if page is None or not self._descends_from(widget, page):
                return
            if isinstance(widget, ttk.Combobox):
                return
            # Text and Treeview already receive native Tk class wheel bindings.
            if isinstance(widget, (tk.Text, ttk.Treeview)) and self._scrollable(widget):
                return
            candidates = [item for item in self._page_wheel_targets(self.selected)
                          if item.winfo_ismapped() and self._scrollable(item)]
            if not candidates:
                return
            target = min(candidates, key=lambda item:
                         (self._wheel_ancestor_distance(widget, item),
                          self._wheel_distance(item, event.x_root, event.y_root)))
        if target is None or not target.winfo_ismapped() or not self._scrollable(target):
            return
        if target is not self._wheel_target:
            self._wheel_target = target
            self._wheel_remainder = 0
        if getattr(event, 'num', None) in (4, 5):
            steps = -1 if event.num == 4 else 1
        else:
            delta = getattr(event, 'delta', 0)
            if platform.system() == 'Darwin' and delta:
                steps = -1 if delta > 0 else 1
            else:
                self._wheel_remainder += delta
                steps = -int(self._wheel_remainder / 120)
                self._wheel_remainder += steps * 120
        if steps:
            target.yview_scroll(steps, 'units')
            return 'break'

    def _sampling_worker(self):
        while not self.shutdown.is_set():
            try:
                sample = self.monitor.collect().to_dict()
                now=time.monotonic()
                interval=3 if self.selected=='processes' else 12
                if now-self._last_process_scan>=interval or not self._cached_processes:
                    self._cached_processes=self.monitor.get_process_snapshot()
                    self._last_process_scan=now
                processes = self._cached_processes
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
                self.notice.configure(text='MÉTRICAS LOCAIS • ATUALIZAÇÕES OPCIONAIS', fg=GREEN)
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
            elif kind == 'app-update-check':
                self.app_update_checking = False
                result, manual = msg[1], msg[2]
                if result.warning:
                    self.app_update_release = None
                    self.app_update_path = None
                    self.app_update_button.configure(text='Nenhuma atualização verificável', state='disabled')
                    self.app_update_status.configure(text=result.warning, fg=YELLOW)
                elif result.release:
                    self.app_update_release = result.release
                    self.app_update_path = None
                    self.app_update_progress['value'] = 0
                    self.app_update_status.configure(
                        text=f'Nova versão disponível: {result.release.tag} · {result.release.title}', fg=GREEN)
                    self.app_update_button.configure(text='Baixar atualização', state='normal')
                    if not manual and not self._app_update_notified:
                        self._app_update_notified = True
                        if messagebox.askyesno('Atualização do OSReview disponível',
                                f'Encontramos a versão {result.release.tag}. Abrir a tela de atualizações?\n\n'
                                'O download e a instalação dependem da sua escolha.'):
                            self.switch('updates')
                else:
                    self.app_update_release = None
                    self.app_update_path = None
                    self.app_update_button.configure(text='Nenhuma atualização disponível', state='disabled')
                    self.app_update_status.configure(text=f'OSReview {__version__} está atualizado.', fg=GREEN)
            elif kind == 'app-update-progress':
                done, total = msg[1], msg[2]
                self.app_update_progress['value'] = done * 100 / total
                self.app_update_status.configure(text=f'Baixando atualização: {done/1048576:.1f} / {total/1048576:.1f} MiB', fg=BLUE)
            elif kind == 'app-update-ready':
                self.app_update_downloading = False
                self.app_update_path = msg[1]
                self.app_update_progress['value'] = 100
                self.app_update_status.configure(text='Download completo e SHA-256 conferido. Aguarde a análise do Avast.', fg=GREEN)
                self.app_update_button.configure(text='Instalar agora', state='normal')
            elif kind == 'app-update-cancelled':
                self.app_update_downloading = False
                self.app_update_progress['value'] = 0
                self.app_update_status.configure(text='Download cancelado.', fg=MUTED)
                self.app_update_button.configure(text='Baixar atualização', state='normal')
            elif kind == 'app-update-confirm-install':
                self.app_update_downloading = False
                self.app_update_button.configure(state='normal')
                self._confirm_and_launch_update(msg[1])
            elif kind == 'app-update-error':
                self.app_update_checking = False
                self.app_update_downloading = False
                self.app_update_path = None
                self.app_update_status.configure(text=msg[1][:320], fg=YELLOW)
                self.app_update_button.configure(text='Baixar atualização',
                                                 state='normal' if self.app_update_release else 'disabled')
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
            elif kind == 'bench-progress':
                progress=msg[1]
                self.bench_samples=progress['samples']
                self.bench_chart_duration=progress['duration']
                self.bench_progress['value']=100*progress['elapsed']/progress['duration']
                self.bench_status.configure(text=f"Teste em execução · {progress['elapsed']:.0f} / {progress['duration']} s",
                                            fg=BLUE)
                if self.selected=='benchmark':self._draw_bench_chart()
            elif kind == 'bench-result':
                self.bench_running = False
                result=msg[1]
                self.bench_progress['value']=100
                self.bench_samples=result['samples']
                self.bench_chart_duration=result['duration_seconds']
                self.bench_status.configure(text='Teste concluído · resultado salvo localmente', fg=GREEN)
                self.bench_metrics['score'].configure(text=f"{result['score']:,.0f} {result['unit']}")
                self.bench_metrics['stability'].configure(text=f"{result['stability_percent']:.1f}%")
                self.bench_metrics['range'].configure(text=f"{result['min_score']:,.0f}–{result['max_score']:,.0f}")
                self.bench_metrics['duration'].configure(text=f"{result['duration_seconds']//60} min")
                set_text(self.bench_result,result['note'])
                if self.selected=='benchmark':self._draw_bench_chart()
                self.store.append({'type': 'benchmark', 'timestamp_readable': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                                   'result': result, 'version': __version__})
                self.refresh_bench_history()
            elif kind == 'bench-stop':
                self.bench_running = False
                self.bench_status.configure(text='Teste interrompido', fg=YELLOW)
            elif kind == 'bench-error':
                self.bench_running = False
                self.bench_status.configure(text='Falha durante o benchmark', fg=RED)
                set_text(self.bench_result, msg[1])
            elif kind == 'services-list':
                self.service_loading=False
                if msg[2]:
                    self.service_action_status.configure(text='Falha ao listar serviços: '+msg[2],fg=YELLOW)
                else:
                    self.service_rows={row['name']:row for row in msg[1]}
                    for item in self.service_tree.get_children():
                        self.service_tree.delete(item)
                    for row in msg[1]:
                        self.service_tree.insert('','end',iid=row['name'],values=(row['display'],
                            row['status'],row['start_type'],'Permitido' if row['manageable'] else 'Protegido'))
                    self.service_action_status.configure(text=f"{len(msg[1])} serviços listados. Controle apenas de terceiros não protegidos.",fg=MUTED)
            elif kind == 'service-action':
                self.service_action_status.configure(text=msg[1],fg=GREEN if msg[2] else YELLOW)
                self.request_services()
            elif kind == 'process-action':
                action,info,error=msg[1:]
                if error:
                    self.proc_action_status.configure(text=error,fg=YELLOW)
                else:
                    self._last_closed_app=info
                    self.proc_action_status.configure(text=(
                        f"Solicitação enviada para {info['name']} (PID {info['pid']}). " +
                        ('A janela pode pedir confirmação de salvamento.' if action=='close' else
                         'O aplicativo pode ser reaberto, mas a sessão anterior não é restaurada.')),fg=GREEN)
                    self._last_process_scan=0
            elif kind == 'process-reopened':
                self.proc_action_status.configure(text=msg[1],fg=GREEN if msg[2] else YELLOW)
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
            'ram': (fmt(s['memory_percent'], '%'),
                    ram_card_detail(s, getattr(self, 'hardware_detail', None)),
                    s['memory_percent'], BLUE),
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
        if self.selected=='dashboard':self._draw_graph()
        if self.selected=='processes':self._refresh_processes()
        self.left_status.configure(text='●  Monitoramento ativo\n' + datetime.now().strftime('%H:%M:%S'), fg=GREEN)

    def _draw_graph(self):
        c = self.graph
        if c.winfo_width() < 100 or c.winfo_height() < 80:
            return
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
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
        if len(self.cpu_history) < 2 and len(self.ram_history) < 2:
            c.create_text(w / 2, h / 2, text='Coletando leituras de CPU e RAM...',
                          fill=MUTED, font=(FONT, 10))
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

    def _process_action(self, action: str):
        selected=self.proc_tree.selection()
        if not selected:
            self.proc_action_status.configure(text='Selecione um processo na tabela.',fg=YELLOW);return
        pid=int(selected[0])
        row=next((item for item in self.procs if item['pid']==pid),None)
        name=row['name'] if row else f'PID {pid}'
        warning=('Enviar pedido para fechar a janela? O aplicativo poderá solicitar que você salve o trabalho.'
                 if action=='close' else 'Forçar o encerramento pode perder dados não salvos. Continuar?')
        if not messagebox.askyesno('OSReview · confirmar ação',f'{name} (PID {pid})\n\n{warning}'):
            return
        self.proc_action_status.configure(text='Executando ação solicitada...',fg=BLUE)
        def worker():
            try:
                info=close_process_window(pid) if action=='close' else terminate_process(pid)
                self.events.put(('process-action',action,info,None))
            except Exception as exc:
                self.events.put(('process-action',action,None,str(exc)))
        threading.Thread(target=worker,daemon=True,name='osreview-process-action').start()

    def _reopen_last_app(self):
        info=self._last_closed_app
        if not info:
            self.proc_action_status.configure(text='Nenhum aplicativo encerrado nesta sessão.',fg=YELLOW);return
        path=info['exe']
        if not messagebox.askyesno('OSReview · reabrir aplicativo',
                f'Reabrir o executável abaixo? A sessão e documentos anteriores não serão restaurados.\n\n{path}'):
            return
        def worker():
            try:
                if process_still_running(info):
                    raise ValueError('O aplicativo ainda está em execução. Aguarde o fechamento antes de reabrir.')
                pid=reopen_executable(path)
                self.events.put(('process-reopened',f'Aplicativo iniciado com PID {pid}.',True))
            except Exception as exc:
                self.events.put(('process-reopened',f'Não foi possível reabrir: {exc}',False))
        threading.Thread(target=worker,daemon=True,name='osreview-process-reopen').start()

    def request_services(self):
        if self.service_loading:return
        self.service_loading=True
        self.service_action_status.configure(text='Consultando serviços locais...',fg=BLUE)
        def worker():
            try:self.events.put(('services-list',list_services(),None))
            except Exception as exc:self.events.put(('services-list',[],str(exc)))
        threading.Thread(target=worker,daemon=True,name='osreview-service-list').start()

    def _service_action(self, action: str):
        selected=self.service_tree.selection()
        if not selected:
            self.service_action_status.configure(text='Selecione um serviço na tabela.',fg=YELLOW);return
        name=selected[0]
        row=self.service_rows.get(name)
        if not row or not row['manageable']:
            self.service_action_status.configure(text='Serviço do Windows ou de segurança protegido.',fg=YELLOW);return
        verb='iniciar' if action=='start' else 'parar'
        if not messagebox.askyesno('OSReview · confirmar serviço',
                f'Deseja {verb} {row["display"]} ({name})?\n\nO Windows pode negar a operação. Nenhuma permissão será elevada automaticamente.'):
            return
        self.service_action_status.configure(text='Enviando comando ao Gerenciador de Serviços...',fg=BLUE)
        def worker():
            try:
                result=change_service(name,action)
                self.events.put(('service-action',result,True))
            except Exception as exc:
                self.events.put(('service-action',f'Ação não concluída: {exc}',False))
        threading.Thread(target=worker,daemon=True,name='osreview-service-action').start()

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
                score=result.get('score',result.get('score_primes_s',result.get('copy_mb_s','?')))
                unit=result.get('unit','primos/s' if 'score_primes_s' in result else 'MB/s')
                lines.append(f"  {result.get('type','Teste')} | {score} {unit}")
            else:
                sample = rec.get('sample', {})
                lines.append(f"  CPU {sample.get('cpu_percent','?')}% | RAM {sample.get('memory_percent','?')}%")
        set_text(self.history_text, '\n'.join(lines))

    def _benchmark_type_changed(self):
        self.bench_status.configure(text=f'Selecionado: {self.bench_type.get()}', fg=BLUE)

    def _draw_bench_chart(self):
        chart=getattr(self,'bench_chart',None)
        if chart is None:return
        chart.delete('all')
        w=max(chart.winfo_width(),250);h=max(chart.winfo_height(),120)
        x0,x1,y0,y1=43,w-15,12,h-27
        for fraction in (0,.5,1):
            y=y1-(y1-y0)*fraction
            chart.create_line(x0,y,x1,y,fill=EDGE,dash=(2,5))
        points=self.bench_samples
        if not points:
            chart.create_text(w/2,h/2,text='Gráfico de desempenho aparecerá durante o teste',
                              fill=MUTED,font=(FONT,10))
            return
        ceiling=max(1.,max(row['value'] for row in points)*1.1)
        duration=max(self.bench_chart_duration,points[-1]['elapsed'],1)
        coords=[]
        for row in points:
            coords.extend((x0+(x1-x0)*row['elapsed']/duration,
                           y1-(y1-y0)*row['value']/ceiling))
        if len(coords)>=4:chart.create_line(*coords,fill=BLUE,width=2,smooth=False)
        elif coords:chart.create_oval(coords[0]-3,coords[1]-3,coords[0]+3,coords[1]+3,
                                      fill=BLUE,outline='')
        chart.create_text(25,y0,text=f'{ceiling:.0f}',fill=MUTED,font=(FONT,8))
        chart.create_text(25,y1,text='0',fill=MUTED,font=(FONT,8))
        chart.create_text(x1,y1+14,text=f'{int(duration//60)} min',anchor='e',fill=MUTED,font=(FONT,8))

    def refresh_bench_history(self):
        tree=getattr(self,'bench_history',None)
        if tree is None:return
        for item in tree.get_children():tree.delete(item)
        try:records=self.store.load()
        except (OSError,ValueError):records=[]
        for row in [rec for rec in records if rec.get('type')=='benchmark'][-8:][::-1]:
            result=row.get('result') or {}
            score=result.get('score',result.get('score_primes_s',result.get('copy_mb_s')))
            unit=result.get('unit','primos/s' if 'score_primes_s' in result else 'MB/s')
            duration=result.get('duration_seconds')
            tree.insert('', 'end', values=(row.get('timestamp_readable','?'),result.get('type','Teste'),
                f'{duration//60} min' if isinstance(duration,(int,float)) else '—',
                f'{score:,.0f} {unit}' if isinstance(score,(int,float)) else '—',
                f"{result['stability_percent']:.1f}%" if isinstance(result.get('stability_percent'),(int,float)) else '—'))

    def start_benchmark(self):
        if self.bench_running:
            self.bench_status.configure(text='Já existe um teste em andamento.', fg=YELLOW)
            return
        kind = self.bench_type.get()
        size = int(self.bench_size.get().split()[0])
        duration = int(self.bench_duration.get().split()[0])*60
        self.bench_stop.clear()
        self.bench_running = True
        self.bench_samples=[]
        self.bench_chart_duration=duration
        self.bench_progress['value']=0
        for label in self.bench_metrics.values():label.configure(text='—')
        self._draw_bench_chart()
        self.bench_status.configure(text='Teste em execução. Evite iniciar durante trabalho importante.', fg=YELLOW)
        set_text(self.bench_result, f'Teste: {kind}\nDuração: {duration//60} min · Bloco RAM: {size} MB. O resultado será salvo localmente.')
        def worker():
            try:
                result=timed_benchmark('cpu' if kind.startswith('CPU') else 'memory',duration,size,
                                       self.bench_stop,lambda update:self.events.put(('bench-progress',update)))
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

    def _on_unmap(self, event):
        if event.widget is self and not self.shutdown.is_set():
            self.after_idle(self._minimize_to_tray)

    def _minimize_to_tray(self):
        if (self.winfo_exists() and self.state() == 'iconic' and
                self.tray.available and self.tray.icon and self.var_tray.get()):
            self.withdraw()

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
        self.app_update_cancel.set()
        self.bench_stop.set()
        self.tray.stop()
        self.destroy()


def main():
    OSReviewApp().mainloop()
