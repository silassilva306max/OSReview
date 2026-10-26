"""WinGet update discovery. Never install without informed user action."""
from __future__ import annotations
import platform
import shutil
import subprocess


def scan_upgrades(timeout=55):
    if platform.system() != 'Windows':
        return {'supported': False, 'status': 'Disponível somente no Windows', 'lines': []}
    winget = shutil.which('winget')
    if not winget:
        return {'supported': False, 'status': 'WinGet não encontrado. Instale o App Installer pela Microsoft Store.', 'lines': []}
    try:
        result = subprocess.run([winget, 'upgrade', '--disable-interactivity'],
                                capture_output=True, text=True, encoding='utf-8', errors='replace',
                                timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        output = (result.stdout or '').strip()
        error = (result.stderr or '').strip()
        # winget returns various locale-dependent formats; do not claim a verified count.
        return {'supported': True, 'status': 'Consulta concluída; confira versões e nomes abaixo.'
                if output else ('Sem listagem disponível: ' + error[:220]),
                'lines': output.splitlines()[:140], 'returncode': result.returncode}
    except subprocess.TimeoutExpired:
        return {'supported': True, 'status': 'Consulta ultrapassou o tempo limite. Tente novamente com internet.', 'lines': []}
    except OSError as exc:
        return {'supported': False, 'status': f'Falha ao consultar WinGet: {exc}', 'lines': []}
