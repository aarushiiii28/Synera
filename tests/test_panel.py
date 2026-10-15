"""Panel discovery engine: calibration under the null, recovery of planted interactions, proxy removal."""
import numpy as np
import pytest
from scipy import stats

from synera_core.benchmark.generator import STRESSORS, label_pairs, simulate_benchmark
from synera_core.discovery.panel import PanelDiscovery
from tests.conftest import make_panel


def _lam(p):
    p = np.clip(np.asarray(p, float), 1e-300, 1)
    return float(np.median(stats.chi2.isf(p, 1)) / stats.chi2.ppf(0.5, 1))


def test_null_calibration_bootstrap_beats_naive():
    """With persistent regressors and AR(1) errors the naive F is inflated; the bootstrap-calibrated test is closer to honest."""
    naive, boot = [], []
    for s in range(6):
        df = make_panel(seed=100 + s, null=True)
        df["outcome"] = df["outcome"]          # null: main effects, city effects, season, AR(1) noise only
        d = PanelDiscovery(df, "outcome", STRESSORS, n_boot=99, seed=s)
        for pair in d.pairs[::4]:
            j = d._test_pair(*pair).joint
            naive.append(j.p_naive)
            boot.append(j.p_boot)
    assert _lam(naive) > _lam(boot)                     # calibration actually helps
    assert np.mean(np.array(boot) < 0.05) < 0.2         # and false-positive rate is near nominal, not catastrophic


def test_planted_interactions_recovered_with_types():
    df = make_panel(n_days=260, seed=7, snr=20.0)
    d = PanelDiscovery(df, "outcome", STRESSORS, n_boot=99, n_ci=40, seed=7)
    out = d.run()
    found = {frozenset(r.pair): r.type for r in out["accepted"]}
    assert frozenset(("heat_index", "pm25")) in found
    assert found[frozenset(("heat_index", "pm25"))] == "SYNERGISTIC"
    assert found.get(frozenset(("heat_index", "rh"))) in (None, "ANTAGONISTIC")


def test_conditional_selection_removes_proxies():
    df = make_panel(n_days=260, seed=11, snr=20.0)
    d = PanelDiscovery(df, "outcome", STRESSORS, n_boot=99, n_ci=40, seed=11)
    out = d.run()
    assert out["stage_counts"]["marginal_bh"] >= out["stage_counts"]["after_backward"]
    assert out["stage_counts"]["marginal_bh"] > out["stage_counts"]["after_backward"]   # leakage into correlated pairs was removed
    _, truth = simulate_benchmark(df.drop(columns=["outcome", "provenance"]), snr=20.0, seed=11)
    labels = label_pairs(df, truth)
    selected = [labels[r.pair] for r in out["accepted"]]
    assert selected.count("easy_decoy") == 0


def test_block_length_and_surface_shape():
    df = make_panel(n_days=200, seed=3, snr=20.0)
    d = PanelDiscovery(df, "outcome", STRESSORS, n_boot=49, n_ci=20, seed=3)
    out = d.run()
    assert 5 <= out["block_len"] <= 30
    for r in out["accepted"]:
        z = np.array(r.surface["z_gap"])
        assert z.shape == (30, 30) and np.isfinite(z).all()


def test_make_panel_rejects_unsorted():
    df = make_panel(n_days=50)
    with pytest.raises(ValueError):
        PanelDiscovery(df.sample(frac=1.0, random_state=0).reset_index(drop=True), "outcome", STRESSORS)
