"""Evented, reproducible analysis pipeline.

One run is nine ordered steps. Every step calls the real function it names and reports its measured duration,
the counts it produced and a human-readable message; there are no fixed delays and no canned text.

    1 LOAD_DATA                 SHA-256 of the dataset vs the ledger (mismatch -> BLOCKED)
    2 SECURITY_PRECHECK         ensemble scan (range / duplicates / outliers / drift / labels / time)
    3 DISCOVERY                 parametric panel test (or factorial OLS) + LightGBM-SHAP + neural second opinions
    4 VALIDATION                BH-FDR, conditional selection, bootstrap CIs, effect gate
    5 REPLICATION               city hold-out (Track B) or cross-tissue consistency (Track A)
    6 PROVENANCE                run manifest + EXPERIMENT_RUN ledger block
    7 SECURITY_POSTCHECK        ledger chain, dataset hash and source-code drift re-checked
    8 REPRODUCIBILITY_REPLAY    the analysis is run again from the same seed; result digests must match
    9 FINALIZE                  statuses assigned, ledger blocks appended, findings returned

The module has no database dependency: it returns a plain dict and reports progress through ``emit``.
"""

from __future__ import annotations

import time
import traceback
from typing import Any, Callable

import numpy as np
import pandas as pd

from synera_core.benchmark.generator import STRESSORS
from synera_core.config import find_repo_root, get_settings
from synera_core.discovery.panel import PanelDiscovery
from synera_core.discovery.stack import run_full_stack
from synera_core.pipeline import track_a as TA
from synera_core.pipeline.gates import finding_hash, run_gates
from synera_core.pipeline.registry import DatasetSpec, get_spec, load_panel
from synera_core.provenance.hashing import sha256_obj
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import build_run_manifest, compute_result_hash
from synera_core.provenance.store import open_ledger
from synera_core.security.integrity import IntegrityGuard
from synera_core.security.pipeline_integrity import detect_code_drift, reproducibility_replay
from synera_core.security.poisoning import scan_dataset
from synera_core.validation.bootstrap import factorial_bootstrap_ci
from synera_core.validation.confidence import compute_confidence
from synera_core.validation.replication import replicate

STEPS = [
    ("LOAD_DATA", "Load and hash-check the dataset"),
    ("SECURITY_PRECHECK", "Scan the data for tampering and poisoning"),
    ("DISCOVERY", "Search for interactions"),
    ("VALIDATION", "Validate: FDR, confidence intervals, effect size"),
    ("REPLICATION", "Check replication"),
    ("PROVENANCE", "Record the run in the evidence ledger"),
    ("SECURITY_POSTCHECK", "Re-check integrity after the analysis"),
    ("REPRODUCIBILITY_REPLAY", "Replay the analysis from the same seed"),
    ("FINALIZE", "Assign statuses and persist findings"),
]

Emit = Callable[[dict], None]


class RunBlocked(Exception):
    """Raised when an integrity-critical check fails; the run ends BLOCKED."""


def _sig(x: float | None, digits: int = 8) -> float | None:
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else float(f"{x:.{digits}g}")


def default_params(dataset_id: str, quick: bool = False) -> dict:
    s = get_settings()
    p = {"alpha": s.alpha, "effect_gate": s.discovery.effect_gate, "n_boot": s.discovery.n_boot, "n_ci": s.discovery.n_ci,
         "topk": s.discovery.topk_second_opinion, "seed": s.seeds.global_seed,
         "variant": s.osdr_expression_variant}
    if quick:
        p.update({"n_boot": 99, "n_ci": 60, "quick": True})
    return p


def config_hash(dataset_id: str, params: dict) -> str:
    return sha256_obj({"dataset_id": dataset_id, "params": params})


def recompute_digest(dataset_id: str, params: dict) -> str:
    """Re-run the analysis from the registered inputs and return the digest of its outputs (no ledger writes)."""
    spec = get_spec(dataset_id)
    if spec.kind == "panel":
        res = run_full_stack(load_panel(spec), "outcome", spec.stressor_cols, alpha=params["alpha"], effect_gate=params["effect_gate"],
                             n_boot=params["n_boot"], n_ci=params["n_ci"], seed=params["seed"], topk=params["topk"])
        return panel_digest(res)
    expr, meta = TA.load_study(spec.abs_path.name.split("_")[1])
    return factorial_digest(TA.interaction_table(expr, meta, params["alpha"]))


def _bh_scaled(p: np.ndarray, m_total: int) -> np.ndarray:
    srt = np.argsort(p)
    adj = np.minimum.accumulate((p[srt] * m_total / np.arange(1, len(p) + 1))[::-1])[::-1]
    q = np.empty(len(p))
    q[srt] = np.clip(adj, 0, 1)
    return q


# --------------------------------------------------------------------------------------------------
# Result digests (what the replay must reproduce). Floats are rounded to 8 significant digits.
# --------------------------------------------------------------------------------------------------
def panel_digest(res: dict) -> str:
    rows = []
    for r in res["pairs"]:
        rows.append([r["a"], r["b"], _sig(r["p_boot"]), _sig(r["q_boot"]), r["s3_conditional"], r.get("type"),
                     _sig(r.get("effect_size")), r.get("gbm_rank"), r.get("nid_rank"), r["final"]])
    return sha256_obj(rows)


def factorial_digest(res_d: pd.DataFrame) -> str:
    return sha256_obj([[str(i), _sig(float(p)), _sig(float(b))] for i, p, b in zip(res_d.index, res_d["p_AB"], res_d["b_AB"])])


# --------------------------------------------------------------------------------------------------
# Panel (Track B) pieces
# --------------------------------------------------------------------------------------------------
def _holdout_replication(df: pd.DataFrame, accepted: list[dict], params: dict, stressors: list[str] | None = None) -> dict[tuple[str, str], dict]:
    """Internal replication by city hold-out: fit each accepted pair in two disjoint halves of the cities."""
    cities = sorted(df["city"].unique())
    halves = {"A": cities[0::2], "B": cities[1::2]}
    pairs = [(r["a"], r["b"]) for r in accepted]
    out: dict[tuple[str, str], dict] = {p: {"halves": {}} for p in pairs}
    for h, cs in halves.items():
        sub = df[df["city"].isin(cs)].reset_index(drop=True)
        disc = PanelDiscovery(sub, "outcome", stressors or STRESSORS, alpha=params["alpha"], n_boot=params["n_boot"], seed=params["seed"])
        for p in pairs:
            others = [q for q in pairs if q != p]
            r = disc.holdout_check(p[0], p[1], others)
            out[p]["halves"][h] = {"cities": cs, "p": r["p_boot"], "direction": r["direction"]}
    for p, v in out.items():
        ps = [h["p"] for h in v["halves"].values()]
        dirs = {h["direction"] for h in v["halves"].values()}
        v["replicated"] = bool(all(np.isfinite(x) and x < params["alpha"] for x in ps) and len(dirs) == 1)
    return out


def _panel_findings(res: dict, df: pd.DataFrame, spec: DatasetSpec, dataset_hash: str, params: dict, hold: dict,
                    sec: dict, ledger_state: dict) -> list[dict]:
    gate = params["effect_gate"]
    accepted = [r for r in res["pairs"] if r["s3_conditional"]]
    m_total = res["n_pairs"]
    cond_p = np.array([r["conditional_p"] if r["conditional_p"] is not None else r["p_boot"] for r in accepted]) if accepted else np.array([])
    q_cond = _bh_scaled(cond_p, m_total) if len(accepted) else np.array([])
    findings = []
    for r, qc in zip(accepted, q_cond):
        h = hold.get((r["a"], r["b"]), {"halves": {}, "replicated": False})
        rep = {"evidence_level": "INTERNAL_REPLICATION", "n_shared": 1, "replicated": bool(h["replicated"]),
               "replication_rate": 1.0 if h["replicated"] else 0.0, "halves": h["halves"],
               "detail": "Re-fitted in two disjoint halves of the cities; replicated when both halves are significant with the same direction."}
        fid = sha256_obj({"dataset_hash": dataset_hash, "pair": [r["a"], r["b"]], "config": params})[:12]
        eff = {"b_AB": r["b_AB_std"], "ci_low": r["ci_low"], "ci_high": r["ci_high"], "cohens_d": r["effect_size"],
               "effect_size": r["effect_size"], "eff_ci_low": r["eff_ci_low"], "eff_ci_high": r["eff_ci_high"]}
        f = {
            "id": fid, "track": spec.track, "provenance": spec.provenance, "evidence_level": "INTERNAL_REPLICATION",
            "dataset_ids": [spec.id], "dataset_hashes": {spec.id: dataset_hash}, "stressors": [r["a"], r["b"]],
            "feature": None, "type": r["type"], "effect": eff,
            "stats": {"p": float(r["conditional_p"] or r["p_boot"]), "q": float(qc), "n": int(res["n_rows"]), "df": float(res["n_rows"]),
                      "p_naive": r["p_naive"], "p_hac": r["p_hac"], "q_marginal": r["q_boot"], "p_bilinear": r.get("p_bilinear"),
                      "p_nonlinear": r.get("p_nonlinear"), "lambda_boot": r["lambda_boot"]},
            "methods": {**r["methods"], "gbm_rank": r["gbm_rank"], "nid_rank": r["nid_rank"]},
            "replication": rep, "security": sec, "surface": r["surface"], "effect_gate": gate,
            "config": params, "history": [], "gates": [],
        }
        f["status"] = _panel_status(r, rep, gate)
        f["_robustness"] = r["robustness"]
        findings.append(f)
    return findings


def _panel_status(r: dict, rep: dict, gate: float) -> str:
    if r["effect_size"] < gate or r["eff_ci_low"] < gate:
        return "REJECTED"        # detectable but below the pre-specified minimal effect
    if not (r["methods"]["gbm"] or r["methods"]["nid"]):
        return "CANDIDATE"       # statistics pass but no independent method corroborates
    return "VALIDATED"


# --------------------------------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------------------------------
def execute_run(dataset_id: str, params: dict | None = None, emit: Emit | None = None, ledger: Ledger | None = None,
                run_id: str | None = None) -> dict:
    """Execute the full pipeline for ``dataset_id`` and return a result dict (see module docstring)."""
    t_run = time.time()
    ledger = ledger or open_ledger()
    spec = get_spec(dataset_id)
    if not spec.runnable:
        raise ValueError(f"{dataset_id} has no outcome variable, so no interaction analysis can be run on it")
    params = {**default_params(dataset_id), **(params or {})}
    run_id = run_id or f"run_{config_hash(dataset_id, params)[:10]}"
    chash = config_hash(dataset_id, params)
    steps: list[dict] = []
    state: dict[str, Any] = {"status": "RUNNING"}

    def step(i: int, status: str, message: str, data: dict | None = None, duration: float | None = None) -> None:
        name = STEPS[i][0]
        ev = {"run_id": run_id, "step": i + 1, "step_name": name, "label": STEPS[i][1], "status": status,
              "progress": (i + (1 if status != "RUNNING" else 0.15)) / len(STEPS), "message": message, "data": data or {},
              "duration_s": duration, "ts": time.time()}
        steps.append(ev)
        if emit:
            emit(ev)

    def timed(i: int, fn: Callable[[], tuple[str, dict]]):
        step(i, "RUNNING", STEPS[i][1] + "...")
        t0 = time.time()
        msg, data = fn()
        step(i, "DONE", msg, data, time.time() - t0)

    try:
        guard = IntegrityGuard(ledger)
        is_panel = spec.kind == "panel"

        # 1 ---- LOAD_DATA ------------------------------------------------------------------------
        def s1():
            files = [spec.abs_path] + ([spec.abs_meta_path] if spec.abs_meta_path else [])
            hashes = {}
            for p in files:
                chk = guard.check_dataset(p)
                hashes[p.name] = chk.actual_hash
                if not chk.ok:
                    raise RunBlocked(f"integrity failure: {chk.detail}")
            state["dataset_hash"] = hashes[spec.abs_path.name]
            state["file_hashes"] = hashes
            if is_panel:
                state["df"] = load_panel(spec)
                n = len(state["df"])
                return (f"{spec.abs_path.name}: SHA-256 {state['dataset_hash'][:12]}... matches the ledger; {n} rows loaded",
                        {"sha256": state["dataset_hash"], "rows": n, "cities": int(state["df"]["city"].nunique())})
            e, m = TA.load_study(spec.abs_path.name.split("_")[1])
            state["expr"], state["meta"] = e, m
            return (f"{spec.abs_path.name}: SHA-256 {state['dataset_hash'][:12]}... matches the ledger; {e.shape[0]} genes x {e.shape[1]} samples",
                    {"sha256": state["dataset_hash"], "genes": int(e.shape[0]), "samples": int(e.shape[1])})
        timed(0, s1)

        # 2 ---- SECURITY_PRECHECK ----------------------------------------------------------------
        def s2():
            if is_panel:
                scan_df = state["df"][["city", "date", *spec.stressor_cols]]
            else:
                X = state["expr"].T.to_numpy(float)
                u, s, _ = np.linalg.svd(X - X.mean(0), full_matrices=False)
                scan_df = pd.DataFrame(u[:, :5] * s[:5], columns=[f"PC{i + 1}" for i in range(5)])
            rep = scan_dataset(scan_df, ranges=None if spec.units == "raw" else {})
            state["security"] = {"status": rep.status, "checks": rep.checks}
            if rep.status == "COMPROMISED":
                raise RunBlocked("blocking security check failed: " + ", ".join(c["name"] for c in rep.checks if c["blocking"] and c["status"] == "FAIL"))
            warn = [c["name"] for c in rep.checks if c["status"] != "PASS"]
            return (f"scan {rep.status}: {len(rep.checks)} checks" + (f"; advisory warnings: {', '.join(warn)}" if warn else "; no warnings"),
                    {"status": rep.status, "warnings": warn, "checks": [{k: c[k] for k in ('name', 'status', 'score', 'detail', 'blocking')} for c in rep.checks]})
        timed(1, s2)

        # 3-4 ---- DISCOVERY + VALIDATION ------------------------------------------------------
        counts: dict[str, Any] = {}

        def on_stage(stage: str, info: dict) -> None:
            counts[stage] = info

        if is_panel:
            step(2, "RUNNING", "Screening all stressor pairs and fitting LightGBM-SHAP / neural second opinions...")
            t0 = time.time()
            res = run_full_stack(state["df"], "outcome", spec.stressor_cols, alpha=params["alpha"], effect_gate=params["effect_gate"],
                                 n_boot=params["n_boot"], n_ci=params["n_ci"], seed=params["seed"], topk=params["topk"],
                                 on_stage=on_stage)
            state["res"] = res
            so = res["second_opinion"]
            n_pairs = res["n_pairs"]
            step(2, "DONE", f"{n_pairs} pairs screened ({res['n_rows']} rows, block length {res['block_len']} d); "
                            f"{sum(p['s1_raw'] for p in res['pairs'])} raw p<{params['alpha']}; "
                            f"GBM hold-out R2 {so['gbm_holdout_r2']:.2f}, NID R2 {so['nid_holdout_r2']:.2f}",
                 {"n_pairs": n_pairs, "raw_significant": int(sum(p["s1_raw"] for p in res["pairs"])), "block_length": res["block_len"],
                  "gbm_holdout_r2": so["gbm_holdout_r2"], "nid_holdout_r2": so["nid_holdout_r2"]}, time.time() - t0)
            sc = res["stage_counts"]
            n_final = sum(p["final"] for p in res["pairs"])
            step(3, "DONE", f"BH-FDR: {sc['marginal_bh']} pairs; after conditional selection: {sc['after_backward']} "
                            f"(removed {sc['marginal_bh'] - sc['after_backward']} proxies/leakage); effect gate + method agreement: {n_final}",
                 {**sc, "validated": int(n_final)}, res["runtime_s"]["parametric"])
        else:
            def s3():
                res_d = TA.interaction_table(state["expr"], state["meta"], params["alpha"])
                e2, m2 = TA.load_study("OSD-237" if "211" in spec.id else "OSD-211")
                res_r = TA.interaction_table(e2, m2, params["alpha"])
                state["res_d"], state["res_r"], state["meta_r"] = res_d, res_r, m2
                n_hit = int((res_d.q_AB < params["alpha"]).sum())
                return (f"{len(res_d)} genes tested; empirical-Bayes prior df {res_d.attrs.get('prior_df', 0):.2f}; "
                        f"best p {res_d.p_AB.min():.2e}", {"genes_tested": int(len(res_d)), "prior_df": float(res_d.attrs.get("prior_df", 0)),
                                                           "best_p": float(res_d.p_AB.min()), "hits_q05": n_hit})
            timed(2, s3)

            def s4():
                res_d = state["res_d"]
                hits = res_d[res_d.q_AB < params["alpha"]]
                state["hits"] = hits
                return (f"BH-FDR at {params['alpha']}: {len(hits)} gene(s) pass (best q = {res_d.q_AB.min():.3f}); "
                        f"{len(hits)} bootstrap interval(s) computed", {"hits": int(len(hits)), "best_q": float(res_d.q_AB.min())})
            timed(3, s4)

        # 5 ---- REPLICATION ----------------------------------------------------------------------
        def s5():
            if is_panel:
                acc = [p for p in state["res"]["pairs"] if p["s3_conditional"]]
                hold = _holdout_replication(state["df"], acc, params, spec.stressor_cols) if acc else {}
                state["hold"] = hold
                n_rep = sum(v["replicated"] for v in hold.values())
                return (f"city hold-out (two disjoint city halves): {n_rep}/{len(acc)} selected pairs replicate - INTERNAL_REPLICATION only",
                        {"evidence_level": "INTERNAL_REPLICATION", "pairs": len(acc), "replicated": int(n_rep)})
            cons = TA.cross_tissue_consistency(state["res_d"], state["res_r"], state["meta"], state["meta_r"], params["alpha"])
            state["consistency"] = cons
            return (f"{cons['animals_shared']} of {cons['animals_discovery']} animals are shared between the tissues: "
                    f"CROSS_TISSUE_SAME_COHORT, not independent. {cons['fdr_hits_discovery']} gene(s) to replicate",
                    {k: cons[k] for k in ("evidence_level", "animals_shared", "fdr_hits_discovery", "fdr_hits_replication",
                                          "exploratory_top100_sign_concordance")})
        timed(4, s5)

        # 6 ---- PROVENANCE -----------------------------------------------------------------------
        def s6():
            digest = panel_digest(state["res"]) if is_panel else factorial_digest(state["res_d"])
            state["digest"] = digest
            manifest = build_run_manifest(config={"dataset_id": dataset_id, **params}, dataset_hashes=state["file_hashes"],
                                          model_hashes={}, seed=params["seed"], repo_root=find_repo_root())
            state["manifest"] = manifest
            state["result_hash"] = compute_result_hash(manifest, digest)
            if is_panel:
                fs = _panel_findings(state["res"], state["df"], spec, state["dataset_hash"], params, state.get("hold", {}),
                                     state["security"], {})
            else:
                fs = _factorial_findings(state, spec, params)
            state["findings"] = fs
            fh = [finding_hash(f) for f in fs]
            blk = ledger.append("EXPERIMENT_RUN", {
                "run_id": run_id, "dataset_id": dataset_id, "dataset_hash": state["dataset_hash"], "config_hash": chash,
                "result_hash": state["result_hash"], "outputs_digest": digest, "params": params,
                "src_tree_hash": manifest["src_tree_hash"], "git_commit": manifest["git_commit"],
                "n_findings": len(fs), "finding_ids": [f["id"] for f in fs], "provenance": spec.provenance,
            }, artifact_hashes=[state["dataset_hash"], chash, state["result_hash"], *fh])
            state["run_block"] = blk.index
            return (f"EXPERIMENT_RUN block {blk.index} appended (signed, Merkle root {blk.merkle_root[:12]}...); "
                    f"result hash {state['result_hash'][:12]}...", {"block_index": blk.index, "result_hash": state["result_hash"],
                                                                     "config_hash": chash, "findings_hashed": len(fh)})
        timed(5, s6)

        # 7 ---- SECURITY_POSTCHECK ---------------------------------------------------------------
        def s7():
            v = ledger.verify()
            if not v["valid"]:
                raise RunBlocked(f"ledger chain invalid after run: {v['issues'][:1]}")
            chk = guard.check_dataset(spec.abs_path)
            if not chk.ok:
                raise RunBlocked(f"dataset changed during the run: {chk.detail}")
            drift = detect_code_drift(state["manifest"])
            if drift:
                raise RunBlocked("source code changed during the run")
            return (f"chain valid ({v['height']} blocks), dataset hash unchanged, no source-code drift",
                    {"chain_valid": True, "height": v["height"], "code_drift": False})
        timed(6, s7)

        # 8 ---- REPRODUCIBILITY_REPLAY -----------------------------------------------------------
        def s8():
            t0 = time.time()
            rp = reproducibility_replay(lambda: recompute_digest(dataset_id, params), state["digest"])
            state["replay"] = {**rp, "seconds": time.time() - t0}
            rd = rp["replay_hash"]
            return ((f"replay digest identical ({rd[:12]}...)" if rp["matches"] else
                     f"REPLAY MISMATCH: {state['digest'][:12]}... vs {rd[:12]}..."), state["replay"])
        timed(7, s8)

        # 9 ---- FINALIZE -------------------------------------------------------------------------
        def s9():
            trust = int(state["replay"]["matches"])
            out_f = []
            for f in state["findings"]:
                rep = f.get("replication") or {}
                robustness = f.pop("_robustness", 1.0)
                conf = compute_confidence(f["stats"]["q"], params["alpha"], f["effect"].get("effect_size") or f["effect"]["cohens_d"],
                                          bool(f["effect"].get("eff_ci_low", 0) >= params.get("effect_gate", 0) if is_panel else
                                               not (f["effect"]["ci_low"] < 0 < f["effect"]["ci_high"])),
                                          f["evidence_level"], bool(rep.get("replicated")), robustness, trust,
                                          weights=get_settings().confidence_weights.model_dump())
                f["confidence"] = {"score": conf["score"], "components": conf["components"]}
                if not trust:
                    f["status"] = "BLOCKED"
                f["run_id"] = run_id
                f["history"] = [f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC: {f['status']} by run {run_id}"]
                run_ctx = {"replay": state["replay"], "src_tree_hash": state["manifest"]["src_tree_hash"]}
                g = run_gates(f, ledger, spec.abs_path, state["dataset_hash"], run_ctx, state["manifest"]["src_tree_hash"])
                f["gates"] = g["gates"]
                # The gate may demote integrity failures; it never promotes beyond what the lifecycle allows.
                if g["new_status"] == "BLOCKED":
                    f["status"] = "BLOCKED"
                elif g["new_status"] == "VERIFIED":
                    f["status"] = "VERIFIED"
                if f["status"] in ("VALIDATED", "VERIFIED"):
                    ledger.append("FINDING_VALIDATED", {"finding_id": f["id"], "run_id": run_id, "status": f["status"],
                                                        "type": f["type"], "stressors": f["stressors"], "provenance": f["provenance"]},
                                  artifact_hashes=[finding_hash(f)])
                elif f["status"] == "REJECTED":
                    ledger.append("FINDING_REJECTED", {"finding_id": f["id"], "run_id": run_id, "reason": "below pre-specified minimal effect"},
                                  artifact_hashes=[finding_hash(f)])
                out_f.append(f)
            state["findings"] = out_f
            by = {s: sum(1 for f in out_f if f["status"] == s) for s in ("CANDIDATE", "VALIDATED", "VERIFIED", "BLOCKED", "REJECTED")}
            state["summary"] = by
            return (f"{len(out_f)} finding(s): " + ", ".join(f"{v} {k}" for k, v in by.items() if v) if out_f else "0 findings: nothing passed all gates",
                    by)
        timed(8, s9)

        state["status"] = "COMPLETED"
    except RunBlocked as exc:
        state["status"] = "BLOCKED"
        state["error"] = str(exc)
        idx = max((s["step"] for s in steps), default=1) - 1
        step(min(idx, len(STEPS) - 1), "FAILED", f"RESULT BLOCKED FROM VERIFIED STATUS: {exc}")
        try:
            ledger.append("INTEGRITY_ALERT", {"run_id": run_id, "dataset_id": dataset_id, "detail": str(exc)}, artifact_hashes=[])
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001 - report, never hide
        state["status"] = "FAILED"
        state["error"] = f"{type(exc).__name__}: {exc}"
        state["traceback"] = traceback.format_exc()
        idx = max((s["step"] for s in steps), default=1) - 1
        step(min(idx, len(STEPS) - 1), "FAILED", state["error"])

    res = state.get("res")
    return {
        "run_id": run_id, "dataset_id": dataset_id, "status": state["status"], "error": state.get("error"),
        "params": params, "config_hash": chash, "dataset_hash": state.get("dataset_hash"),
        "result_hash": state.get("result_hash"), "ledger_block": state.get("run_block"),
        "src_tree_hash": (state.get("manifest") or {}).get("src_tree_hash"),
        "steps": steps, "summary": state.get("summary", {}), "security": state.get("security"),
        "replay": state.get("replay"), "findings": [_public(f) for f in state.get("findings", [])],
        "stage_counts": res["stage_counts"] if res else None,
        "pairs": ([{k: v for k, v in p.items() if k != "surface"} for p in res["pairs"]] if res else None),
        "consistency": state.get("consistency"), "runtime_s": time.time() - t_run, "track": spec.track,
        "provenance": spec.provenance,
    }


def _public(f: dict) -> dict:
    f = dict(f)
    f.pop("_robustness", None)
    return f


# --------------------------------------------------------------------------------------------------
# Factorial (Track A) findings: only genes passing FDR in the discovery tissue become findings.
# --------------------------------------------------------------------------------------------------
def _factorial_findings(state: dict, spec: DatasetSpec, params: dict) -> list[dict]:
    res_d, res_r = state["res_d"], state["res_r"]
    hits = state["hits"]
    if len(hits) == 0:
        return []
    meta = state["meta"]
    Y = state["expr"].T.loc[:, hits.index]
    X = np.column_stack([np.ones(len(meta)), meta.radiation.to_numpy(float), meta.microgravity.to_numpy(float),
                         (meta.radiation * meta.microgravity).to_numpy(float)])
    lo, hi = factorial_bootstrap_ci(Y.to_numpy(float), X, n_boot=500, seed=params["seed"])
    rep = replicate(res_d, res_r, params["alpha"], params["alpha"], TA.EVIDENCE_LEVEL)
    flags = rep.get("flags", pd.Series(dtype=bool))
    fs = []
    for gene, ci_lo, ci_hi in zip(hits.index, lo, hi):
        r = hits.loc[gene]
        replicated = bool(flags.get(gene, False))
        fid = sha256_obj({"dataset_hash": state["dataset_hash"], "gene": gene, "config": params})[:12]
        both = abs(r.b_AB) >= get_settings().min_abs_effect and not (ci_lo < 0 < ci_hi)
        fs.append({
            "id": fid, "track": spec.track, "provenance": spec.provenance, "evidence_level": TA.EVIDENCE_LEVEL,
            "dataset_ids": [spec.id], "dataset_hashes": {spec.id: state["dataset_hash"]}, "stressors": ["radiation", "hindlimb_unloading"],
            "feature": str(gene), "type": r["type"],
            "effect": {"b_AB": float(r.b_AB), "ci_low": float(ci_lo), "ci_high": float(ci_hi), "cohens_d": float(r.cohens_d_int)},
            "stats": {"p": float(r.p_AB), "q": float(r.q_AB), "n": int(len(meta)), "df": float(r.df)},
            "methods": {"parametric": True, "gbm": False, "nid": False},
            "replication": {"evidence_level": TA.EVIDENCE_LEVEL, "n_shared": int(rep["n_shared"]), "concordance": rep["concordance"],
                            "replicated": replicated, "replication_rate": float(rep["replication_rate"]),
                            "detail": "Same animals, two tissues: a consistency check, not independent replication."},
            "security": state["security"], "surface": None, "config": params, "history": [], "gates": [],
            # Only the parametric test is applicable to a 21-sample 2x2 design (tree/neural models are not fitted).
            "min_abs_effect": get_settings().min_abs_effect, "_robustness": 1.0,
            "status": "VALIDATED" if both else "CANDIDATE",
        })
    return fs
