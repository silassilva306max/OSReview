from osreview.services.background_activity import calculate_activity, parse_update_events, interpret_background_activity, collect_background_activity
from osreview.services.network_diagnostics import run_speedtest
from osreview.ui_cards import hardware_cards, board_cards, network_cards, activity_cards


def test_activity_cpu_disk_rate_and_type():
    before={7:{'pid':7,'name':'TiWorker.exe','cpu_time':1.0,'read':0,'write':0,'rss':1000000}}
    after={7:{'pid':7,'name':'TiWorker.exe','cpu_time':3.,'read':1048576*4,'write':1048576*8,'rss':1048576*90}}
    rows=calculate_activity(before,after,2.,4)
    assert rows[0]['cpu_percent']==25.
    assert rows[0]['read_mb_s']==2.
    assert rows[0]['write_mb_s']==4.
    assert rows[0]['category']=='atualização'
    assert 'NÃO confirma' in rows[0]['certainty']


def test_update_event_levels():
    events=parse_update_events([
        {'Id':43,'TimeCreated':'10:00','Message':'started'},
        {'Id':19,'TimeCreated':'10:30','Message':'installed'},
        {'Id':101,'TimeCreated':'11:00','Message':'other'},
    ])
    assert [x['id'] for x in events]==[43,19]
    assert 'início' in events[0]['status']


def test_idle_no_false_confirmed_updates():
    x=interpret_background_activity([],[],None,None,20)
    assert x['observed_active']==0
    assert 'Sem indícios' in x['status']


def test_active_process_no_confirmation():
    p={'pid':2,'name':'msiexec.exe','category':'instalação',
       'cpu_percent':2,'read_mb_s':2,'write_mb_s':1}
    x=interpret_background_activity([p],[],14,8,65)
    assert 'Atividade' in x['status']
    assert 'limitada' in x['confidence']
    assert len(x['impact_notes'])>=2


def test_background_nonwindows_read_only():
    import platform
    if platform.system()!='Windows':
        assert not collect_background_activity()['supported']


def test_card_specifications():
    cards=hardware_cards({'cpus':[{'name':'Intel Core i5','reported_mhz':2700}],
       'ram_sticks':[{'manufacturer':'Kingston','configured_mhz':3200}],
       'disks':[{'model':'SSD Test','technology':'SSD NVMe','size_gb':512}]})
    assert any('PROCESSADOR' in card['title'] for card in cards)
    assert any('SSD Test' in card['title'] for card in cards)
    assert not any('{' in card['title'] for card in cards)
    assert board_cards({'model':'B660','chipset':'B660'})[0]['rows'][1][1]=='B660'
    assert network_cards({'interfaces':[]})[0]['title']=='SITUAÇÃO DA REDE'
    assert activity_cards({'supported':True,'status':'Sem indícios','events':[]})[0]['title'].startswith('DIAGNÓSTICO')


def test_speedtest_no_network_dependency(monkeypatch):
    from urllib.error import URLError
    from osreview.services import network_diagnostics as net
    def fail(*args,**kwargs):raise URLError('Sem rede')
    monkeypatch.setattr('urllib.request.urlopen',fail)
    monkeypatch.setattr(net, '_speedtest_ookla', fail)
    result=run_speedtest()
    assert not result['ok']
    assert 'error' in result
    assert result['server']=='Cloudflare Speed Test'
