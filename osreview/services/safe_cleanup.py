"""Explicit-only, allowlisted cache cleaning. Never touches profiles, passwords or cookies."""
from __future__ import annotations
import os
import platform
import time
from pathlib import Path
from typing import Any
import psutil


BROWSER_PROCESSES = {'Edge': {'msedge.exe'}, 'Chrome': {'chrome.exe'}, 'Firefox': {'firefox.exe'}}
MAX_FILES = 18000


def get_safe_locations():
    if platform.system() != 'Windows':
        return {}
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local')))
    roaming = Path(os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming')))
    temp = Path(os.environ.get('TEMP', str(local / 'Temp')))
    # Never follow a reconfigured TEMP environment variable outside this user's AppData.
    try:
        if not temp.resolve().is_relative_to(local.resolve()):
            temp = local / 'Temp'
    except (OSError, RuntimeError):
        temp = local / 'Temp'
    paths = {
        'Temp (usuário)': [temp],
        'Chrome': [], 'Edge': [], 'Firefox': [],
    }
    for label, root in [('Chrome', local/'Google'/'Chrome'/'User Data'),
                        ('Edge', local/'Microsoft'/'Edge'/'User Data')]:
        if root.is_dir():
            # Profile folders: Default, Profile 1, Profile 2...; exclude passwords/cookies.
            for child in root.iterdir():
                if child.is_dir() and (child.name == 'Default' or child.name.startswith('Profile ')):
                    cache = child/'Cache'/'Cache_Data'
                    paths[label] += [cache if cache.is_dir() else child/'Cache',
                                     child/'Code Cache'/'js', child/'GPUCache']
    firefox = local / 'Mozilla' / 'Firefox' / 'Profiles'
    if firefox.is_dir():
        for profile in firefox.iterdir():
            if profile.is_dir():
                paths['Firefox'].append(profile / 'cache2' / 'entries')
    # Only built-in browser cache folders and current-user Temp are scanned.
    return {key: [p for p in entries if p.is_dir()] for key, entries in paths.items()}


def _running_browsers():
    names = set()
    for p in psutil.process_iter(['name']):
        try:
            names.add((p.info.get('name') or '').lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {label for label, procs in BROWSER_PROCESSES.items() if names.intersection(procs)}


def _safe_file(path: Path, root: Path) -> bool:
    try:
        if path.is_symlink() or root.is_symlink():
            return False
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False


def _file_candidates(kind: str, max_files: int = MAX_FILES):
    if kind not in ('Temp (usuário)', 'Chrome', 'Edge', 'Firefox'):
        raise ValueError('Categoria não permitida')
    roots = get_safe_locations().get(kind, [])
    running = _running_browsers()
    if kind in running:
        raise RuntimeError(f'Feche o {kind} antes da limpeza de cache; nenhuma alteração realizada.')
    age = time.time() - 48 * 3600
    count = 0
    for root in roots:
        for dirpath, folders, files in os.walk(root, followlinks=False):
            folders[:] = [n for n in folders if not (Path(dirpath)/n).is_symlink()]
            for filename in files:
                if count >= max_files:
                    return
                p = Path(dirpath) / filename
                if not _safe_file(p, root):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if kind == 'Temp (usuário)' and st.st_mtime > age:
                    continue
                count += 1
                yield p, st.st_size


def preview_cleanup(kind: str) -> dict[str, Any]:
    count = 0
    size = 0
    for _, bytes_size in _file_candidates(kind):
        count += 1
        size += bytes_size
    return {'kind': kind, 'count': count, 'bytes': size, 'mb': round(size / (1024**2), 2),
            'limited': count >= MAX_FILES}


def clean_category(kind: str) -> dict[str, Any]:
    # Must only be called following a separate explicit confirmation in UI.
    deleted = errors = freed = 0
    for p, size in _file_candidates(kind):
        try:
            p.unlink()
            deleted += 1
            freed += size
        except (OSError, PermissionError):
            errors += 1
    return {'deleted': deleted, 'errors': errors, 'freed_mb': round(freed/(1024**2), 2)}
