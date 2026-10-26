"""Regression tests: third-party sensor binaries must pass integrity gate."""
import hashlib
from pathlib import Path

from osreview.services.bridge_integrity import inspect_bridge, create_sha256_manifest
from osreview.services.collection_integrity import diagnose_collection
from osreview.services.energy_sensors import normalize_sensor


def test_absent_bridge_is_not_executable(tmp_path):
    status = inspect_bridge(tmp_path/'SensorBridge.exe', platform_name='Windows')
    assert not status['allowed'] and not status['present']


def test_unknown_binary_is_blocked(tmp_path):
    exe = tmp_path/'SensorBridge.exe'
    exe.write_bytes(b'foo')
    status = inspect_bridge(exe, platform_name='Windows')
    assert status['present'] and not status['allowed']


def test_intact_file_requires_matching_manifest(tmp_path):
    exe = tmp_path/'SensorBridge.exe'
    exe.write_bytes(b'locally-built-sensor-collector')
    manifest = create_sha256_manifest(exe)
    assert manifest.read_text().startswith(hashlib.sha256(exe.read_bytes()).hexdigest())
    result = inspect_bridge(exe, platform_name='Windows')
    assert result['allowed'] and result['integrity']=='sha256 correspondente'
    exe.write_bytes(exe.read_bytes()+b' modified')
    assert inspect_bridge(exe, platform_name='Windows')['integrity']=='alterado'


def test_manifest_must_reference_same_filename(tmp_path):
    exe = tmp_path/'SensorBridge.exe'
    exe.write_bytes(b'x')
    exe.with_suffix('.exe.sha256').write_text(hashlib.sha256(b'x').hexdigest()+'  evil.exe\n')
    assert not inspect_bridge(exe, platform_name='Windows')['allowed']


def test_nonwindows_bridge_never_runs(tmp_path):
    exe = tmp_path/'SensorBridge.exe'
    exe.write_bytes(b'x')
    create_sha256_manifest(exe)
    assert not inspect_bridge(exe, platform_name='Darwin')['allowed']


def test_collector_audit_exposes_source_and_status():
    state = diagnose_collection(os_name='Linux')
    assert state['total'] >= 4
    assert all('source' in check and 'status' in check for check in state['checks'])
    assert state['os']=='Linux'
    assert 'não é certificação antivírus' in state['notice']


def test_sensor_keeps_native_storage_source():
    sensor = normalize_sensor({'Name':'Disco 0: temperatura','SensorType':'Temperature',
                               'Value':34, 'Identifier':'/storage/0/temperature'},
                              source='Windows Storage Reliability')
    assert sensor['category']=='SSD / HD'
    assert sensor['source']=='Windows Storage Reliability'
