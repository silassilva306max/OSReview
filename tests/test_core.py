from pathlib import Path
import threading

from osreview.services.benchmark import cpu_benchmark, memory_benchmark, BenchmarkCancelled
from osreview.services.configuration import ConfigStore
from osreview.services.diagnostics import DiagnosticsEngine
from osreview.services.windows_health import collect_windows_health


def sample(**updates):
    d = {'cpu_percent': 10.0, 'memory_percent': 40.0, 'disk_percent': 30.0,
         'swap_percent': 0.0, 'cpu_temp_c': None, 'gpu_memory_used_mb': None,
         'gpu_memory_total_mb': None}
    d.update(updates)
    return d


def test_heavy_usage_recommendations():
    findings = DiagnosticsEngine().analyze(sample(cpu_percent=98, memory_percent=94, disk_percent=97, cpu_temp_c=96),
                                            [{'name': 'browser.exe'}])
    levels = {x.level for x in findings}
    titles = {x.title for x in findings}
    assert 'critical' in levels
    assert 'RAM' in ' '.join(titles)
    assert any('temperatura' in x.title.lower() for x in findings)
    assert any('browser.exe' in x.technical for x in findings)


def test_no_fabricated_temperature():
    findings = DiagnosticsEngine().analyze(sample(), [])
    assert any('indisponível' in x.title.lower() for x in findings)


def test_windows_reboot_signal():
    findings = DiagnosticsEngine().analyze(sample(), [], {'supported': True, 'pending_reboot': True, 'update_processes': []})
    assert any('Reinicialização' in x.title for x in findings)


def test_settings_persistence(tmp_path: Path):
    cfg = ConfigStore(tmp_path)
    cfg.set('notifications', False)
    assert ConfigStore(tmp_path).data['notifications'] is False


def test_cpu_benchmark_can_cancel():
    cancel = threading.Event()
    cancel.set()
    try:
        cpu_benchmark(3, cancel)
    except BenchmarkCancelled:
        return
    raise AssertionError('cancel did not interrupt benchmark')


def test_memory_benchmark_result():
    result = memory_benchmark(8)
    assert result['size_mb'] == 8
    assert result['copy_mb_s'] > 0


def test_windows_health_contract():
    result = collect_windows_health()
    assert isinstance(result['services'], list)
    assert 'supported' in result
