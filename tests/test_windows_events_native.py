"""Regression for the native Windows Event Log handle lifecycle."""
import sys
from types import SimpleNamespace

from osreview.services import windows_native


def test_native_events_survive_a_blocked_log_without_evtclose(monkeypatch):
    closed=[]
    class Handle:
        def __init__(self, kind):
            self.kind=kind
            self.read=False
        def Close(self):
            closed.append(self.kind)
    def query(name, direction, expression):
        if name=='Application':
            raise PermissionError('blocked')
        return Handle('query')
    def next_batch(handle, count, timeout, flags):
        if handle.read:
            return []
        handle.read=True
        return [Handle('event')]
    def render(handle, flags):
        return ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
                '<System><Provider Name="EventLog"/><EventID>6008</EventID><Level>2</Level>'
                '<TimeCreated SystemTime="2026-10-27T12:00:00Z"/></System></Event>')
    fake=SimpleNamespace(EvtQueryReverseDirection=1,EvtRenderEventXml=2,
                         EvtQuery=query,EvtNext=next_batch,EvtRender=render)
    monkeypatch.setitem(sys.modules,'win32evtlog',fake)
    monkeypatch.setattr(windows_native.platform,'system',lambda:'Windows')
    rows=windows_native.collect_events(max_events=5)
    assert rows and rows[0]['Id']==6008
    assert closed==['event','query']
