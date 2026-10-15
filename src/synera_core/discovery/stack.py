"""The full SYNERA discovery stack for panel (continuous-stressor) data.

One entry point, :func:`run_full_stack`, is shared by the benchmark, the pipeline orchestrator and the
API so that every number shown anywhere comes from the same code path.

Stages (each pair carries a boolean per stage so the loss of recall is visible):

    S0  screened                     every stressor pair
    S1  raw p < alpha                block-bootstrap-calibrated joint test, before multiplicity
    S2  BH q < alpha                 over all pairs (marginal screen)
    S3  conditional selection        forward selection + backward elimination (removes proxies)
    S4  effect gate                  standardised effect >= gate AND bootstrap CI lower bound >= gate
    S5  second opinion               top-K pair in LightGBM-SHAP and/or the neural detector

A finding is ``VALIDATED`` when it passes S4 and has at least one second-opinion method
(robustness >= 2/3); it is a ``CANDIDATE`` when it passes S3 only.
"""

from __future__ import annotations

import time
from typing import Sequence

import numpy as np
import pandas as pd

from synera_core.discovery.gbm_interactions import run_gbm_interactions
from synera_core.discovery.neural import run_neural_interactions
from synera_core.discovery.panel import PanelDiscovery


def nuisance_frame(df: pd.DataFrame, stressors: Sequence[str]) -> pd.DataFrame:
    """Stressors plus city code and seasonality, so tree/neural models can absorb them."""
    X = df[list(stressors)].copy()
    X["city_code"] = pd.factorize(df["city"])[0].astype(float)
    doy = pd.to_datetime(df["date"]).dt.dayofyear.to_numpy(float)
    X["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    X["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    return X


def run_full_stack(df: pd.DataFrame, y_col: str, stressors: Sequence[str], *, alpha: float = 0.05,
                   effect_gate: float = 0.05, n_boot: int = 299, n_ci: int = 200, seed: int = 0,
                   second_opinion: bool = True, topk: int = 6, gbm_permutations: int = 0,
                   progress=None, on_stage=None) -> dict:
    """Run discovery + validation + second opinions. ``df`` must be sorted by (city, date).

    ``on_stage(name, info)`` (optional) is called as the stages complete: ``screen``, ``forward``,
    ``backward`` and ``second_opinion``.
    """
    t0 = time.time()
    stressors = list(stressors)
    disc = PanelDiscovery(df, y_col, stressors, alpha=alpha, n_boot=n_boot, effect_gate=effect_gate, seed=seed, n_ci=n_ci)
    out = disc.run(progress=progress, on_stage=on_stage)
    t_param = time.time() - t0

    gbm = nid = None
    t1 = time.time()
    if second_opinion:
        X = nuisance_frame(df, stressors)
        y = df[y_col].to_numpy(float)
        gbm = run_gbm_interactions(X, y, stressors, seed=seed, n_permutations=gbm_permutations,
                                   city_slices=disc.panel.city_slices)
        nid = run_neural_interactions(X, y, stressors, seed=seed)
    t_second = time.time() - t1
    if on_stage and second_opinion:
        on_stage("second_opinion", {"gbm_holdout_r2": gbm["holdout_r2"], "nid_holdout_r2": nid["holdout_r2"]})
    g_rank = {(d["a"], d["b"]): d["rank"] for d in (gbm["ranked_pairs"] if gbm else [])}
    n_rank = {(d["a"], d["b"]): d["rank"] for d in (nid["ranked_pairs"] if nid else [])}
    g_p = {(d["a"], d["b"]): d.get("p_perm") for d in (gbm["ranked_pairs"] if gbm else [])}
    accepted_keys = {r.pair for r in out["accepted"]}

    pairs: list[dict] = []
    for r in out["screen"]:
        key = r.pair
        rec = {
            "a": r.a, "b": r.b,
            "p_naive": r.joint.p_naive, "p_hac": r.joint.p_hac, "p_boot": r.joint.p_boot,
            "q_naive": r.q["p_naive"], "q_hac": r.q["p_hac"], "q_boot": r.q["p_boot"],
            "lambda_boot": r.joint.lambda_boot, "F": r.joint.F,
            "s1_raw": bool(r.joint.p_boot < alpha),
            "s2_bh": bool(r.q["p_boot"] < alpha),
            "s3_conditional": key in accepted_keys,
            "conditional_p": r.conditional_p,
            "gbm_rank": g_rank.get(key), "nid_rank": n_rank.get(key), "gbm_p_perm": g_p.get(key),
        }
        if key in accepted_keys:
            gbm_ok = bool(second_opinion and g_rank.get(key, 10 ** 6) <= topk)
            nid_ok = bool(second_opinion and n_rank.get(key, 10 ** 6) <= topk)
            effect_ok = bool(r.passes_effect and r.ci_clears_gate)
            rec.update({
                "type": r.type, "effect_size": r.effect_size, "b_AB_std": r.b_AB_std,
                "ci_low": r.ci_low, "ci_high": r.ci_high,
                "eff_ci_low": r.eff_ci_low, "eff_ci_high": r.eff_ci_high,
                "p_bilinear": r.bilinear.p_boot if r.bilinear else None,
                "p_nonlinear": r.nonlinear.p_boot if r.nonlinear else None,
                "s4_effect": effect_ok,
                "methods": {"parametric": True, "gbm": gbm_ok, "nid": nid_ok},
                "robustness": (1 + gbm_ok + nid_ok) / 3.0,
                "s5_second_opinion": bool(effect_ok and (gbm_ok or nid_ok)),
                "surface": r.surface,
            })
            rec["final"] = bool(rec["s5_second_opinion"])
        else:
            rec.update({"s4_effect": False, "s5_second_opinion": False, "final": False})
        pairs.append(rec)

    return {
        "pairs": pairs,
        "n_rows": out["n_rows"], "n_pairs": out["n_pairs"], "block_len": out["block_len"],
        "stage_counts": out["stage_counts"],
        "second_opinion": {
            "gbm_holdout_r2": gbm["holdout_r2"] if gbm else None,
            "nid_holdout_r2": nid["holdout_r2"] if nid else None,
            "topk": topk, "gbm_permutations": gbm_permutations,
        },
        "config": {"alpha": alpha, "effect_gate": effect_gate, "n_boot": n_boot, "n_ci": n_ci, "seed": seed},
        "runtime_s": {"parametric": t_param, "second_opinion": t_second, "total": time.time() - t0},
        "gbm": gbm, "nid": nid,
    }
