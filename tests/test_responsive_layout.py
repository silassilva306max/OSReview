"""The CPU/RAM and benchmark charts remain available in small native windows."""
from collections import deque
import tkinter as tk

import pytest

from osreview.app import OSReviewApp
from osreview.enhanced_app import OSReviewAppV5


class LayoutHarness(tk.Tk):
    _page = OSReviewApp._page
    _panel = OSReviewApp._panel
    _make_dashboard = OSReviewApp._make_dashboard
    _dashboard_width_changed = OSReviewApp._dashboard_width_changed
    _draw_graph = OSReviewApp._draw_graph
    _make_benchmark = OSReviewApp._make_benchmark
    _benchmark_width_changed = OSReviewApp._benchmark_width_changed
    _draw_bench_chart = OSReviewApp._draw_bench_chart
    _enhance_dashboard_cards = OSReviewAppV5._enhance_dashboard_cards

    def __init__(self):
        super().__init__()
        self.tabs = {}
        self.content = tk.Frame(self)
        self.content.pack(fill='both', expand=True)
        self.cpu_history = deque([20, 35, 28, 47], maxlen=65)
        self.ram_history = deque([54, 55, 56, 57], maxlen=65)
        self.latest = None
        self.bench_samples = []
        self.bench_chart_duration = 180

    def switch(self, _key):
        pass

    def request_analysis(self):
        pass

    def save_snapshot(self):
        pass

    def start_benchmark(self):
        pass

    def stop_benchmark(self):
        pass

    def reset_benchmark(self):
        pass

    def _benchmark_type_changed(self):
        pass

    def refresh_bench_history(self):
        pass


def _root():
    try:
        return LayoutHarness()
    except tk.TclError as exc:
        pytest.skip(f'Tk indisponível: {exc}')


def test_dashboard_graph_and_sensor_cards_survive_small_window_and_resize():
    root = _root()
    try:
        root._make_dashboard()
        root._enhance_dashboard_cards()
        root.tabs['dashboard'].pack(fill='both', expand=True)
        root.geometry('760x380')
        root.update()
        assert root._dashboard_stacked
        assert root.graph.winfo_width() > 100
        assert root.graph.winfo_height() >= 200
        assert len(root.graph.find_all()) > 5
        assert root.dashboard_scroll.canvas.yview()[1] < 1
        assert root.dash_sensor_boxes[4].grid_info()['row'] == 2

        root.geometry('1100x700')
        root.update()
        assert not root._dashboard_stacked
        assert root.graph.winfo_width() > 300
        assert len(root.graph.find_all()) > 5
        assert root.dash_sensor_boxes[4].grid_info()['row'] == 1
    finally:
        root.destroy()


def test_benchmark_chart_remains_drawn_in_short_window():
    root = _root()
    try:
        root._make_benchmark()
        root.tabs['benchmark'].pack(fill='both', expand=True)
        root.geometry('760x380')
        root.update()
        assert root._benchmark_stacked
        assert root.bench_chart.winfo_width() > 300
        assert root.benchmark_scroll.canvas.yview()[1] < 1
        root.bench_samples = [{'elapsed': 1, 'value': 100}, {'elapsed': 2, 'value': 110}]
        root._draw_bench_chart()
        assert len(root.bench_chart.find_all()) > 5

        root.geometry('1100x700')
        root.update()
        assert not root._benchmark_stacked
        assert root.bench_chart.winfo_width() > 300
        assert len(root.bench_chart.find_all()) > 5
    finally:
        root.destroy()
