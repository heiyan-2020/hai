"""Summarize — aggregate runs into a latency summary table."""
import sys

import yaml


def summarize(run_paths: list[str], output_path: str) -> dict:
    runs = []
    for p in run_paths:
        with open(p, "r", encoding="utf-8") as fh:
            runs.append(yaml.safe_load(fh))

    n = len(runs)
    prefill_ms = sum(r["prefill_ms"] for r in runs) / n
    # PIN: decode-time-is-measured
    decode_ms = sum(r["decode_ms"] for r in runs) / n
    total_ms = sum(r["total_ms"] for r in runs) / n

    # DERIVED: overhead is the residual once measured prefill and decode are
    # subtracted from measured total. Any measurement error lands here.
    overhead_ms = total_ms - prefill_ms - decode_ms

    summary = {
        "produced_by": "demo.summarize",
        "prefill_ms": prefill_ms,
        "decode_ms": decode_ms,
        "overhead_ms": overhead_ms,
    }
    with open(output_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(summary, fh)
    return summary


if __name__ == "__main__":
    summarize(sys.argv[1:-1], sys.argv[-1])
