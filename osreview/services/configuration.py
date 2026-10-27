"""Local privacy-first configuration and opt-in startup settings."""
from __future__ import annotations

import json
import plistlib
import os
from pathlib import Path
import platform
import sys
from typing import Any

from platformdirs import user_config_dir

DEFAULTS = {"notifications": True, "close_to_tray": True, "start_with_system": False,
            "sample_seconds": 3, "mode": "simples",
            "theme": "dark", "accent_theme": "graphite", "compact_mode": False, "tray_hover_popup": True,
            "check_app_updates": True, "update_prereleases": True}


class ConfigStore:
    def __init__(self, base: Path | None = None):
        self.base = base or Path(user_config_dir("OSReview", "OSReview"))
        self.base.mkdir(parents=True, exist_ok=True)
        self.path = self.base / "settings.json"
        self.data = DEFAULTS.copy()
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
            except (OSError, ValueError, TypeError):
                pass

    def set(self, key: str, value: Any):
        if key not in DEFAULTS:
            raise KeyError(key)
        self.data[key] = value
        self.save()

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    python = Path(sys.executable)
    if platform.system() == "Windows":
        alternate = python.with_name("pythonw.exe")
        if alternate.is_file():
            python = alternate
    root = Path(__file__).resolve().parents[2]
    return f'"{python}" "{root / "run.py"}"'


def configure_windows_startup(enabled: bool) -> tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "Inicialização automática nesta versão está disponível somente para Windows."
    try:
        import winreg
        keypath = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, keypath, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, "OSReview", 0, winreg.REG_SZ, _startup_command())
            else:
                try:
                    winreg.DeleteValue(key, "OSReview")
                except FileNotFoundError:
                    pass
        return True, "Inicialização automática ativada." if enabled else "Inicialização automática desativada."
    except OSError as exc:
        return False, f"Não foi possível alterar a inicialização automática: {exc}"


def get_windows_startup_status() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            value, _ = winreg.QueryValueEx(key, "OSReview")
            return bool(value)
    except (OSError, FileNotFoundError):
        return False


# macOS per-user login agent. Installation is always opt-in; no root rights.
_MAC_LABEL = "com.osreview.diagnostics.login"

def _mac_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / (_MAC_LABEL + ".plist")

def configure_macos_startup(enabled: bool) -> tuple[bool, str]:
    if platform.system() != "Darwin":
        return False, "Este comando e exclusivo do macOS."
    agent = _mac_agent_path()
    try:
        if enabled:
            if not getattr(sys, "frozen", False):
                return False, "Instale OSReview.app antes de habilitar o inicio automatico."
            exe = Path(sys.executable).resolve()
            # A PyInstaller .app is OSReview.app/Contents/MacOS/OSReview.
            if not any(x.suffix == '.app' for x in exe.parents):
                return False, "O OSReview deve ser executado de dentro do aplicativo .app."
            agent.parent.mkdir(parents=True, exist_ok=True)
            payload = {"Label": _MAC_LABEL, "ProgramArguments": [str(exe)],
                       "RunAtLoad": True, "KeepAlive": False}
            temp = agent.with_suffix('.tmp')
            temp.write_bytes(plistlib.dumps(payload))
            temp.replace(agent)
            return True, "Inicio no login configurado. Revise em Ajustes do Sistema > Itens de Inicio."
        if agent.is_file():
            agent.unlink()
        return True, "Inicio automatico desativado (efetivo no proximo login)."
    except OSError as exc:
        return False, f"Nao foi possivel atualizar o Login Agent: {exc}"

def get_macos_startup_status() -> bool:
    return platform.system() == 'Darwin' and _mac_agent_path().is_file()

def configure_system_startup(enabled: bool) -> tuple[bool, str]:
    if platform.system() == 'Windows':
        return configure_windows_startup(enabled)
    if platform.system() == 'Darwin':
        return configure_macos_startup(enabled)
    return False, 'Inicializacao automatica indisponivel neste sistema.'

def get_system_startup_status() -> bool:
    if platform.system() == 'Windows':
        return get_windows_startup_status()
    if platform.system() == 'Darwin':
        return get_macos_startup_status()
    return False
