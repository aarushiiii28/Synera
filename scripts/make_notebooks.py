"""Generate notebooks/00-08 (thin: every computation lives in synera_core) and optionally execute them headless.

    python scripts/make_notebooks.py            # write notebooks
    python scripts/make_notebooks.py --execute  # write + execute in place (kernel "synera" or python3)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

SETUP = '''import json, warnings
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from pathlib import Path
from synera_core.config import find_repo_root, get_settings
warnings.filterwarnings("ignore")
ROOT = find_repo_root()
C = dict(bg="#061424", panel="#0b2037", cyan="#16B5FF", green="#6FD65B", amber="#FFB547", red="#FF4D5E", teal="#19E3B1", text="#EAF2FB", muted="#8FA6BF")
plt.rcParams.update({"figure.facecolor": C["bg"], "axes.facecolor": C["bg"], "axes.edgecolor": C["muted"], "axes.labelcolor": C["text"],
    "text.color": C["text"], "xtick.color": C["muted"], "ytick.color": C["muted"], "grid.color": "#1c3a5c", "axes.grid": True, "grid.linewidth": 0.5,
    "axes.prop_cycle": plt.cycler(color=[C["cyan"], C["green"], C["amber"], C["red"], C["teal"]]), "figure.dpi": 110, "font.size": 9})
SEED = get_settings().seeds.global_seed
RES = ROOT / "artifacts" / "results"
'''


def md(s): return nbf.v4.new_markdown_cell(s.strip())
def code(s): return nbf.v4.new_code_cell(s.strip("\n"))


NOTEBOOKS: dict[str, list] = {}

NOTEBOOKS["00_environment_check"] = [
    md("# 00 · Environment check\nImports every core dependency, prints versions, seeds the RNG from `configs/settings.yaml` and confirms `synera_core` is importable."),
    code(SETUP),
    code('''import importlib, platform, sys
print("python", sys.version.split()[0], platform.platform())
for m in ["numpy","pandas","scipy","statsmodels","sklearn","lightgbm","shap","torch","fastapi","sqlmodel","cryptography","pyarrow"]:
    mod = importlib.import_module(m); print(f"{m:14s}", getattr(mod, "__version__", "ok"))
import synera_core; print("synera_core ->", synera_core.__file__)
rng = np.random.default_rng(SEED); print("seeded from settings:", SEED, "first draw:", round(float(rng.normal()), 6))'''),
]

NOTEBOOKS["01_data_acquisition"] = [
    md("# 01 · Data acquisition and provenance\nEvery dataset is registered by its SHA-256 in the signed ledger the moment it enters. Raw HTTP responses are cached under `data/raw/cache`, so a second run is fully offline."),
    code(SETUP),
    code('''from synera_core.pipeline.registry import get_registry, summarize
from synera_core.provenance.store import open_ledger
ledger = open_ledger()
rows = []
for s in get_registry().values():
    sm = summarize(s)
    hit = ledger.find_by_artifact(sm["sha256"]) if sm.get("available") else []
    rows.append({"id": s.id, "track": s.track, "provenance": s.provenance, "kind": s.kind, "sha256": (sm.get("sha256") or "")[:16],
                 "ledger_block": hit[0][0].index if hit else None, "rows/samples": sm.get("rows", sm.get("samples"))})
pd.DataFrame(rows)'''),
    code('''cache = list((ROOT / "data" / "raw" / "cache").glob("*.raw"))
print(f"{len(cache)} cached raw API responses ({sum(p.stat().st_size for p in cache)/1e6:.1f} MB): re-running is offline")
v = ledger.verify(); print("ledger:", v["height"], "blocks, valid:", v["valid"])
pd.DataFrame([{"index": b.index, "type": b.block_type, "time": b.timestamp[:19], "artifacts": len(b.payload.get("artifact_hashes", []))}
              for b in ledger.iter_blocks()]).tail(8)'''),
    md("The environmental panel combines Open-Meteo weather and air-quality archives for eight cities. Missing values are never filled; rows with missing stressors are dropped explicitly at analysis time."),
    code('''env = pd.read_parquet(ROOT / "data/processed/env_panel.parquet")
display(env.groupby("city").agg(days=("date","count"), start=("date","min"), end=("date","max")))
print("missing share per column:"); display((env[["pm25","pm10","o3","no2","uv"]].isna().mean()*100).round(2).rename("% missing"))'''),
]

NOTEBOOKS["02_eda_and_qc"] = [
    md("# 02 · Exploratory analysis and QC\n**Track A**: sample sizes per cell of the 2×2, PCA coloured by group, animal structure. **Environmental panel**: correlations, missingness, seasonality."),
    code(SETUP),
    code('''from synera_core.pipeline import track_a as TA
e1, m1 = TA.load_study("OSD-211"); e2, m2 = TA.load_study("OSD-237")
display(pd.DataFrame([TA.cell_counts(m1), TA.cell_counts(m2)], index=["OSD-211 spleen", "OSD-237 skin"]))
print("shared animals:", len(set(m1.animal_id) & set(m2.animal_id)), "of", len(set(m1.animal_id)), "- the two studies are NOT independent")'''),
    code('''fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, (nm, e, m) in zip(axes, [("OSD-211 spleen", e1, m1), ("OSD-237 skin", e2, m2)]):
    X = e.T.to_numpy(float); X = X - X.mean(0); u, s, _ = np.linalg.svd(X, full_matrices=False); pc = u * s
    grp = m.radiation.astype(str) + m.microgravity.astype(str)
    for g, col, lab in [("00", C["muted"], "control"), ("10", C["amber"], "radiation"), ("01", C["cyan"], "unloading"), ("11", C["green"], "both")]:
        k = (grp == g).to_numpy(); ax.scatter(pc[k, 0], pc[k, 1], c=col, label=lab, s=36)
    ax.set_title(f"{nm}: PC1 {s[0]**2/(s**2).sum():.0%}, PC2 {s[1]**2/(s**2).sum():.0%}"); ax.set_xlabel("PC1"); ax.set_ylabel("PC2"); ax.legend(fontsize=7)
plt.tight_layout(); plt.show()'''),
    md("Samples do not separate cleanly by group on the leading axes, which is what a weak, noisy interaction signal looks like. The notebook does **not** read anything into the PCs beyond what is tested in `scripts/build_space_biology.py`."),
    code('''env = pd.read_parquet(ROOT / "data/processed/env_panel.parquet")
cols = ["heat_index","pm25","pm10","o3","no2","rh","drought_index","uv","wind","precip"]
cor = env[cols].corr()
fig, ax = plt.subplots(figsize=(6.4, 5)); im = ax.imshow(cor, cmap="RdBu_r", vmin=-1, vmax=1); ax.set_xticks(range(len(cols)), cols, rotation=60, ha="right"); ax.set_yticks(range(len(cols)), cols)
ax.grid(False); plt.colorbar(im); ax.set_title("Stressor correlations (raw units)"); plt.show()
print("Strongly correlated stressors (|r| >= 0.6) can stand in for each other in an interaction test:")
print([(a, b, round(cor.loc[a, b], 2)) for i, a in enumerate(cols) for b in cols[i+1:] if abs(cor.loc[a, b]) >= 0.6])'''),
    code('''env["doy"] = pd.to_datetime(env["date"]).dt.dayofyear
fig, axes = plt.subplots(1, 3, figsize=(11, 3.2))
for ax, v in zip(axes, ["tmax", "pm25", "o3"]):
    for city, g in env.groupby("city"): ax.plot(g["doy"], g[v].rolling(14, min_periods=1).mean(), lw=0.8, label=city)
    ax.set_title(v + " (14-day mean)"); ax.set_xlabel("day of year")
axes[0].legend(fontsize=6); plt.tight_layout(); plt.show()
print("Aug-Dec appear twice (2022 and 2023) and Jan-Jul once: season is partly confounded with year. The engine therefore adjusts for city and seasonality.")'''),
]

NOTEBOOKS["03_synthetic_benchmark"] = [
    md("# 03 · Engine report card (Track B, SIMULATED)\nReal covariates, simulated outcome with planted synergistic, antagonistic and non-linear interactions. Everything below is read from `artifacts/results/benchmark.json`, which `scripts/run_benchmark.py` writes from measurement. **Semi-synthetic data measures the engine, not nature.**"),
    code(SETUP),
    code('''B = json.loads((RES / "benchmark.json").read_text())
print("limitations recorded with the results:"); [print(" -", x) for x in B["limitations"]]'''),
    code('''rows = []
for snr, v in B["discovery"]["by_snr"].items():
    for st, s in v["stages"].items():
        rows.append({"SNR": float(snr), "stage": st, "discoveries": s["discoveries"], "true": s["true_positives"], "proxy": s["proxy"], "hard decoy": s["hard_decoy"], "easy decoy": s["easy_decoy"],
                     "recall": round(s["recall"], 2), "FDR strict": None if s["fdr_strict"] is None else round(s["fdr_strict"], 3), "FDR proxy-aware": None if s["fdr_proxy_aware"] is None else round(s["fdr_proxy_aware"], 3)})
T = pd.DataFrame(rows); display(T.pivot(index="stage", columns="SNR", values="FDR strict"))
display(T[T.stage.isin(["marginal_boot", "conditional", "full_stack"])].sort_values(["SNR", "stage"]))'''),
    code('''N = B["null_calibration"]
fig, axes = plt.subplots(1, 3, figsize=(11, 3))
for ax, m, col in zip(axes, ["naive", "hac", "boot"], [C["red"], C["amber"], C["green"]]):
    h = N[m]["p_histogram_10bins"]; ax.bar(np.arange(10) / 10 + 0.05, h, width=0.09, color=col); ax.axhline(sum(h) / 10, color=C["muted"], ls="--", lw=0.8)
    ax.set_title(f"{m}: lambda {N[m]['lambda_median']:.2f} [{N[m]['lambda_range'][0]:.2f}, {N[m]['lambda_range'][1]:.2f}]"); ax.set_xlabel("p-value under the null")
plt.tight_layout(); plt.show()'''),
    code('''M = B["moderation"]["by_effect_sd"]; sizes = sorted(M, key=float)
fig, ax = plt.subplots(1, 2, figsize=(9, 3))
for meth, col in [("none", C["muted"]), ("fixed_df4", C["amber"]), ("estimated", C["green"])]:
    ax[0].plot([float(s) for s in sizes], [M[s][meth]["power_mean"] for s in sizes], "o-", color=col, label=meth)
    ax[1].plot([float(s) for s in sizes], [M[s][meth]["fdr_mean"] for s in sizes], "o-", color=col)
ax[0].set_title("power vs planted effect (6/6/3/6 design)"); ax[1].axhline(0.05, color=C["red"], ls="--"); ax[1].set_title("FDR"); ax[0].legend(); plt.tight_layout(); plt.show()'''),
]

NOTEBOOKS["04_interaction_discovery"] = [
    md("# 04 · Interaction discovery\nRuns the real full stack (`synera_core.discovery.stack`) on the Track B dataset, then looks at the Track A gene-level result."),
    code(SETUP),
    code('''from synera_core.discovery.stack import run_full_stack
from synera_core.pipeline.registry import get_spec, load_panel
from synera_core.benchmark.generator import STRESSORS
df = load_panel(get_spec("benchmark_track_b"))
res = run_full_stack(df, "outcome", STRESSORS, n_boot=99, n_ci=60, seed=SEED)
print("rows", res["n_rows"], "block length", res["block_len"], "days;", res["stage_counts"], f"{res['runtime_s']['total']:.0f}s")
P = pd.DataFrame(res["pairs"]); display(P[P.s3_conditional][["a","b","type","effect_size","q_boot","gbm_rank","nid_rank","final"]].round(4))'''),
    code('''from synera_core.discovery.stack import nuisance_frame
S = list(STRESSORS); M = np.zeros((len(S), len(S)))
for r in res["pairs"]:
    i, j = S.index(r["a"]), S.index(r["b"]); M[i, j] = M[j, i] = -np.log10(max(r["q_boot"], 1e-300))
fig, ax = plt.subplots(figsize=(6, 5)); im = ax.imshow(M, cmap="viridis"); ax.set_xticks(range(len(S)), S, rotation=60, ha="right"); ax.set_yticks(range(len(S)), S); ax.grid(False)
plt.colorbar(im, label="-log10 q (marginal screen)"); ax.set_title("Marginal screen: many pairs light up through correlated stressors"); plt.show()'''),
    code('''acc = [r for r in res["pairs"] if r["s3_conditional"]]
fig, axes = plt.subplots(1, max(len(acc), 1), figsize=(4.2 * max(len(acc), 1), 3.6), squeeze=False)
for ax, r in zip(axes[0], acc):
    s = r["surface"]; ga, gb = np.array(s["grid_a"]), np.array(s["grid_b"])
    ax.contour(ga, gb, np.array(s["z_additive"]), colors=C["muted"], linestyles="--", linewidths=0.8)
    cs = ax.contour(ga, gb, np.array(s["z_full"]), colors=C["cyan"], linewidths=1.0); ax.contourf(ga, gb, np.array(s["z_gap"]), levels=8, cmap="magma", alpha=0.45)
    ax.set_xlabel(r["a"]); ax.set_ylabel(r["b"]); ax.set_title(f"{r['a']} x {r['b']}: {r['type']}")
plt.tight_layout(); plt.show()'''),
    md("## Track A: gene-level interaction (REAL NASA data)\nNo gene passes FDR; the volcano is an exploratory ranking."),
    code('''G = json.loads((RES / "osdr_genes.json").read_text()); g = pd.DataFrame(G)
fig, ax = plt.subplots(figsize=(6.4, 4)); ax.scatter(g.b_AB, g.neg_log10_p, s=2, c=C["muted"], alpha=0.5)
ax.axhline(-np.log10(0.05 / len(g)), color=C["red"], ls="--", lw=0.8); ax.text(g.b_AB.min(), -np.log10(0.05 / len(g)) + 0.05, "p needed for BH q<0.05 (best-ranked gene)", color=C["red"], fontsize=7)
ax.set_xlabel("interaction b_AB (log2)"); ax.set_ylabel("-log10 p"); ax.set_title(f"{len(g):,} genes tested, best q = {g.q.min():.2f}"); plt.show()
display(g.head(10)[["gene_symbol", "b_AB", "p", "q"]])'''),
]

NOTEBOOKS["05_statistical_validation"] = [
    md("# 05 · Statistical validation\nWhy the naive test cannot be trusted on a daily panel, and what calibrates it: p-value histograms and λ under the null, multiplicity correction before/after, effect sizes with block-bootstrap intervals."),
    code(SETUP),
    code('''from scipy import stats
from synera_core.benchmark.generator import STRESSORS, load_env_panel, simulate_benchmark, standardise_per_city
from synera_core.discovery.panel import PanelDiscovery
env = standardise_per_city(load_env_panel())
naive, hac, boot = [], [], []
for s in range(8):
    df, _ = simulate_benchmark(env, snr=2.0, seed=500 + s, null=True)
    d = PanelDiscovery(df, "outcome", STRESSORS, n_boot=199, seed=s)
    for pair in d.pairs[::5]:
        j = d._test_pair(*pair).joint; naive.append(j.p_naive); hac.append(j.p_hac); boot.append(j.p_boot)
lam = lambda p: np.median(stats.chi2.isf(np.clip(p, 1e-300, 1), 1)) / stats.chi2.ppf(0.5, 1)
fig, axes = plt.subplots(1, 3, figsize=(11, 3))
for ax, nm, p, col in zip(axes, ["naive F", "HAC (Newey-West)", "block bootstrap"], [naive, hac, boot], [C["red"], C["amber"], C["green"]]):
    ax.hist(p, bins=10, range=(0, 1), color=col); ax.set_title(f"{nm}: lambda = {lam(np.array(p)):.2f}"); ax.set_xlabel("p under the null")
plt.tight_layout(); plt.show()'''),
    md("A flat histogram and λ ≈ 1 mean honest p-values. The naive F spikes near zero (false alarms); a 16-restriction Newey-West test is worse still with persistent regressors; the block-bootstrap-calibrated test is closest to honest."),
    code('''from synera_core.validation.multitest import bh_fdr
p = np.array(boot); q = bh_fdr(p)
print(f"null tests: {len(p)}; raw p<0.05: {(p < 0.05).sum()}; after BH q<0.05: {(q < 0.05).sum()}")'''),
    code('''from synera_core.pipeline.registry import get_spec, load_panel
from synera_core.discovery.stack import run_full_stack
res = run_full_stack(load_panel(get_spec("benchmark_track_b")), "outcome", STRESSORS, n_boot=99, n_ci=100, seed=SEED)
acc = [r for r in res["pairs"] if r["s3_conditional"]]
fig, ax = plt.subplots(figsize=(6, 0.7 * max(len(acc), 1) + 1))
for i, r in enumerate(acc):
    ax.plot([r["ci_low"], r["ci_high"]], [i, i], color=C["cyan"]); ax.plot(r["b_AB_std"], i, "o", color=C["green"])
ax.axvline(0, color=C["muted"], lw=0.8); ax.set_yticks(range(len(acc)), [f"{r['a']} x {r['b']}" for r in acc]); ax.set_xlabel("bilinear coefficient (outcome SD), 95% block-bootstrap CI"); plt.tight_layout(); plt.show()'''),
]

NOTEBOOKS["06_cross_dataset_replication"] = [
    md("# 06 · Replication\n**Track B**: city hold-out (INTERNAL_REPLICATION). **Track A**: spleen vs skin from the **same animals** (CROSS_TISSUE_SAME_COHORT): a consistency check, never independent replication."),
    code(SETUP),
    code('''from synera_core.pipeline import track_a as TA
e1, m1 = TA.load_study("OSD-211"); e2, m2 = TA.load_study("OSD-237")
r1, r2 = TA.interaction_table(e1, m1), TA.interaction_table(e2, m2)
cons = TA.cross_tissue_consistency(r1, r2, m1, m2)
print(json.dumps({k: cons[k] for k in ["evidence_level","animals_shared","animals_discovery","genes_shared_after_filter","fdr_hits_discovery","fdr_hits_replication",
  "exploratory_top100_sign_concordance","interaction_effect_spearman_rho_all_shared_genes"]}, indent=1)); print(cons["caveat"]); print(cons["interpretation"])'''),
    code('''j = r1.join(r2, lsuffix="_spleen", rsuffix="_skin", how="inner")
fig, ax = plt.subplots(figsize=(4.6, 4.4)); ax.scatter(j.b_AB_spleen, j.b_AB_skin, s=2, c=C["cyan"], alpha=0.35)
ax.axhline(0, color=C["muted"], lw=0.6); ax.axvline(0, color=C["muted"], lw=0.6); ax.set_xlabel("interaction b_AB, spleen (OSD-211)"); ax.set_ylabel("interaction b_AB, skin (OSD-237)")
ax.set_title(f"all shared genes; Spearman rho = {cons['interaction_effect_spearman_rho_all_shared_genes']:.2f}"); plt.show()'''),
    code('''from synera_core.pipeline.orchestrator import _holdout_replication, default_params
from synera_core.pipeline.registry import get_spec, load_panel
from synera_core.discovery.stack import run_full_stack
from synera_core.benchmark.generator import STRESSORS
params = default_params("benchmark_track_b", quick=True)
df = load_panel(get_spec("benchmark_track_b"))
res = run_full_stack(df, "outcome", STRESSORS, n_boot=params["n_boot"], n_ci=params["n_ci"], seed=params["seed"])
acc = [p for p in res["pairs"] if p["s3_conditional"]]
hold = _holdout_replication(df, acc, params)
pd.DataFrame([{"pair": f"{a} x {b}", "half A p": v["halves"]["A"]["p"], "half B p": v["halves"]["B"]["p"], "replicated": v["replicated"]} for (a, b), v in hold.items()])'''),
]

NOTEBOOKS["07_security_poisoning_lab"] = [
    md("# 07 · Security and poisoning lab\nThe attacks run on **temporary copies**. The hash check is cryptographic and catches every change; the statistical detectors are advisory and are honest about what they miss. The contrast is why cryptographic provenance exists."),
    code(SETUP),
    code('''from synera_core.security.tamper_sim import simulate_attack, MODES
rows = []
for m in [x for x in MODES if x not in ("swap_model", "ledger_tamper")]:
    r = simulate_attack("benchmark_track_b", m, magnitude=0.05, seed=1)
    rows.append({"attack": m, "hash changed": not r["hash_match"], "statistical detectors fired": ", ".join(r["statistical_detections"]) or "none", "hash only": r["hash_only"], "verdict": r["verdict"]})
pd.DataFrame(rows)'''),
    code('''r = simulate_attack("benchmark_track_b", "swap_model", seed=0)
print("model checks after weight perturbation:"); [print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['name']}: {c['detail']}") for c in r["model"]["after"]["checks"]]
r = simulate_attack("benchmark_track_b", "ledger_tamper")
print("\\nledger copy before:", r["ledger"]["before"]["valid"], "| after one payload edit:", r["ledger"]["after"]["valid"], [i["code"] for i in r["ledger"]["after"]["issues"]][:3])'''),
    md("## Measured detector reliability (benchmark.json)"),
    code('''S = json.loads((RES / "benchmark.json").read_text())["security"]
print("clean false-alarm rate per detector:", {k: round(v, 3) for k, v in S["clean_false_alarm_rate"].items()})
tbl = pd.DataFrame({f"{m} {int(float(f)*100)}%": {k: v for k, v in c.items()} for m, d in S["attacks"].items() for f, c in d.items()}).T.round(2); display(tbl)
print("attacks caught by the hash but by no statistical detector:"); display(pd.DataFrame(S["hash_only_attacks"]))'''),
]

NOTEBOOKS["08_provenance_ledger_demo"] = [
    md("# 08 · Provenance ledger demo\nRegister a dummy dataset, record an experiment, flip one byte of a **copy**, watch the hash mismatch raise an INTEGRITY_ALERT, and see `verify()` catch edits to the chain itself. Uses a temporary ledger; the project ledger is untouched."),
    code(SETUP),
    code('''import tempfile, shutil, sqlite3
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import register_file
from synera_core.security.integrity import IntegrityGuard
tmp = Path(tempfile.mkdtemp()); led = Ledger(tmp / "demo.db", tmp / "demo.key")
data = tmp / "demo.csv"; pd.DataFrame({"x": np.arange(10), "y": np.arange(10) ** 2}).to_csv(data, index=False)
h, blk = register_file(led, data, "dataset", {"demo": True}, manifest_path=tmp / "data" / "MANIFEST.json")
exp = led.append("EXPERIMENT_RUN", {"note": "dummy run"}, artifact_hashes=[h])
print("registered", h[:16], "in block", blk.index, "| experiment block", exp.index, "| chain valid:", led.verify()["valid"])'''),
    code('''b = bytearray(data.read_bytes()); b[5] ^= 1; data.write_bytes(bytes(b))
res = IntegrityGuard(led).check_dataset(data)
print("HASH MISMATCH" if not res.ok else "ok", "| expected", res.expected_hash[:12], "actual", res.actual_hash[:12])
print("blocks now:", [x.block_type for x in led.iter_blocks()])'''),
    code('''def tamper(kind):
    copy = tmp / f"c_{kind}.db"; shutil.copy(tmp / "demo.db", copy); con = sqlite3.connect(copy)
    for (n,) in con.execute("select name from sqlite_master where type='trigger'").fetchall(): con.execute(f"drop trigger {n}")
    if kind == "payload": con.execute("update blocks set payload_json = replace(payload_json, 'dummy', 'FORGED') where block_index = 1")
    if kind == "delete_middle": con.execute("delete from blocks where block_index = 1")
    con.commit(); con.close(); return Ledger(copy, tmp / "demo.key").verify()
for k in ["payload", "delete_middle"]: v = tamper(k); print(f"{k:14s} valid={v['valid']} issues={[i['code'] for i in v['issues']]}")'''),
    code('''blocks = list(led.iter_blocks()); fig, ax = plt.subplots(figsize=(9, 1.8))
for i, b in enumerate(blocks):
    col = C["red"] if b.block_type == "INTEGRITY_ALERT" else C["cyan"]; ax.add_patch(plt.Rectangle((i * 1.5, 0), 1.1, 1, fill=False, ec=col)); ax.text(i * 1.5 + 0.55, 0.5, b.block_hash[:6], ha="center", color=col, fontsize=7)
    ax.text(i * 1.5 + 0.55, -0.35, b.block_type.replace("_", " ")[:14], ha="center", fontsize=6, color=C["muted"])
    if i: ax.annotate("", (i * 1.5, 0.5), (i * 1.5 - 0.4, 0.5), arrowprops=dict(arrowstyle="-", color=C["muted"]))
ax.set_xlim(-0.2, len(blocks) * 1.5); ax.set_ylim(-0.7, 1.3); ax.axis("off"); plt.show()'''),
]


def build() -> list[Path]:
    NB.mkdir(exist_ok=True)
    for old in NB.glob("*.ipynb"):
        old.unlink()
    out = []
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
        p = NB / f"{name}.ipynb"
        nbf.write(nb, p)
        out.append(p)
    return out


def execute(paths: list[Path]) -> None:
    from nbconvert.preprocessors import ExecutePreprocessor
    for p in paths:
        nb = nbf.read(p, as_version=4)
        print("executing", p.name, flush=True)
        ExecutePreprocessor(timeout=1800, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT)}})
        nbf.write(nb, p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    paths = build()
    print("wrote", len(paths), "notebooks")
    if a.execute:
        execute(paths)
