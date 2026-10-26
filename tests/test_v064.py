"""v0.6.4: full /24 scan and hostname/author credits regressions."""
from pathlib import Path
from unittest.mock import patch

import pytest

from osreview.services.network_diagnostics import (
    local_scan_targets, discover_local_hosts, resolve_local_hostname, _netbios_name
)
from osreview.ui_cards import local_devices_cards, power_cards


def adapter(ip='192.168.0.37', mask='255.255.255.0'):
    return [{'name': 'Ethernet', 'up': True,
             'ipv4': [{'ip':ip, 'mask':mask, 'kind':'privado'}]}]


def test_scanner_supports_all_254_assignable_ipv4():
    targets, subnet = local_scan_targets(adapter(), 'Ethernet', 254)
    assert subnet == '192.168.0.0/24'
    assert len(targets) == 254
    assert targets[0] == '192.168.0.1'
    assert targets[-1] == '192.168.0.254'
    assert '192.168.0.0' not in targets
    assert '192.168.0.255' not in targets
    assert '192.168.0.37' in targets


def test_public_or_apipa_not_scanned():
    with pytest.raises(ValueError):
        local_scan_targets(adapter('169.254.20.5'), 'Ethernet', 254)
    with pytest.raises(ValueError):
        local_scan_targets(adapter('8.8.8.8'), 'Ethernet', 254)
    with pytest.raises(ValueError):
        local_scan_targets(adapter(), 'Ethernet', 255)


def test_resolve_returns_reverse_dns_hostname():
    with patch('socket.gethostbyaddr',return_value=('pc-ti.empresa.local',[],['192.168.0.3'])):
        host,source=resolve_local_hostname('192.168.0.3')
    assert host=='pc-ti.empresa.local'
    assert 'DNS' in source


def test_unresolved_name_is_explicit():
    with patch('socket.gethostbyaddr',side_effect=OSError('sem PTR')):
        with patch('osreview.services.network_diagnostics._netbios_name',return_value=None):
            host,source=resolve_local_hostname('192.168.0.3')
    assert host is None and source=='Não resolvido'


def test_local_name_does_not_require_dns():
    with patch('socket.gethostname',return_value='PC-LOCAL'):
        host,source=resolve_local_hostname('192.168.0.37',is_local=True)
    assert host=='PC-LOCAL' and 'computador' in source.lower()


def test_netbios_parser_mock_windows():
    from subprocess import CompletedProcess
    mocked=b'    PC-FINANCEIRO      <00>  UNIQUE       Registered\r\n    WORKGROUP  <00>  GROUP       Registered'
    with patch('osreview.services.network_diagnostics.platform.system',return_value='Windows'),\
         patch('osreview.services.network_diagnostics.shutil.which',return_value=r'C:\\Windows\\System32\\nbtstat.exe'),\
         patch('osreview.services.network_diagnostics.subprocess.run',return_value=CompletedProcess([],0,mocked)):
        assert _netbios_name('192.168.0.4')=='PC-FINANCEIRO'


def test_scan_merges_mac_and_hostname_without_guessing():
    net={'interfaces':adapter()}
    with patch('osreview.services.network_diagnostics._ping',return_value=(True,5.5)),\
         patch('osreview.services.network_diagnostics.resolve_local_hostname',return_value=('PC-1','DNS reverso')) ,\
         patch('osreview.services.network_diagnostics.read_neighbor_cache',return_value={'192.168.0.1':{'mac':'AA-BB-CC-DD-EE-FF','neighbor_state':'Reachable'}}):
        result=discover_local_hosts(net,'Ethernet',1)
    assert result['tested']==1
    assert result['devices'][0]['hostname']=='PC-1'
    assert result['devices'][0]['mac']=='AA-BB-CC-DD-EE-FF'
    cards=local_devices_cards(result)
    assert any((key=='Nome do computador' and val=='PC-1') for key,val in cards[1]['rows'])


def test_sensor_credit_in_cards_and_license_exists():
    cards=power_cards({'groups':{},'sensor_count':0,'lhm_connected':False})
    txt=str(cards)
    assert 'LibreHardwareMonitorLib 0.9.6' in txt
    assert 'Mozilla Public License' in txt
    assert 'independente' in txt.lower()
    root=Path(__file__).resolve().parents[1]
    assert (root/'licenses/MPL-2.0.txt').is_file()
    assert (root/'licenses/NOTICE-LIBREHARDWAREMONITOR.txt').is_file()
    assert 'LibreHardwareMonitorLib' in (root/'sensor_bridge/SensorBridge.csproj').read_text()
