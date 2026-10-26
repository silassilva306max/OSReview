"""Read-only diagnostics for Windows updates, service states and event logs.
No driver, service, update or registry system setting is modified here.
"""
from __future__ import annotations

from datetime import datetime
import json
import platform
import subprocess
from typing import Any

import psutil

SERVICE_NAMES = {
    "wuauserv": "Windows Update",
    "BITS": "Transferência inteligente (BITS)",
    "UsoSvc": "Orquestrador de atualizações",
    "DoSvc": "Otimização de entrega",
    "TrustedInstaller": "Instalador de módulos",
    "WSearch": "Pesquisa do Windows",
    "SysMain": "SysMain (pré-carregamento)",
    "WinDefend": "Microsoft Defender",
    "Spooler": "Fila de impressão",
}
UPDATE_NAMES = {"tiworker.exe", "trustedinstaller.exe", "mousocoreworker.exe", "usoclient.exe", "wuauclt.exe", "msiexec.exe"}


def _pending_reboot() -> bool | None:
    try:
        import winreg
        paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        ]
        for path in paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path):
                    return True
            except FileNotFoundError:
                pass
        return False
    except Exception:
        return None


def collect_windows_health() -> dict[str, Any]:
    if platform.system() != "Windows":
        return {"supported": False, "message": "Análise detalhada de serviços/Windows Update disponível somente no Windows.",
                "services": [], "update_processes": [], "recent_hotfixes": [], "errors": [], "pending_reboot": None}

    results: dict[str, Any] = {
        "supported": True, "collected_at": datetime.now().isoformat(timespec="seconds"),
        "services": [], "update_processes": [], "recent_hotfixes": [], "errors": [],
        "pending_reboot": _pending_reboot(), "message": "Verificação somente leitura."
    }
    for name, friendly in SERVICE_NAMES.items():
        try:
            srv = psutil.win_service_get(name).as_dict()
            state = srv.get("status", "desconhecido")
            results["services"].append({"name": name, "label": friendly, "state": state,
                                          "start_type": srv.get("start_type", "desconhecido")})
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, AttributeError):
            results["services"].append({"name": name, "label": friendly, "state": "não consultável", "start_type": "?"})

    for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name in UPDATE_NAMES:
                results["update_processes"].append({"name": p.info["name"], "pid": p.info["pid"]})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    from .windows_native import collect_events
    # Win32_QuickFixEngineering has crashed the Python 3.14/pywin32 collector
    # on Windows in the baseline regression run. Keep this optional field empty
    # until it has an isolated, verified implementation.
    results['message'] += ' Histórico de hotfixes: consulte Atualizações.'
    records = collect_events(max_events=7, logs=('System',), days=1)
    if records is not None:
        results['errors'] = [{**r, 'Message': (r.get('Message') or '')[:320]} for r in records]
    else:
        results['message'] += ' Logs de eventos indisponíveis sem API nativa.'
    return results
