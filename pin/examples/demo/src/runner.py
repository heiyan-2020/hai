"""Runner — produces a single latency measurement.

Every number this file emits is wall-clock MEASURED, never computed from a
per-token rate. The `decode-time-is-measured` pin protects that property.
"""
import sys
import time

import yaml


def measure_prefill_ms() -> float:
    """Wall-clock time of a stand-in prefill pass, in milliseconds."""
    start = time.perf_counter()
    _ = sum(i * i for i in range(60_000))
    return (time.perf_counter() - start) * 1000.0


def measure_decode_ms() -> float:
    """Wall-clock time of a stand-in decode loop, in milliseconds.

    # PIN: decode-time-is-measured
    This is real elapsed time around the loop — not tokens times a per-token
    latency. Keep it that way; a synthetic decode time silently fakes the
    headline result.
    """
    start = time.perf_counter()
    _ = sum(i for i in range(140_000))
    return (time.perf_counter() - start) * 1000.0


def run(output_path: str) -> dict:
    prefill = measure_prefill_ms()
    decode = measure_decode_ms()
    record = {
        "produced_by": "demo.runner",
        "prefill_ms": prefill,
        "decode_ms": decode,
        "total_ms": prefill + decode,
    }
    with open(output_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(record, fh)
    return record


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "data/run.yaml")
