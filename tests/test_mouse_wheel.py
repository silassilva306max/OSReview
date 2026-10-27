"""Wheel routing over nested cards and page content in a small Tk window."""
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import pytest

from osreview.app import OSReviewApp
from osreview.ui_cards import SpecCards


class WheelHarness(tk.Tk):
    _descends_from = staticmethod(OSReviewApp._descends_from)
    _scrollable = staticmethod(OSReviewApp._scrollable)
    _wheel_distance = staticmethod(OSReviewApp._wheel_distance)
    _page_wheel_targets = OSReviewApp._page_wheel_targets
    _route_mouse_wheel = OSReviewApp._route_mouse_wheel


def test_wheel_over_card_label_and_page_heading_scrolls_active_cards():
    try:
        root = WheelHarness()
    except tk.TclError as exc:
        pytest.skip(f'Tk indisponível: {exc}')
    try:
        root.geometry('460x300')
        root._wheel_targets_cache = {}
        root._wheel_target = None
        root._wheel_remainder = 0
        root.selected = 'hardware'
        page = tk.Frame(root)
        page.pack(fill='both', expand=True)
        heading = tk.Label(page, text='Inventário físico')
        heading.pack()
        cards = SpecCards(page)
        cards.pack(fill='both', expand=True)
        cards.render([{'title': f'Componente {i}', 'rows': [('Valor', str(i))]}
                      for i in range(25)])
        root.tabs = {'hardware': page}
        root.update()
        assert cards.canvas.yview()[1] < 1
        label = cards.body.winfo_children()[0].winfo_children()[0]
        event = SimpleNamespace(widget=label, x_root=label.winfo_rootx() + 4,
                                y_root=label.winfo_rooty() + 4, delta=-120, num=0)
        assert root._route_mouse_wheel(event) == 'break'
        assert cards.canvas.yview()[0] > 0
        before = cards.canvas.yview()[0]
        event.widget = heading
        event.x_root = heading.winfo_rootx() + 4
        event.y_root = heading.winfo_rooty() + 4
        assert root._route_mouse_wheel(event) == 'break'
        assert cards.canvas.yview()[0] > before
    finally:
        root.destroy()


def test_wheel_over_page_button_scrolls_treeview():
    try:
        root = WheelHarness()
    except tk.TclError as exc:
        pytest.skip(f'Tk indisponível: {exc}')
    try:
        root.geometry('400x240')
        root._wheel_targets_cache = {}
        root._wheel_target = None
        root._wheel_remainder = 0
        root.selected = 'services'
        page = tk.Frame(root)
        page.pack(fill='both', expand=True)
        button = tk.Button(page, text='Listar serviços')
        button.pack()
        tree = ttk.Treeview(page)
        tree.pack(fill='both', expand=True)
        for index in range(60):
            tree.insert('', 'end', text=f'Serviço {index}')
        root.tabs = {'services': page}
        root.update()
        event = SimpleNamespace(widget=button, x_root=button.winfo_rootx() + 5,
                                y_root=button.winfo_rooty() + 5, delta=-120, num=0)
        assert root._route_mouse_wheel(event) == 'break'
        assert tree.yview()[0] > 0
    finally:
        root.destroy()
