from osreview import __version__
"""v0.7.2 log export and passive alternative diagnostics."""
import json
from unittest.mock import patch

from osreview.services.sensor_diagnostics import redact, build_report, write_report, advice
from osreview.services.energy_sensors import organize_sensors, sensor_inventory, collect_energy_sensors
from osreview.ui_cards import power_cards


def _sample():
    groups = organize_sensors([
        {'Name':'CPU Package', 'SensorType':'Temperature','Value':52.4,
         'HardwareType':'Cpu', 'Device':'Intel Core i5'},
        {'Name':'CPU Power','SensorType':'Power','Value':18.2,
         'HardwareType':'Cpu', 'Device':'Intel Core i5'},
    ])
    return {'groups': groups, 'sensor_count':2, 'sensor_inventory':sensor_inventory(groups),
            'lhm_connected':True, 'windows_admin':False, 'note':'',
            'engine_status':{'available':True,'devices':3,'hardware':[{'Hardware':'CPU','Type':'Cpu','SensorCount':10}],
                'unavailable':[{'Hardware':'CPU','Sensor':'Tdie','SensorType':'Temperature'}],
                'missing_count':1, 'warnings':[], 'stderr':[], 'age_seconds':0.5}}


def test_report_has_classified_sensors_and_no_value():
    with patch('osreview.services.sensor_diagnostics.find_trusted_bridge',return_value=(None,{'present':False,'integrity':'indisponível','reason':'não compilada','allowed':False})):
        report=build_report(_sample())
    assert report['inventory']['thermal_count']==1
    assert report['motor']['missing_count']==1
    assert len(report['valid_sensors'])==2
    assert report['no_value_sensors'][0]['Sensor']=='Tdie'
    assert 'CPU' in report['sensors_by_group']


def test_export_json_to_user_chosen_location(tmp_path):
    out=tmp_path/'meu_diagnostico.json'
    with patch('osreview.services.sensor_diagnostics.find_trusted_bridge',return_value=(None,{})):
        write_report(_sample(),out)
    obj=json.loads(out.read_text(encoding='utf-8'))
    assert obj['app']=='OSReview' and obj['version']==__version__
    assert obj['environment']['admin_windows'] is False


def test_rejects_non_json_file(tmp_path):
    try: write_report(_sample(),tmp_path/'diagnostico.exe')
    except ValueError: return
    assert False, 'Deve bloquear a extensão não JSON'


def test_redacts_sensitive_values():
    value='C:\\Users\\silasteste\\AppData\\Local e joao@example.com 192.168.0.17 AA:BB:CC:DD:EE:FF'
    clean=redact(value)
    assert 'silasteste' not in clean
    assert 'joao@example.com' not in clean
    assert '192.168.0.17' not in clean
    assert 'AA:BB:CC:DD:EE:FF' not in clean


def test_no_temp_advice():
    data=_sample()
    data['sensor_inventory']['thermal_count']=0
    notes=advice(data)
    assert any('temperatura' in x for x in notes)


def test_power_status_has_missing_sensor_count():
    cards=power_cards(_sample())
    rowstr=str(next(x['rows'] for x in cards if 'DIAGNÓSTICO DO MOTOR' in x['title']))
    assert 'Sensores sem valor' in rowstr


def test_openhardwaremonitor_fallback_is_passive():
    raw=[{'Name':'CPU Package','SensorType':'Temperature','Value':51,
          'Identifier':'/intelcpu/0/temperature/0'}]
    # All external queries are mocked; fallback must simply read a WMI class.
    with patch('osreview.services.energy_sensors.platform.system',return_value='Windows'),\
         patch('osreview.services.energy_sensors._bundled_sensor_bridge',return_value=(None,None)),\
         patch('osreview.services.energy_sensors.native_windows_query',return_value=None),\
         patch('osreview.services.windows_native.query_wmi',side_effect=lambda cls,fields,**k: raw if k.get('namespace')==r'root\OpenHardwareMonitor' else []) as wmi,\
         patch('osreview.services.energy_sensors._fallback_storage_sensors',return_value=[]),\
         patch('osreview.services.energy_sensors._fallback_acpi_thermal_zones',return_value=[]),\
         patch('osreview.services.sensor_runtime.runtime.snapshot',return_value={'available':False, 'error':'sem dados'}):
        res=collect_energy_sensors()
    assert res['sensor_inventory']['thermal_count'] == 1
    assert res['groups']['CPU'][0]['value'] == 51
    assert 'Open Hardware Monitor' in res['sensor_source']
    assert wmi.called


def test_report_never_contains_raw_pid(tmp_path):
    data=_sample()
    data['engine_status']['pid']=99124
    with patch('osreview.services.sensor_diagnostics.find_trusted_bridge',return_value=(None,{})):
        report=build_report(data)
    assert 'pid' not in report['motor']


def test_psu_sensor_credited_without_estimating_total():
    from osreview.services.energy_sensors import normalize_sensor
    result = normalize_sensor({'Name':'Output Power','SensorType':'Power','Value':110,
        'HardwareType':'Psu','Device':'Fonte Corsair com telemetria'})
    assert result['category']=='Fonte / PSU' and result['unit']=='W'
