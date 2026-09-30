"""Synthetic benchmark generator with planted multi-stressor interactions.

Generates ground-truth simulated outcomes on real or synthetic covariates to
rigorously evaluate discovery precision, recall, and FDR control.

NOTE: All generated data carries provenance=SIMULATED.
"""

from __future__ import annotations

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd


def generate_benchmark_dataset(
    n_samples: int = 200,
    n_stressors: int = 5,
    seed: int = 20260929,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Generate simulated dataset with planted ground-truth synergy and antagonism.

    Args:
        n_samples: Number of observations.
        n_stressors: Number of stressor covariate columns.
        seed: Random seed for deterministic generation.

    Returns:
        Tuple of (DataFrame with simulated provenance metadata, ground_truth_dict).
    """
    rng = np.random.default_rng(seed)
    stressor_cols = [f"stressor_{i+1}" for i in range(n_stressors)]
    x = rng.normal(0.0, 1.0, size=(n_samples, n_stressors))
    df = pd.DataFrame(x, columns=stressor_cols)

    # Plant synergy between stressor_1 and stressor_2
    # Combined > additive
    synergy_term = 1.2 * (df["stressor_1"] * df["stressor_2"])
    # Plant antagonism between stressor_3 and stressor_4
    # Combined < additive
    antagonism_term = -1.0 * (df["stressor_3"] * df["stressor_4"])
    noise = rng.normal(0.0, 0.2, size=n_samples)

    df["outcome"] = (
        0.8 * df["stressor_1"]
        + 0.5 * df["stressor_2"]
        + synergy_term
        + antagonism_term
        + noise
    )
    df["provenance"] = "SIMULATED"

    ground_truth = {
        "planted_synergies": [("stressor_1", "stressor_2")],
        "planted_antagonisms": [("stressor_3", "stressor_4")],
        "provenance": "SIMULATED",
    }
    return df, ground_truth
