"""Security and native telemetry regressions. No Windows host required."""
import importlib
import platform
import plistlib
from unittest import mock

from osreview.services.mac_power import _battery_from_iokit
from osreview.services.energy_sensors import collect_energy_sensors
from osreview.services.windows_inventory import native_windows_query
from osreview.services import windows_native


def test_unsupported_legacy_query_never_executed():
    with mock.patch.object(windows_native, 'query_wmi') as query, mock.patch('subprocess.run') as run:
        assert native_windows_query('Start-Process powershell -Verb RunAs') is None
        query.assert_not_called()
        run.assert_not_called()


def test_wmi_inventory_routes_to_allowlisted_class():
    with mock.patch.object(windows_native,'query_wmi',return_value=[{'Name':'Intel UHD Graphics'}]) as query:
        rows=native_windows_query('Get-CimInstance Win32_VideoController | Select-Object Name | ConvertTo-Json')
        assert rows[0]['Name']=='Intel UHD Graphics'
        assert query.call_args.args[0]=='Win32_VideoController'


def test_windows_updates_use_native_com_reader():
    with mock.patch.object(windows_native,'collect_updates',return_value={'ok':True,'updates':[], 'total':0}):
        value=native_windows_query('New-Object -ComObject Microsoft.Update.Session')
        assert value['ok'] is True


def test_powershell_command_is_not_run_by_runtime(monkeypatch):
    monkeypatch.setattr(platform,'system',lambda:'Windows')
    with mock.patch('subprocess.run') as run, mock.patch.object(windows_native,'_com',return_value=None):
        assert native_windows_query('Get-CimInstance Win32_BaseBoard | ConvertTo-Json') is None
        run.assert_not_called()


def test_mac_battery_reading_is_labeled_not_psu():
    sample={'Voltage':12300,'Amperage':-1500}
    result=_battery_from_iokit([sample])
    assert result['voltage_v']==12.3
    assert result['power_w']==-18.45
    assert 'bateria' in result['scope'].lower()


def test_mac_battery_unavailable_when_bad():
    assert _battery_from_iokit([]) is None
    assert _battery_from_iokit([{'Voltage':None,'Amperage':12}]) is None
    assert _battery_from_iokit([{'Voltage':100_000,'Amperage':12}]) is None


def test_mac_os_power_collects_without_privilege(monkeypatch):
    from osreview.services import mac_power
    monkeypatch.setattr(mac_power.platform,'system',lambda:'Darwin')
    monkeypatch.setattr(mac_power,'_run',lambda *a,**k:plistlib.dumps([{'Voltage':12100,'Amperage':1300}]))
    result=mac_power.collect_mac_power()
    assert result['ok']
    assert result['battery_electrical']['power_w']==15.73


def test_unknown_unsupported_sensor_is_unavailable_not_fabricated():
    from osreview.services.energy_sensors import normalize_sensor
    assert normalize_sensor({'Name':'PCH','SensorType':'Temperature','Value':None}) is None
    assert normalize_sensor({'Name':'PCH','SensorType':'Temperature','Value':200.0}) is None


def test_native_query_not_used_off_windows():
    with mock.patch.object(windows_native,'_com',return_value=None):
        assert windows_native.query_wmi('Win32_BaseBoard',('Manufacturer',)) is None
