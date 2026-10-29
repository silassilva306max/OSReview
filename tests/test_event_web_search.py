"""Search a selected event without sending the original log message."""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from osreview.services import event_web_search as search


EVENT = {
    'id': 41,
    'provider': 'Microsoft-Windows-Kernel-Power',
    'title': 'Reinicialização/desligamento inesperado',
    'message': 'C:\\Users\\Pessoa\\chave-secreta.txt 192.168.1.42',
    'time': '2026-10-28 10:00:00',
}


@pytest.mark.parametrize('engine',list(search.SEARCH_ENGINES))
def test_search_url_uses_only_generic_event_fields(engine):
    url=search.event_search_url(EVENT,engine)
    parsed=urlparse(url)
    terms=parse_qs(parsed.query)['q'][0]
    assert parsed.scheme=='https'
    assert 'Event ID 41' in terms
    assert 'Microsoft-Windows-Kernel-Power' in terms
    assert 'chave-secreta' not in url
    assert '192.168.1.42' not in url
    assert 'Pessoa' not in url


def test_default_browser_opens_selected_event_without_token(monkeypatch):
    opened=[]
    monkeypatch.setattr(search.webbrowser,'open',lambda url,new:opened.append((url,new)) or True)
    terms=search.open_event_search(EVENT,'Google','Navegador padrão')
    assert terms.startswith('Windows Event ID 41')
    assert opened and opened[0][1]==2


def test_explicit_browser_is_selected_without_shell(monkeypatch):
    calls=[]
    monkeypatch.setattr(search,'_browser_executable',lambda name:Path('C:/Browser/msedge.exe'))
    monkeypatch.setattr(search.subprocess,'Popen',lambda args,**kw:calls.append((args,kw)))
    search.open_event_search(EVENT,'Bing','Microsoft Edge')
    assert calls[0][0][0].endswith('msedge.exe')
    assert calls[0][0][1].startswith('https://www.bing.com/search?')
    assert calls[0][1]['close_fds'] is True


def test_bad_browser_or_event_never_opens_url(monkeypatch):
    monkeypatch.setattr(search.webbrowser,'open',lambda *_args,**_kw:pytest.fail('browser opened'))
    with pytest.raises(ValueError):
        search.open_event_search(EVENT,'Google','Não permitido')
    with pytest.raises(ValueError):
        search.open_event_search({'id':'not an id'},'Google','Navegador padrão')


def test_provider_that_looks_like_a_user_path_is_omitted():
    event={**EVENT,'provider':r'C:\Users\Pessoa\AppData\secret.exe'}
    terms=search.event_search_terms(event)
    assert 'Pessoa' not in terms
    assert 'secret' not in terms
    assert 'Event ID 41' in terms
