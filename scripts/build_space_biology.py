"""Track A (REAL NASA OSDR data): gene-level Radiation x Hindlimb-Unloading analysis -> result files.

Writes
    artifacts/results/osdr_genes.json      every tested gene (symbol, b_AB, p, q) for the volcano / table
    artifacts/results/space_biology.json   design, positive controls, null calibration, power / minimum
                                           detectable effect, cross-tissue consistency, PC1 drivers

All numbers are computed (see synera_core.pipeline.track_a); nothing is edited by hand.

    python scripts/build_space_biology.py [--perms 200]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from synera_core.config import find_repo_root, get_settings
from synera_core.pipeline import track_a as TA
from synera_core.provenance.manifest import register_file
from synera_core.provenance.store import open_ledger

ROOT = find_repo_root()
OUT = ROOT / "artifacts" / "results"


def main(perms: int = 200) -> None:
    s = get_settings()
    OUT.mkdir(parents=True, exist_ok=True)
    e1, m1 = TA.load_study("OSD-211")
    e2, m2 = TA.load_study("OSD-237")
    sym_path = ROOT / "data" / "reference" / "mouse_ensembl_symbols.tsv"
    sym = pd.read_csv(sym_path, sep="\t", index_col=0) if sym_path.exists() else pd.DataFrame(columns=["symbol", "name"])

    res1 = TA.interaction_table(e1, m1)
    res2 = TA.interaction_table(e2, m2)
    shared = res1.index.intersection(res2.index)
    consistency = TA.cross_tissue_consistency(res1, res2, m1, m2)

    table = res1.join(res2[["b_AB", "p_AB", "q_AB"]], rsuffix="_rep").join(sym, how="left").sort_values("p_AB")
    genes = []
    for gid, r in table.iterrows():
        name = r.get("name") if isinstance(r.get("name"), str) else ""
        symbol = r.get("symbol") if isinstance(r.get("symbol"), str) and r.get("symbol") else gid
        rep_b = r["b_AB_rep"]
        genes.append({
            "ensembl_id": gid, "gene_symbol": symbol, "name": name,
            "b_AB": round(float(r["b_AB"]), 4), "p": float(r["p_AB"]), "q": round(float(r["q_AB"]), 6),
            "neg_log10_p": round(float(-np.log10(max(r["p_AB"], 1e-300))), 4),
            "neg_log10_q": round(float(-np.log10(max(r["q_AB"], 1e-300))), 4),
            "type": r["type"],
            "replication_b_AB": None if pd.isna(rep_b) else round(float(rep_b), 4),
            "replication_p": None if pd.isna(r["p_AB_rep"]) else float(r["p_AB_rep"]),
            "same_sign_in_replication": None if pd.isna(rep_b) else bool(np.sign(r["b_AB"]) == np.sign(rep_b)),
            "passed_filter_both": bool(gid in shared),
            "replicated": False,
        })
    (OUT / "osdr_genes.json").write_text(json.dumps(genes))

    overview = {
        "provenance": "REAL", "source": "NASA OSDR / GeneLab",
        "studies": [
            {"id": "OSD-211", "role": "discovery", "tissue": str(m1.tissue.iloc[0]), "organism": str(m1.organism.iloc[0]),
             "samples": int(len(m1)), "genes_tested": int(e1.shape[0]), "design_2x2": TA.cell_counts(m1)},
            {"id": "OSD-237", "role": "replication", "tissue": str(m2.tissue.iloc[0]), "organism": str(m2.organism.iloc[0]),
             "samples": int(len(m2)), "genes_tested": int(e2.shape[0]), "design_2x2": TA.cell_counts(m2)},
        ],
        "factors": {"radiation": "chronic low-dose ionizing radiation",
                    "microgravity": "hindlimb unloading (ground analogue of microgravity)"},
        "expression_variant": s.osdr_expression_variant,
        "expression_filter": s.expression_filter.model_dump(),
        "moderation": {"method": "empirical-Bayes, data-estimated prior (method of moments on log s^2)",
                       "prior_df_discovery": float(res1.attrs.get("prior_df", 0.0)),
                       "prior_df_replication": float(res2.attrs.get("prior_df", 0.0))},
        "fdr_alpha": s.alpha, "fdr_line_p": float(s.alpha / len(table)),
        "fdr_line_note": "the best-ranked gene would need p <= alpha / m to pass BH",
        "genes_tested": int(len(table)),
        "counts_by_type": {"SYNERGISTIC": sum(g["type"] == "SYNERGISTIC" for g in genes),
                           "ANTAGONISTIC": sum(g["type"] == "ANTAGONISTIC" for g in genes), "NONLINEAR": 0},
        "best_q": float(table["q_AB"].min()),
        "top_exploratory": [{"gene": g["gene_symbol"], "b_AB": g["b_AB"], "p": g["p"], "q": g["q"]} for g in genes[:10]],
    }
    controls = {"note": "Overall effects from y ~ radiation + unloading (all 21 samples); genes with BH q < 0.05",
                **{st: {m: TA.additive_main_effects(e.T, mm, mod) for m, mod in TA.PRIOR_MODES}
                   for st, e, mm in (("OSD-211", e1, m1), ("OSD-237", e2, m2))}}
    print("null calibration ...")
    null = TA.permutation_null(e1, m1, perms)
    print("spike-in power ...")
    power = TA.spike_in_power(e1, m1)
    pcs = {"OSD-211": TA.pc1_drivers(e1, m1, sym), "OSD-237": TA.pc1_drivers(e2, m2, sym)}
    report = {"overview": overview, "positive_controls": controls, "null_calibration_osd211": null,
              "power": power, "consistency": consistency, "pc1": pcs}
    (OUT / "space_biology.json").write_text(json.dumps(report, indent=2))

    ledger = open_ledger()
    for p in (OUT / "osdr_genes.json", OUT / "space_biology.json"):
        register_file(ledger, p, "dataset", {"type": "result", "provenance": "REAL", "evidence_level": TA.EVIDENCE_LEVEL})
    print(f"genes tested {len(genes)}; best q = {overview['best_q']:.3f}; FDR hits = {consistency['fdr_hits_discovery']}")
    print("controls:", json.dumps(controls["OSD-211"]), json.dumps(controls["OSD-237"]))
    print("null:", {k: null[k] for k in ("frac_p_lt_05_median", "lambda_median", "mean_hits_q05_per_permutation", "frac_permutations_with_a_hit")})
    print("power:", {k: round(v["power_mean"], 2) for k, v in power["by_log2_effect"].items()}, "MDE:", power["minimum_detectable_log2_80pct_power"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--perms", type=int, default=200)
    main(ap.parse_args().perms)
