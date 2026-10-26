"""Static acceptance gate for compiled Windows x64 payload, BEFORE Inno Setup.

This does not replace a Windows malware scan, Authenticode verification or running
an installer on a clean machine. No binaries are downloaded or executed here.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys


def validate(root: Path) -> list[str]:
    folder = root / 'dist' / 'OSReview'
    errors: list[str] = []
    launcher = folder / 'OSReview.exe'
    if not launcher.is_file() or launcher.stat().st_size < 100_000:
        errors.append('OSReview.exe compilado ausente ou pequeno demais.')
    elif launcher.read_bytes()[:2] != b'MZ':
        errors.append('OSReview.exe não parece um PE do Windows.')
    # No source launchers: end users must only double click the executable.
    prohibited = [p.relative_to(folder).as_posix() for ext in ('*.bat','*.cmd','*.ps1') for p in folder.rglob(ext)] if folder.exists() else []
    if prohibited:
        errors.append('Scripts não permitidos no instalador: ' + ', '.join(prohibited[:8]))

    bridge = folder / '_internal' / 'sensor_bridge' / 'SensorBridge.exe'
    manifest = bridge.with_suffix('.exe.sha256')
    if not bridge.is_file():
        errors.append('Ponte .NET de sensores ausente no pacote PyInstaller.')
    elif not manifest.is_file():
        errors.append('Manifesto SHA-256 da ponte ausente.')
    else:
        parts = manifest.read_text(encoding='ascii').strip().split()
        actual = hashlib.sha256(bridge.read_bytes()).hexdigest()
        if len(parts) != 2 or parts[1] != bridge.name or parts[0] != actual:
            errors.append('Integridade da ponte de sensores inválida.')
        if bridge.read_bytes()[:2] != b'MZ':
            errors.append('SensorBridge.exe não parece um PE do Windows.')

    fps = folder / '_internal' / 'fps_engine' / 'PresentMon.exe'
    if not fps.is_file():
        errors.append('Motor FPS verificado ausente no pacote.')
    if not folder.is_dir():
        errors.append('Diretório dist/OSReview não encontrado.')
    return errors


if __name__ == '__main__':
    project_root = Path(__file__).resolve().parents[1]
    findings = validate(project_root)
    if findings:
        for finding in findings: print('ERRO:', finding)
        sys.exit(2)
    print('OK: bundle Windows contém EXE, sensores, FPS e nenhum inicializador shell.')
