"""Small voluntary synthetic benchmarks, not hardware defect or burn-in tests."""
from __future__ import annotations

import math
import statistics
import threading
import time
from typing import Any


class BenchmarkCancelled(Exception):
    pass


def timed_benchmark(kind: str, seconds: int, size_mb: int = 64,
                    stop: threading.Event | None = None, progress=None) -> dict[str, Any]:
    """Fixed workload, one worker, comparable only with this OSReview method."""
    if kind not in ('cpu', 'memory') or not 1 <= seconds <= 600:
        raise ValueError('Tipo ou duração de benchmark inválido.')
    if not 8 <= size_mb <= 128:
        raise ValueError('Bloco de memória fora do limite de 8–128 MB.')
    stop = stop or threading.Event()
    if stop.is_set():
        raise BenchmarkCancelled()
    source = target = None
    if kind == 'memory':
        import psutil
        if psutil.virtual_memory().available < size_mb * 1048576 * 3:
            raise ValueError('Memória disponível insuficiente para este tamanho de bloco.')
        source = bytearray(size_mb * 1048576)
        target = bytearray(len(source))
        for pos in range(0, len(source), 4096):
            source[pos] = pos % 251
    start = time.perf_counter()
    window_start = start
    window_work = 0.0
    completed = 0
    n = 2
    samples = []
    while True:
        if stop.is_set():
            raise BenchmarkCancelled()
        now = time.perf_counter()
        elapsed = now - start
        if elapsed >= seconds:
            break
        if kind == 'cpu':
            for _ in range(300):
                if n < 4 or all(n % divisor for divisor in range(2, math.isqrt(n) + 1)):
                    completed += 1
                n = 2 if n >= 5000 else n + 1
        else:
            copy_start = time.perf_counter()
            target[:] = source
            window_work += time.perf_counter() - copy_start
            completed += 1
            stop.wait(0.01)
        now = time.perf_counter()
        if now-window_start >= 1 or now-start >= seconds:
            period = max(now-window_start, 0.001)
            rate = (completed/period if kind == 'cpu' else
                    completed*size_mb/max(window_work, 0.001))
            sample = {'elapsed': round(min(now-start, seconds), 1),
                      'value': round(rate, 1)}
            samples.append(sample)
            if progress:
                progress({'elapsed': sample['elapsed'], 'duration': seconds,
                          'value': sample['value'], 'samples': samples[-120:]})
            window_start = now
            window_work = 0.0
            completed = 0
    # A short final window has very noisy throughput and would skew the score.
    period=time.perf_counter()-window_start
    if completed and period >= 0.75:
        rate=(completed/period if kind=='cpu' else completed*size_mb/max(window_work,0.001))
        samples.append({'elapsed':round(seconds,1),'value':round(rate,1)})
    values=[sample['value'] for sample in samples]
    if not values:
        raise ValueError('O teste terminou sem amostras válidas.')
    center=statistics.median(values)
    dispersion=statistics.pstdev(values) if len(values)>1 else 0.
    stability=max(0.,100*(1-dispersion/center)) if center else 0.
    return {'type':'CPU · 1 núcleo' if kind=='cpu' else 'RAM · cópia',
            'kind':kind,'duration_seconds':seconds,'size_mb':size_mb if kind=='memory' else None,
            'elapsed':round(time.perf_counter()-start,2),
            'score':round(center,1),'unit':'primos/s' if kind=='cpu' else 'MB/s',
            'stability_percent':round(stability,1),
            'min_score':round(min(values),1),'max_score':round(max(values),1),
            'samples':samples,
            'note':'Pontuação = mediana das amostras por segundo. Compare apenas testes OSReview do mesmo tipo, duração e versão.'}


def cpu_benchmark(seconds: int = 4, stop: threading.Event | None = None) -> dict[str, Any]:
    stop = stop or threading.Event()
    start = time.perf_counter()
    n, primes = 2, 0
    while time.perf_counter() - start < seconds:
        for _ in range(500):
            if n < 4 or all(n % divisor for divisor in range(2, math.isqrt(n) + 1)):
                primes += 1
            n += 1
        if stop.is_set():
            raise BenchmarkCancelled()
    elapsed = max(time.perf_counter() - start, 0.01)
    return {"type": "CPU – 1 núcleo", "elapsed": round(elapsed, 2),
            "primes": primes, "iterations": n - 2,
            "score_primes_s": round(primes / elapsed, 2),
            "note": "Pontuação experimental; compare somente versões idênticas do OSReview."}


def memory_benchmark(size_mb: int = 64, stop: threading.Event | None = None) -> dict[str, Any]:
    stop = stop or threading.Event()
    if stop.is_set():
        raise BenchmarkCancelled()
    start = time.perf_counter()
    first = bytearray(size_mb * 1048576)
    for pos in range(0, len(first), 4096):
        first[pos] = pos % 251
    if stop.is_set():
        raise BenchmarkCancelled()
    copy_start = time.perf_counter()
    second = first[:]
    copied = time.perf_counter() - copy_start
    total = time.perf_counter() - start
    checksum = second[len(second)//2]  # Access the result; retains actual copy.
    del first, second
    return {"type": "RAM – cópia sintética", "size_mb": size_mb,
            "elapsed": round(total, 4), "copy_seconds": round(copied, 4),
            "copy_mb_s": round(size_mb / max(copied, 0.000001), 1),
            "checksum": checksum,
            "note": "Mede cópia de dados em Python; não substitui MemTest86 nem mede a frequência física da RAM."}
