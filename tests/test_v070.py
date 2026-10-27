"""New engine regression tests, independent of physical Windows sensors."""
import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from osreview.services.fps_live import FPSLive, valid_process, verify_presentmon, PRESENTMON_SHA256
from osreview.services.sensor_runtime import SensorRuntime
from osreview.services.energy_sensors import normalize_sensor, organize_sensors
from osreview.ui_cards import power_cards


def test_valid_fps_target_names_only():
    assert valid_process('SkyrimSE.exe')
    assert valid_process('game.exe')
    for name in ('C:\\evil\\game.exe','../game.exe','sh.exe /c','', 'notepad.txt'):
        assert not valid_process(name)


def test_fps_pinned_hash_prevents_untrusted_binary(tmp_path):
    bad = tmp_path/'PresentMon.exe'
    bad.write_bytes(b'not the official PresentMon')
    assert not verify_presentmon(bad)
    assert not verify_presentmon(tmp_path/'missing.exe')
    assert len(PRESENTMON_SHA256)==64


def test_fps_initial_state():
    s=FPSLive().snapshot()
    assert s['enabled'] is False
    assert s['fps'] is None
    assert s['frametime_ms'] is None


def test_new_sensor_min_max_valid():
    sensor = normalize_sensor({'Name':'CPU Package','SensorType':'Temperature','Value':52.4,
                               'Identifier':'/intelcpu/0/temperature/1','Min':32.1,'Max':77.3}, 'LibreHardwareMonitor')
    assert sensor['category']=='CPU'
    assert sensor['min']==32.1 and sensor['max']==77.3


def test_sensor_runtime_missing_bridge_explained():
    runtime=SensorRuntime()
    with patch('osreview.services.sensor_runtime.platform.system', return_value='Windows'), \
         patch('osreview.services.sensor_runtime.find_trusted_bridge', return_value=(None,{'reason':'Manifesto ausente'})):
        snap=runtime.snapshot()
    assert not snap['available']
    assert 'Manifesto ausente' in snap['error']


def test_sensor_runtime_does_not_log_untrusted_reason_or_store_private_path():
    runtime = SensorRuntime()
    reason = 'Falha em C:\\Users\\Example\\segredo@example.com'
    with patch('osreview.services.sensor_runtime.platform.system', return_value='Windows'), \
         patch('osreview.services.sensor_runtime.find_trusted_bridge',
               return_value=(None, {'reason': reason})), \
         patch('osreview.services.sensor_runtime.LOG.warning') as warning:
        runtime.start()
    assert reason == runtime._error
    assert reason not in str(warning.call_args)
    runtime._process = SimpleNamespace(stderr=io.StringIO(reason + '\n'))
    runtime._read_stderr()
    assert 'Example' not in runtime._stderr_lines[0]
    assert 'segredo@example.com' not in runtime._stderr_lines[0]


def test_sensor_cards_explain_engine_failure():
    data={'groups':{},'sensor_count':0,'lhm_connected':False,'note':'sem fonte',
          'engine_status':{'available':False,'error':'DLL não encontrada','devices':0,
                           'age_seconds':None,'warnings':[]}}
    cards=power_cards(data)
    diag=next(c for c in cards if c['title']=='DIAGNÓSTICO DO MOTOR DE SENSORES')
    assert ('Detalhe','DLL não encontrada') in diag['rows']


def test_sensor_cards_print_extremes():
    data={'groups':{'CPU':[{'name':'CPU Package','type':'Temperature','value':55,'unit':'°C','min':30,'max':80}]},
          'sensor_count':1,'lhm_connected':True,'note':'teste'}
    rows=next(x for x in power_cards(data) if x['title']=='CPU')['rows']
    assert 'mín 30 / máx 80' in rows[0][1]


def test_icon_and_attributions_packaged():
    root=Path(__file__).resolve().parents[1]
    assert (root/'assets/osreview.ico').stat().st_size > 10000
    assert (root/'assets/osreview.png').stat().st_size > 10000
    assert 'LibreHardwareMonitor' in (root/'licenses/NOTICE-LIBREHARDWAREMONITOR.txt').read_text()
    assert 'PresentMon' in (root/'fps_engine/AVISO_DE_TERCEIROS.md').read_text()
