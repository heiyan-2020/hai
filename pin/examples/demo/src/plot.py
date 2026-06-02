"""Render the latency-breakdown figure from summary.yaml.

This is the *figure's* one entry point: `plot.py <args>` on a clean shell fully
determines the image, exactly like an experiment's run script. A figure is an
artifact too, so it earns its own protocol — and every colored segment below
traces to the line that draws it.
"""
import argparse

import yaml

try:  # the renderer is optional; the protocol only needs these lines to exist
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    plt = None

PREFILL = "#d1495b"   # prefill segment colour
DECODE = "#2e4057"    # decode segment colour
OVERHEAD = "#cccccc"  # overhead residual colour


def render(summary_path: str, out_path: str) -> None:
    """Draw a single stacked horizontal bar: prefill | decode | overhead."""
    with open(summary_path, "r", encoding="utf-8") as fh:
        s = yaml.safe_load(fh)

    fig, ax = plt.subplots(figsize=(8, 1.6))

    # prefill segment: anchored at x=0, width is the measured prefill time
    ax.barh(0, s["prefill_ms"], left=0.0, color=PREFILL, label="prefill")
    # decode segment: starts where prefill ends, width is the measured decode time
    ax.barh(0, s["decode_ms"], left=s["prefill_ms"], color=DECODE, label="decode")
    # overhead segment: the residual tail, drawn after prefill+decode
    ax.barh(0, s["overhead_ms"], left=s["prefill_ms"] + s["decode_ms"],
            color=OVERHEAD, label="overhead")

    ax.set_xlabel("time (ms) from start")  # x-axis is absolute milliseconds
    ax.legend(loc="upper right")
    fig.savefig(out_path, dpi=120, bbox_inches="tight")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Render the latency-breakdown figure.")
    ap.add_argument("--summary", default="data/summary.yaml",
                    help="summary.yaml produced by run_demo.py")
    ap.add_argument("--out", default="data/latency_breakdown.png",
                    help="output PNG path")
    args = ap.parse_args(argv)
    render(args.summary, args.out)


if __name__ == "__main__":
    main()
