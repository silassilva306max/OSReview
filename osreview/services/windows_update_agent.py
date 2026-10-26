"""Read-only native Windows Update COM catalog search; user opt-in only."""
from __future__ import annotations
from .windows_native import collect_updates

def scan_pending_windows_updates():
    return collect_updates()
