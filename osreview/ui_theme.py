"""Three complete, high contrast metallic palettes for the desktop UI.

The attached character photographs are color references only. No third-party
image, logo or character artwork is bundled in the public application.
"""
from __future__ import annotations

THEMES = {
    'armor': ('Armadura Mark III · vermelho e ouro', '#E5A93A', '#A63B30', '#FBD47B'),
    'war': ('Máquina de Combate · grafite e titânio', '#AFC1C5', '#476570', '#F2F8F5'),
    'patriot': ('Patriota de Ferro · azul e prata', '#83BDEB', '#2E639B', '#E6F4FC'),
}
_LEGACY = {'rog': 'patriot', 'graphite': 'war', 'cyber': 'armor'}

_KEYS = ('BG', 'SIDEBAR', 'PANEL', 'PANEL2', 'EDGE', 'WHITE', 'MUTED',
         'RED', 'GREEN', 'BLUE', 'PURPLE', 'YELLOW',
         'METAL_HI', 'METAL_LO', 'GLOW', 'SHADOW')

_DARK = {
    'armor': ('#13090D', '#230C14', '#2D121B', '#421925', '#78313B',
              '#FFF3DF', '#D3B9A9', '#FF5552', '#76E7C4', '#8AE7F5', '#C899D1', '#FFD36C',
              '#FFE7A5', '#78401C', '#A9F6FF', '#080507'),
    'war': ('#0B1013', '#131C21', '#1D292F', '#2A3A42', '#5E727B',
            '#F1F7F7', '#B3C4C9', '#FF695E', '#7BD9B8', '#A1CEE0', '#BFB5CE', '#E7CC91',
            '#E4F2F2', '#455963', '#FF8C68', '#05080A'),
    'patriot': ('#0B1323', '#132039', '#1A2C49', '#274261', '#577A9D',
                '#F4F9FC', '#B8CADE', '#F16C74', '#7DDCC6', '#8CC8F6', '#BDB8E1', '#E8D7A2',
                '#EAF7FD', '#466C96', '#B5F3FF', '#060B17'),
}
_LIGHT = {
    'armor': ('#FAF0EA', '#F1DCD5', '#FFFAF4', '#F5E4D9', '#C99890',
              '#3A1E25', '#72565A', '#B62F32', '#126E56', '#246C89', '#79548B', '#80601B',
              '#FFF3CD', '#AC6956', '#168C9C', '#D5BBB2'),
    'war': ('#EBF1F2', '#D8E3E5', '#FCFEFD', '#E5EDEF', '#8FA6AA',
            '#1B2E34', '#52666B', '#AD4141', '#136A53', '#316B84', '#6E5784', '#785F22',
            '#F4FAF8', '#647D83', '#B94A40', '#C0CDD0'),
    'patriot': ('#ECF3FA', '#D9E7F3', '#FBFDFF', '#E1EDF8', '#9CB8CE',
                '#18314F', '#566E88', '#B53E4E', '#126C58', '#266B9E', '#685787', '#7B641F',
                '#F2FAFE', '#527EAA', '#3E9EC3', '#C0D4E5'),
}


def normalize_theme(theme: str) -> str:
    theme = _LEGACY.get(theme, theme)
    return theme if theme in THEMES else 'armor'


def palette(mode: str, theme: str) -> dict[str, str]:
    theme = normalize_theme(theme)
    light = mode == 'light'
    colors = dict(zip(_KEYS, (_LIGHT if light else _DARK)[theme]))
    _, accent_dark, accent_light, secondary = THEMES[theme]
    colors.update({
        'ACCENT': accent_light if light else accent_dark,
        'ACCENT_FG': '#FFFFFF' if light else
                     {'armor': '#261211', 'war': '#102027', 'patriot': '#10253A'}[theme],
        'ACTIVE_ACCENT': secondary if not light else
                         {'armor': '#843427', 'war': '#34525D', 'patriot': '#28547E'}[theme],
    })
    return colors
