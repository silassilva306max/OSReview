"""Read-only realtime FPS capture via bundled Intel PresentMon CLI 2.6.0.

No DLL injection, external standalone user installation or synthetic FPS.
Only starts capture after user clicks Activar. No target EXE modification.
"""
from __future__ import annotations
from collections import deque
import csv
import hashlib
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import threading
import time
from typing import Any

PRESENTMON_SHA256='b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af'
COLUMNS=('MsBetweenDisplayChange','MsBetweenPresents','MsBetweenAppPresents')


def bundled_presentmon_path() -> Path:
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))
    return root/'fps_engine'/'PresentMon.exe'


def verify_presentmon(exe: Path) -> bool:
    if not exe.is_file(): return False
    h=hashlib.sha256()
    with exe.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()==PRESENTMON_SHA256


def valid_process(name: str) -> bool:
    return (bool(name) and name.lower().endswith('.exe') and name == Path(name).name
            and len(name) <= 120 and '\\' not in name and '/' not in name)


class FPSLive:
    def __init__(self):
        self._proc=None
        self._lock=threading.RLock()
        self._dts=deque(maxlen=500)
        self._last=0.0
        self._error='Contador desativado.'
        self._process_name=''

    def start(self, process_name: str):
        if platform.system() != 'Windows':
            raise RuntimeError('Captura de FPS por ETW disponível apenas no Windows.')
        if not valid_process(process_name):
            raise ValueError('Informe o nome de um processo executável, como jogo.exe.')
        binary=bundled_presentmon_path()
        if not verify_presentmon(binary):
            raise RuntimeError('Motor FPS ausente ou SHA-256 inválido. Reinstale o OSReview a partir do instalador oficial.')
        self.stop()
        args=[str(binary),'--process_name',process_name,'--output_stdout',
              '--no_console_stats','--session_name','OSReviewFPS']
        try:
            proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,text=True,encoding='utf-8-sig',errors='replace',
                                  bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except OSError as exc:
            raise RuntimeError(f'Falha ao iniciar motor FPS: {exc}') from exc
        with self._lock:
            self._proc=proc
            self._dts.clear()
            self._last=0.
            self._process_name=process_name
            self._error='Aguardando quadros do processo '+process_name+'...'
        threading.Thread(target=self._consume,args=(proc,),daemon=True,name='osreview-fps').start()

    def _consume(self,proc):
        try:
            # PresentMon emits CSV header first (v2 schema); no polling of file.
            reader=csv.DictReader(proc.stdout)
            if not reader.fieldnames:
                raise ValueError('PresentMon não enviou um cabeçalho CSV.')
            col=next((name for name in COLUMNS if name in reader.fieldnames),None)
            if not col:
                raise ValueError('Colunas FPS não reconhecidas: '+', '.join(reader.fieldnames[:9]))
            for line in reader:
                if proc.poll() is not None: break
                try: ms=float(line.get(col) or 0)
                except (ValueError,TypeError): continue
                if 0.1 <= ms <= 2000:
                    with self._lock:
                        if proc is not self._proc: return
                        self._dts.append(ms)
                        self._last=time.monotonic()
                        self._error=''
        except Exception as exc:
            with self._lock:
                if proc is self._proc:self._error=str(exc)
        finally:
            if proc is self._proc:
                with self._lock:
                    if not self._error:self._error='Captura encerrada.'

    def snapshot(self) -> dict[str,Any]:
        with self._lock:
            age = time.monotonic()-self._last if self._last else None
            values=list(self._dts)
            valid=age is not None and age < 3 and len(values)>3
            ms=statistics.mean(values) if valid else None
            return {'enabled':self._proc is not None and self._proc.poll() is None,
                    'fps':round(1000/ms,1) if ms else None,
                    'frametime_ms':round(ms,2) if ms else None,
                    'frames':len(values),'target':self._process_name,
                    'status':('Capturando quadros reais' if valid else self._error or 'Aguardando quadros...')}

    def stop(self):
        with self._lock:
            proc=self._proc
            self._proc=None
            self._dts.clear()
            self._last=0.
            self._error='Contador desativado.'
        if proc and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill()


fps_session=FPSLive()
