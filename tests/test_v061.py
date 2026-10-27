"""v0.6.1 regressions for network UI, APIPA, speedtest fallbacks and DNS."""
from unittest.mock import patch

from osreview.services.network_diagnostics import (
    adapter_findings, analyze_network, compare_public_dns, DNS_PROVIDERS,
    _dns_query_packet, run_speedtest, probe_dns_server,
)
from osreview.ui_cards import network_cards


def test_disconnected_wifi_with_apipa_must_be_in_warnings():
    interfaces=[
        {'name':'Wi-Fi','up':False,'ipv4':[{'ip':'169.254.70.230','kind':'link-local (APIPA)'}],
         'ipv6':['fe80::1'],'errors_in':0,'errors_out':0},
        {'name':'Ethernet','up':True,'ipv4':[{'ip':'192.168.1.21','kind':'privado'}],
         'ipv6':[],'speed_mbps':1000,'errors_in':0,'errors_out':0},
    ]
    out=analyze_network(interfaces, {'Ethernet':['192.168.1.1']},{'Ethernet':['192.168.1.1']})
    assert out['level']=='unverified'
    assert out['primary_interface']=='Ethernet'
    assert out['primary_link_mbps']==1000
    assert any('APIPA' in x for x in out['adapter_warnings'])
    cards=network_cards({'interfaces':interfaces, 'dns':{'Ethernet':['192.168.1.1']},
                         'gateways':{'Ethernet':['192.168.1.1']}})
    assert any('Wi-Fi' in x['title'] for x in cards)
    assert any('169.254.70.230' in str(x) for x in cards)


def test_no_false_definitive_internet_health():
    net=[{'name':'Ethernet','up':True,'ipv4':[{'ip':'192.168.20.7','kind':'privado'}], 'ipv6':[]}]
    out=analyze_network(net, {},{})
    assert 'precisa ser testada' in out['status']
    assert out['level']=='unverified'


def test_bad_connection_dns_failure_visible():
    nic=[{'name':'en0','up':True,'ipv4':[{'kind':'privado','ip':'10.0.0.2'}], 'ipv6':[]}]
    res=analyze_network(nic,{}, {}, {'dns':False,'internet':False,'gateway':False})
    assert res['level']=='attention'
    assert any('DNS' in x for x in res['issues'])


def test_speedtest_uses_backup_when_first_engine_fails(monkeypatch):
    from osreview.services import network_diagnostics as net
    monkeypatch.setattr(net,'_speedtest_ookla',lambda progress=None,duration_s=10: (_ for _ in ()).throw(RuntimeError('bloqueado')))
    monkeypatch.setattr(net,'_speedtest_cloudflare',lambda progress=None,duration_s=10:{'ok':True,'server':'Cloudflare Speed Test', 'download_mbps':34.,'upload_mbps':10.})
    out=run_speedtest()
    assert out['ok'] and out['download_mbps']==34.
    assert len(out['attempts'])==2


def test_speedtest_passes_selected_duration_to_engine(monkeypatch):
    from osreview.services import network_diagnostics as net
    selected=[]
    def fake(_progress, duration_s):
        selected.append(duration_s)
        return {'ok':True,'download_mbps':800.,'upload_mbps':900.}
    monkeypatch.setattr(net,'_speedtest_ookla',fake)
    assert run_speedtest(provider='ookla',duration_s=20)['ok']
    assert selected==[20]
    assert not run_speedtest(duration_s=1)['ok']


def test_speedtest_preserves_proper_error_no_fabricated_values(monkeypatch):
    from osreview.services import network_diagnostics as net
    monkeypatch.setattr(net,'_speedtest_ookla',lambda progress=None,duration_s=10: (_ for _ in ()).throw(RuntimeError('bloqueado')))
    monkeypatch.setattr(net,'_speedtest_cloudflare',lambda progress=None,duration_s=10: {'ok':False,'server':'Cloudflare Speed Test','error':'HTTP 403', 'download_mbps':None,'upload_mbps':None})
    out=run_speedtest()
    assert not out['ok'] and 'HTTP 403' in out['error']
    assert out['download_mbps'] is None


def test_dns_presets_only_from_official_addresses():
    assert [(d['primary'],d['secondary']) for d in DNS_PROVIDERS]==[
        ('1.1.1.1','1.0.0.1'),('8.8.8.8','8.8.4.4'),('9.9.9.9','149.112.112.112')]


def test_dns_compare_chooses_measured_latency_not_arbitrary_preference(monkeypatch):
    from osreview.services import network_diagnostics as net
    timings={'1.1.1.1':19.,'8.8.8.8':32.,'9.9.9.9':9.}
    monkeypatch.setattr(net,'probe_dns_server',lambda ip:{'ip':ip,'median_ms':timings[ip],'ok':True})
    result=compare_public_dns()
    assert result['fastest']=='Quad9 (protegido)'
    assert len(result['providers'])==3


def test_dns_test_is_read_only_and_unknown_cannot_be_guessed():
    result=probe_dns_server('127.0.0.1',attempts=1,timeout=0.02)
    assert result['ok'] is False
    assert result['median_ms'] is None
    assert len(_dns_query_packet('example.com',7))>20


def test_successful_connectivity_is_not_reported_as_untested():
    nic=[{'name':'Ethernet','up':True,'ipv4':[{'ip':'10.2.0.22','kind':'privado'}], 'ipv6':[]}]
    result=analyze_network(nic,{}, {'Ethernet':['10.2.0.1']},
                           {'dns':True,'internet':True,'gateway':False})
    assert 'confirmada' in result['status']
    assert result['level']=='ok'


def test_arp_device_cannot_be_marked_as_online_without_response():
    from osreview.ui_cards import local_devices_cards
    rows=local_devices_cards({'interface':'Ethernet','subnet':'192.168.1.0/24',
                              'tested':64,'devices':[{'ip':'192.168.1.10','responds':False,'mac':'aa-bb-cc','neighbor_state':'Stale'}]})
    assert 'presença atual não confirmada' in str(rows)
