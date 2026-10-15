"""Benchmark generator and the security detectors: each detector can fire on an obvious case and stays quiet on clean data."""
import numpy as np
import pandas as pd

from synera_core.benchmark.generator import generate_benchmark
from synera_core.security.poisoning import Baseline, scan_dataset
from synera_core.security.tamper_sim import simulate_attack  # noqa: F401  (import check; behaviour is in test_tamper.py)


def test_benchmark_generator(tmp_path):
    out_path, truth_path = generate_benchmark(out_dir=tmp_path, seed=42, n_per_city=10)
    assert out_path.exists() and truth_path.exists()
    df = pd.read_parquet(out_path)
    assert "outcome" in df.columns and (df["provenance"] == "SIMULATED").all()


def test_clean_benchmark_is_not_compromised(tmp_path):
    out_path, _ = generate_benchmark(out_dir=tmp_path, seed=42, n_per_city=50)
    report = scan_dataset(pd.read_parquet(out_path))
    assert report.status in ["CLEAN", "SUSPICIOUS"]          # z-scored columns are not judged against physical-unit ranges


def test_detector_physical_range():
    df = pd.DataFrame({"temp_c": [20.0, 22.1, 19.5, 23.0, 21.0]})
    ranges = {"temp_c": (-50, 60)}
    assert {c["name"]: c["status"] for c in scan_dataset(df, ranges=ranges).checks}["physical_range"] == "PASS"
    poisoned = df.assign(temp_c=df["temp_c"] * 1.8 + 32 + 40)           # Fahrenheit-as-Celsius drift pushes values out of range
    rep = scan_dataset(poisoned, ranges=ranges)
    assert {c["name"]: c["status"] for c in rep.checks}["physical_range"] == "FAIL" and rep.status == "COMPROMISED"


def test_range_check_is_skipped_for_empty_ranges_dict():
    z = pd.DataFrame({"rh": np.random.default_rng(0).normal(size=200)})   # z-scores: negative "humidity"
    assert "physical_range" not in {c["name"] for c in scan_dataset(z, ranges={}).checks}
    assert "physical_range" not in {c["name"] for c in scan_dataset(z).checks}      # median at the range edge -> not physical units


def test_detector_isolation_forest():
    rng = np.random.default_rng(42)
    baseline = {"X_matrix": rng.normal(0, 1, (500, 2))}
    df = pd.DataFrame({"x": rng.normal(0, 1, 100), "y": rng.normal(0, 1, 100)})
    assert {c["name"]: c["status"] for c in scan_dataset(df, baseline=baseline).checks}["isolation_forest"] == "PASS"
    bad = df.copy()
    bad.iloc[:20, 0] = bad.iloc[:20, 0] * 10 + 50
    assert {c["name"]: c["status"] for c in scan_dataset(bad, baseline=baseline).checks}["isolation_forest"] == "WARN"


def test_detector_mcd():
    rng = np.random.default_rng(42)
    df = pd.DataFrame(rng.normal(0, 1, (100, 5)))
    assert {c["name"]: c["status"] for c in scan_dataset(df).checks}["mcd"] == "PASS"
    bad = df.copy()
    bad.iloc[:20] = bad.iloc[:20] * 10 + 50
    assert {c["name"]: c["status"] for c in scan_dataset(bad).checks}["mcd"] == "WARN"


def test_detector_ks_drift():
    rng = np.random.default_rng(42)
    baseline = {"var1": {"sample": rng.normal(0, 1, 500).tolist()}}
    assert {c["name"]: c["status"] for c in scan_dataset(pd.DataFrame({"var1": rng.normal(0, 1, 100)}), baseline=baseline).checks}["distribution_drift"] == "PASS"
    assert {c["name"]: c["status"] for c in scan_dataset(pd.DataFrame({"var1": rng.normal(5, 2, 100)}), baseline=baseline).checks}["distribution_drift"] == "WARN"


def test_detector_label_flip():
    rng = np.random.default_rng(42)
    X = np.vstack([rng.normal(0, 1, (50, 2)), rng.normal(10, 1, (50, 2))])
    y = np.array([0] * 50 + [1] * 50)
    df = pd.DataFrame(X, columns=["f1", "f2"])
    assert {c["name"]: c["status"] for c in scan_dataset(df, meta=pd.DataFrame({"label": y})).checks}["label_flip"] == "PASS"
    yp = y.copy()
    yp[rng.choice(100, 20, replace=False)] ^= 1
    assert {c["name"]: c["status"] for c in scan_dataset(df, meta=pd.DataFrame({"label": yp})).checks}["label_flip"] == "WARN"


def test_label_flip_reports_when_labels_have_no_structure():
    rng = np.random.default_rng(1)
    df = pd.DataFrame(rng.normal(size=(120, 4)))
    rep = scan_dataset(df, meta=pd.DataFrame({"label": rng.integers(0, 2, 120)}))
    c = next(c for c in rep.checks if c["name"] == "label_flip")
    assert c["status"] == "PASS" and "cannot be informative" in c["detail"]


def test_statistical_detectors_never_block_on_their_own():
    rng = np.random.default_rng(3)
    base = Baseline.from_frame(pd.DataFrame(rng.normal(size=(600, 4)), columns=list("abcd")))
    bad = pd.DataFrame(rng.normal(size=(600, 4)) * 6 + 9, columns=list("abcd"))
    rep = scan_dataset(bad, baseline=base)
    assert rep.status == "SUSPICIOUS"                         # advisory warnings, but not COMPROMISED
    assert all(c["status"] != "FAIL" for c in rep.checks if not c["blocking"])
