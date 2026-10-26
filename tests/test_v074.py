import json
from pathlib import Path
from osreview.services.sensor_triage import triage


def test_no_temp_with_missing_sensors():
    data={
      'windows_admin':False,
      'engine_status':{'available':True,'unavailable':[{'SensorType':'Temperature','Sensor':'CPU Package'}],
                       'hardware':[{'Hardware':'Intel i5'}]},
      'sensor_inventory':{'thermal_count':0},
      'groups':{'CPU':[{'type':'Power','value':0.0},{'type':'Load','value':10}]}
    }
    result=triage(data)
    assert result['missing_temperatures']==1
    assert result['invalid_power_zero']==1
    assert any('sem elevação' in x.lower() for x in result['findings'])
    assert result['valid_temperatures']==0


def test_one_real_temperature():
    result=triage({'sensor_inventory':{'thermal_count':1},
                   'engine_status':{'available':True},
                   'groups':{'CPU':[{'type':'Temperature','value':50.0}]}})
    assert result['valid_temperatures']==1
    assert result['missing_temperatures']==0


def test_power_zero_warning_avoids_inventing_consumption():
    result=triage({'sensor_inventory':{'thermal_count':0}, 'engine_status':{'available':True},
                   'groups':{'GPU':[{'type':'Power','value':0.0},{'type':'Voltage','value':0.23}]}})
    assert result['invalid_power_zero']==1
    assert any('não confirmam' in x for x in result['findings'])


def test_battery_mwh_not_mislabeled_wh():
    from osreview.services.energy_sensors import normalize_sensor
    item=normalize_sensor({'HardwareType':'Battery','SensorType':'Energy',
        'Name':'Designed Capacity', 'Identifier':'/battery/example/energy/0',
        'Value':42009})
    assert item['value']==42.01 and item['unit']=='Wh'

