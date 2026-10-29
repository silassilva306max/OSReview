"""The packaged Windows GUI has no standard output streams."""
import importlib
import os
import sys
from types import SimpleNamespace

from osreview.services import network_diagnostics as net


def test_speedtest_can_import_with_no_console(monkeypatch):
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    net._ensure_speedtest_streams()
    for stream in (sys.stdout, sys.stderr):
        descriptor = stream.fileno()
        assert descriptor >= 0
        os.close(descriptor)
    assert hasattr(importlib.reload(importlib.import_module('speedtest')), 'Speedtest')


def test_ookla_runs_once_per_direction_for_selected_duration(monkeypatch):
    calls = []

    class Client:
        def __init__(self, secure, timeout):
            assert secure and timeout == 8
            self.config = {'length': {'download': 0, 'upload': 0}}
            self.results = SimpleNamespace(ping=12.0)

        def get_best_server(self):
            calls.append('server')

        def download(self, callback):
            calls.append(('download', self.config['length']['download']))
            return 500_000_000

        def upload(self, callback, pre_allocate):
            calls.append(('upload', self.config['length']['upload'], pre_allocate))
            return 200_000_000

    monkeypatch.setitem(sys.modules, 'speedtest', SimpleNamespace(Speedtest=Client))
    result = net._speedtest_ookla(duration_s=20)
    assert calls == ['server', ('download', 20), ('upload', 20, False)]
    assert result['ok'] and result['download_mbps'] == 500
    assert result['upload_mbps'] == 200
    assert result['download_samples'] == result['upload_samples'] == 1
