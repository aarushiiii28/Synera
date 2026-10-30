"""Build the application database from the datasets and the pipeline (idempotent).

    python scripts/seed_db.py            # full-strength runs (Track B takes a few minutes)
    python scripts/seed_db.py --quick    # fewer bootstrap resamples (demo)
    python scripts/seed_db.py --force    # re-run even if an identical run exists
    python scripts/seed_db.py --core     # only the core runs (shorter, for slow machines)

Nothing is hand-written into the database: datasets come from the registry and the files on disk, and
findings come only from running the real pipeline. If the pipeline finds nothing, there are no findings.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # repo root, so `backend` is importable when run as a script

from sqlmodel import Session, select  # noqa: E402

from backend.app.db.database import engine, migrate_db
from backend.app.db.models import Finding, Run
from backend.app.services.persist import sync_datasets
from backend.app.services.runs import manager
from synera_core.pipeline.registry import ensure_benchmark_dataset
from synera_core.provenance.manifest import register_file
from synera_core.provenance.store import open_ledger


ALL_RUNNABLE = ("osd-211", "benchmark_track_b", "us_mortality", "us_heart", "us_stroke", "india_grid", "india_grid_b")
CORE = ("osd-211", "benchmark_track_b", "us_mortality")      # a shorter build for slow machines (each real-data run takes 1 to 6 minutes depending on the load)


def seed(quick: bool = False, force: bool = False, only: tuple[str, ...] = ALL_RUNNABLE) -> None:
    migrate_db()
    ledger = open_ledger()
    ensure_benchmark_dataset(ledger)
    # Measured result files are artifacts too: register them so any later edit is detectable.
    results = Path(__file__).resolve().parents[1] / "artifacts" / "results"
    for name, prov in (("benchmark.json", "SIMULATED"), ("space_biology.json", "REAL"), ("osdr_genes.json", "REAL"), ("scenario_model_all.json", "REAL"), ("scenario_model_heart.json", "REAL"), ("scenario_model_stroke.json", "REAL")):
        if (results / name).exists():
            register_file(ledger, results / name, "dataset", {"type": "result", "provenance": prov})
    with Session(engine) as s:
        sync_datasets(s, ledger)
    for dataset_id in only:
        with Session(engine) as s:
            run_id, reused = manager.start(s, ledger, dataset_id, {"quick": quick}, force, inline=True)
        with Session(engine) as s:
            run = s.get(Run, run_id)
            n = len(s.exec(select(Finding).where(Finding.dataset_id == dataset_id)).all())
            print(f"{dataset_id:18s} run {run_id} {'(reused)' if reused else ''} -> {run.status}  "
                  f"findings={n}  replay_match={(run.replay or {}).get('matches')}  result={ (run.result_hash or '')[:12] }")
            if run.status != "COMPLETED":
                print("   ", run.error)
    with Session(engine) as s:
        sync_datasets(s, ledger)
    v = ledger.verify()
    print(f"ledger: height={v['height']} chain_valid={v['valid']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--core", action="store_true", help="only the core runs (NASA, benchmark, all-cause deaths): faster, for deployed images")
    ap.add_argument("--only", nargs="+", metavar="DATASET", help="run only these dataset ids (for example: --only india_grid india_grid_b)")
    a = ap.parse_args()
    seed(a.quick, a.force, tuple(a.only) if a.only else CORE if a.core else ALL_RUNNABLE)    # later-data panels are inputs of the india_* runs, not runs of their own
