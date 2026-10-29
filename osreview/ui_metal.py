"""Lightweight Tk canvas trim with a brushed-metal highlight."""
from __future__ import annotations

import tkinter as tk


def _blend(first: str, second: str, fraction: float) -> str:
    a = [int(first[index:index + 2], 16) for index in (1, 3, 5)]
    b = [int(second[index:index + 2], 16) for index in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * fraction):02x}' for x, y in zip(a, b))


class MetalStrip(tk.Canvas):
    """Small gradient accent; no bitmap, animation or extra refresh timer."""

    def __init__(self, parent, colors, *, role='accent', height=5):
        self.colors = colors
        self.role = role
        super().__init__(parent, height=height, bd=0, highlightthickness=0,
                         bg=colors()['PANEL'])
        self.bind('<Configure>', self.draw)

    def draw(self, _event=None):
        if not self.winfo_exists():
            return
        colors = self.colors()
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 2 or height < 2:
            return
        self.delete('all')
        center = colors['GLOW'] if self.role == 'glow' else (
            colors['RED'] if self.role == 'red' else colors['ACCENT'])
        stops = ((0.0, colors['METAL_LO']), (0.16, center),
                 (0.40, colors['METAL_HI']), (0.57, center),
                 (0.86, colors['METAL_LO']), (1.0, colors['SHADOW']))
        segments = min(48, max(12, width // 20))
        for index in range(segments):
            fraction = (index + 0.5) / segments
            for (start, left), (end, right) in zip(stops, stops[1:]):
                if start <= fraction <= end:
                    color = _blend(left, right, (fraction - start) / (end - start))
                    break
            x0 = round(index * width / segments)
            x1 = round((index + 1) * width / segments)
            self.create_rectangle(x0, 0, x1 + 1, height, fill=color, outline='')
        self.create_line(0, 0, width, 0, fill=colors['METAL_HI'])
        self.create_line(0, height - 1, width, height - 1, fill=colors['SHADOW'])
