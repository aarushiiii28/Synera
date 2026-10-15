"""Shared fixtures: a tiny real-structure panel dataset and a temporary ledger, so pipeline tests run in seconds."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from synera_core.benchmark.generator import STRESSORS, simulate_benchmark
from synera_core.pipeline.registry import DatasetSpec
from synera_core.provenance.ledger import Ledger


def make_panel(n_cities: int = 4, n_days: int = 140, seed: int = 0, snr: float = 8.0, null: bool = False) -> pd.DataFrame:
    """AR(1)-persistent stressors in several cities + simulated outcome (same generator as the benchmark)."""
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_cities):
        base = rng.normal(size=(n_days, len(STRESSORS)))
        for t in range(1, n_days):                       # persistent covariates, like weather
            base[t] = 0.8 * base[t - 1] + 0.6 * base[t]
        # induce the heat_index/rh and pm25/pm10 correlations seen in the real panel
        base[:, STRESSORS.index("pm10")] = 0.9 * base[:, STRESSORS.index("pm25")] + 0.4 * base[:, STRESSORS.index("pm10")]
        d = pd.DataFrame(base, columns=STRESSORS)
        d["city"] = f"C{c}"
        d["date"] = pd.date_range("2023-01-01", periods=n_days)
        rows.append(d)
    env = pd.concat(rows, ignore_index=True)
    for s in STRESSORS:
        g = env.groupby("city")[s]
        env[s] = (env[s] - g.transform("mean")) / g.transform("std")
    df, _ = simulate_benchmark(env, snr=snr, seed=seed, null=null)
    return df


@pytest.fixture()
def tiny_panel() -> pd.DataFrame:
    return make_panel()


@pytest.fixture()
def tmp_ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger.db", tmp_path / "key.pem")


@pytest.fixture()
def tiny_registry(tmp_path, monkeypatch, tmp_ledger):
    """Point the registry at a temporary panel dataset registered in a temporary ledger."""
    from synera_core.pipeline import orchestrator, registry
    from synera_core.provenance.manifest import register_file

    df = make_panel()
    p = tmp_path / "data" / "synthetic" / "tiny_panel.parquet"
    p.parent.mkdir(parents=True)
    df.to_parquet(p, index=False)
    # `repo_root / absolute_path` is the absolute path, so DatasetSpec.abs_path resolves to the temporary file.
    spec = DatasetSpec("tiny_panel", "Tiny panel", "B", "panel", "SIMULATED", str(p), units="standardised")
    reg = {"tiny_panel": spec}
    for mod in (orchestrator, registry):
        monkeypatch.setattr(mod, "get_registry", lambda: reg, raising=False)
    monkeypatch.setattr(orchestrator, "get_spec", lambda i: reg[i])
    register_file(tmp_ledger, p, "dataset", {"provenance": "SIMULATED"}, manifest_path=tmp_path / "data" / "MANIFEST.json")
    return {"spec": spec, "path": p, "ledger": tmp_ledger, "df": df}
