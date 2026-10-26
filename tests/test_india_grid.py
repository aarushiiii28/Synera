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
