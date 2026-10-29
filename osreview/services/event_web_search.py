"""Open a selected Windows event in a web search without sharing its log message."""
from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from urllib.parse import urlencode
import webbrowser


SEARCH_ENGINES = {
    'Google': 'https://www.google.com/search',
    'Bing': 'https://www.bing.com/search',
    'DuckDuckGo': 'https://duckduckgo.com/',
    'Brave Search': 'https://search.brave.com/search',
}
BROWSERS = {
    'Navegador padrão': None,
    'Microsoft Edge': 'msedge.exe',
    'Google Chrome': 'chrome.exe',
    'Opera': 'opera.exe',
    'Mozilla Firefox': 'firefox.exe',
    'Brave': 'brave.exe',
}


def event_search_terms(event: dict) -> str:
    """Only the generic event ID, provider and local explanation leave the app."""
    try:
        event_id = int(event.get('id'))
    except (TypeError, ValueError) as exc:
        raise ValueError('O evento selecionado não tem ID válido.') from exc
    if not 0 <= event_id <= 999999:
        raise ValueError('O evento selecionado não tem ID válido.')
    provider = str(event.get('provider') or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 .()_-]{0,79}', provider):
        provider = ''
    title = str(event.get('title') or '')
    title = ' '.join(re.sub(r'[^\w .()_-]', ' ', title, flags=re.UNICODE).split())[:80]
    terms = ['Windows', f'Event ID {event_id}']
    if provider and provider != 'Não informado':
        terms.append(provider)
    if title and title != 'Erro registrado (causa não determinada)':
        terms.append(title)
    return ' '.join(terms)


def event_search_url(event: dict, engine: str) -> str:
    if engine not in SEARCH_ENGINES:
        raise ValueError('Escolha um mecanismo de busca válido.')
    return SEARCH_ENGINES[engine] + '?' + urlencode({'q': event_search_terms(event)})


def _browser_executable(name: str) -> Path | None:
    filename = BROWSERS.get(name)
    if not filename or platform.system() != 'Windows':
        return None
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, rf'Software\Microsoft\Windows\CurrentVersion\App Paths\{filename}') as key:
                    value = winreg.QueryValueEx(key, '')[0]
                candidate = Path(os.path.expandvars(str(value).strip('"')))
                if candidate.is_file() and candidate.name.casefold() == filename:
                    return candidate
            except OSError:
                continue
    except ImportError:
        pass
    found = shutil.which(filename)
    candidate = Path(found) if found else None
    return candidate if candidate and candidate.is_file() and candidate.name.casefold() == filename else None


def open_event_search(event: dict, engine: str, browser: str) -> str:
    """Return the generic query terms after opening a trusted search URL."""
    if browser not in BROWSERS:
        raise ValueError('Escolha um navegador válido.')
    url = event_search_url(event, engine)
    if browser == 'Navegador padrão':
        if not webbrowser.open(url, new=2):
            raise OSError('O navegador padrão não abriu a pesquisa.')
    else:
        executable = _browser_executable(browser)
        if executable is None:
            raise FileNotFoundError(f'{browser} não foi encontrado. Escolha outro navegador ou use o padrão.')
        subprocess.Popen([str(executable), url], close_fds=True)
    return event_search_terms(event)
