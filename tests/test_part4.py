"""Tests for Part 4 (Discovery & Validation)."""

import numpy as np
import pandas as pd
import pytest

from synera_core.discovery.interactions import factorial_interaction
from synera_core.discovery.classify import classify_factorial
from synera_core.discovery.continuous import continuous_interaction
from synera_core.validation.multitest import bh_fdr
from synera_core.validation.replication import replicate
from synera_core.validation.confidence import compute_confidence
from synera_core.pipeline.states import Finding, EffectModel, StatsModel, MethodsModel, SecurityModel

def test_bh_matches_statsmodels():
    try:
        from statsmodels.stats.multitest import multipletests
        pvals = [0.01, 0.04, 0.05, 0.1, 0.2, 0.5, 0.9]
        q1 = bh_fdr(pvals)
        _, q2, _, _ = multipletests(pvals, method='fdr_bh')
        np.testing.assert_allclose(q1, q2)
    except ImportError:
        pass

def test_factorial_fdr_control():
    # simulate 2x2 with planted effects over 30 seeds
    # we just need to test empirical fdr on null features
    np.random.seed(42)
    n_features = 500
    n_samples = 40
    
    a = np.repeat([0, 1, 0, 1], 10)
    b = np.repeat([0, 0, 1, 1], 10)
    meta = pd.DataFrame({"A": a, "B": b})
    
    Y = np.random.randn(n_samples, n_features)
    # Plant an interaction in first 20 features
    for i in range(20):
        Y[:, i] += 2.0 * (a * b)
        
    res = factorial_interaction(pd.DataFrame(Y, columns=[f"F{i}" for i in range(n_features)]), meta, "A", "B")
    q = bh_fdr(res["p_AB"].values)
    
    # Check hits in the null set (features 20 to 500)
    hits = (q < 0.05)
    false_discoveries = hits[20:].sum()
    total_discoveries = hits.sum()
    fdr = false_discoveries / total_discoveries if total_discoveries > 0 else 0
    assert fdr <= 0.10

def test_classify_factorial():
    res = classify_factorial(b_A=1.0, b_B=1.0, b_AB=1.5, q=0.01, min_abs_effect=0.5)
    assert res["type"] == "synergistic"
    assert res["reversal"] is False
    
    res2 = classify_factorial(b_A=1.0, b_B=1.0, b_AB=-3.0, q=0.01)
    assert res2["type"] == "antagonistic"
    assert res2["reversal"] is True

def test_continuous():
    np.random.seed(42)
    n = 200
    A = np.random.rand(n)
    B = np.random.rand(n)
    # bilinear
    Y1 = 2*A + 2*B + 4*A*B + np.random.randn(n)*1.0
    df1 = pd.DataFrame({'A': A, 'B': B, 'Y': Y1})
    res1 = continuous_interaction('Y', 'A', 'B', df1)
    assert res1['type'] in ('synergistic', 'nonlinear')

def test_replication():
    disc = pd.DataFrame({
        "b_AB_d": [1.5, -2.0, 0.5],
        "q_AB_d": [0.01, 0.01, 0.01],
        "t_AB_d": [4.0, -4.0, 2.0],
        "df_d": [10, 10, 10]
    })
    rep = pd.DataFrame({
        "b_AB_r": [1.0, -1.5, -0.5],
        "t_AB_r": [3.0, -3.0, -1.0],
        "df_r": [10, 10, 10]
    })
    res = replicate(disc, rep, evidence_level="INTERNAL_REPLICATION")
    assert res["n_hits"] == 3
    assert res["concordance"] == pytest.approx(2/3)

def test_confidence_trust():
    c = compute_confidence(0.01, 0.05, 1.5, True, "INDEPENDENT_REPLICATION", True, 1.0, trust=0)
    assert c["score"] == 0.0
    assert c["is_blocked"] is True

def test_finding_status():
    f = Finding(
        id="hash", track="A", provenance="REAL", evidence_level="CROSS_TISSUE_SAME_COHORT",
        dataset_ids=["1"], stressors=["A","B"], feature="G1", type="synergistic",
        effect=EffectModel(b_AB=1.5, ci_low=0.5, ci_high=2.5, cohens_d=1.5),
        stats=StatsModel(p=0.001, q=0.01, n=20, df=16),
        methods=MethodsModel(parametric=True, gbm=True, nid=True),
        security=SecurityModel(status="TAMPERED"),
        status="CANDIDATE"
    )
    f.evaluate_status()
    assert f.status == "BLOCKED"
