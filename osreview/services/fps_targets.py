"""Visible graphical processes and display refresh (not synthetic FPS)."""
from __future__ import annotations
import platform
import psutil


def graphical_processes() -> list[str]:
    if platform.system() != 'Windows': return []
    names=set()
    try:
        import win32gui, win32process
        def each(hwnd, ignored):
            try:
                if not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd).strip(): return True
                _tid,pid=win32process.GetWindowThreadProcessId(hwnd)
                name=psutil.Process(pid).name()
                if name.lower().endswith('.exe') and name.lower() not in ('explorer.exe','applicationframehost.exe'):
                    names.add(name)
            except (psutil.Error, OSError): pass
            return True
        win32gui.EnumWindows(each,None)
    except ImportError:
        pass
    except Exception:
        pass
    return sorted(names, key=str.casefold)


def desktop_refresh_hz() -> int | None:
    if platform.system() != 'Windows':return None
    try:
        import win32api, win32con
        mode=win32api.EnumDisplaySettings(None,win32con.ENUM_CURRENT_SETTINGS)
        hz=int(mode.DisplayFrequency)
        return hz if 20 <= hz <= 1000 else None
    except (ImportError, OSError, AttributeError):
        return None
