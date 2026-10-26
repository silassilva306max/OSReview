"""Regressions for live updates that users can observe in the desktop UI."""
from datetime import datetime, timedelta
from types import SimpleNamespace

from osreview.app import OSReviewApp, ram_card_detail
from osreview.enhanced_app import OSReviewAppV5
from osreview.services.hardware_deep import memory_frequency_summary


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Label:
    def configure(self, **kwargs):
        self.text = kwargs['text']


class ProcessTree:
    def __init__(self):
        self.order = ['99', '42']
        self.rows = {'99': object(), '42': object()}
        self.selected = ('42',)
        self.focused = '42'
        self.position = 0.4

    def get_children(self):
        return tuple(self.order)

    def yview(self):
        return (self.position, 0.6)

    def yview_moveto(self, value):
        self.position = value

    def selection(self):
        return self.selected

    def selection_set(self, *items):
        self.selected = items

    def focus(self, item=None):
        if item is not None:
            self.focused = item
        return self.focused

    def delete(self, item):
        self.order.remove(item)
        del self.rows[item]

    def item(self, item, **kwargs):
        self.rows[item] = self.rows[item]

    def move(self, item, parent, index):
        self.order.remove(item)
        self.order.insert(index, item)

    def insert(self, parent, index, iid, **kwargs):
        self.order.insert(index, iid)
        self.rows[iid] = object()


def test_process_refresh_keeps_selection_and_scroll():
    tree = ProcessTree()
    selected_row = tree.rows['42']
    app = SimpleNamespace(
        proc_tree=tree, proc_search=Value(''), proc_sort=Value('CPU'),
        procs=[
            {'pid': 42, 'name': 'Editor', 'cpu': 12, 'memory': 4, 'status': 'running'},
            {'pid': 99, 'name': 'Worker', 'cpu': 3, 'memory': 1, 'status': 'running'},
        ],
    )
    OSReviewApp._refresh_processes(app)
    assert tree.order == ['42', '99']
    assert tree.rows['42'] is selected_row
    assert tree.selected == ('42',)
    assert tree.focused == '42'
    assert tree.position == 0.4


def test_compact_panel_ignores_temperature_metadata_and_stale_values():
    label = Label()
    app = SimpleNamespace(
        latest={'cpu_percent': 20, 'memory_percent': 40, 'gpu_percent': None,
                'disk_percent': 30, 'net_recv_mb': 0, 'net_sent_mb': 0,
                'cpu_temp_c': None},
        power_detail={
            'collected_at': datetime.now().isoformat(),
            'groups': {'CPU': [
                {'type': 'Temperature', 'name': 'Distance to TjMax', 'value': 50},
                {'type': 'Temperature', 'name': 'CPU Package', 'value': 53},
            ]},
        },
        mini_labels={'temp': label}, hover_values={},
    )
    OSReviewAppV5._update_mini(app)
    assert label.text == '53.0 °C'
    app.power_detail['collected_at'] = (datetime.now()-timedelta(minutes=2)).isoformat()
    OSReviewAppV5._update_mini(app)
    assert label.text == 'Indisponível'


def test_minimize_to_tray_only_when_icon_is_ready_and_option_enabled():
    root = SimpleNamespace(
        winfo_exists=lambda: True, state=lambda: 'iconic',
        tray=SimpleNamespace(available=True, icon=object()), var_tray=Value(True),
        withdrawn=False,
    )
    root.withdraw = lambda: setattr(root, 'withdrawn', True)
    OSReviewApp._minimize_to_tray(root)
    assert root.withdrawn
    root.withdrawn = False
    root.var_tray = Value(False)
    OSReviewApp._minimize_to_tray(root)
    assert not root.withdrawn


def test_ram_card_shows_available_capacity_and_configured_frequency():
    sample = {'memory_available_gb': 6.25, 'memory_total_gb': 15.69,
              'memory_used_gb': 9.44}
    inventory = {'ram_sticks': [
        {'configured_mhz': 4800, 'speed_mhz': 5600},
        {'configured_mhz': 4800, 'speed_mhz': 5600},
    ]}
    assert ram_card_detail(sample, inventory) == (
        'Disponível: 6.2 / 15.7 GB\nFreq.: 4800 MHz (config.)')
    assert memory_frequency_summary({'ram_sticks': [
        {'configured_mhz': 3200}, {'configured_mhz': 4800}]}) == (
        '3200–4800 MHz (módulos)')
    assert memory_frequency_summary({'ram_sticks': [
        {'configured_mhz': None, 'speed_mhz': 5600}]}) == '5600 MHz (nominal)'
    assert 'Não informada' in ram_card_detail(sample, None)
