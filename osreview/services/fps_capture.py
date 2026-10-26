"""Measured frame presentations through separately installed PresentMon CLI.
Never derives FPS from refresh rate or GPU load; opt-in capture for named processes only.
"""
from __future__ import annotations
import csv
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile

# CSV v2 fields vary with PresentMon release, so accept only known elapsed-ms values.
FRAME_MS_COLUMNS = ('MsBetweenDisplayChange', 'MsBetweenPresents', 'MsBetweenAppPresents')

def summarize_csv(path: Path) -> dict:
    times: list[float] = []
    col = None
    with path.open('r', encoding='utf-8-sig', errors='replace', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        col = next((c for c in FRAME_MS_COLUMNS if c in fields), None)
        if not col:
            raise ValueError('Arquivo PresentMon sem coluna de intervalos suportada: '+', '.join(fields[:12]))
        for row in reader:
            try:
                dt = float(row.get(col) or 0)
            except ValueError:
                continue
            if 0.1 <= dt <= 5000:
                times.append(dt)
    if len(times) < 3:
        raise ValueError('Dados insuficientes: abra o jogo/programa, selecione o processo correto e tente novamente.')
    return {'frames':len(times), 'fps_mean':round(1000 / statistics.mean(times), 1),
            'frametime_avg_ms':round(statistics.mean(times), 2),
            'frametime_p95_ms':round(sorted(times)[int((len(times)-1)*0.95)], 2),
            'measurement':col, 'note':'Média de intervalos de quadros capturados, não uma contagem universal de FPS de toda a tela.'}


def capture_fps(presentmon_path: str, process_name: str, seconds: int = 10) -> dict:
    if platform.system() != 'Windows':
        raise RuntimeError('Captura PresentMon disponível apenas para Windows nesta versão.')
    exe = Path(presentmon_path).expanduser()
    if not exe.is_file() or exe.suffix.lower() != '.exe':
        raise ValueError('Selecione o executável oficial PresentMon no seu computador.')
    process_name = process_name.strip()
    if not (process_name.lower().endswith('.exe') and process_name == Path(process_name).name and len(process_name) < 120):
        raise ValueError('Informe apenas nome do processo, como jogo.exe, sem caminhos.')
    if not 3 <= seconds <= 30:
        raise ValueError('Duração inválida.')
    with tempfile.TemporaryDirectory(prefix='osreview_fps_') as folder:
        destination = Path(folder) / 'frames.csv'
        args = [str(exe), '--process_name', process_name, '--timed', str(seconds),
                '--terminate_after_timed', '--no_console_stats', '--output_file', str(destination)]
        try:
            result = subprocess.run(args, timeout=seconds + 25, capture_output=True,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('PresentMon não concluiu a captura dentro do prazo.') from exc
        if result.returncode != 0 or not destination.is_file():
            raise RuntimeError('Captura sem dados. Confira compatibilidade da versão CLI do PresentMon e privilégios.')
        return {'process':process_name, 'duration_seconds':seconds, **summarize_csv(destination)}
