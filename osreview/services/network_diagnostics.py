"""Diagnóstico de rede local e Internet. Coleta passiva por padrão.

Testes de conexão, speedtest e varredura são SOMENTE após ação explícita do usuário.
Varredura limitada a endereços IPv4 privados da sub-rede local configurada.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import json
import platform
import re
import shutil
import socket
import subprocess
import time
from typing import Any

import psutil
from .windows_inventory import native_windows_query, _list


def _ip_type(ip: str) -> str:
    try:
        parsed = ipaddress.ip_address(ip.split('%', 1)[0])
        if parsed.is_loopback:
            return 'loopback'
        if parsed.is_link_local:
            return 'link-local (APIPA)' if parsed.version == 4 else 'link-local IPv6'
        if parsed.is_private:
            return 'privado'
        return 'público'
    except ValueError:
        return 'desconhecido'


def basic_interfaces(addrs=None, stats=None, counters=None) -> list[dict[str, Any]]:
    if addrs is None:
        addrs = psutil.net_if_addrs()
    if stats is None:
        stats = psutil.net_if_stats()
    if counters is None:
        counters = psutil.net_io_counters(pernic=True)
    rows = []
    for alias, ips in addrs.items():
        stat = stats.get(alias)
        counter = counters.get(alias) if counters else None
        ip4 = []
        ip6 = []
        mac = None
        for address in ips:
            if address.family == socket.AF_INET:
                ip4.append({'ip': address.address, 'mask': address.netmask,
                            'kind': _ip_type(address.address)})
            elif address.family == socket.AF_INET6:
                ip6.append(address.address)
            elif address.family == getattr(psutil, 'AF_LINK', -1):
                mac = address.address
        rows.append({'name': alias, 'up': bool(stat.isup) if stat else None,
                     'speed_mbps': stat.speed if stat and stat.speed > 0 else None,
                     'mtu': stat.mtu if stat else None, 'mac': mac,
                     'ipv4': ip4, 'ipv6': ip6,
                     'received_mb': round(counter.bytes_recv / 1048576, 1) if counter else None,
                     'sent_mb': round(counter.bytes_sent / 1048576, 1) if counter else None,
                     'errors_in': counter.errin if counter else None,
                     'errors_out': counter.errout if counter else None,
                     'drops_in': counter.dropin if counter else None,
                     'drops_out': counter.dropout if counter else None})
    return rows


def collect_network() -> dict:
    interfaces = basic_interfaces()
    result = {'platform': platform.system(), 'interfaces': interfaces,
              'dns': {}, 'gateways': {}, 'adapter_details': [],
              'overview': analyze_network(interfaces, {}, {}),
              'note': 'Velocidade da interface ≠ velocidade contratada da Internet. Download/upload no card = tráfego instantâneo do PC.'}
    if platform.system() == 'Windows':
        ps = native_windows_query("Get-NetIPConfiguration -All -ErrorAction SilentlyContinue | ForEach-Object { "
            "[PSCustomObject]@{ InterfaceAlias=$_.InterfaceAlias; InterfaceIndex=$_.InterfaceIndex; "
            "IPv4DefaultGateway=@($_.IPv4DefaultGateway | ForEach-Object {$_.NextHop}); "
            "IPv6DefaultGateway=@($_.IPv6DefaultGateway | ForEach-Object {$_.NextHop}); "
            "DNSServers=@($_.DNSServer.ServerAddresses); "
            "NetProfile=$_.NetProfile.Name } } | ConvertTo-Json -Compress -Depth 5", 20)
        adapters = native_windows_query("Get-NetAdapter -ErrorAction SilentlyContinue | Select-Object Name,InterfaceDescription,LinkSpeed,Status,MacAddress,InterfaceIndex | ConvertTo-Json -Compress -Depth 3", 18)
        for p in _list(ps):
            if not isinstance(p, dict):
                continue
            name = str(p.get('InterfaceAlias') or '')
            result['dns'][name] = [str(x) for x in _list(p.get('DNSServers')) if x]
            gateways = [str(x) for x in _list(p.get('IPv4DefaultGateway')) if x]
            result['gateways'][name] = gateways
        result['adapter_details'] = [x for x in _list(adapters) if isinstance(x, dict)]
    elif platform.system() == 'Darwin':
        try:
            out = subprocess.run(['scutil', '--dns'], capture_output=True, text=True, timeout=8)
            result['dns']['macOS'] = list(dict.fromkeys(re.findall(r'nameserver\[\d+\]\s*:\s*(\S+)', out.stdout)))[:12]
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            from pathlib import Path
            text = Path('/etc/resolv.conf').read_text(errors='replace')
            result['dns']['system'] = re.findall(r'^nameserver\s+(\S+)', text, flags=re.MULTILINE)
        except OSError:
            pass
    result['overview'] = analyze_network(interfaces, result['dns'], result['gateways'])
    result['adapter_health'] = {n['name']: adapter_findings(n, result['dns'], result['gateways']) for n in interfaces}
    return result


def adapter_findings(nic: dict, dns: dict | None = None,
                     gateways: dict | None = None) -> dict:
    """Single-NIC diagnosis, including down/APIPA interfaces. No Internet claim."""
    name = str(nic.get('name') or 'Adaptador')
    findings = []
    if (name.lower() in ('lo','loopback','loopback pseudo-interface 1') or
        (nic.get('ipv4') and all(x.get('kind') == 'loopback' for x in nic.get('ipv4',[])))):
        return {'level':'loopback','issues':[], 'description':'Interface interna do sistema; não é conexão externa.'}
    if not nic.get('up'):
        findings.append('Interface desconectada ou desativada; não há link utilizável neste adaptador.')
    addr4 = nic.get('ipv4') or []
    if any(x.get('kind') == 'link-local (APIPA)' for x in addr4):
        findings.append('IPv4 169.254.x.x (APIPA): endereço automático; DHCP não forneceu IPv4 normal nesta interface.')
    if nic.get('up') and not [x for x in addr4 if x.get('kind') not in ('loopback', 'link-local (APIPA)')]:
        findings.append('Interface ligada, mas sem IPv4 utilizável; pode usar somente IPv6 ou estar sem configuração DHCP.')
    errors = (nic.get('errors_in') or 0) + (nic.get('errors_out') or 0)
    if errors:
        findings.append('Contadores acumulados de erros de rede não zerados; observe se aumentam ao longo do tempo.')
    if nic.get('up') and addr4 and gateways is not None and name in gateways and not gateways.get(name):
        findings.append('Gateway IPv4 não informado para este adaptador; pode ser normal em rede isolada.')
    level = 'attention' if findings else ('ok' if nic.get('up') else 'inactive')
    return {'level': level, 'issues': findings, 'description': '; '.join(findings) if findings
            else 'Nenhum alerta de configuração local identificado; conectividade externa requer teste.'}


def analyze_network(interfaces: list[dict], dns: dict, gateways: dict,
                    connectivity: dict | None = None) -> dict:
    """Separate whole-device path health from disconnected secondary adapters."""
    up = [n for n in interfaces if n.get('up') and adapter_findings(n, dns, gateways)['level'] != 'loopback']
    valid_ipv4 = [n for n in up if any(ip.get('kind') not in ('loopback', 'link-local (APIPA)')
                     for ip in n.get('ipv4', []))]
    device_issues = []
    local_alerts = []
    for nic in interfaces:
        name = str(nic.get('name') or '')
        report = adapter_findings(nic, dns, gateways)
        if report['issues'] and not (name.lower().startswith('loopback')):
            for warning in report['issues']:
                local_alerts.append(f'{name}: {warning}')
    if not up:
        device_issues.append('Nenhuma interface ativa; verifique Wi-Fi, cabo Ethernet e adaptadores desativados.')
    elif not valid_ipv4:
        # IPv6-only networks are valid; do not claim Internet is impossible.
        if not any(n.get('ipv6') for n in up):
            device_issues.append('Não foi identificado IPv4 utilizável nem IPv6 nas interfaces ativas.')
        else:
            device_issues.append('Sem IPv4 utilizável detectado; acesso pode depender de IPv6.')
    if valid_ipv4 and platform.system() == 'Windows' and not any(gateways.get(n['name']) for n in valid_ipv4):
        device_issues.append('Nenhuma rota IPv4 padrão identificada nas interfaces com IPv4 válido.')
    if connectivity is not None:
        if connectivity.get('dns') is False:
            device_issues.append('Falha na resolução de DNS durante teste solicitado.')
        if connectivity.get('internet') is False:
            device_issues.append('Não foi estabelecida conexão externa TCP 443 no teste solicitado.')
        if connectivity.get('gateway') is False and connectivity.get('internet') is not True:
            local_alerts.append('Gateway sem resposta a ICMP; roteador pode bloquear ping.')
    if device_issues:
        status = 'Atenção: conexão ou configuração requer investigação'
        level = 'attention'
    elif connectivity is not None and connectivity.get('dns') is True and connectivity.get('internet') is True:
        status = ('Internet acessível no teste pontual; outros adaptadores merecem atenção' if local_alerts
                  else 'Conectividade externa confirmada no teste pontual')
        level = 'warning' if local_alerts else 'ok'
    elif local_alerts:
        status = 'Conexão principal não comprovada; há alertas em adaptadores'
        level = 'warning'
    else:
        status = 'Configuração local sem alertas; Internet ainda precisa ser testada'
        level = 'unverified'
    return {'status':status,'level':level,'issues':device_issues,
            'adapter_warnings':local_alerts,
            'caveat':'Triagem local: estado da interface não comprova acesso à Internet. Adaptadores desconectados podem coexistir com outro acesso funcional.'}


def _ping(host: str, timeout_s: float = 1.8) -> tuple[bool, float | None]:
    args = ['ping', '-n', '1', '-w', str(max(200, int(timeout_s * 1000))), host] if platform.system() == 'Windows' \
        else ['ping', '-c', '1', '-W', str(max(1, int(timeout_s))), host]
    try:
        begin = time.monotonic()
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s + 1.5,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        elapsed = round((time.monotonic() - begin) * 1000, 1)
        return p.returncode == 0, elapsed if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return False, None


def test_connectivity(network_data: dict, test_host: str = 'www.microsoft.com') -> dict:
    gateways = [g for values in network_data.get('gateways', {}).values() for g in values if g]
    gateway = gateways[0] if gateways else None
    gw_ping, gw_time = _ping(gateway) if gateway else (None, None)
    dns_success = False
    dns_time = None
    resolved_ip = None
    t = time.monotonic()
    try:
        rows = socket.getaddrinfo(test_host, 443, type=socket.SOCK_STREAM)
        dns_success = bool(rows)
        if rows:
            resolved_ip = rows[0][4][0]
    except (OSError, socket.gaierror):
        pass
    dns_time = round((time.monotonic() - t) * 1000, 1)
    internet = False
    tcp_ms = None
    if dns_success:
        t = time.monotonic()
        try:
            with socket.create_connection((test_host, 443), timeout=3):
                internet = True
                tcp_ms = round((time.monotonic() - t) * 1000, 1)
        except OSError:
            pass
    return {'gateway_ip':gateway, 'gateway':gw_ping, 'gateway_rtt_ms':gw_time,
            'dns':dns_success, 'dns_resolution_ms':dns_time, 'resolved_ip':resolved_ip,
            'internet':internet, 'tcp_443_ms':tcp_ms, 'test_host':test_host,
            'note':'Ping pode ser bloqueado. TCP 443 conectado não equivale a teste completo da Internet.'}


def local_scan_targets(interfaces: list[dict], interface_name: str, limit: int = 64) -> tuple[list[str], str]:
    """Only directly attached RFC1918 IPv4 subnet; do not accept arbitrary CIDRs/user targets."""
    if not 1 <= limit <= 254:
        raise ValueError('Limite inválido para descoberta local.')
    chosen = next((x for x in interfaces if x.get('name') == interface_name and x.get('up')), None)
    if not chosen:
        raise ValueError('Escolha uma interface local ativa.')
    for ip in chosen.get('ipv4', []):
        try:
            addr = ipaddress.IPv4Address(ip['ip'])
            permitted = any(addr in block for block in (
                ipaddress.IPv4Network('10.0.0.0/8'),
                ipaddress.IPv4Network('172.16.0.0/12'),
                ipaddress.IPv4Network('192.168.0.0/16')))
            if not permitted or addr.is_loopback or addr.is_link_local or addr.is_multicast:
                continue
            mask = ip.get('mask')
            if not mask:
                continue
            net = ipaddress.IPv4Network(f'{addr}/{mask}', strict=False)
            # Too-wide networks are sampled from a local /24 only.
            if net.prefixlen < 24:
                net = ipaddress.IPv4Network(f'{addr}/24', strict=False)
            # Cap to 254 and small default; selection deterministic for user awareness.
            hosts = [str(x) for x in net.hosts()][:limit]
            return hosts, str(net)
        except (ValueError, KeyError):
            continue
    raise ValueError('Sem sub-rede IPv4 privada válida nesta interface.')


def read_neighbor_cache() -> dict[str, dict]:
    """ARP/neighbor records; stale entries are marked as unconfirmed."""
    found: dict[str,dict] = {}
    if platform.system() == 'Windows':
        items = native_windows_query("Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object IPAddress,LinkLayerAddress,State,InterfaceAlias | ConvertTo-Json -Compress -Depth 3", 16)
        for entry in _list(items):
            if not isinstance(entry, dict):
                continue
            ip = str(entry.get('IPAddress') or '')
            if ip:
                found[ip] = {'mac':entry.get('LinkLayerAddress') or None,
                             'neighbor_state':str(entry.get('State') or 'Desconhecido')}
    else:
        exe = shutil.which('arp')
        if exe:
            try:
                result = subprocess.run([exe, '-an'], capture_output=True, text=True, timeout=6)
                for line in result.stdout.splitlines():
                    addr = re.search(r'(?:\(|\b)(\d{1,3}(?:\.\d{1,3}){3})(?:\)|\b)', line)
                    mac = re.search(r'([0-9a-f]{2}(?:[:-][0-9a-f]{2}){5})', line, flags=re.I)
                    if addr:
                        found[addr.group(1)] = {'mac':mac.group(1) if mac else None,'neighbor_state':'cache ARP'}
            except (OSError, subprocess.TimeoutExpired):
                pass
    return found


def _netbios_name(ip: str) -> str | None:
    """Windows NetBIOS workstation name lookup; only for local discovered hosts.

    Does not use PowerShell, remote commands, WMI sessions or port scanning.
    A host may disable NetBIOS, so missing names are expected.
    """
    if platform.system() != 'Windows' or not shutil.which('nbtstat'):
        return None
    try:
        proc = subprocess.run(['nbtstat', '-A', ip], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=2.5,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if proc.returncode != 0:
            return None
        # nbtstat output follows the active Windows code page, not always UTF-8.
        output = proc.stdout.decode('cp1252', errors='replace')
        for line in output.splitlines():
            match = re.search(r'^\s*([^\s<>]{1,48})\s+<00>\s+', line)
            if match and not re.search(r'\b(GROUP|GRUPO)\b', line, re.I):
                name = match.group(1).strip()
                if name != ip and not name.startswith('__'):
                    return name
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def resolve_local_hostname(ip: str, is_local: bool = False) -> tuple[str | None, str]:
    """Resolve by host identity or reverse DNS; fall back to local Windows NetBIOS.

    Hostnames are hints from local name services, not proof of ownership.
    """
    if is_local:
        return socket.gethostname(), 'Este computador'
    try:
        hostname = socket.gethostbyaddr(ip)[0].rstrip('.')
        if hostname and hostname != ip:
            return hostname, 'DNS reverso / resolvedor local'
    except (OSError, UnicodeError):
        pass
    name = _netbios_name(ip)
    if name:
        return name, 'NetBIOS local'
    return None, 'Não resolvido'


def discover_local_hosts(network_data: dict, interface_name: str, limit: int = 64,
                         cancel_event=None) -> dict:
    """Explicit, bounded discovery of one attached IPv4 LAN, at most 254 hosts.

    This only probes IPv4 interfaces directly attached to a private subnet.
    ICMP + local ARP + local hostname lookups. No port sweeps or escalation.
    """
    targets, subnet = local_scan_targets(network_data['interfaces'], interface_name, limit)
    nic = next((n for n in network_data['interfaces'] if n['name']==interface_name), {})
    own_addrs = {str(row.get('ip')) for row in nic.get('ipv4', [])}
    rows: list[dict] = []
    def worker(ip):
        if cancel_event and cancel_event.is_set():
            return None
        is_local = ip in own_addrs
        if is_local:
            reached, delay = True, 0.0
        else:
            reached, delay = _ping(ip, timeout_s=0.75)
        if not reached:
            return None
        hostname, hostname_source = resolve_local_hostname(ip, is_local)
        return {'ip':ip,'responds':reached,'rtt_ms':delay,
                'hostname':hostname,'hostname_source':hostname_source,
                'is_local':is_local}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(worker, ip) for ip in targets]
        for f in as_completed(futures):
            try:
                row = f.result()
            except (OSError, ValueError):
                row = None
            if row:
                rows.append(row)
    neighbors = read_neighbor_cache()
    scope = set(targets)
    result_by_ip = {x['ip']:x for x in rows}
    for ip, info in neighbors.items():
        if ip in scope and ip not in result_by_ip and info.get('mac') and info['mac'] != '00-00-00-00-00-00':
            result_by_ip[ip] = {'ip':ip, 'responds':False, 'rtt_ms':None,
                                'hostname':None,'hostname_source':'Não verificado',
                                'is_local':False}
    for ip, row in result_by_ip.items():
        row.update(neighbors.get(ip, {'mac':None, 'neighbor_state':'Não listado no ARP'}))
        # A stale ARP entry is only evidence of previous presence.
    rows = sorted(result_by_ip.values(), key=lambda r: ipaddress.IPv4Address(r['ip']))
    return {'interface':interface_name, 'subnet':subnet, 'tested':len(targets),
            'devices':rows, 'note':('Até 254 endereços utilizáveis em uma rede /24 (rede e broadcast não são dispositivos). '
                                 'Nomes obtidos por DNS reverso / NetBIOS podem estar ausentes ou desatualizados. '
                                 'Respostas ICMP e ARP não identificam todos os dispositivos ativos; '
                                 'entradas ARP antigas não confirmam presença atual.')}


DNS_PROVIDERS = (
    {'name': 'Cloudflare', 'primary': '1.1.1.1', 'secondary': '1.0.0.1',
     'feature': 'Privacidade e desempenho', 'official_url': 'https://developers.cloudflare.com/1.1.1.1/setup/'},
    {'name': 'Google Public DNS', 'primary': '8.8.8.8', 'secondary': '8.8.4.4',
     'feature': 'Alternativa de uso geral', 'official_url': 'https://developers.google.com/speed/public-dns/docs/using?hl=pt-BR'},
    {'name': 'Quad9 (protegido)', 'primary': '9.9.9.9', 'secondary': '149.112.112.112',
     'feature': 'Bloqueio de domínios maliciosos', 'official_url': 'https://quad9.net/service/service-addresses-and-features/'},
)


def _dns_query_packet(host: str, ident: int) -> bytes:
    import struct
    question = b''.join(bytes([len(label)])+label.encode('ascii')
                        for label in host.split('.'))+b'\x00'
    return struct.pack('!HHHHHH', ident, 0x0100, 1, 0, 0, 0) + question + struct.pack('!HH',1,1)


def probe_dns_server(ip: str, attempts: int = 2, timeout: float = 1.2) -> dict:
    """Bounded UDP DNS A query; actual round trip, not an HTTPS proxy latency."""
    import secrets
    import statistics
    import struct
    samples = []
    errors = []
    for _ in range(max(1, min(attempts, 3))):
        ident = secrets.randbelow(65536)
        packet = _dns_query_packet('example.com', ident)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            start = time.perf_counter()
            sock.sendto(packet, (ip, 53))
            data, _ = sock.recvfrom(4096)
            if len(data) < 12:
                raise OSError('Resposta DNS incompleta')
            rxid, flags, qdcount, ancount, _, _ = struct.unpack('!HHHHHH', data[:12])
            if rxid != ident or not flags & 0x8000:
                raise OSError('Resposta DNS inválida')
            if flags & 0x000F:
                raise OSError(f'Resposta DNS com código {flags & 0x000F}')
            if not ancount:
                raise OSError('Resposta DNS sem registros')
            samples.append(round((time.perf_counter()-start)*1000, 1))
        except (OSError, TimeoutError) as exc:
            errors.append(str(exc)[:80])
        finally:
            sock.close()
    return {'ip':ip,'ok':bool(samples), 'median_ms':round(statistics.median(samples),1) if samples else None,
            'samples_ms':samples,'errors':errors,
            'note':'UDP porta 53: redes empresariais, provedores e firewalls podem bloquear consultas externas.'}


def compare_public_dns() -> dict:
    """Opt-in public DNS benchmark; no system changes, no privileged operations."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        measured = list(pool.map(lambda provider: probe_dns_server(provider['primary']), DNS_PROVIDERS))
    rows = [{**provider, **test} for provider, test in zip(DNS_PROVIDERS, measured)]
    winners = sorted([r for r in rows if r['ok']], key=lambda x: x['median_ms'])
    return {'providers': rows, 'fastest': winners[0]['name'] if winners else None,
            'note':'Latência pontual de DNS, não velocidade de download. Não altera o DNS; em redes com AD, VPN ou DNS corporativo, consulte o administrador antes de modificar a configuração.'}


def _speedtest_ookla(progress=None) -> dict:
    """Speedtest.net via speedtest-cli Python library, bundled in the compiled app."""
    import speedtest  # optional library installed through requirements.txt
    if progress: progress('preparing', 0., 0.)
    test = speedtest.Speedtest(secure=True, timeout=8)
    test.get_best_server()
    if progress: progress('download', 0., 0.)
    download_mbps = test.download(threads=4) / 1e6
    if progress: progress('download', download_mbps, 1.)
    if progress: progress('upload', 0., 0.)
    upload_mbps = test.upload(pre_allocate=False, threads=4) / 1e6
    if progress: progress('upload', upload_mbps, 1.)
    ping_ms = (test.results.ping if getattr(test, 'results', None) else None)
    if progress: progress('complete', 0., 1.)
    return {'ok':True, 'download_mbps':round(download_mbps,2),
            'upload_mbps':round(upload_mbps,2), 'ping_ms': ping_ms,
            'server':'Speedtest.net (cliente integrado)',
            'note':'Teste com servidor público. O download/upload consome dados e pode utilizar dezenas ou centenas de MB. Não é certificação da banda contratada.'}


def _speedtest_cloudflare(progress=None) -> dict:
    """Fallback bounded HTTPS speed sample; preserve partial download on failures."""
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode
    from urllib.error import HTTPError, URLError
    base = 'https://speed.cloudflare.com'
    downloaded = down_seconds = uploaded = up_seconds = 0.0
    sizes = (2_000_000, 8_000_000)
    upload_sizes = (1_000_000, 3_000_000)
    stage = 'download'
    try:
        if progress:progress('download',0.,0.)
        for size in sizes:
            url = base + '/__down?' + urlencode({'bytes':size})
            req = Request(url,headers={'Cache-Control':'no-store','User-Agent':'Mozilla/5.0 OSReview/0.6.1'})
            t = time.perf_counter()
            with urlopen(req,timeout=20) as response:
                if response.status != 200: raise OSError(f'HTTP {response.status} no download')
                got=0
                while got<size:
                    part=response.read(min(128*1024,size-got))
                    if not part: break
                    got +=len(part)
                    if progress and got % (1024*1024) < 128*1024:
                        progress('download',got*8/max(time.perf_counter()-t,.001)/1e6,
                                 min(1.,(downloaded+got)/sum(sizes)))
            if got < size*.9:raise OSError(f'Download incompleto: {got}/{size}')
            down_seconds += max(.001,time.perf_counter()-t)
            downloaded += got
        download = round(downloaded*8/max(down_seconds,.001)/1e6,2)
        if progress:progress('download',download,1.)
        stage='upload'
        if progress:progress('upload',0.,0.)
        for size in upload_sizes:
            req=Request(base+'/__up',method='POST',data=bytes(size),headers={
                'Content-Type':'application/octet-stream','User-Agent':'Mozilla/5.0 OSReview/0.6.1'})
            t=time.perf_counter()
            with urlopen(req,timeout=23) as response:
                response.read(256)
                if not 200<=response.status<300:raise OSError(f'HTTP {response.status} no upload')
            up_seconds += max(.001,time.perf_counter()-t)
            uploaded+=size
            if progress:progress('upload',size*8/max(time.perf_counter()-t,.001)/1e6,uploaded/sum(upload_sizes))
        upload=round(uploaded*8/max(up_seconds,.001)/1e6,2)
        if progress: progress('complete',0.,1.)
        return {'ok':True,'download_mbps':download,'upload_mbps':upload,
                'server':'Cloudflare Speed Test (amostra HTTP)',
                'download_mb':round(downloaded/1e6,1),'upload_mb':round(uploaded/1e6,1),
                'note':'Amostra HTTP pequena, não equivalente a um benchmark multiconexão. IP do dispositivo enviado ao servidor.'}
    except (OSError,TimeoutError,HTTPError,URLError) as exc:
        return {'ok':False,'error':f'{type(exc).__name__}: {str(exc)[:160]}',
                'failed_stage':stage,'download_mbps':round(downloaded*8/max(down_seconds,.001)/1e6,2) if downloaded else None,
                'upload_mbps':round(uploaded*8/max(up_seconds,.001)/1e6,2) if uploaded else None,
                'server':'Cloudflare Speed Test',
                'note':'403 significa que o servidor recusou a transferência; não prova falha na conexão local.'}


def run_speedtest(progress=None, provider: str='auto') -> dict:
    """Speedtest.net primary, Cloudflare fallback. Never show made-up results.

    One click, external traffic, run in background thread. Failure is explicit.
    """
    if provider not in ('auto','ookla','cloudflare'):
        return {'ok':False,'error':'Serviço desconhecido','server':'Não iniciado'}
    errors=[]
    if provider in ('auto','ookla'):
        try:
            result=_speedtest_ookla(progress)
            return {**result,'attempts':['Speedtest.net']}
        except Exception as exc:
            errors.append('Speedtest.net: '+type(exc).__name__+': '+str(exc)[:135])
            if progress:progress('fallback',0.,0.)
    if provider in ('auto','cloudflare'):
        result=_speedtest_cloudflare(progress)
        if result['ok']:
            result['attempts'] = errors + ['Cloudflare: concluído']
            return result
        errors.append('Cloudflare: '+result.get('error','Falhou'))
        result['attempts']=errors
        result['error']=' | '.join(errors)
        if progress:progress('failed',0.,0.)
        return result
    if progress:progress('failed',0.,0.)
    return {'ok':False,'error':' | '.join(errors),'server':'Speedtest.net','attempts':errors,
            'note':'Mecanismo escolhido indisponível; o erro do servidor não prova falha do adaptador.'}
