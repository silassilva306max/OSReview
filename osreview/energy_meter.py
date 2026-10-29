"""Compact thermal indicator: observed readings only (not inferred)."""
from __future__ import annotations

import tkinter as tk
from . import app as base
from .ui_metal import MetalStrip


class SensorMeter(tk.Frame):
    def __init__(self, master, title: str):
        super().__init__(master, bg=base.PANEL, highlightthickness=1,
                         highlightbackground=base.EDGE)
        MetalStrip(self,base.material_palette,role='glow',height=4).pack(fill='x')
        self.title_label=tk.Label(self,text=title,bg=base.PANEL,fg=base.MUTED,
                                  font=(base.FONT,10,'bold'))
        self.title_label.pack(anchor='w',padx=12,pady=(7,0))
        self.value_label=tk.Label(self,text='Indisponível',bg=base.PANEL,fg=base.WHITE,
                                  font=(base.FONT,16,'bold'))
        self.value_label.pack(anchor='w',padx=12)
        self.source_label=tk.Label(self,text='Aguardando sensor...',bg=base.PANEL,fg=base.MUTED,
                                   font=(base.FONT,8),anchor='w',justify='left',wraplength=180)
        self.source_label.pack(anchor='w',padx=12)
        self.canvas=tk.Canvas(self,width=110,height=8,bg=base.PANEL,highlightthickness=0)
        self.canvas.pack(fill='x',padx=12,pady=(4,9))
        self.canvas.bind('<Configure>',lambda _:self._draw())
        self.percent=None
        self.color=base.BLUE

    def _draw(self):
        self.canvas.delete('all')
        width=max(self.canvas.winfo_width(),2)
        self.canvas.create_rectangle(0,0,width,8,fill=base.EDGE,outline='')
        if self.percent is not None:
            self.canvas.create_rectangle(0,0,width*min(1,max(0,self.percent)),8,
                                         fill=self.color,outline='')

    def show_temperature(self, degrees, source=None):
        try:
            c=float(degrees)
            if not -30<=c<=180:
                raise ValueError('Invalid sensor')
            self.value_label.configure(text=f'{c:.1f} °C')
            self.percent=c/110.
            self.color=(base.RED if c>=90 else base.YELLOW if c>=80 else base.GREEN)
        except (TypeError,ValueError):
            self.value_label.configure(text='Indisponível')
            self.percent=None
            self.color=base.BLUE
        if source is not None:
            self.source_label.configure(text=str(source)[:58])
        self._draw()


def representative_temperatures(result: dict) -> dict[str, float | None]:
    """Measured temperatures only (never NVMe thresholds or TjMax margins)."""
    from .services.sensor_analysis import temperature_readings
    readings=temperature_readings(result)
    return {key:reading.value if reading else None for key,reading in readings.items()}
