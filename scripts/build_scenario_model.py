"""Fit the scenario models (one per outcome) from the real panels and register them in the ledger.

    python scripts/build_scenario_model.py          # writes artifacts/results/scenario_model_<outcome>.json

Deterministic (fixed seeds): the same panel and code always give the same model and the same file hash.
"""
from __future__ import annotations

import json
import sys
import time

import pandas as pd

from synera_core.config import find_repo_root
from synera_core.prediction.scenario import OUTCOMES, fit_scenario_model
from synera_core.provenance.hashing import sha256_file
from synera_core.provenance.manifest import register_file
from synera_core.provenance.store import open_ledger

ROOT = find_repo_root()


def main() -> int:
    out_dir = ROOT / "artifacts" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = open_ledger()
    done = 0
    for oid, spec in OUTCOMES.items():
        panel_path = ROOT / spec["panel"]
        if not panel_path.exists():
            print(f"  {oid}: panel missing ({spec['panel']}); run scripts/build_health_panel.py")
            continue
        t0 = time.time()
        panel = pd.read_parquet(panel_path)
        dataset_hash = sha256_file(panel_path)
        blocks = ledger.find_by_artifact(dataset_hash)
        meta = {"outcome": {"id": oid, "label": spec["label"], "unit": "% more or fewer deaths than a typical week"},
                "dataset": {"id": spec["dataset_id"], "sha256": dataset_hash, "ledger_block": blocks[0][0].index if blocks else None}}
        model = fit_scenario_model(panel, meta)
        path = out_dir / f"scenario_model_{oid}.json"
        path.write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
        _, block = register_file(ledger, path, "model", {"provenance": "REAL", "outcome": oid, "dataset_id": spec["dataset_id"],
                                                         "dataset_sha256": dataset_hash, "description": "Scenario model learned from real mortality data"})
        v = model["validation"]["leave_states_out"]
        print(f"  {oid:7s} {model['training']['rows']:6d} rows, {model['training']['states']} states | out-of-sample R2 additive {v['additive']:+.4f} "
              f"with interactions {v['with_interactions']:+.4f} gbm {v['gradient_boosting']:+.4f} | {path.stat().st_size / 1e6:.2f} MB, ledger block {block.index} ({time.time() - t0:.0f}s)")
        done += 1
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
