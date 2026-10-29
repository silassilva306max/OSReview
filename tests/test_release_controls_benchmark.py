"""Regression checks for the new controls and measured benchmark path."""
import threading
import os

import pytest
import psutil

from osreview.services.benchmark import BenchmarkCancelled, timed_benchmark
from osreview.services import local_controls
from osreview.services.local_controls import service_manageable, _is_windows_path
from osreview.services.sensor_analysis import clock_readings, power_readings
from osreview.ui_theme import THEMES, normalize_theme, palette


def test_service_guard_excludes_windows_and_security_services():
    assert not service_manageable('RpcSs', r'C:\Windows\System32\svchost.exe')
    assert not service_manageable('ThirdParty', r'C:\Windows\System32\third.exe')
    assert not service_manageable('AvastAgent', r'C:\Program Files\Avast\agent.exe')
    assert not service_manageable('CompanyAgent', r'\SystemRoot\System32\agent.exe')
    assert not service_manageable('Host', 'svchost.exe -k group')
    assert service_manageable('ExampleAgent', r'C:\Program Files\Example\agent.exe')
    assert _is_windows_path(r'"C:\Windows\System32\svchost.exe" -k group')


def test_timed_benchmark_reports_real_samples_and_stops():
    progress = []
    result = timed_benchmark('cpu', 1, progress=progress.append)
    assert result['kind'] == 'cpu'
    assert result['score'] > 0
    assert result['min_score'] <= result['score'] <= result['max_score']
    assert result['samples']
    assert progress
    stop = threading.Event()
    stop.set()
    with pytest.raises(BenchmarkCancelled):
        timed_benchmark('memory', 1, size_mb=8, stop=stop)


def test_ram_benchmark_has_throughput_and_samples():
    result = timed_benchmark('memory', 1, size_mb=8)
    assert result['kind'] == 'memory'
    assert result['unit'] == 'MB/s'
    assert result['score'] > 0
    assert result['samples']


def test_protected_service_cannot_reach_service_control(monkeypatch):
    class Service:
        def as_dict(self):
            return {'name': 'AvastAgent', 'binpath': r'C:\Program Files\Avast\agent.exe'}

    monkeypatch.setattr(local_controls.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(local_controls.psutil, 'win_service_get', lambda _name: Service(), raising=False)
    with pytest.raises(PermissionError):
        local_controls.change_service('AvastAgent', 'stop')


def test_reopen_guard_detects_existing_process():
    pid = os.getpid()
    created = psutil.Process(pid).create_time()
    assert local_controls.process_still_running({'pid': pid, 'created': created})
    assert not local_controls.process_still_running({'pid': 0, 'created': created})


def test_clock_and_zero_power_are_measured_only():
    snapshot = {'groups': {
        'CPU': [
            {'type': 'Clock', 'name': 'CPU Core #1', 'value': 2850, 'source': 'sensor'},
            {'type': 'Clock', 'name': 'CPU Bus', 'value': 4000},
        ],
        'GPU': [
            {'type': 'Clock', 'name': 'GPU Memory', 'value': 6000},
            {'type': 'Clock', 'name': 'GPU Core', 'value': 720},
            {'type': 'Power', 'name': 'GPU Power', 'value': 0},
        ],
    }}
    clocks = clock_readings(snapshot)
    assert clocks['CPU'].value == 2850
    assert clocks['GPU'].value == 720
    assert power_readings(snapshot)['gpu'].display('W') == '0.00 W'
    assert power_readings({'groups': {'GPU': []}})['gpu'] is None


def test_three_metallic_palettes_preserve_readable_surfaces():
    assert set(THEMES) == {'armor','war','patriot'}
    for mode in ('dark', 'light'):
        colors = [palette(mode, key) for key in THEMES]
        assert len({color['ACCENT'] for color in colors}) == 3
        assert all(color['PANEL'] != color['WHITE'] for color in colors)
        assert len({color['BG'] for color in colors}) == 3
        assert len({color['SIDEBAR'] for color in colors}) == 3
        assert len({color['PANEL2'] for color in colors}) == 3
        for color in colors:
            assert len(set(color.values())) == len(color)
            assert _contrast(color['WHITE'], color['PANEL2']) >= 4.5
            assert _contrast(color['MUTED'], color['PANEL']) >= 4.5
            assert _contrast(color['ACCENT_FG'], color['ACCENT']) >= 4.5
            assert _contrast(color['ACCENT_FG'], color['ACTIVE_ACCENT']) >= 4.5


def test_old_theme_preferences_are_mapped_to_three_new_choices():
    assert normalize_theme('rog') == 'patriot'
    assert normalize_theme('graphite') == 'war'
    assert normalize_theme('cyber') == 'armor'


def _contrast(first: str, second: str) -> float:
    def luminance(value: str) -> float:
        components = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [component / 12.92 if component <= 0.04045
                  else ((component + 0.055) / 1.055) ** 2.4 for component in components]
        return sum(component * weight for component, weight in
                   zip(linear, (0.2126, 0.7152, 0.0722)))

    brighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (brighter + 0.05) / (darker + 0.05)
