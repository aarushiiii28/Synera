"""Live India readings -> the existing SYNERA engine.

Two parts of the engine take a live reading:

1. **Scenario model** (``synera_core.prediction.scenario``): the ridge model learned from real US weekly deaths, weather and air pollution. It works in anomalies,
   so an Indian city is expressed against its own normal (``climatology``). The result is an average, population-level association learned in the US and
   transferred in standardised units: indicative, never a statement about any person, and not validated for India. Its out-of-sample skill and how many of its
   interaction terms stand out from chance are returned with every answer, because they decide how much weight it deserves.
2. **Track D findings** (``VALIDATED`` / ``VERIFIED`` on real Indian grid data): heat x humidity interactions on electricity demand. Their stored response
   surfaces are evaluated at the city's conditions in the state's own standardised units, exactly as the risk module does for Track B.

Neither replaces the official thresholds in ``guidelines``; the recommendations say which of the two a statement rests on.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from synera_core.config import find_repo_root
from synera_core.india import climatology as clim
from synera_core.prediction.scenario import _terms_for, predict, week_of_year


@lru_cache(maxsize=1)
def scenario_model(outcome: str = "all") -> dict | None:
    p = find_repo_root() / "artifacts" / "results" / f"scenario_model_{outcome}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@lru_cache(maxsize=4)
def _grid_panel(name: str) -> pd.DataFrame | None:
    p = find_repo_root() / "data" / "processed" / f"{name}_panel.parquet"
    return pd.read_parquet(p) if p.exists() else None


def _pair_term(model: dict, a: str, b: str) -> int | None:
    for i, t in enumerate(model["terms"]):
        if t["kind"] == "product" and {t["a"], t["b"]} == {a, b}:
            return i
    return None


def scenario_for_city(city: dict, w: dict, a: dict | None, history: dict | None, today: pd.Timestamp) -> dict[str, Any]:
    """The scenario model evaluated for the city's current week. ``available`` False (with the reason) when it cannot be done honestly."""
    model = scenario_model("all")
    if model is None:
        return {"available": False, "reason": "the scenario model file is not built (python scripts/build_scenario_model.py)"}
    if not history:
        return {"available": False, "reason": "no climatology for this city (history download unavailable), so conditions cannot be compared with its normal"}
    norm = clim.normals(history, today)
    live = clim.live_week(w, a, today)
    z, left_out = clim.anomalies(live, norm)
    if "heat_index" not in z and "pm25" not in z:
        return {"available": False, "reason": "neither heat nor PM2.5 could be placed against the city's normal"}
    woy = int(week_of_year(pd.Series([today]))[0])
    names = model["stressors"]
    flat = lambda v: [float(v)] * 52                                                      # noqa: E731 - a constant week-of-year curve
    loc = {"clim": {s: flat(norm[s]["mean"] if s in norm else 0.0) for s in names}, "sd": {s: float(norm[s]["sd"]) if s in norm else 1.0 for s in names},
           "expected_deaths": flat(1.0), "support": [999] * 52}
    m = {**model, "locations": {"IN": loc}}
    res = predict(m, "IN", woy, anomalies=z)
    zz = np.array([res["anomalies"][s] for s in names])
    season = (loc["clim"]["heat_index"][woy] - model["season"]["mean"]) / model["season"]["sd"]
    d = _terms_for(zz, season)
    coef, boot = np.array(model["coef"]), np.array(model["boot"]) / np.array(model["scale"])
    terms = []
    for i, t in enumerate(model["terms"]):
        if t["kind"] != "product" or d[i] == 0:
            continue
        c = float(d[i] * coef[i])
        draws = boot[:, i] * d[i]
        lo, hi = float(np.percentile(draws, 5)), float(np.percentile(draws, 95))
        terms.append({"a": t["a"], "b": t["b"], "label": f"{model['labels'][t['a']]} x {model['labels'][t['b']]}", "contribution_pct": c, "lo_pct": lo, "hi_pct": hi,
                      "supported": bool(lo > 0 or hi < 0), "z_a": float(zz[names.index(t["a"])]), "z_b": float(zz[names.index(t["b"])])})
    terms.sort(key=lambda t: -abs(t["contribution_pct"]))
    ic, v = model["interaction_check"], model["validation"]
    return {
        "available": True, "outcome": "weekly deaths from all causes, versus a typical week, as learned in 46 US states (2014-2019)",
        "week_of_year": woy + 1, "anomalies": {s: round(float(res["anomalies"][s]), 2) for s in names}, "live_week": {k: (None if x is None else round(x, 2)) for k, x in live.items()},
        "normals": {k: {"mean": round(x["mean"], 2), "sd": round(x["sd"], 2), "n": x["n"]} for k, x in norm.items() if k != "_tmax" and x},
        "effect_pct": res["effect_pct"], "lo_pct": res["lo_pct"], "hi_pct": res["hi_pct"], "additive_pct": res["additive_pct"], "interaction_pct": res["interaction_pct"],
        "interaction_lo_pct": res["interaction_lo_pct"], "interaction_hi_pct": res["interaction_hi_pct"], "contributions": {s: round(float(x), 4) for s, x in res["contributions"].items()},
        "interaction_terms": terms, "supported_interactions": [t for t in terms if t["supported"]],
        "left_at_normal": left_out, "extrapolation": {"unusual_combination": res["support"]["unusual"], "max_abs_anomaly": res["support"]["max_abs_anomaly"]},
        "model_skill": {"r2_leave_states_out": v["leave_states_out"]["with_interactions"], "calibration_slope": v["calibration_slope"], "calibration_slope_ci": v["calibration_slope_ci"],
                        "interaction_pairs_tested": ic["pairs_tested"], "interaction_pairs_excluding_zero": ic["pairs_excluding_zero"], "expected_by_chance": ic["expected_by_chance"],
                        "training": model["training"], "ledger_block": model["dataset"]["ledger_block"], "dataset_sha256": model["dataset"]["sha256"]},
        "caveats": ["Learned from US data, transferred to this city in standardised units: indicative, not validated for India.",
                    "An average association for a population, not a forecast for any person.", "Weekly conditions, not a single day's peak."],
    }


# ---- Track D ------------------------------------------------------------------------------------------------------------
SUPPORT_DAYS = 30
def _interp(surface: dict, key: str) -> RegularGridInterpolator:
    return RegularGridInterpolator((np.asarray(surface["grid_b"]), np.asarray(surface["grid_a"])), np.asarray(surface[key]), bounds_error=False, fill_value=None)


def grid_stress(state: str, today_values: dict[str, float | None], findings: list[dict]) -> dict[str, Any]:
    """Evaluate the stored heat x humidity surfaces of REAL Track D findings at today's conditions for ``state``.
    ``findings``: dicts with id, status, dataset_id, stressors, surface, effect. Only pairs whose two stressors are available live are used (tmax, rh)."""
    usable = [f for f in findings if f.get("surface") and f["status"] in ("VALIDATED", "VERIFIED") and f.get("provenance") == "REAL" and set(f["stressors"]) <= {"tmax", "rh"}]
    out: list[dict] = []
    skipped: list[str] = []
    for f in sorted(usable, key=lambda f: f["status"] != "VERIFIED"):
        panel = _grid_panel(f["dataset_id"])
        if panel is None or state not in set(panel["city"]):
            continue
        g = panel[panel["city"] == state]
        a, b = f["surface"]["a"], f["surface"]["b"]
        if any(today_values.get(x) is None for x in (a, b)):
            continue
        # The stored surfaces are on the panel's physical units (tmax in deg C, rh in %), whatever their label says, so they are evaluated there.
        mu, sd = {x: float(g[x].mean()) for x in (a, b)}, {x: float(g[x].std()) for x in (a, b)}
        za, zb = (today_values[a] - mu[a]) / sd[a], (today_values[b] - mu[b]) / sd[b]
        # The fitted surface is wild where there is no data (its corners reach tens of SD), so it is only read where the state has real history:
        # at least SUPPORT_DAYS days within half a usual deviation of today's pair.
        near = int(((g[a] - today_values[a]).abs() <= 0.5 * sd[a]).mul(((g[b] - today_values[b]).abs() <= 0.5 * sd[b])).sum())
        if near < SUPPORT_DAYS:
            skipped.append(f"{state}'s history has only {near} days near today's {a} and {b}, too few to read the learned surface (needs {SUPPORT_DAYS})")
            continue
        gap = _interp(f["surface"], "z_gap")
        up = float(gap(np.array([[today_values[b], today_values[a]]]))[0])
        hist = gap(np.column_stack([g[b].to_numpy(), g[a].to_numpy()]))
        hist = hist[np.isfinite(hist)]
        pct = float((hist <= up).mean()) if len(hist) and np.isfinite(up) else None
        y_sd = float(panel["outcome"].std())
        out.append({"finding_id": f["id"], "status": f["status"], "dataset_id": f["dataset_id"], "stressors": [a, b], "type": f.get("type"), "z": {a: round(za, 2), b: round(zb, 2)},
                    "uplift_sd": None if not np.isfinite(up) else up, "uplift_pp": None if not np.isfinite(up) else up * y_sd, "state_percentile": pct, "days_nearby": near,
                    "replication": f.get("evidence_level"), "outcome": "% above the state's own expected electricity supplied (Grid-India daily supply)",
                    "inside_surface": bool(np.isfinite(up)), "state": state})
    if not out:
        return {"available": False, "reason": skipped[0] if skipped else f"{state} is not one of the 16 states in the Indian grid panels, or no verified heat x humidity finding applies"}
    return {"available": True, "results": out}
