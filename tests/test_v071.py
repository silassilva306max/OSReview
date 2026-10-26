"""Regression checks for telemetry classification and explicit network privacy."""
import io
import json
from unittest.mock import patch

from osreview.services.energy_sensors import normalize_sensor, organize_sensors, sensor_inventory, _fallback_acpi_thermal_zones
from osreview.energy_meter import representative_temperatures
from osreview.services.isp_lookup import fetch_isp
from osreview.services.fps_targets import graphical_processes, desktop_refresh_hz
from osreview.ui_cards import power_cards, network_cards


def test_intel_gpu_temperature_from_hardware_type():
    s=normalize_sensor({'Name':'Temperature','SensorType':'Temperature','Value':42.0,
                        'Identifier':'/unknown/heat/1','HardwareType':'GpuIntel',
                        'Device':'Intel UHD Graphics'})
    assert s['category']=='GPU' and s['device']=='Intel UHD Graphics'


def test_amd_cpu_temperature_from_hardware_type():
    s=normalize_sensor({'Name':'Heat','SensorType':'Temperature','Value':64.4,
                        'Identifier':'/unknown/heat/2','HardwareType':'Cpu'})
    assert s['category']=='CPU'


def test_storage_thermal_category():
    s=normalize_sensor({'Name':'Temperature 1','SensorType':'Temperature','Value':49,
                        'Identifier':'/sensor/1','HardwareType':'Storage'})
    assert s['category']=='SSD / HD'


def test_all_telemetry_not_thermal():
    groups=organize_sensors([{'Name':'CPU Clock','SensorType':'Clock','Value':1300,'HardwareType':'Cpu'},
         {'Name':'Total CPU Load','SensorType':'Load','Value':30,'HardwareType':'Cpu'}])
    inv=sensor_inventory(groups)
    assert inv['thermal_count']==0 and inv['types']=={'clock':1,'load':1}
    cards=power_cards({'groups':groups,'sensor_count':2,'lhm_connected':True,'note':'', 'sensor_inventory':inv})
    assert any('nenhuma temperatura física' in str(c['rows']).lower() for c in cards)


def test_general_temperature_not_mislabeled_cpu():
    groups=organize_sensors([{'Name':'Zona térmica ACPI','SensorType':'Temperature','Value':37,
                              'Identifier':'/acpi/thermal/0'}])
    measures=representative_temperatures({'groups':groups})
    assert measures['Geral']==37 and measures['CPU'] is None


def test_acpi_kelvin_converts_correctly():
    with patch('osreview.services.windows_native.query_wmi',return_value=[{'InstanceName':'TZ1', 'CurrentTemperature':3082}]):
        values=_fallback_acpi_thermal_zones()
    assert len(values)==1 and abs(values[0]['Value']-35.1)<0.2


def test_acpi_invalid_ignored():
    with patch('osreview.services.windows_native.query_wmi',return_value=[{'InstanceName':'TZ1', 'CurrentTemperature':0}]):
        assert _fallback_acpi_thermal_zones()==[]


def test_isp_provider_lookup():
    class Reply:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return json.dumps({'ip':'203.0.113.9','org':'Rede ISP de teste','asn':'AS64500'}).encode()
    with patch('osreview.services.isp_lookup.urlopen',return_value=Reply()):
        result=fetch_isp()
    assert result['ok'] and result['organization']=='Rede ISP de teste'
    cards=network_cards({'interfaces':[]},isp=result)
    assert any('OPERADORA' in c['title'] for c in cards)


def test_isp_lookup_rejects_bad_ip():
    class Reply:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'{"ip":"garbage","org":"fake"}'
    with patch('osreview.services.isp_lookup.urlopen',return_value=Reply()):
        assert not fetch_isp()['ok']


def test_graphics_targets_no_windows():
    with patch('osreview.services.fps_targets.platform.system',return_value='Linux'):
        assert graphical_processes()==[]
        assert desktop_refresh_hz() is None
