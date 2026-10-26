"""Pre-execution integrity gate for the optional LibreHardwareMonitor sensor bridge.

The SHA-256 manifest detects accidental/unauthorized modifications against the
local release bundle. It is NOT an authenticated publisher signature. Trusted
release identity requires Authenticode on the bridge AND the containing release.
No antivirus bypass, automatic exclusions, privilege escalation, or PowerShell.
"""
from __future__ import annotations

import hashlib
import hmac
import platform
import sys
from pathlib import Path
from typing import Any


def bridge_candidates() -> list[Path]:
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    development = Path(__file__).resolve().parents[2]
    paths = [base / 'sensor_bridge' / 'SensorBridge.exe', development / 'sensor_bridge' / 'SensorBridge.exe']
    # Preserve order while avoiding duplicate execution candidates.
    return list(dict.fromkeys(paths))


def create_sha256_manifest(exe: Path) -> Path:
    """Build-time ONLY: call after compiling/signing the executable."""
    digester = hashlib.sha256()
    with exe.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digester.update(block)
    digest = digester.hexdigest()
    out = exe.with_suffix(exe.suffix + '.sha256')
    out.write_text(f'{digest}  {exe.name}\n', encoding='ascii')
    return out


def inspect_bridge(exe: Path, platform_name: str | None = None) -> dict[str, Any]:
    osname = platform_name or platform.system()
    info: dict[str, Any] = {'present': False, 'integrity': 'indisponível',
                            'allowed': False, 'path': str(exe), 'reason': '', 'sha256': None}
    if osname != 'Windows':
        info['reason'] = 'Ponte Windows não é executada neste sistema.'
        return info
    if not exe.is_file():
        info['reason'] = 'A ponte não foi compilada/incluída. Sensores WMI e nativos continuam disponíveis.'
        return info
    info['present'] = True
    manifest = exe.with_suffix(exe.suffix + '.sha256')
    if not manifest.is_file():
        info['integrity'] = 'não verificada'
        info['reason'] = 'Manifesto de hash ausente: a ponte NÃO será iniciada.'
        return info
    try:
        # Explicitly require a same-name manifest, not an arbitrary digest file.
        parts = manifest.read_text(encoding='ascii').strip().split()
        if len(parts) != 2 or parts[1] != exe.name or len(parts[0]) != 64:
            raise ValueError('manifesto malformado')
        expected = bytes.fromhex(parts[0])
        digester = hashlib.sha256()
        with exe.open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                digester.update(block)
        current = digester.digest()
        info['sha256'] = current.hex()
        if not hmac.compare_digest(expected, current):
            info['integrity'] = 'alterado'
            info['reason'] = 'SHA-256 não corresponde ao manifesto. Execução bloqueada.'
            return info
    except (ValueError, OSError, UnicodeError) as exc:
        info['integrity'] = 'não verificada'
        info['reason'] = f'Falha na conferência de integridade: {type(exc).__name__}.'
        return info
    info['integrity'] = 'sha256 correspondente'
    # SHA256 != signed identity. Report the distinction explicitly.
    info['allowed'] = True
    info['reason'] = ('Hash local corresponde ao manifesto de distribuição. '
                      'Para validar editor e cadeia de confiança, assine a distribuição com certificado válido. '
                      'Nenhum antivírus é desativado ou ignorado.')
    return info


def find_trusted_bridge() -> tuple[Path | None, dict[str, Any]]:
    if platform.system() != 'Windows':
        return None, inspect_bridge(bridge_candidates()[0])
    result = None
    for path in bridge_candidates():
        state = inspect_bridge(path)
        if state['allowed']:
            return path, state
        if state['present']:
            result = state
    return None, result or inspect_bridge(bridge_candidates()[0])
