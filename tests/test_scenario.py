"""Scenario model: it recovers planted truth, its predictions add up, and the browser twin sees the same numbers."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from synera_core.prediction import synthetic
from synera_core.prediction.scenario import fit_scenario_model, predict

FIXTURE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "tests" / "fixtures" / "scenario_parity.json"


@pytest.fixture(scope="module")
def model():
    return fit_scenario_model(synthetic.make_test_panel(), {"outcome": {"id": "all", "label": "t", "unit": "%"}, "dataset": {"id": "synthetic"}}, n_boot=60)


def test_recovers_the_planted_pm25_and_ozone_effects(model):
    rows = {t["term"]: t for t in model["learned_terms"]}
    for term, truth in (("pm25", synthetic.PM25_EFFECT), ("o3", synthetic.O3_EFFECT)):
        # the coefficient is per standardised unit of the within-week anomaly; the planted effect is per usual deviation
        t = rows[term]
        assert t["lo"] > 0, f"{term} should be clearly positive"
        assert abs(t["coef"] - truth) < 0.25, f"{term}: recovered {t['coef']:.2f}, planted {truth}"


def test_a_typical_week_has_no_effect_and_the_pieces_add_up(model):
    st = next(iter(model["locations"]))
    zero = predict(model, st, 20)
    assert zero["effect_pct"] == 0 and zero["lo_pct"] == 0 and zero["hi_pct"] == 0
    r = predict(model, st, 20, anomalies={"pm25": 2.0, "o3": 1.5, "heat_index": 1.0})
    assert r["effect_pct"] == pytest.approx(r["additive_pct"] + r["interaction_pct"])
    assert sum(r["contributions"].values()) == pytest.approx(r["effect_pct"])
    assert r["extra_deaths_per_week"] == pytest.approx(r["effect_pct"] / 100 * r["expected_deaths_per_week"])
    assert r["lo_pct"] <= r["effect_pct"] <= r["hi_pct"] or abs(r["effect_pct"] - r["lo_pct"]) < 0.5   # bootstrap interval brackets the estimate


def test_more_pollution_means_more_deaths_in_the_planted_world(model):
    st = next(iter(model["locations"]))
    lo = predict(model, st, 10, anomalies={"pm25": 1.0})["effect_pct"]
    hi = predict(model, st, 10, anomalies={"pm25": 3.0})["effect_pct"]
    assert 0 < lo < hi


def test_unusual_combinations_are_flagged(model):
    st = next(iter(model["locations"]))
    assert not predict(model, st, 10, anomalies={"pm25": 1.0})["support"]["unusual"]
    assert predict(model, st, 10, anomalies={s: 5.0 for s in model["stressors"]})["support"]["unusual"]


def test_levels_and_anomalies_agree(model):
    st = next(iter(model["locations"]))
    loc = model["locations"][st]
    level = loc["clim"]["pm25"][10] + 2.0 * loc["sd"]["pm25"]
    a = predict(model, st, 10, levels={"pm25": level})
    b = predict(model, st, 10, anomalies={"pm25": 2.0})
    assert a["effect_pct"] == pytest.approx(b["effect_pct"])


def test_python_matches_the_browser_fixture():
    """frontend/src/tests/fixtures/scenario_parity.json holds a model and the expected answers; vitest checks the TypeScript twin
    against the same file. Regenerate it with  python scripts/make_scenario_fixture.py  after changing the model code."""
    if not FIXTURE.exists():
        pytest.skip("parity fixture not generated")
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in fx["cases"]:
        r = predict(fx["model"], case["state"], case["woy"], case.get("levels"))
        for key in ("effect_pct", "lo_pct", "hi_pct", "additive_pct", "interaction_pct", "interaction_lo_pct", "interaction_hi_pct",
                    "extra_deaths_per_week"):
            assert np.isclose(r[key], case["expected"][key], rtol=1e-9, atol=1e-9), (case, key)
