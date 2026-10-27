"""Long-lived, read-only LibreHardwareMonitor sensor bridge session.

The bridge stays in one local process (no repeated spawn/stop on every poll).
No network, elevation, antivirus exemptions or PowerShell. Store only validated
measurements. Errors are visible to the dashboard so users can fix prerequisites.
"""
from __future__ import annotations
import json
import math
import platform
import subprocess
import threading
import time
from typing import Any
from .bridge_integrity import find_trusted_bridge
from .sensor_diagnostics import redact
from .startup_logging import LOG


class SensorRuntime:
    def __init__(self):
        self._lock = threading.RLock()
        self._process = None
        self._started = False
        self._rows: list[dict] = []
        self._last_received = 0.0
        self._error = 'O motor de sensores ainda não foi iniciado.'
        self._device_count = 0
        self._warnings: list[str] = []
        self._extremes: dict[str, tuple[float, float]] = {}
        self._hardware: list[dict] = []
        self._unavailable: list[dict] = []
        self._missing_count = 0
        self._stderr_lines: list[str] = []
        self._last_packet_status = ''
        self._started_at = 0.0
        self._last_attempt_at = 0.0
        self._retry_paused = False
        self._last_exit_code = None

    def start(self):
        with self._lock:
            if platform.system() != 'Windows' or self._retry_paused:
                return
            if self._process is not None and self._process.poll() is None:
                return
            now = time.monotonic()
            if self._last_attempt_at and now - self._last_attempt_at < 20:
                return
            self._last_attempt_at = now
            self._started_at = now
            bridge, result = find_trusted_bridge()
            if bridge is None:
                self._started = False
                self._error = result.get('reason', 'Motor não encontrado')
                LOG.warning('SensorBridge indisponivel; confira a integridade e a instalacao.')
                return
            self._started = True
            try:
                self._process = subprocess.Popen(
                    [str(bridge), '--stream'], stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', errors='replace', bufsize=1,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            except OSError as exc:
                self._error = f'Não foi possível iniciar a ponte ({type(exc).__name__}).'
                self._started = False
                self._retry_paused = True
                LOG.error('Nao foi possivel executar SensorBridge (%s). Novas tentativas automaticas suspensas.', type(exc).__name__)
                return
            threading.Thread(target=self._read_stderr, name='osreview-lhm-errors', daemon=True).start()
            threading.Thread(target=self._read_stream, name='osreview-lhm', daemon=True).start()

    def _read_stderr(self):
        process = self._process
        if process is None or process.stderr is None: return
        try:
            for line in process.stderr:
                with self._lock:
                    self._stderr_lines = (self._stderr_lines + [redact(line.strip()[:500])])[-40:]
        except OSError:
            pass

    def _read_stream(self):
        process = self._process
        if process is None: return
        try:
            for line in process.stdout:
                try:
                    payload = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                clean = []
                for row in payload.get('sensors') or []:
                    if not isinstance(row, dict): continue
                    try: v = float(row.get('Value'))
                    except (ValueError, TypeError): continue
                    if not math.isfinite(v): continue
                    clean.append(row)
                with self._lock:
                    self._rows = clean
                    self._last_received = time.monotonic()
                    self._device_count = int(payload.get('devices') or 0)
                    self._warnings = [str(x) for x in (payload.get('warnings') or [])[:30]]
                    self._hardware = [x for x in (payload.get('hardware') or [])[:100] if isinstance(x,dict)]
                    self._unavailable = [x for x in (payload.get('unavailable') or [])[:240] if isinstance(x,dict)]
                    self._missing_count = int(payload.get('missingCount') or 0)
                    self._last_packet_status = str(payload.get('status') or '')
                    self._error = '' if clean else str(payload.get('status') or 'Nenhum sensor acessível')
                    for row in clean:
                        key = str(row.get('Identifier') or row.get('Name'))
                        v = float(row['Value'])
                        lo, hi = self._extremes.get(key, (v, v))
                        self._extremes[key] = (min(lo, v), max(hi, v))
                if payload.get('status') == 'falha no motor de sensores': break
        except (OSError, ValueError) as exc:
            with self._lock: self._error = f'Falha na comunicação: {type(exc).__name__}.'
        try:
            code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            code = None
        with self._lock:
            if code is not None:
                self._last_exit_code = code
                detail = '\n'.join(self._stderr_lines[-5:])
                if code != 0:
                    self._error = f'Motor encerrado (código {code}). {detail.strip()}'
                    self._retry_paused = True
                    LOG.error('SensorBridge encerrou com codigo %s; reinicializacao automatica suspensa.', code)
                elif not self._rows:
                    self._error = 'Motor encerrou sem disponibilizar sensores.'
            if self._process is process:
                self._process = None
                self._started = False

    def snapshot(self) -> dict[str, Any]:
        self.start()
        with self._lock:
            age = time.monotonic() - self._last_received if self._last_received else None
            valid = age is not None and age <= 12 and bool(self._rows)
            measurements = []
            if valid:
                for item in self._rows:
                    item = dict(item)
                    key = str(item.get('Identifier') or item.get('Name'))
                    lo, hi = self._extremes.get(key,(float(item['Value']), float(item['Value'])))
                    item['Min'] = round(lo,2)
                    item['Max'] = round(hi,2)
                    measurements.append(item)
            return {'available': valid, 'rows': measurements, 'devices': self._device_count,
                'age_seconds': round(age,1) if age is not None else None,
                'error': self._error if not valid else '', 'warnings': list(self._warnings),
                'hardware': list(self._hardware), 'unavailable': list(self._unavailable),
                'missing_count': self._missing_count, 'status': self._last_packet_status,
                'stderr': list(self._stderr_lines), 'exit_code': self._last_exit_code,
                'pid': self._process.pid if self._process is not None and self._process.poll() is None else None,
                'started_seconds_ago':round(time.monotonic()-self._started_at,1) if self._started_at else None,
                'automatic_retry_paused': self._retry_paused}

    def stop(self):
        with self._lock:
            p = self._process
            self._process = None
            self._started = False
            self._rows = []
            self._last_received = 0.0
            self._error = 'Motor parado; aguardando reinicialização.'
            self._device_count = 0
            self._hardware = []
            self._unavailable = []
            self._missing_count = 0
            self._last_packet_status = ''
            self._stderr_lines = []
            self._extremes = {}
            self._last_exit_code = None
            self._last_attempt_at = 0.0
            self._retry_paused = False
        if p and p.poll() is None:
            p.terminate()
            try: p.wait(timeout=3)
            except subprocess.TimeoutExpired: p.kill()


runtime = SensorRuntime()
