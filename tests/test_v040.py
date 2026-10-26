from pathlib import Path
import platform
import tempfile
from unittest.mock import patch
import pytest

from osreview.services.windows_inventory import gpu_kind, normalize_gpus, collect_inventory
from osreview.services.event_intelligence import explain_event, normalize_events, collect_events
from osreview.services.online_ai import build_sanitized_event_payload
from osreview.services.safe_cleanup import preview_cleanup, clean_category


def test_detect_12th_gen_intel_uhd():
    result = normalize_gpus({'Name': 'Intel(R) UHD Graphics 770', 'DriverVersion': '31.0.101.4577',
                             'AdapterCompatibility': 'Intel Corporation', 'PNPDeviceID': 'PCI\\VEN_8086&DEV_4680',
                             'Status': 'OK', 'ConfigManagerErrorCode': 0,
                             'CurrentHorizontalResolution': 1920, 'CurrentVerticalResolution': 1080})
    assert len(result) == 1
    assert 'integrada' in result[0]['type']
    assert result[0]['driver_version'] == '31.0.101.4577'
    assert '770' in result[0]['name']


def test_multiple_gpus_and_generic_driver():
    result = normalize_gpus([
        {'Name': 'Intel(R) Iris Xe Graphics', 'PNPDeviceID': 'PCI\\VEN_8086'},
        {'Name': 'NVIDIA GeForce RTX 3070', 'PNPDeviceID': 'PCI\\VEN_10DE'},
        {'Name': 'Microsoft Basic Display Adapter'},
        {'Name': 'AMD Radeon(TM) Graphics', 'PNPDeviceID': 'PCI\\VEN_1002'},
    ])
    assert len(result) == 4
    assert result[1]['type'].startswith('NVIDIA')
    assert result[2]['type'].startswith('driver genérico')
    assert result[3]['type'].startswith('integrada')


def test_power_event_not_direct_psu_diagnosis():
    d = explain_event('Microsoft-Windows-Kernel-Power', 41)
    assert 'não aponta' in d['meaning'].lower()
    assert d['severity'] == 'atenção'


def test_storage_events_prioritized():
    d = explain_event('Disk', 153)
    assert 'backup' in d['action'].lower()


def test_dcom_10016_avoid_false_alarm():
    assert explain_event('Microsoft-Windows-DistributedCOM', 10016)['severity'] == 'informativo'


def test_clean_event_normalization():
    data = normalize_events([{'Id': 4101, 'ProviderName': 'Display', 'Message': 'Recovered',
                              'LogName': 'System', 'TimeCreated': '2026-10-23 08:00:00'},
                             {'Id': 'bad'}])
    assert len(data) == 1
    assert 'vídeo' in data[0]['title'].lower()


def test_ai_payload_never_sends_raw_message():
    e = {'id': 41, 'provider': 'Microsoft-Windows-Kernel-Power', 'log': 'System',
         'title': 'Reinicialização', 'message': 'C:\\Users\\SampleUser\\Documents private mail@example.com 192.168.1.1'}
    data = build_sanitized_event_payload(e)
    assert 'SampleUser' not in data and 'mail@example' not in data and '192.168' not in data


def test_preview_and_explicit_clean(monkeypatch, tmp_path):
    from osreview.services import safe_cleanup
    root = tmp_path / 'Temp'
    root.mkdir()
    candidate = root / 'old.tmp'
    candidate.write_bytes(b'a' * 2000)
    other = root / 'recent.txt'
    other.write_bytes(b'new')
    import time, os
    os.utime(candidate, (time.time()-4*86400, time.time()-4*86400))
    monkeypatch.setattr(safe_cleanup, 'get_safe_locations', lambda: {'Temp (usuário)': [root]})
    monkeypatch.setattr(safe_cleanup, '_running_browsers', lambda: set())
    summary = preview_cleanup('Temp (usuário)')
    assert summary['count'] == 1
    assert candidate.exists() and other.exists()
    removed = clean_category('Temp (usuário)')
    assert removed['deleted'] == 1
    assert not candidate.exists() and other.exists()


def test_browser_in_use_blocks_cleanup(monkeypatch, tmp_path):
    from osreview.services import safe_cleanup
    monkeypatch.setattr(safe_cleanup, '_running_browsers', lambda: {'Chrome'})
    monkeypatch.setattr(safe_cleanup, 'get_safe_locations', lambda: {'Chrome': [tmp_path]})
    with pytest.raises(RuntimeError):
        preview_cleanup('Chrome')


def test_nonwindows_integration_returns_unsupported():
    if platform.system() == 'Windows':
        pytest.skip('Test for non Windows only')
    assert not collect_inventory()['supported']
    assert not collect_events()['supported']
