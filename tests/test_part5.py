import pytest
import pandas as pd
import numpy as np
from synera_core.benchmark.generator import generate_benchmark
from synera_core.security.poisoning import scan_dataset
from synera_core.security.tamper_sim import simulate_attack

def test_benchmark_generator(tmp_path):
    out_path, truth_path = generate_benchmark(out_dir=tmp_path, seed=42, n_per_city=10)
    assert out_path.exists()
    assert truth_path.exists()
    
    df = pd.read_parquet(out_path)
    assert 'outcome' in df.columns
    assert 'provenance' in df.columns
    assert (df['provenance'] == 'SIMULATED').all()

def test_clean_dataset(tmp_path):
    out_path, _ = generate_benchmark(out_dir=tmp_path, seed=42, n_per_city=50)
    df = pd.read_parquet(out_path)
    report = scan_dataset(df)
    assert report.status in ["CLEAN", "SUSPICIOUS"]

def test_detector_physical_range():
    # Clean
    df = pd.DataFrame({"temp_c": [20.0, 22.1, 19.5, 23.0, 21.0]})
    ranges = {"temp_c": (-50, 60)}
    report_clean = scan_dataset(df, ranges=ranges)
    checks = {c["name"]: c["status"] for c in report_clean.checks}
    assert checks["physical_range"] == "PASS"
    
    # Poisoned (Fahrenheit instead of Celsius)
    df_poison = df.copy()
    df_poison["temp_c"] = df_poison["temp_c"] * 1.8 + 32  # e.g., 20C -> 68F, which is out of range if range was tighter!
    # Wait, 68 is out of (-50, 60).
    report_poison = scan_dataset(df_poison, ranges=ranges)
    checks_p = {c["name"]: c["status"] for c in report_poison.checks}
    assert checks_p["physical_range"] == "FAIL"

def test_detector_isolation_forest():
    # Clean
    np.random.seed(42)
    base = np.random.normal(0, 1, (500, 2))
    df = pd.DataFrame({"x": np.random.normal(0, 1, 100), "y": np.random.normal(0, 1, 100)})
    baseline = {"X_matrix": base}
    report_clean = scan_dataset(df, baseline=baseline)
    checks = {c["name"]: c["status"] for c in report_clean.checks}
    assert checks["isolation_forest"] == "PASS"
    
    # Poisoned (10x outliers at 20%)
    df_poison = df.copy()
    df_poison.iloc[:20, 0] = df_poison.iloc[:20, 0] * 10 + 50
    report_poison = scan_dataset(df_poison, baseline=baseline)
    checks_p = {c["name"]: c["status"] for c in report_poison.checks}
    assert checks_p["isolation_forest"] == "WARN"

def test_detector_mcd():
    # Clean
    np.random.seed(42)
    df = pd.DataFrame(np.random.normal(0, 1, (100, 5)))
    report_clean = scan_dataset(df)
    checks = {c["name"]: c["status"] for c in report_clean.checks}
    assert checks["mcd"] == "PASS"
    
    # Poisoned
    df_poison = df.copy()
    df_poison.iloc[:20] = df_poison.iloc[:20] * 10 + 50
    report_poison = scan_dataset(df_poison)
    checks_p = {c["name"]: c["status"] for c in report_poison.checks}
    assert checks_p["mcd"] == "WARN"

def test_detector_ks_drift():
    # Clean
    np.random.seed(42)
    base = np.random.normal(0, 1, 500)
    baseline = {"var1": {"sample": base.tolist()}}
    df = pd.DataFrame({"var1": np.random.normal(0, 1, 100)})
    report_clean = scan_dataset(df, baseline=baseline)
    checks = {c["name"]: c["status"] for c in report_clean.checks}
    assert checks["distribution_drift"] == "PASS"
    
    # Poisoned
    df_poison = pd.DataFrame({"var1": np.random.normal(5, 2, 100)})
    report_poison = scan_dataset(df_poison, baseline=baseline)
    checks_p = {c["name"]: c["status"] for c in report_poison.checks}
    assert checks_p["distribution_drift"] == "WARN"

def test_detector_label_flip():
    np.random.seed(42)
    # Clean: clear clusters
    X = np.vstack([np.random.normal(0, 1, (50, 2)), np.random.normal(10, 1, (50, 2))])
    y = np.array([0]*50 + [1]*50)
    df = pd.DataFrame(X, columns=["f1", "f2"])
    meta = pd.DataFrame({"label": y})
    report_clean = scan_dataset(df, meta=meta)
    checks = {c["name"]: c["status"] for c in report_clean.checks}
    assert checks["label_flip"] == "PASS"
    
    # Poisoned: flip 20%
    y_poison = y.copy()
    idx = np.random.choice(100, 20, replace=False)
    y_poison[idx] = 1 - y_poison[idx]
    meta_poison = pd.DataFrame({"label": y_poison})
    report_poison = scan_dataset(df, meta=meta_poison)
    checks_p = {c["name"]: c["status"] for c in report_poison.checks}
    assert checks_p["label_flip"] == "WARN"

def test_ar1_hac_bootstrap():
    np.random.seed(42)
    # AR(1) null with 8 cities
    n_per_city = 60
    cities = [f"c{i}" for i in range(8)]
    rho = 0.6
    
    dfs = []
    for c in cities:
        x = np.zeros(n_per_city)
        y = np.zeros(n_per_city)
        for t in range(1, n_per_city):
            x[t] = rho * x[t-1] + np.sqrt(1 - rho**2) * np.random.normal()
            y[t] = rho * y[t-1] + np.sqrt(1 - rho**2) * np.random.normal()
        dfs.append(pd.DataFrame({"A": x, "B": np.random.normal(0, 1, n_per_city), "city": c, "outcome": y}))
        
    df = pd.concat(dfs).reset_index(drop=True)
    df['sin_doy'] = 0.0
    df['cos_doy'] = 0.0
    n = len(df)
    
    from synera_core.discovery.continuous import continuous_interaction
    from scripts.part5_fixes_script import get_hac_p
    
    p_naive_list = []
    p_hac_list = []
    
    # simulate 30 null AR(1) series to get lambda
    for _ in range(30):
        y_null_list = []
        for c in cities:
            yn = np.zeros(n_per_city)
            for t in range(1, n_per_city):
                yn[t] = rho * yn[t-1] + np.sqrt(1 - rho**2) * np.random.normal()
            y_null_list.append(yn)
        df_null = df.copy()
        df_null['outcome'] = np.concatenate(y_null_list)
        res = continuous_interaction("outcome", "A", "B", df_null, covariates=["city"])
        m1 = res['models'][1]
        
        pn = m1.pvalues.get("A:B", np.nan)
        ph = get_hac_p(m1)
        if not np.isnan(pn): p_naive_list.append(pn)
        if not np.isnan(ph): p_hac_list.append(ph)
        
    from scipy.stats import chi2
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if len(p_hac_list) > 0:
            stat_hac = chi2.ppf(1 - np.array(p_hac_list), 1)
            lambda_hac = np.median(stat_hac) / 0.4549364
            assert 0.5 <= lambda_hac <= 2.0, f"HAC lambda {lambda_hac} out of bounds"
            
    # Planted effect
    df_planted = df.copy()
    df_planted['outcome'] += 2.0 * df_planted['A'] * df_planted['B']
    res = continuous_interaction("outcome", "A", "B", df_planted, covariates=["city"])
    m1 = res['models'][1]
    p_hac_planted = get_hac_p(m1)
    assert p_hac_planted < 0.05
