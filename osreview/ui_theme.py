"""Readable surface and accent palettes for the desktop UI."""
from __future__ import annotations

THEMES = {
    'armor': ('Armadura · vermelho e dourado', '#E65B52', '#B43F36', '#F3C96A'),
    'war': ('Combate · aço e azul', '#578DCE', '#346BA9', '#A7BED8'),
    'rog': ('ROG · violeta e magenta', '#C45DC8', '#9C3D9F', '#E18BD8'),
    'graphite': ('Grafite · preto e cinza', '#75A9BD', '#346F83', '#A9B8C5'),
    'cyber': ('Ciber · verde e turquesa', '#3FBFA9', '#16846F', '#8FE3C9'),
}


def palette(mode: str, theme: str) -> dict[str, str]:
    if theme not in THEMES:
        theme = 'graphite'
    light = mode == 'light'
    _, accent_dark, accent_light, secondary = THEMES[theme]
    colors = {
        'BG': '#F2F5F9' if light else '#0C1119',
        'SIDEBAR': '#E8EDF4' if light else '#121A25',
        'PANEL': '#FFFFFF' if light else '#171F2B',
        'PANEL2': '#E8EEF5' if light else '#202B39',
        'EDGE': '#CCD6E2' if light else '#324052',
        'WHITE': '#172638' if light else '#F4F7FB',
        'MUTED': '#526477' if light else '#A6B7C9',
        'RED': '#AA343C' if light else '#FF7772',
        'GREEN': '#08735F' if light else '#58D7B0',
        'BLUE': '#1C639D' if light else '#79BBF0',
        'PURPLE': '#74519A' if light else '#C2A7F5',
        'YELLOW': '#846009' if light else '#F5C971',
        'ACCENT': accent_light if light else accent_dark,
        'ACCENT_FG': '#FFFFFF' if light else '#08121A',
        'ACTIVE_ACCENT': accent_dark if light else secondary,
    }
    return colors
