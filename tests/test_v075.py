"""Regression tests: never present NVMe thresholds as measured temperatures."""

from osreview.services.energy_sensors import sensor_inventory
from osreview.services.sensor_analysis import (
    is_real_temperature, temperature_readings, temperature_thresholds,
    power_readings, sensor_overview,
)
from osreview.energy_meter import representative_temperatures


def row(group, name, value, unit='°C', kind='Temperature'):
    return {'group':group,'name':name,'value':value,'unit':unit,'type':kind,
            'device':'Teste SSD' if group=='SSD / HD' else 'CPU exemplo',
            'identifier':('/nvme/0/temperature/11' if name=='Critical Temperature' else
                          '/nvme/0/temperature/10' if name=='Warning Temperature' else '')}


def sample():
    return {'groups':{
        'CPU':[row('CPU','CPU Package',53),row('CPU','Core Average',50.4),
               row('CPU','P-Core #1 Distance to TjMax',50),
               row('CPU','CPU Package',11.67,'W','Power'),
               row('CPU','CPU Platform',21.13,'W','Power')],
        'GPU':[row('GPU','GPU Power',.02,'W','Power')],
        'SSD / HD':[row('SSD / HD','Composite Temperature',37),
                    row('SSD / HD','Temperature #1',36.85),
                    row('SSD / HD','Temperature #2',39.85),
                    row('SSD / HD','Warning Temperature',82),
                    row('SSD / HD','Critical Temperature',89)]}}


def test_nvme_critical_limit_is_never_current_temperature():
    t=temperature_readings(sample())
    assert t['Disco'].value==37
    assert t['Geral'].value==53
    assert t['CPU'].name=='CPU Package'


def test_general_temperature_same_as_cpu_has_same_provenance():
    t=temperature_readings(sample())
    assert t['Geral'].group=='CPU'
    assert t['Geral'].value==t['CPU'].value


def test_nvme_limits_are_still_visible_as_reference():
    limits=temperature_thresholds(sample())
    assert limits=={'warning':82,'critical':89}


def test_valid_temperature_excludes_distance_to_tjmax():
    assert not is_real_temperature(row('CPU','P-Core #1 Distance to TjMax',50))


def test_valid_thermal_count_excludes_metadata():
    inv=sensor_inventory(sample()['groups'])
    assert inv['thermal_count']==5   # CPU2, SSD3, not tjmax/limits
    assert inv['thermal_metadata_count']==3


def test_negative_and_nonfinite_temperature_ignored():
    assert not is_real_temperature(row('CPU','Core Max',float('nan')))
    assert not is_real_temperature(row('CPU','Core Max',300))


def test_cpu_and_platform_power_are_not_combined():
    watt=power_readings(sample())
    assert watt['cpu_package'].value==11.67
    assert watt['cpu_platform'].value==21.13
    assert watt['gpu'].value==0.02
    assert watt['psu_total'] is None


def test_dashboard_reports_unmeasured_total_psu():
    cards=sensor_overview(sample())
    assert len(cards)==6
    total=next(x for x in cards if x['key']=='power_total')
    assert total['value']=='Não medida'


def test_no_sensor_no_invented_values():
    result=temperature_readings(None)
    assert all(val is None for val in result.values())
    assert all(x is None for x in power_readings(None).values())


def test_generic_meter_function_agrees_with_diagnostic_engine():
    assert representative_temperatures(sample()) == {'CPU':53,'GPU':None,'Disco':37,'Geral':53}
