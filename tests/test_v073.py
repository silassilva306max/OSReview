from osreview import __version__
from pathlib import Path
import json
import platform
import zipfile

from osreview.services import startup_logging, support_bundle, sensor_runtime
from osreview.services.sensor_diagnostics import redact


def test_support_bundle_after_gui_failure(tmp_path, monkeypatch):
    monkeypatch.setenv('OSREVIEW_LOG_DIR', str(tmp_path / 'logs'))
    logs = startup_logging.log_dir()
    (logs / 'osreview.log').write_text('Trace C:\\Users\\Example\\secret.py\n', encoding='utf-8')
    archive = support_bundle.export_support_zip(tmp_path / 'suporte.zip')
    with zipfile.ZipFile(archive) as z:
        assert 'diagnostico_inicializacao.json' in z.namelist()
        assert 'logs/osreview.log.txt' in z.namelist()
        data=json.loads(z.read('diagnostico_inicializacao.json'))
        assert data['app']=='OSReview'
        assert data['version']==__version__
        assert b'Example' not in z.read('logs/osreview.log.txt')


def test_support_bundle_contains_sensor_inventory_when_supplied(tmp_path, monkeypatch):
    monkeypatch.setenv('OSREVIEW_LOG_DIR', str(tmp_path / 'logs'))
    fake = {'groups': {'CPU':[{'name':'CPU Package','type':'Temperature', 'value':55,
                              'device':'Processador', 'identifier':'cpu0', 'unit':'°C'}]},
            'sensor_inventory':{'types':{'temperature':1}, 'thermal_count':1},
            'engine_status':{'available':True,'hardware':[{'Hardware':'CPU', 'Type':'CPU'}]},
            'windows_admin':False}
    archive = support_bundle.export_support_zip(tmp_path / 'report.zip', fake)
    with zipfile.ZipFile(archive) as z:
        d=json.loads(z.read('diagnostico_sensores.json'))
        assert any(s['value']==55 for s in d['valid_sensors'])
        assert d['version']==__version__


def test_missing_bridge_is_not_stuck_started(monkeypatch):
    sensor_runtime.runtime.stop()
    monkeypatch.setattr(sensor_runtime.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(sensor_runtime, 'find_trusted_bridge',
                        lambda: (None, {'reason':'Não compilado'}))
    x=sensor_runtime.SensorRuntime()
    x.start()
    assert x.snapshot()['available'] is False
    assert x._started is False
    assert 'compilado' in x._error
    x._last_attempt_at -= 30
    x.start()
    assert x._started is False


def test_redactor_masks_private_fields():
    value = redact('C:\\Users\\Example\\AppData\\Local 192.168.0.5 00:11:22:AA:BB:CC example@email.com')
    assert 'Example' not in value
    assert '192.168.0.5' not in value
    assert '00:11:22:AA:BB:CC' not in value
    assert 'example@email.com' not in value
