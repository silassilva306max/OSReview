"""Complete, readable color palettes for the desktop interface."""
from __future__ import annotations

THEMES = {
    'armor': ('Armadura · vermelho e dourado', '#E9A84E', '#A64139', '#F8CE76'),
    'war': ('Máquina de Combate · aço e azul', '#83B0CE', '#356C9E', '#B9CEDA'),
    'rog': ('ROG · violeta e magenta', '#D579D4', '#944795', '#ECA5E2'),
    'graphite': ('Grafite · preto e cinza', '#75A9BD', '#346F83', '#A9B8C5'),
    'cyber': ('Ciber · verde e turquesa', '#59D5B8', '#177A69', '#A2E9D1'),
}

# Each dark theme changes the complete shell, surfaces, borders and status
# colors. Light themes retain strong contrast while tinting the same surfaces.
_DARK = {
    'armor': ('#130F12', '#21151A', '#291B20', '#38262B', '#67434A',
              '#FFF6EC', '#CBB5AE', '#FF8279', '#83D6AD', '#8EC2E8', '#D8A6D6', '#F3C873'),
    'war': ('#10161D', '#19222C', '#222D38', '#2D3B47', '#536676',
            '#F2F6F8', '#B7C5CE', '#F28A83', '#83D3B8', '#92C7E8', '#BEB5DC', '#E9CF88'),
    'rog': ('#130F1B', '#1E1629', '#271D35', '#352742', '#674B75',
            '#FBF4FC', '#C9B7D1', '#F98596', '#83D8C4', '#A7BFF0', '#E4A9EA', '#F3CD81'),
    'graphite': ('#0C1119', '#121A25', '#171F2B', '#202B39', '#324052',
                 '#F4F7FB', '#A6B7C9', '#FF7772', '#58D7B0', '#79BBF0', '#C2A7F5', '#F5C971'),
    'cyber': ('#0B1516', '#112323', '#172B2B', '#213838', '#3A6260',
              '#EEFBF6', '#A9C9C1', '#F78E7D', '#79DEB0', '#85CEDE', '#C8B5EA', '#E9D18C'),
}
_LIGHT = {
    'armor': ('#FAF5F1', '#F1E7DF', '#FFFDFC', '#F5EBE3', '#D9C8BE',
              '#30252A', '#695957', '#B43E3D', '#196A52', '#245F8D', '#78518A', '#806015'),
    'war': ('#F2F6F8', '#E5EDF2', '#FCFEFF', '#E9F0F4', '#C5D3DC',
            '#24343F', '#556B77', '#AF454A', '#176954', '#245F8A', '#70518B', '#7C5C17'),
    'rog': ('#F8F4FA', '#EFE7F3', '#FEFCFF', '#F1EAF5', '#D9C7DF',
            '#30263B', '#67576E', '#B2435E', '#176A58', '#315F94', '#80458C', '#806017'),
    'graphite': ('#F2F5F9', '#E8EDF4', '#FDFEFF', '#E8EEF5', '#CCD6E2',
                 '#172638', '#526477', '#AA343C', '#08735F', '#1C639D', '#74519A', '#846009'),
    'cyber': ('#F1F8F6', '#E3F0EB', '#FBFFFD', '#E8F4EF', '#BDD7CB',
              '#1C3430', '#506F65', '#AA4740', '#086F55', '#286986', '#73558A', '#7B6416'),
}
_KEYS = ('BG', 'SIDEBAR', 'PANEL', 'PANEL2', 'EDGE', 'WHITE', 'MUTED',
         'RED', 'GREEN', 'BLUE', 'PURPLE', 'YELLOW')


def palette(mode: str, theme: str) -> dict[str, str]:
    if theme not in THEMES:
        theme = 'graphite'
    light = mode == 'light'
    colors = dict(zip(_KEYS, (_LIGHT if light else _DARK)[theme]))
    _, accent_dark, accent_light, secondary = THEMES[theme]
    colors.update({
        'ACCENT': accent_light if light else accent_dark,
        'ACCENT_FG': '#FFFFFF' if light else '#18141A',
        'ACTIVE_ACCENT': accent_dark if light else secondary,
    })
    return colors
