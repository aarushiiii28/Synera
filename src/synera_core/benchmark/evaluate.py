"""Engine Report Card: measure the discovery + validation + security stack on the semi-synthetic benchmark.

Everything written to ``artifacts/results/benchmark.json`` is *computed* here from simulation runs.
Nothing is rounded up, tuned afterwards or filled in by hand; quantities that were not measured are
simply absent (the API and UI show them as "not computed").

Sections
--------
``discovery``        stage-by-stage precision / recall / FDR per SNR (50 seeds each by default)
``null_calibration`` genomic-inflation lambda of naive / HAC / block-bootstrap p-values under the null
``moderation``       empirical-Bayes variance moderation on simulated 6/6/3/6 two-by-two omics designs
``security``         detector detection rates vs contamination, clean false-alarm rates, hash detection
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats

from synera_core.benchmark.generator import (
    STRESSORS, label_pairs, load_env_panel, simulate_benchmark, standardise_per_city,
)
from synera_core.config import find_repo_root
from synera_core.discovery.interactions import factorial_interaction
from synera_core.discovery.panel import PanelDiscovery
from synera_core.discovery.stack import run_full_stack
from synera_core.validation.multitest import bh_fdr

GATES = [0.0, 0.02, 0.05, 0.10, 0.20]
STAGES = ["marginal_naive", "marginal_hac", "marginal_boot", "conditional", "effect_gate", "full_stack"]


# --------------------------------------------------------------------------- #
# Discovery benchmark
# --------------------------------------------------------------------------- #
def _stage_sets(pairs: list[dict], alpha: float = 0.05) -> dict[str, set[tuple[str, str]]]:
    key = lambda r: (r["a"], r["b"])  # noqa: E731
    return {
        "marginal_naive": {key(r) for r in pairs if r["q_naive"] < alpha},
        "marginal_hac": {key(r) for r in pairs if r["q_hac"] < alpha},
        "marginal_boot": {key(r) for r in pairs if r["q_boot"] < alpha},
        "conditional": {key(r) for r in pairs if r["s3_conditional"]},
        "effect_gate": {key(r) for r in pairs if r["s4_effect"]},
        "full_stack": {key(r) for r in pairs if r["final"]},
    }


def _one_dataset(snr: float, seed: int, n_boot: int, n_ci: int, effect_gate: float, cache_dir: Path | None = None) -> dict:
    cache = None
    if cache_dir is not None:
        cache = Path(cache_dir) / f"d_snr{snr}_seed{seed}_b{n_boot}_c{n_ci}_g{effect_gate}.json"
        if cache.exists():
            return json.loads(cache.read_text())
    out = _one_dataset_uncached(snr, seed, n_boot, n_ci, effect_gate)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, default=float))
        tmp.replace(cache)
    return out


def _one_dataset_uncached(snr: float, seed: int, n_boot: int, n_ci: int, effect_gate: float) -> dict:
    env = standardise_per_city(load_env_panel())
    df, truth = simulate_benchmark(env, snr=snr, seed=seed)
    t0 = time.time()
    res = run_full_stack(df, "outcome", STRESSORS, n_boot=n_boot, n_ci=n_ci, seed=seed, effect_gate=effect_gate)
    labels = label_pairs(df, truth)
    true_type = {tuple(sorted((it["var1"], it["var2"]))): it["type"] for it in truth["interactions"]}
    by_pair = {(r["a"], r["b"]): r for r in res["pairs"]}
    stage_sets = _stage_sets(res["pairs"])
    rec_stage: dict[str, Any] = {}
    for st, s in stage_sets.items():
        counts = {"true": 0, "proxy": 0, "hard_decoy": 0, "easy_decoy": 0}
        for pr in s:
            counts[labels[pr]] += 1
        type_ok = sum(1 for pr in s if labels[pr] == "true" and by_pair[pr].get("type") == true_type[tuple(sorted(pr))])
        found_true = {tuple(sorted(pr)): by_pair[pr].get("type") for pr in s if labels[pr] == "true"}
        rec_stage[st] = {**counts, "n": len(s), "type_correct": type_ok,
                         "found_true": {f"{k[0]}|{k[1]}": v for k, v in found_true.items()}}
    # Effect-gate curve on conditionally-selected pairs (post hoc, same selected set)
    gate_curve = {}
    sel = [r for r in res["pairs"] if r["s3_conditional"]]
    for g in GATES:
        kept = [(r["a"], r["b"]) for r in sel if r["effect_size"] >= g]
        c = {"true": 0, "proxy": 0, "hard_decoy": 0, "easy_decoy": 0}
        for pr in kept:
            c[labels[pr]] += 1
        gate_curve[str(g)] = {**c, "n": len(kept)}
    return {"snr": snr, "seed": seed, "stages": rec_stage, "gate_curve": gate_curve,
            "n_true": len(true_type), "runtime_s": time.time() - t0,
            "block_len": res["block_len"], "stage_counts": res["stage_counts"],
            "second_opinion": res["second_opinion"],
            "lambda_boot_median": float(np.nanmedian([r["lambda_boot"] for r in res["pairs"]]))}


def _summarise_stage(recs: list[dict], stage: str, n_true_per: int = 3) -> dict:
    tp = sum(r["stages"][stage]["true"] for r in recs)
    prox = sum(r["stages"][stage]["proxy"] for r in recs)
    hard = sum(r["stages"][stage]["hard_decoy"] for r in recs)
    easy = sum(r["stages"][stage]["easy_decoy"] for r in recs)
    n = tp + prox + hard + easy
    fp_strict = prox + hard + easy
    fp_pa = hard + easy
    per_seed_fdr = [
        (r["stages"][stage]["proxy"] + r["stages"][stage]["hard_decoy"] + r["stages"][stage]["easy_decoy"]) / r["stages"][stage]["n"]
        for r in recs if r["stages"][stage]["n"] > 0
    ]
    zero = sum(1 for r in recs if r["stages"][stage]["n"] == 0)
    tc = sum(r["stages"][stage]["type_correct"] for r in recs)
    return {
        "discoveries": n, "true_positives": tp, "proxy": prox, "hard_decoy": hard, "easy_decoy": easy,
        "recall": tp / (n_true_per * len(recs)),
        "precision": (tp / n) if n else None,
        "fdr_strict": (fp_strict / n) if n else None,
        "fdr_proxy_aware": (fp_pa / (tp + fp_pa)) if (tp + fp_pa) else None,
        "fdr_strict_per_seed_mean": float(np.mean(per_seed_fdr)) if per_seed_fdr else None,
        "seeds_with_zero_discoveries": zero,
        "type_accuracy": (tc / tp) if tp else None,
    }


def evaluate_discovery(seeds: int = 50, snrs: tuple[float, ...] = (1.0, 5.0, 20.0), n_boot: int = 299,
                       n_ci: int = 100, effect_gate: float = 0.05, n_jobs: int = 6) -> dict:
    """Run the full stack on ``seeds`` simulated datasets per SNR level (resumable: finished datasets are cached)."""
    cache_dir = find_repo_root() / "artifacts" / "results" / "benchmark_cache"
    jobs = [(s, sd) for s in snrs for sd in range(seeds)]
    recs = Parallel(n_jobs=n_jobs, verbose=5, max_nbytes=None)(
        delayed(_one_dataset)(s, sd, n_boot, n_ci, effect_gate, cache_dir) for s, sd in jobs)
    out: dict[str, Any] = {"seeds": seeds, "snrs": list(snrs), "effect_gate": effect_gate, "n_boot": n_boot, "by_snr": {}}
    for s in snrs:
        rs = [r for r in recs if r["snr"] == s]
        out["by_snr"][str(s)] = {
            "stages": {st: _summarise_stage(rs, st) for st in STAGES},
            "gate_curve": {
                str(g): {
                    "recall": sum(r["gate_curve"][str(g)]["true"] for r in rs) / (3 * len(rs)),
                    "fdr_strict": (lambda n, tp: (n - tp) / n if n else None)(
                        sum(r["gate_curve"][str(g)]["n"] for r in rs), sum(r["gate_curve"][str(g)]["true"] for r in rs)),
                } for g in GATES},
            "recall_by_type": _recall_by_type(rs),
            "runtime_s_mean": float(np.mean([r["runtime_s"] for r in rs])),
            "block_len_median": float(np.median([r["block_len"] for r in rs])),
            "gbm_holdout_r2_mean": float(np.mean([r["second_opinion"]["gbm_holdout_r2"] for r in rs])),
            "nid_holdout_r2_mean": float(np.mean([r["second_opinion"]["nid_holdout_r2"] for r in rs])),
        }
    out["raw"] = recs
    return out


def _recall_by_type(rs: list[dict]) -> dict:
    kinds = {"SYNERGISTIC": "heat_index|pm25", "ANTAGONISTIC": "heat_index|rh", "NONLINEAR": "heat_index|o3"}
    out = {}
    for stage in ("conditional", "full_stack"):
        out[stage] = {}
        for kind, key in kinds.items():
            alt = "|".join(reversed(key.split("|")))
            found = sum(1 for r in rs if key in r["stages"][stage]["found_true"] or alt in r["stages"][stage]["found_true"])
            typed = sum(1 for r in rs if r["stages"][stage]["found_true"].get(key, r["stages"][stage]["found_true"].get(alt)) == kind)
            out[stage][kind] = {"detected": found / len(rs), "detected_and_typed_correctly": typed / len(rs)}
    return out


# --------------------------------------------------------------------------- #
# Null calibration
# --------------------------------------------------------------------------- #
def _null_sim(seed: int, pairs_per_sim: int, n_boot: int, rho: float) -> dict:
    env = standardise_per_city(load_env_panel())
    df, _ = simulate_benchmark(env, snr=2.0, rho=rho, seed=10_000 + seed, null=True)
    d = PanelDiscovery(df, "outcome", STRESSORS, n_boot=n_boot, seed=seed)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(d.pairs), pairs_per_sim, replace=False)
    ps = {"naive": [], "hac": [], "boot": []}
    for i in pick:
        j = d._test_pair(*d.pairs[i]).joint
        ps["naive"].append(j.p_naive)
        ps["hac"].append(j.p_hac)
        ps["boot"].append(j.p_boot)

    def lam(p):
        p = np.clip(np.asarray(p, float), 1e-300, 1.0)
        return float(np.median(stats.chi2.isf(p, 1)) / stats.chi2.ppf(0.5, 1))
    return {m: {"lambda": lam(v), "frac_p_lt_05": float(np.mean(np.asarray(v) < 0.05)), "p": [float(x) for x in v]}
            for m, v in ps.items()}


def evaluate_null_calibration(n_sims: int = 100, pairs_per_sim: int = 15, n_boot: int = 299,
                              rho: float = 0.5, n_jobs: int = 10) -> dict:
    sims = Parallel(n_jobs=n_jobs, verbose=5)(delayed(_null_sim)(s, pairs_per_sim, n_boot, rho) for s in range(n_sims))
    out: dict[str, Any] = {"n_simulations": n_sims, "pairs_per_simulation": pairs_per_sim, "rho": rho,
                           "note": "lambda = median(chi2_1 quantile of p) / 0.4549; 1.0 is perfectly calibrated"}
    for m in ("naive", "hac", "boot"):
        lams = np.array([s[m]["lambda"] for s in sims])
        fr = np.array([s[m]["frac_p_lt_05"] for s in sims])
        pooled = np.concatenate([s[m]["p"] for s in sims])
        out[m] = {"lambda_median": float(np.median(lams)), "lambda_range": [float(lams.min()), float(lams.max())],
                  "frac_p_lt_05_median": float(np.median(fr)), "frac_p_lt_05_pooled": float(np.mean(pooled < 0.05)),
                  "p_histogram_10bins": np.histogram(pooled, bins=10, range=(0, 1))[0].tolist()}
    return out


# --------------------------------------------------------------------------- #
# Variance moderation sweep (6/6/3/6 two-by-two omics design)
# --------------------------------------------------------------------------- #
def _moderation_sim(seed: int, effect_sd: float, n_genes: int = 5000, frac: float = 0.10, d0: float = 4.0) -> dict:
    rng = np.random.default_rng(seed)
    cells = [(0, 0, 6), (1, 0, 6), (0, 1, 3), (1, 1, 6)]
    A = np.concatenate([[a] * n for a, b, n in cells]).astype(float)
    B = np.concatenate([[b] * n for a, b, n in cells]).astype(float)
    sigma2 = d0 / rng.chisquare(d0, n_genes)          # scaled inverse chi-square, prior variance 1
    sigma = np.sqrt(sigma2)
    planted = rng.random(n_genes) < frac
    sign = rng.choice([-1.0, 1.0], n_genes)
    Y = rng.normal(0, 1, (len(A), n_genes)) * sigma
    Y += np.outer(A * B, planted * sign * effect_sd * sigma)
    meta = pd.DataFrame({"a": A, "b": B})
    out = {}
    for name, mod in (("none", False), ("fixed_df4", True), ("estimated", "estimate")):
        res = factorial_interaction(pd.DataFrame(Y), meta, "a", "b", moderate=mod)
        p = res["p_AB"].to_numpy()
        q = bh_fdr(p)
        hit = q < 0.05
        tp = int((hit & planted).sum())
        out[name] = {"power": tp / max(int(planted.sum()), 1), "fdr": (int(hit.sum()) - tp) / max(int(hit.sum()), 1),
                     "discoveries": int(hit.sum()), "prior_df": res.attrs.get("prior_df", 0.0)}
    return out


def evaluate_moderation(n_sims: int = 200, effects: tuple[float, ...] = (2, 3, 4, 5, 6), n_jobs: int = 10) -> dict:
    out: dict[str, Any] = {"design": "6/6/3/6", "n_simulations": n_sims, "n_genes": 5000, "planted_fraction": 0.10,
                           "variance_model": "scaled inverse chi-square, prior df 4", "by_effect_sd": {}}
    for e in effects:
        sims = Parallel(n_jobs=n_jobs)(delayed(_moderation_sim)(s, float(e)) for s in range(n_sims))
        row = {}
        for m in ("none", "fixed_df4", "estimated"):
            pw = np.array([s[m]["power"] for s in sims])
            fd = np.array([s[m]["fdr"] for s in sims])
            ci = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]  # noqa: E731
            row[m] = {"power_mean": float(pw.mean()), "power_ci95": ci(pw), "fdr_mean": float(fd.mean()), "fdr_ci95": ci(fd),
                      "estimated_prior_df_mean": float(np.mean([s[m]["prior_df"] for s in sims]))}
        out["by_effect_sd"][str(e)] = row
    return out


# --------------------------------------------------------------------------- #
# Security sweep
# --------------------------------------------------------------------------- #
ATTACKS = ["subtle_edit", "row_edit", "inject_outliers", "drift_units", "poison_labels"]
LEVELS = [0.01, 0.05, 0.10, 0.20]
DETECTORS = ["physical_range", "duplicates", "isolation_forest", "mcd", "autoencoder", "distribution_drift", "label_flip"]


def _raw_panel() -> pd.DataFrame:
    df = load_env_panel()
    cols = ["tmax", "tmean", "rh", "heat_index", "precip", "drought_index", "pm25", "pm10", "o3", "no2", "uv", "wind"]
    out = df[["city", "date", *cols]].reset_index(drop=True)
    out[cols] = out[cols].astype(float)
    return out


def _block_resample(df: pd.DataFrame, rng: np.random.Generator, block: int = 14) -> pd.DataFrame:
    """Clean replicate: permute non-overlapping 14-day blocks within each city (same marginal and
    short-range dependence structure, no duplicated rows), keeping the original date column."""
    parts = []
    for _, g in df.groupby("city", sort=False):
        n = len(g)
        nb = int(np.ceil(n / block))
        order = rng.permutation(nb)
        idx = np.concatenate([np.arange(b * block, min((b + 1) * block, n)) for b in order])
        parts.append(g.iloc[idx].assign(date=g["date"].to_numpy()))
    return pd.concat(parts).reset_index(drop=True)

def _split_panel(seed: int, block: int = 14) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Disjoint train/test halves of the real panel: within each city, 14-day blocks are dealt at random to
    the half that fits the detectors' baseline or to the half they are tested on. Row order and dates are kept,
    so each half is a real, time-ordered sample. Testing on rows the baseline was fitted on would make the
    false-alarm rate zero by construction (the cutoffs are that baseline's own 99th percentiles)."""
    df = _raw_panel()
    rng = np.random.default_rng(seed)
    tr, te = [], []
    for _, g in df.groupby("city", sort=False):
        n = len(g)
        nb = int(np.ceil(n / block))
        to_train = rng.permutation(nb) < nb // 2
        mask = np.repeat(to_train, block)[:n]
        tr.append(g[mask])
        te.append(g[~mask])
    return pd.concat(tr).reset_index(drop=True), pd.concat(te).reset_index(drop=True)


def _hot_day(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"hot_day": (df["heat_index"] > df["heat_index"].median()).astype(int).to_numpy()})


def _apply_attack(df: pd.DataFrame, mode: str, frac: float, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    out = df.copy()
    num = [c for c in out.columns if c not in ("city", "date")]
    n = len(out)
    k = max(1, int(round(frac * n)))
    rows = rng.choice(n, k, replace=False)
    meta = None
    sd = out[num].std()
    if mode == "subtle_edit":          # shift one column by +0.3 SD, staying inside physical ranges
        for r in rows:
            c = num[rng.integers(0, len(num))]
            out.loc[r, c] = out.loc[r, c] + 0.3 * sd[c]
    elif mode == "row_edit":           # multiply one cell by 10 (a fat-finger / decimal-shift edit)
        for r in rows:
            c = num[rng.integers(0, len(num))]
            out.loc[r, c] = out.loc[r, c] * 10.0
    elif mode == "inject_outliers":    # push 4 columns of each affected row to +/-4 robust SD (not clipped to physical limits)
        med = out[num].median()
        for r in rows:
            for c in rng.choice(num, 4, replace=False):
                out.loc[r, c] = med[c] + rng.choice([-1, 1]) * 4.0 * sd[c]
    elif mode == "drift_units":        # Celsius -> Fahrenheit on tmax for the contaminated rows
        out.loc[rows, "tmax"] = out.loc[rows, "tmax"] * 1.8 + 32.0
    elif mode == "poison_labels":      # flip a binary factor label that normally tracks heat
        lab = (df["heat_index"] > df["heat_index"].median()).astype(int).to_numpy().copy()
        lab[rows] = 1 - lab[rows]
        meta = pd.DataFrame({"hot_day": lab})
    return out, meta


def _security_trial(mode: str, frac: float, seed: int, base_blob: bytes) -> dict:
    import pickle

    from synera_core.provenance.hashing import sha256_dataframe
    from synera_core.security.poisoning import scan_dataset

    baseline = pickle.loads(base_blob)
    rng = np.random.default_rng(seed)
    clean = _block_resample(_split_panel(0)[1], rng)   # held-out half: the baseline never saw these rows
    attacked, meta_a = _apply_attack(clean, mode, frac, rng)
    clean_meta = _hot_day(clean)
    meta = meta_a if meta_a is not None else clean_meta
    rep = scan_dataset(attacked, meta=meta, baseline=baseline)
    fired = {c["name"]: (c["status"] != "PASS") for c in rep.checks}
    h_changed = sha256_dataframe(clean) != sha256_dataframe(attacked) or (meta_a is not None)
    if meta_a is not None:   # the label column is part of the dataset: a flipped label changes its hash
        h_changed = sha256_dataframe(clean_meta) != sha256_dataframe(meta_a)
    return {"mode": mode, "frac": frac, "hash": bool(h_changed), "fired": fired, "status": rep.status}


def _clean_trial(seed: int) -> dict:
    from synera_core.security.poisoning import Baseline, scan_dataset

    train, test = _split_panel(900_000 + seed)
    baseline = Baseline.from_frame(train.drop(columns=["city", "date"]), seed=0, meta=_hot_day(train))
    rep = scan_dataset(test, meta=_hot_day(test), baseline=baseline)
    return {"fired": {c["name"]: (c["status"] != "PASS") for c in rep.checks}, "status": rep.status}

def evaluate_security(trials: int = 30, clean_seeds: int = 100, n_jobs: int = 10) -> dict:
    import pickle

    from synera_core.security.poisoning import Baseline

    train0, _ = _split_panel(0)
    baseline = Baseline.from_frame(train0.drop(columns=["city", "date"]), seed=0, meta=_hot_day(train0))
    blob = pickle.dumps(baseline)
    jobs = [(m, f, 1000 * i + t) for i, m in enumerate(ATTACKS) for f in LEVELS for t in range(trials)]
    res = Parallel(n_jobs=n_jobs, verbose=5)(delayed(_security_trial)(m, f, s, blob) for m, f, s in jobs)
    clean = Parallel(n_jobs=n_jobs)(delayed(_clean_trial)(s) for s in range(clean_seeds))

    out: dict[str, Any] = {
        "trials_per_cell": trials, "clean_seeds": clean_seeds, "baseline": baseline.summary(),
        "contamination_levels": LEVELS, "attacks": {}, "clean_false_alarm_rate": {}, "clean_false_alarm_counts": {}, "clean_false_alarm_ci95": {}, "hash_only_attacks": [],
        "design_notes": [
            "Each detector baseline is fitted on one half of the real panel and tested on the other half (14-day blocks dealt at random within each city), so no clean row was ever seen by the baseline. Every clean trial draws a fresh split and refits.",
            "inject_outliers pushes 4 columns of each contaminated row to +/-4 robust SD; subtle_edit shifts one cell by +0.3 SD.",
            "poison_labels flips a binary 'hot_day' label that tracks heat_index; the label-flip detector is only informative where labels have structure.",
        ],
    }
    from scipy.stats import beta

    def _record(name: str, flags: list) -> None:
        k, n = int(np.sum(flags)), len(flags)
        out["clean_false_alarm_rate"][name] = k / n
        out["clean_false_alarm_counts"][name] = [k, n]
        lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))     # Clopper-Pearson 95% interval
        hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
        out["clean_false_alarm_ci95"][name] = [lo, hi]

    for d in DETECTORS:
        flags = [c["fired"].get(d) for c in clean if d in c["fired"]]
        if flags:
            _record(d, flags)
    _record("any_detector_warns", [c["status"] != "CLEAN" for c in clean])
    for m in ATTACKS:
        out["attacks"][m] = {}
        for f in LEVELS:
            rs = [r for r in res if r["mode"] == m and r["frac"] == f]
            cell = {"hash": float(np.mean([r["hash"] for r in rs]))}
            for d in DETECTORS:
                v = [r["fired"][d] for r in rs if d in r["fired"]]
                if v:
                    cell[d] = float(np.mean(v))
            cell["any_statistical"] = float(np.mean([any(r["fired"].get(d, False) for d in DETECTORS) for r in rs]))
            out["attacks"][m][str(f)] = cell
            stat_max = max([cell[d] for d in DETECTORS if d in cell] or [0.0])
            if cell["hash"] >= 0.99 and stat_max < 0.5:
                out["hash_only_attacks"].append({"mode": m, "contamination": f, "best_statistical_detection": stat_max})
    return out


# --------------------------------------------------------------------------- #
# Assemble and write
# --------------------------------------------------------------------------- #
def _limitations(report: dict) -> list[str]:
    lim = ["Semi-synthetic benchmark: real covariates, simulated outcome with planted interactions. It measures the engine, not nature."]
    disc = report.get("discovery")
    if disc:
        fdrs = [(s, v["stages"]["full_stack"]["fdr_strict"]) for s, v in disc["by_snr"].items()]
        fdrs = [(s, f) for s, f in fdrs if f is not None]
        if fdrs:
            tgt = 0.05
            over = [(s, f) for s, f in fdrs if f > tgt]
            allv = ", ".join(f"SNR {s}: {f:.1%}" for s, f in fdrs)
            if over:
                lim.append(f"Full-stack strict FDR exceeds the nominal 5% target at {', '.join(f'SNR {s} ({f:.1%})' for s, f in over)}; all levels: {allv}. "
                           "Correlated stressors that stand in for a planted partner count as false discoveries here.")
            else:
                lim.append(f"Full-stack strict FDR measured at {allv} (target 5%).")
        marg = [(s, v["stages"]["marginal_boot"]["fdr_strict"]) for s, v in disc["by_snr"].items()]
        marg = [(s, f) for s, f in marg if f is not None]
        if marg:
            lim.append("The marginal pairwise screen alone is far from FDR control (" + ", ".join(f"SNR {s}: {f:.1%}" for s, f in marg)
                       + "): omitted planted interactions leak into correlated pairs. Conditional selection is what removes them.")
    nc = report.get("null_calibration")
    if nc:
        lim.append(f"Null calibration over {nc['n_simulations']} simulations: median lambda naive {nc['naive']['lambda_median']:.2f}, "
                   f"HAC {nc['hac']['lambda_median']:.2f}, block bootstrap {nc['boot']['lambda_median']:.2f} (1.0 = calibrated).")
    sec = report.get("security")
    if sec and sec["hash_only_attacks"]:
        lim.append(f"{len(sec['hash_only_attacks'])} attack/contamination cells are caught by the cryptographic hash but by no statistical detector.")
    lim.append("Space-biology Track A has n=6/6/3/6; the minimum detectable interaction is large and no gene-level interaction passes FDR.")
    return lim


def run_benchmark(seeds: int = 50, snrs: tuple[float, ...] = (1.0, 5.0, 20.0), null_sims: int = 100,
                  mod_sims: int = 200, sec_trials: int = 30, n_boot: int = 299, n_jobs: int = 10,
                  out_dir: Path | None = None, sections: tuple[str, ...] = ("discovery", "null", "moderation", "security")) -> dict:
    out_dir = out_dir or (find_repo_root() / "artifacts" / "results")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "benchmark.json"
    # Partial re-runs keep the sections measured earlier by this module; any other key (e.g. from an older
    # generator) is dropped so that nothing unmeasured can ever be served.
    report: dict[str, Any] = {}
    if path.exists():
        old = json.loads(path.read_text())
        report = {k: old[k] for k in ("discovery", "null_calibration", "moderation", "security", "runtime_s") if k in old}
    report["provenance"] = "SIMULATED"
    report["generated_by"] = "synera_core.benchmark.evaluate.run_benchmark"
    t0 = time.time()
    if "discovery" in sections:
        d = evaluate_discovery(seeds=seeds, snrs=snrs, n_boot=n_boot, n_jobs=n_jobs)
        (out_dir / "benchmark_raw.json").write_text(json.dumps(d.pop("raw")))
        report["discovery"] = d
    if "null" in sections:
        report["null_calibration"] = evaluate_null_calibration(n_sims=null_sims, n_boot=n_boot, n_jobs=n_jobs)
    if "moderation" in sections:
        report["moderation"] = evaluate_moderation(n_sims=mod_sims, n_jobs=n_jobs)
    if "security" in sections:
        report["security"] = evaluate_security(trials=sec_trials, n_jobs=n_jobs)
    report["limitations"] = _limitations(report)
    report["runtime_s"] = report.get("runtime_s", 0) + time.time() - t0
    path.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--null-sims", type=int, default=100)
    ap.add_argument("--mod-sims", type=int, default=200)
    ap.add_argument("--sec-trials", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--sections", default="discovery,null,moderation,security")
    a = ap.parse_args()
    run_benchmark(seeds=a.seeds, null_sims=a.null_sims, mod_sims=a.mod_sims, sec_trials=a.sec_trials,
                  n_jobs=a.jobs, sections=tuple(a.sections.split(",")))
