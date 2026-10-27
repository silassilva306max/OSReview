"""Explicit, local process and third-party service controls for Windows."""
from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess

import psutil

PROTECTED_PROCESSES = {
    'system', 'registry', 'idle', 'csrss.exe', 'wininit.exe', 'winlogon.exe',
    'lsass.exe', 'services.exe', 'svchost.exe', 'smss.exe', 'dwm.exe',
    'explorer.exe', 'taskhostw.exe', 'sihost.exe', 'fontdrvhost.exe',
    'securityhealthservice.exe', 'msmpeng.exe', 'osreview.exe',
}
PROTECTED_SERVICES = {
    'rpcss', 'dcomlaunch', 'eventlog', 'plugplay', 'winmgmt', 'schedule',
    'windefend', 'mpssvc', 'wuauserv', 'trustedinstaller', 'cryptsvc',
    'lanmanworkstation', 'bfe', 'securityhealthservice',
}
SECURITY_TERMS = ('antivirus', 'defender', 'avast', 'firewall', 'security', 'endpoint')
SYSTEM_BINARIES = ('svchost.exe', '\\system32\\', '\\syswow64\\', '\\drivers\\')


def _is_windows_path(path: str) -> bool:
    raw=os.path.expandvars(path).strip().lstrip('"').casefold().replace('/', '\\')
    windir=os.environ.get('WINDIR',r'C:\Windows').casefold().rstrip('\\')
    return raw.startswith(windir + '\\') or raw.startswith('\\systemroot\\') or raw.startswith('\\??\\c:\\windows\\')


def service_manageable(name: str, binpath: str) -> bool:
    label=(name+' '+binpath).casefold()
    return (bool(name and binpath) and name.casefold() not in PROTECTED_SERVICES and
            not any(term in label for term in SECURITY_TERMS) and
            not any(term in binpath.casefold() for term in SYSTEM_BINARIES) and
            not binpath.casefold().strip().endswith('.sys') and
            not _is_windows_path(binpath) and
            not binpath.casefold().startswith(('%systemroot%',r'\systemroot')))


def list_services() -> list[dict]:
    if platform.system()!='Windows':return []
    rows=[]
    for item in psutil.win_service_iter():
        try:
            data=item.as_dict()
            rows.append({'name':data['name'],'display':data.get('display_name') or data['name'],
                         'status':data.get('status','?'),'start_type':data.get('start_type','?'),
                         'binpath':data.get('binpath',''),
                         'manageable':service_manageable(data['name'],data.get('binpath',''))})
        except (psutil.Error,OSError):
            continue
    return sorted(rows,key=lambda row:row['display'].casefold())


def change_service(name: str, action: str) -> str:
    if platform.system()!='Windows' or action not in ('start','stop'):
        raise ValueError('Operação de serviço indisponível.')
    service=psutil.win_service_get(name)
    data=service.as_dict()
    if not service_manageable(data['name'],data.get('binpath','')):
        raise PermissionError('Serviço do sistema ou de segurança protegido pelo OSReview.')
    if action=='start' and data.get('start_type')=='disabled':
        raise PermissionError('Serviço desativado; altere sua configuração no Gerenciador de Serviços.')
    if data.get('status')==('running' if action=='start' else 'stopped'):
        return 'O serviço já está no estado solicitado.'
    import win32service
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    try:
        rights=(win32service.SERVICE_START if action=='start' else win32service.SERVICE_STOP)
        handle=win32service.OpenService(manager,name,rights|win32service.SERVICE_QUERY_STATUS)
        try:
            if action=='start':win32service.StartService(handle,None)
            else:win32service.ControlService(handle,win32service.SERVICE_CONTROL_STOP)
        finally:win32service.CloseServiceHandle(handle)
    finally:win32service.CloseServiceHandle(manager)
    return 'Comando de início enviado.' if action=='start' else 'Comando de parada enviado.'


def process_details(pid: int) -> dict:
    proc=psutil.Process(pid)
    with proc.oneshot():
        name=proc.name()
        exe=proc.exe()
        username=proc.username()
        created=proc.create_time()
    current=psutil.Process(os.getpid()).username()
    manageable=(pid>100 and pid!=os.getpid() and name.casefold() not in PROTECTED_PROCESSES
                and username.casefold()==current.casefold() and exe.lower().endswith('.exe')
                and not _is_windows_path(exe))
    return {'pid':pid,'name':name,'exe':exe,'username':username,'created':created,
            'manageable':manageable}


def close_process_window(pid: int) -> dict:
    info=process_details(pid)
    if not info['manageable']:
        raise PermissionError('Processo protegido, de outro usuário ou sem caminho confiável.')
    import win32con
    import win32gui
    import win32process
    windows=[]
    def collect(hwnd,_):
        if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1]==pid:
            windows.append(hwnd)
    win32gui.EnumWindows(collect,None)
    if not windows:
        raise ValueError('Este processo não possui janela para fechar. Use Encerrar processo se necessário.')
    for hwnd in windows:win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
    return info


def terminate_process(pid: int) -> dict:
    info=process_details(pid)
    if not info['manageable']:
        raise PermissionError('Processo protegido, de outro usuário ou sem caminho confiável.')
    proc=psutil.Process(pid)
    if abs(proc.create_time()-info['created'])>0.01:
        raise ValueError('O PID foi reutilizado; atualize a lista e selecione novamente.')
    proc.terminate()  # On Windows this is forceful; the UI labels it explicitly.
    return info


def reopen_executable(path: str) -> int:
    exe=Path(path).resolve(strict=True)
    if exe.suffix.casefold()!='.exe' or _is_windows_path(str(exe)):
        raise PermissionError('Executável do sistema ou caminho inválido.')
    process=subprocess.Popen([str(exe)],cwd=str(exe.parent),stdin=subprocess.DEVNULL,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return process.pid
