"""v0.5.0 regressions: discovery scope, sensors, inventory and safety."""
from pathlib import Path
from unittest.mock import patch
import pytest
from osreview.services.configuration import ConfigStore
from osreview.services.energy_sensors import psu_budget, classify_sensor, normalize_sensor
from osreview.services.hardware_deep import normalize_disks, normalize_memory
from osreview.services.network_diagnostics import local_scan_targets, analyze_network
from osreview.services.fps_capture import summarize_csv
from osreview.services.gemini_questions import ask_gemini


def test_nvme_ssd_discovery():
    rows=normalize_disks([{'Index':0,'Model':'NVMe X','Size':1024**3*512}],
                         [{'DeviceId':0,'BusType':17,'MediaType':4,'SpindleSpeed':0}],[])
    assert rows[0]['technology']=='SSD NVMe'
    assert rows[0]['size_gb']==512
    assert rows[0]['rpm'] is None


def test_hdd_rpm_only_when_reported():
    rows=normalize_disks([{'Index':1,'Model':'Disk X','Size':1024**3*1000}],
                         [{'DeviceId':1,'BusType':11,'MediaType':3,'SpindleSpeed':7200}],[])
    assert rows[0]['technology']=='HDD (SATA)'
    assert rows[0]['rpm']==7200
    rows2=normalize_disks([{'Index':1,'Model':'Disk Y','Size':1024**3*1000}],
                          [{'DeviceId':1,'BusType':11,'MediaType':3}],[])
    assert rows2[0]['rpm'] is None


def test_ddr_memory():
    rows=normalize_memory([{'SMBIOSMemoryType':34,'Speed':5600,'ConfiguredClockSpeed':4800,
                            'Capacity':16*1024**3,'DeviceLocator':'DIMM_A1'}])
    assert rows[0]['technology']=='DDR5' and rows[0]['configured_mhz']==4800


def test_scanner_only_own_private_net():
    rows=[{'name':'Ethernet','up':True,'ipv4':[{'ip':'192.168.40.18','mask':'255.255.255.0','kind':'privado'}]}]
    hosts,subnet=local_scan_targets(rows,'Ethernet',64)
    assert subnet=='192.168.40.0/24'
    assert len(hosts)==64
    assert all(ip.startswith('192.168.40.') for ip in hosts)
    with pytest.raises(ValueError):local_scan_targets(rows,'Internet externa',64)
    external=[{'name':'Wan','up':True,'ipv4':[{'ip':'8.8.8.8','mask':'255.255.255.0'}]}]
    with pytest.raises(ValueError):local_scan_targets(external,'Wan',64)


def test_network_does_not_claim_definitive_health():
    out=analyze_network([{'name':'eth','up':True,'ipv4':[{'kind':'privado','ip':'192.168.1.2'}],'errors_in':0,'errors_out':0}],{}, {})
    assert 'triagem' in out['caveat'].lower()


def test_sensor_vrm_and_no_fabricated_values():
    assert classify_sensor('VRM MOS','/mainboard/vrm/0')=='VRM'
    assert normalize_sensor({'SensorType':'Temperature','Name':'VRM','Value':None}) is None
    assert normalize_sensor({'SensorType':'Temperature','Name':'CPU','Value':1000}) is None


def test_power_recommendation_only_estimate():
    result=psu_budget(125,250,2)
    assert result['ok'] and result['recommended_nominal_w']>=result['estimated_demand_w']
    assert 'estimativa' in result['warning'].lower()
    assert not psu_budget(None,250)['ok']


def test_theme_and_popup_preferences_persist(tmp_path):
    cfg=ConfigStore(tmp_path)
    cfg.set('theme','light')
    cfg.set('tray_hover_popup',False)
    cfg.set('compact_mode',True)
    again=ConfigStore(tmp_path).data
    assert again['theme']=='light'
    assert not again['tray_hover_popup']
    assert again['compact_mode']


def test_fps_csv_does_not_guess(tmp_path):
    path=tmp_path/'x.csv'
    path.write_text('MsBetweenPresents,Other\n16.0,a\n16.5,b\n17.0,c\n',encoding='utf8')
    result=summarize_csv(path)
    assert 58<result['fps_mean']<63
    assert result['frames']==3


def test_gemini_requires_key_before_network():
    with pytest.raises(ValueError,match='chave'):ask_gemini('','Qual o modelo?')
