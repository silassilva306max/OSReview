"""Small voluntary synthetic benchmarks, not hardware defect or burn-in tests."""
from __future__ import annotations

import math
import threading
import time
from typing import Any


class BenchmarkCancelled(Exception):
    pass


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
