"""Validated, provenance-aware sensor interpretation for all OSReview views.

NVMe warning/critical limits and CPU Distance-to-TjMax are METADATA,
never a current temperature. A 'system total power' is never fabricated
from component domains which may overlap. Does not require Windows APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class Reading:
    value: float
    group: str
    name: str
    device: str
    source: str

    def display(self, suffix='°C') -> str:
        precision=2 if suffix=='W' and 0 <= self.value < 0.1 else 1
        return f'{self.value:.{precision}f} {suffix}'

    def provenance(self) -> str:
        return f'{self.group} · {self.name}'


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number=float(value)
    return number if isfinite(number) else None


def is_real_temperature(row: dict) -> bool:
    """Strict positive classification: exclude limits and temperature margins."""
    if str(row.get('type','')).casefold() != 'temperature':
        return False
    name=str(row.get('name','')).casefold()
    ident=str(row.get('identifier','')).casefold()
    if any(token in name for token in (
        'warning temperature', 'critical temperature', 'temperature warning',
        'temperature critical', 'temperature limit', 'threshold', 'trip point',
        'distance to tjmax', 'distance to tcc', 'thermal margin',
        'temperature margin', 'tjunction max', 't j max',
    )):
        return False
    # LHM NVMe specification fields have fixed, documented indices.
    if '/nvme/' in ident and (ident.endswith('/temperature/10') or ident.endswith('/temperature/11')):
        return False
    val=_number(row.get('value'))
    return val is not None and -30<=val<=125


def temperature_readings(snapshot: dict | None) -> dict[str, Reading | None]:
    groups=(snapshot or {}).get('groups') or {}
    samples: list[Reading]=[]
    for group, rows in groups.items():
        for row in rows or []:
            if is_real_temperature(row):
                samples.append(Reading(float(row['value']), str(group), str(row.get('name','Sensor')),
                                       str(row.get('device','')),str(row.get('source',''))))

    def chosen(group: str, preferred: tuple[str,...]) -> Reading | None:
        members=[r for r in samples if r.group == group]
        if not members:return None
        for key in preferred:
            found=[r for r in members if r.name.casefold()==key]
            if found:return found[0]
        return max(members,key=lambda r:r.value)

    cpu=chosen('CPU',('cpu package','core max','core average','tctl/tdie','cpu tctl','cpu tdie'))
    gpu=chosen('GPU',('gpu core','gpu temperature','gpu hot spot'))
    disk=chosen('SSD / HD',('composite temperature','temperature #1','temperature #2'))
    general=max(samples,key=lambda r:r.value) if samples else None
    return {'CPU':cpu,'GPU':gpu,'Disco':disk,'Geral':general}


def power_readings(snapshot: dict | None) -> dict[str, Reading | None]:
    groups=(snapshot or {}).get('groups') or {}
    readings=[]
    for group,rows in groups.items():
        for row in rows or []:
            if str(row.get('type','')).casefold() != 'power':continue
            value=_number(row.get('value'))
            if value is None or value < 0:continue
            readings.append(Reading(value,str(group),str(row.get('name','Sensor')),
                                    str(row.get('device','')),str(row.get('source',''))))
    def find(group,name):
        for r in readings:
            if r.group==group and r.name.casefold()==name and r.value>0:
                return r
        return None
    gpu=next((r for r in readings if r.group=='GPU' and r.value>0),None)
    if gpu is None:gpu=next((r for r in readings if r.group=='GPU' and r.value==0),None)
    return {
        'cpu_package':find('CPU','cpu package'),
        'cpu_platform':find('CPU','cpu platform'),
        'gpu': gpu,
        'battery':next((r for r in readings if 'battery' in r.device.casefold() and r.value>0),None),
        'psu_total':next((r for r in readings if r.group=='Fonte / PSU' and r.value>0 and
                          any(t in r.name.casefold() for t in ('total','input power','output power'))),None)
    }


def clock_readings(snapshot: dict | None) -> dict[str, Reading | None]:
    """Only measured core clocks; bus and memory clocks are not GPU/CPU clocks."""
    groups=(snapshot or {}).get('groups') or {}
    result={}
    for group in ('CPU','GPU'):
        rows=[]
        for row in groups.get(group) or []:
            if str(row.get('type','')).casefold()!='clock':continue
            name=str(row.get('name','')).casefold()
            if not any(word in name for word in ('core','gpu','graphics','cpu')):continue
            if any(word in name for word in ('memory','bus','ring','uncore')):continue
            value=_number(row.get('value'))
            if value is None or not 0 < value < 10000:continue
            rows.append(Reading(value,group,str(row.get('name','Clock')),
                                str(row.get('device','')),str(row.get('source',''))))
        result[group]=max(rows,key=lambda reading:reading.value) if rows else None
    return result


def temperature_thresholds(snapshot: dict | None, group='SSD / HD') -> dict[str,float]:
    out={}
    for row in ((snapshot or {}).get('groups') or {}).get(group,[]):
        name=str(row.get('name','')).casefold()
        value=_number(row.get('value'))
        if value is None:continue
        if name=='warning temperature':out['warning']=value
        if name=='critical temperature':out['critical']=value
    return out


def timestamp_of(snapshot: dict | None) -> str:
    if not snapshot:return 'Aguardando coleta'
    iso=str(snapshot.get('collected_at') or '')
    try:return datetime.fromisoformat(iso).strftime('%H:%M:%S')
    except (ValueError,TypeError):return 'Leitura recente'


def sensor_overview(snapshot: dict | None) -> list[dict]:
    """Live dashboard cards; no fabricated PSU demand or invented readings."""
    temps=temperature_readings(snapshot); power=power_readings(snapshot)
    specs=[]
    for key,title in [('CPU','CPU · Temperatura'),('GPU','GPU · Temperatura'),
                      ('Disco','SSD / HD · Temperatura'),('Geral','Maior temperatura medida')]:
        r=temps[key]
        subtitle=r.provenance() if r else 'Sensor não disponível'
        specs.append({'key':'temp_'+key.lower(),'title':title,'value':r.display() if r else 'Indisponível',
                      'description':subtitle, 'reading':r})
    cpu=power['cpu_package']
    specs.append({'key':'power_cpu','title':'CPU · Potência do pacote',
                  'value':cpu.display('W') if cpu else 'Indisponível',
                  'description':'Leitura do pacote CPU; não corresponde à fonte inteira', 'reading':cpu})
    psu=power['psu_total']
    specs.append({'key':'power_total','title':'Energia / Fonte',
                  'value':psu.display('W') if psu else 'Não medida',
                  'description':'Fonte digital: consumo total reportado' if psu else
                      'Total não mensurável; CPU e GPU exibidas separadamente.',
                  'reading':psu})
    return specs
