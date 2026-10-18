"""Write frontend/src/tests/fixtures/scenario_parity.json: a small model fitted on SYNTHETIC data plus the answers the Python code
gives for a set of scenarios. The vitest suite checks the TypeScript evaluator against it, and tests/test_scenario.py checks Python.

    python scripts/make_scenario_fixture.py
"""
from __future__ import annotations

import json

from synera_core.config import find_repo_root
from synera_core.prediction import synthetic
from synera_core.prediction.scenario import fit_scenario_model, predict


def main() -> None:
    model = fit_scenario_model(synthetic.make_test_panel(n_weeks=240), {"outcome": {"id": "all", "label": "Synthetic", "unit": "%"},
                                                                         "dataset": {"id": "synthetic"}}, n_boot=40)
    states = list(model["locations"])
    cases = []
    for state, woy, anomalies in (
        (states[0], 8, {}), (states[0], 30, {"pm25": 2.0}), (states[1], 12, {"pm25": 1.5, "o3": 2.0}),
        (states[2], 40, {"heat_index": 3.0, "pm25": 1.0, "wind": -1.0}), (states[3], 51, {s: 1.0 for s in model["stressors"]}),
        (states[4], 0, {"heat_index": -2.5, "rh": 1.0}), (states[5], 25, {"o3": 4.0, "no2": 2.0, "pm10": -1.0}),
    ):
        loc = model["locations"][state]
        levels = {s: loc["clim"][s][woy] + a * loc["sd"][s] for s, a in anomalies.items()}
        e = predict(model, state, woy, levels)
        cases.append({"state": state, "woy": woy, "levels": levels, "expected": {k: e[k] for k in (
            "effect_pct", "lo_pct", "hi_pct", "additive_pct", "interaction_pct", "interaction_lo_pct", "interaction_hi_pct", "extra_deaths_per_week")}})
    out = find_repo_root() / "frontend" / "src" / "tests" / "fixtures" / "scenario_parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": model, "cases": cases}, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} KB, {len(cases)} cases)")


if __name__ == "__main__":
    main()
