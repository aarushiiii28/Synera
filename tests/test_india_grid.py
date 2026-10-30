"""India electricity panels (Track D): own stressor columns, real-outcome construction, and the engine's use of them."""
import numpy as np
import pandas as pd
import pytest

from synera_core.benchmark.generator import STRESSORS
from synera_core.pipeline.registry import INDIA_GRID_STRESSORS, get_registry, get_spec, load_panel


def test_india_specs_carry_their_own_stressors():
    for did in ("india_grid", "india_grid_b"):
        s = get_spec(did)
        assert s.track == "D" and s.provenance == "REAL" and s.runnable
        assert s.stressor_cols == list(INDIA_GRID_STRESSORS)
    assert get_spec("us_mortality").stressor_cols == list(STRESSORS)          # every other dataset keeps the ten standard stressors


def test_later_data_counts_for_g7_but_split_the_places_does_not():
    from synera_core.pipeline.gates import REPLICATION_LEVELS
    from synera_core.validation.confidence import compute_confidence
    assert "LATER_DATA_REPLICATION" in REPLICATION_LEVELS and "INDEPENDENT_REPLICATION" in REPLICATION_LEVELS
    assert "INTERNAL_REPLICATION" not in REPLICATION_LEVELS and "CROSS_TISSUE_SAME_COHORT" not in REPLICATION_LEVELS
    score = lambda lvl: compute_confidence(0.001, 0.05, 0.5, True, lvl, True, 1.0, trust=1)["components"]["replication"]   # noqa: E731
    assert score("INDEPENDENT_REPLICATION") > score("LATER_DATA_REPLICATION") > score("INTERNAL_REPLICATION") > 0


def test_later_panels_are_registered_inputs_not_analyses_and_start_after_the_discovery_window():
    reg = get_registry()
    for did, late in (("india_grid", "india_grid_late"), ("india_grid_b", "india_grid_b_late")):
        assert reg[did].replicates_on == late
        assert reg[late].role == "replication data" and not reg[late].runnable          # a check's input, not a run of its own
        if reg[late].abs_path.exists() and reg[did].abs_path.exists():
            first_late = pd.read_parquet(reg[late].abs_path)["date"].min()
            last_found = pd.read_parquet(reg[did].abs_path)["date"].max()
            assert first_late > last_found                                               # not one later-data day was used to find a pair


def test_the_two_panels_use_different_states():
    reg = get_registry()
    if not (reg["india_grid"].abs_path.exists() and reg["india_grid_b"].abs_path.exists()):
        pytest.skip("run scripts/build_india_grid_panel.py first")
    a, b = load_panel(reg["india_grid"]), load_panel(reg["india_grid_b"])
    assert set(a["city"]).isdisjoint(set(b["city"]))
    for d in (a, b):
        assert not d[[*INDIA_GRID_STRESSORS, "outcome"]].isna().any().any()
        assert (d.groupby("city")["date"].diff().dropna() > pd.Timedelta(0)).all()   # strictly increasing dates per state
        # the sensitivity version removes the same-day average of the panel's states (weighted by expected demand)
        w = d["expected_mu"]
        m = (d["outcome_nat"] * w).groupby(d["date"]).sum() / w.groupby(d["date"]).sum()
        assert np.abs(m).max() < 1e-6
        assert np.abs((d["outcome"] * w).groupby(d["date"]).sum() / w.groupby(d["date"]).sum()).max() > 1e-3   # the analysed outcome keeps it


def test_expected_demand_removes_trend_season_and_weekday():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("bip", Path(__file__).resolve().parents[1] / "scripts" / "build_india_grid_panel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    dates = pd.Series(pd.date_range("2019-01-01", periods=1500, freq="D"))
    t = np.arange(1500) / 365.25
    y = 3 + 0.05 * t + 0.2 * np.sin(2 * np.pi * dates.dt.dayofyear / 365.25) + 0.1 * (dates.dt.dayofweek >= 5)
    resid = np.asarray(y) - mod.expected_log(dates, np.asarray(y))
    assert np.abs(resid).max() < 1e-8                                         # a pure trend + season + weekday series leaves nothing
