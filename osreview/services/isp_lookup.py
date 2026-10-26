"""User-triggered public IP/ASN lookup via HTTPS; never runs on app startup."""
from __future__ import annotations
import ipaddress
import json
from urllib.request import Request, urlopen

URL='https://ipapi.co/json/'

def fetch_isp(timeout=8):
    """Exposes public IP to lookup provider. No geolocation fields are retained."""
    try:
        req=Request(URL, headers={'User-Agent':'OSReview/0.7.3 (+local diagnostics)', 'Accept':'application/json'})
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise ValueError(f'HTTP {resp.status}')
            blob=resp.read(24_000)
        data=json.loads(blob)
        if data.get('error'):
            raise ValueError('Serviço recusou a consulta')
        ip=str(ipaddress.ip_address(str(data.get('ip') or '')))
        asn=str(data.get('asn') or '').strip()[:40]
        org=str(data.get('org') or '').strip()[:180]
        if not org: raise ValueError('Organização do endereço não informada')
        return {'ok': True,'ip':ip,'organization':org,'asn':asn,
                'source':'ipapi.co','disclaimer':
                'Indica a rede/ASN que anuncia o IP público; pode mostrar operadora upstream, VPN, proxy ou saída corporativa, não necessariamente seu provedor contratado.'}
    except Exception as exc:
        return {'ok':False,'error':f'{type(exc).__name__}: {str(exc)[:120]}', 'source':'ipapi.co'}
