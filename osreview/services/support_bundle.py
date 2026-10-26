"""User-initiated, redacted support archive; never sends telemetry anywhere."""
from __future__ import annotations
from osreview import __version__

from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import platform
import sys
import zipfile

from .startup_logging import log_dir
from .sensor_diagnostics import build_report, redact
from .bridge_integrity import find_trusted_bridge


def dependency_status():
    return {name: bool(importlib.util.find_spec(name)) for name in
            ('psutil', 'platformdirs', 'PIL', 'pystray', 'speedtest', 'win32com', 'win32api', 'tkinter')}


def build_support_metadata(power=None):
    _, status = find_trusted_bridge()
    summary = {
        'app': 'OSReview', 'version': __version__,
        'utc': datetime.now(timezone.utc).isoformat(),
        'os': platform.system(), 'release': platform.release(),
        'python': sys.version.split()[0], 'architecture': platform.machine(),
        'dependencies': dependency_status(),
        'bridge': {k: status.get(k) for k in ('present', 'integrity', 'allowed', 'reason', 'sha256')},
        'sensor_report_available': bool(power),
        'interpretation': ('Se o aplicativo fecha sozinho, procure erro em osreview.log ou fatal_python.log. '
                           'Falha sem registro pode indicar encerramento externo (por exemplo sistema ou antivírus). '
                           'Nenhum relatório pode provar sozinho a causa.')
    }
    return summary


def export_support_zip(destination: str | Path, power: dict | None = None) -> Path:
    target = Path(destination)
    if target.suffix.lower() != '.zip':
        raise ValueError('O pacote de suporte deve ser um arquivo .zip')
    if not target.parent.is_dir():
        raise ValueError('Pasta de destino não encontrada')
    files = log_dir()
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        meta = build_support_metadata(power)
        archive.writestr('diagnostico_inicializacao.json', json.dumps(meta, ensure_ascii=False, indent=2))
        if power:
            snapshot = build_report(power)
            snapshot['version'] = __version__
            archive.writestr('diagnostico_sensores.json', json.dumps(snapshot, ensure_ascii=False, indent=2))
        for filename in ('osreview.log', 'fatal_python.log', 'osreview.log.1', 'osreview.log.2'):
            path = files / filename
            if path.is_file():
                # Last 256 KiB; avoid sharing unbounded history or local secrets.
                with path.open('rb') as fp:
                    if path.stat().st_size > 262144:
                        fp.seek(-262144, io.SEEK_END)
                    content = fp.read(262144).decode('utf-8', errors='replace')
                archive.writestr('logs/' + filename + '.txt', redact(content))
    return target
