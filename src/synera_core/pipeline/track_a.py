"""Track A (REAL NASA OSDR data): gene-level Radiation x Hindlimb-Unloading analysis.

Discovery study OSD-211 (spleen), replication study OSD-237 (skin). The two studies share 20 of 21 animals,
so the pair is a *cross-tissue, same-cohort* consistency check (``CROSS_TISSUE_SAME_COHORT``) and never an
independent replication. Used by both ``scripts/build_space_biology.py`` and the pipeline orchestrator, so the
numbers in the UI come from one code path.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from synera_core.config import find_repo_root, get_settings
from synera_core.discovery.interactions import estimate_prior, factorial_interaction
from synera_core.validation.multitest import bh_fdr

EVIDENCE_LEVEL = "CROSS_TISSUE_SAME_COHORT"
PRIOR_MODES = (("fixed_prior_df4", True), ("estimated_prior", "estimate"), ("no_moderation", False))


def processed_dir() -> Path:
    return find_repo_root() / "data" / "processed"


def load_study(study: str, root: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(expr genes x samples, meta)``; asserts the sample order is identical."""
    root = root or processed_dir()
    expr = pd.read_parquet(root / f"osdr_{study}_expr.parquet")
    meta = pd.read_parquet(root / f"osdr_{study}_meta.parquet")
    if list(expr.columns) != list(meta["sample_id"]):
        raise ValueError(f"{study}: expression columns and metadata rows are not aligned")
    return expr, meta


def cell_counts(m: pd.DataFrame) -> dict:
    return {"control": int(((m.radiation == 0) & (m.microgravity == 0)).sum()),
            "radiation": int(((m.radiation == 1) & (m.microgravity == 0)).sum()),
            "unloading": int(((m.radiation == 0) & (m.microgravity == 1)).sum()),
            "both": int(((m.radiation == 1) & (m.microgravity == 1)).sum())}


def interaction_table(expr: pd.DataFrame, meta: pd.DataFrame, alpha: float | None = None) -> pd.DataFrame:
    """Per-gene factorial interaction with data-estimated moderation and BH q-values."""
    alpha = alpha if alpha is not None else get_settings().alpha
    res = factorial_interaction(expr.T, meta, "radiation", "microgravity", moderate="estimate")
    res["q_AB"] = bh_fdr(res["p_AB"].to_numpy())
    res["type"] = np.where(res["q_AB"] < alpha, np.where(res["b_AB"] > 0, "SYNERGISTIC", "ANTAGONISTIC"), "none")
    return res


def additive_main_effects(Y: pd.DataFrame, meta: pd.DataFrame, moderate, alpha: float | None = None) -> dict:
    """Overall radiation / unloading effects from y ~ rad + hlu (all samples); genes with BH q < alpha."""
    alpha = alpha if alpha is not None else get_settings().alpha
    X = np.column_stack([np.ones(len(meta)), meta["radiation"].to_numpy(float), meta["microgravity"].to_numpy(float)])
    n, p = X.shape
    df = n - p
    inv = np.linalg.inv(X.T @ X)
    Yv = Y.to_numpy(float)
    beta = inv @ X.T @ Yv
    s2 = ((Yv - X @ beta) ** 2).sum(0) / df
    if moderate == "estimate":
        d0, s0 = estimate_prior(s2, df)
        s2t, d = (np.full_like(s2, s0), np.inf) if np.isinf(d0) else ((d0 * s0 + df * s2) / (d0 + df), df + d0)
    elif moderate:
        s0 = np.nanmedian(s2)
        s2t, d = (4 * s0 + df * s2) / (4 + df), df + 4
    else:
        s2t, d = s2, df
    out = {}
    for j, name in ((1, "radiation"), (2, "hindlimb_unloading")):
        t = beta[j] / np.sqrt(inv[j, j] * s2t)
        pv = 2 * (stats.norm.sf(np.abs(t)) if np.isinf(d) else stats.t.sf(np.abs(t), d))
        out[name] = int((bh_fdr(pv) < alpha).sum())
    return out


def permutation_null(expr: pd.DataFrame, meta: pd.DataFrame, n_perm: int = 200, seed: int | None = None) -> dict:
    """Permute the (radiation, unloading) labels across samples and re-run the interaction test."""
    s = get_settings()
    rng = np.random.default_rng(s.seeds.global_seed if seed is None else seed)
    lam, hits, frac05, pooled = [], [], [], []
    for _ in range(n_perm):
        m = meta.copy()
        idx = rng.permutation(len(m))
        m["radiation"] = m["radiation"].to_numpy()[idx]
        m["microgravity"] = m["microgravity"].to_numpy()[idx]
        r = factorial_interaction(expr.T, m, "radiation", "microgravity", moderate="estimate")
        p = r["p_AB"].dropna().to_numpy()
        lam.append(float(np.median(stats.chi2.isf(np.clip(p, 1e-300, 1), 1)) / stats.chi2.ppf(0.5, 1)))
        hits.append(int((bh_fdr(p) < s.alpha).sum()))
        frac05.append(float((p < 0.05).mean()))
        pooled.append(np.histogram(p, bins=10, range=(0, 1))[0])
    return {
        "n_permutations": n_perm, "scheme": "labels permuted across samples (cell sizes preserved)",
        "frac_p_lt_05_median": float(np.median(frac05)), "frac_p_lt_05_range": [float(min(frac05)), float(max(frac05))],
        "lambda_median": float(np.median(lam)), "lambda_range": [float(min(lam)), float(max(lam))],
        "mean_hits_q05_per_permutation": float(np.mean(hits)),
        "frac_permutations_with_a_hit": float(np.mean(np.array(hits) > 0)),
        "pooled_p_histogram_10bins": [int(x) for x in np.sum(pooled, axis=0)],
    }


def spike_in_power(expr: pd.DataFrame, meta: pd.DataFrame, sizes=(0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0),
                   n_spike: int = 200, reps: int = 5, seed: int | None = None) -> dict:
    """SIMULATED: add a known interaction to the (rad=1, hlu=1) cell of random real genes; measure recovery at q<alpha."""
    s = get_settings()
    rng = np.random.default_rng((s.seeds.global_seed if seed is None else seed) + 1)
    both = ((meta["radiation"] == 1) & (meta["microgravity"] == 1)).to_numpy()
    rows = {}
    for size in sizes:
        rec = []
        for _ in range(reps):
            genes = rng.choice(expr.shape[0], n_spike, replace=False)
            vals = expr.to_numpy().copy()
            sign = rng.choice([-1.0, 1.0], n_spike)
            for g, sg in zip(genes, sign):
                vals[g, both] += sg * size
            r = factorial_interaction(pd.DataFrame(vals, index=expr.index, columns=expr.columns).T, meta,
                                      "radiation", "microgravity", moderate="estimate")
            q = bh_fdr(r["p_AB"].to_numpy())
            rec.append(float((q[genes] < s.alpha).mean()))
        rows[str(size)] = {"power_mean": float(np.mean(rec)), "power_range": [float(min(rec)), float(max(rec))]}
    mde = next((float(x) for x in sizes if rows[str(x)]["power_mean"] >= 0.8), None)
    return {"provenance": "SIMULATED", "note": "spike-in on a copy of the real matrix; originals untouched",
            "n_spiked_genes": n_spike, "replicates": reps, "by_log2_effect": rows,
            "minimum_detectable_log2_80pct_power": mde,
            "minimum_detectable_note": None if mde is not None else f"80% power not reached up to {max(sizes)} log2"}


def cross_tissue_consistency(res_d: pd.DataFrame, res_r: pd.DataFrame, meta_d: pd.DataFrame, meta_r: pd.DataFrame,
                             alpha: float | None = None) -> dict:
    """Agreement of the discovery ranking with the replication tissue. Not independent replication."""
    alpha = alpha if alpha is not None else get_settings().alpha
    shared = res_d.index.intersection(res_r.index)
    j = res_d.loc[shared].join(res_r.loc[shared], lsuffix="_d", rsuffix="_r")
    top = j.sort_values("p_AB_d").head(100)
    conc = float((np.sign(top["b_AB_d"]) == np.sign(top["b_AB_r"])).mean())
    rho, rho_p = stats.spearmanr(j["b_AB_d"], j["b_AB_r"])
    a1, a2 = set(meta_d.animal_id.dropna()), set(meta_r.animal_id.dropna())
    return {
        "evidence_level": EVIDENCE_LEVEL,
        "caveat": "Same animals contributed both tissues; this is a consistency check, not independent replication.",
        "animals_discovery": len(a1), "animals_replication": len(a2), "animals_shared": len(a1 & a2),
        "genes_shared_after_filter": int(len(shared)),
        "fdr_hits_discovery": int((res_d.q_AB < alpha).sum()), "fdr_hits_replication": int((res_r.q_AB < alpha).sum()),
        "exploratory_top100_sign_concordance": conc,
        "exploratory_top100_binomial_p_vs_half": float(stats.binomtest(int(round(conc * 100)), 100, 0.5).pvalue),
        "interaction_effect_spearman_rho_all_shared_genes": float(rho), "spearman_p": float(rho_p),
        "interpretation": "No gene passes FDR in either tissue, so no gene is replicated. The numbers describe agreement of the "
                          "exploratory ranking between tissues only." if (res_d.q_AB < alpha).sum() == 0 else
                          "Genes passing FDR in the discovery tissue are listed in the gene table with their replication-tissue effect.",
    }


def pc1_drivers(expr: pd.DataFrame, meta: pd.DataFrame, symbols: pd.DataFrame) -> dict:
    X = expr.T.to_numpy(float)
    u, s, vt = np.linalg.svd(X - X.mean(0), full_matrices=False)
    pc1 = u[:, 0] * s[0]
    load = pd.Series(vt[0], index=expr.index)
    top = load.abs().sort_values(ascending=False).head(10).index
    sym = symbols["symbol"] if "symbol" in symbols else pd.Series(dtype=str)
    krt = [g for g in expr.index if str(sym.get(g, "")).startswith(("Krt", "Lor", "Flg"))]
    return {"pc1_variance_explained": float(s[0] ** 2 / (s ** 2).sum()),
            "pc1_vs_radiation_p": float(stats.mannwhitneyu(pc1[meta.radiation == 1], pc1[meta.radiation == 0]).pvalue),
            "pc1_vs_unloading_p": float(stats.mannwhitneyu(pc1[meta.microgravity == 1], pc1[meta.microgravity == 0]).pvalue),
            "top_pc1_loading_genes": [str(sym.get(g, g)) for g in top],
            "keratin_marker_genes": len(krt),
            "pc1_spearman_with_mean_keratin_expression": float(stats.spearmanr(pc1, expr.loc[krt].mean(0))[0]) if len(krt) > 3 else None}
