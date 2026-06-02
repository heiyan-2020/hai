"""Single entry point for the demo latency experiment.

This is the one script the protocol points at: it measures latency `--n-runs`
times and writes the aggregated summary. Every configurable knob is a flag, and
nothing is read from the environment — `run_demo.py <args>` on a clean shell
fully determines the run. That is the contract a protocol's one script must
honor.
"""
import argparse
import os

import runner
import summarize


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Demo latency experiment.")
    ap.add_argument("--n-runs", type=int, default=5,
                    help="how many measured runs to average")
    ap.add_argument("--out-dir", default="data",
                    help="directory for the per-run and summary yaml files")
    args = ap.parse_args(argv)

    run_paths = []
    for i in range(args.n_runs):
        path = os.path.join(args.out_dir, f"run_{i}.yaml")
        runner.run(path)
        run_paths.append(path)
    summarize.summarize(run_paths, os.path.join(args.out_dir, "summary.yaml"))


if __name__ == "__main__":
    main()
