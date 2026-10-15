"""Run the Engine Report Card benchmark and write artifacts/results/benchmark.json.

Usage:  python scripts/run_benchmark.py [--seeds 50] [--null-sims 100] [--mod-sims 200] [--sec-trials 30]
        python scripts/run_benchmark.py --sections discovery,null   # run only some sections

Results are measured, never edited by hand. A full run takes roughly 20-40 minutes on 10 cores.
"""
from __future__ import annotations

import argparse

from synera_core.benchmark.evaluate import run_benchmark

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--snrs", default="1.0,2.0,5.0,20.0")
    ap.add_argument("--null-sims", type=int, default=100)
    ap.add_argument("--mod-sims", type=int, default=200)
    ap.add_argument("--sec-trials", type=int, default=30)
    ap.add_argument("--n-boot", type=int, default=299)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--sections", default="discovery,null,moderation,security")
    a = ap.parse_args()
    rep = run_benchmark(seeds=a.seeds, snrs=tuple(float(s) for s in a.snrs.split(",")), null_sims=a.null_sims,
                        mod_sims=a.mod_sims, sec_trials=a.sec_trials, n_boot=a.n_boot, n_jobs=a.jobs,
                        sections=tuple(a.sections.split(",")))
    print("limitations:")
    for line in rep["limitations"]:
        print(" -", line)
