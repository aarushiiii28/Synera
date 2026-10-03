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

def test_tamper_sim(tmp_path):
    out_path, _ = generate_benchmark(out_dir=tmp_path, seed=42, n_per_city=10)
    
    # Check 1: row_edit
    res_row = simulate_attack("row_edit", out_path)
    assert res_row['hash_match'] is False
    assert "RESULT BLOCKED FROM VERIFIED STATUS" in res_row['verdict']
    
    # Check 2: inject_outliers
    res_out = simulate_attack("inject_outliers", out_path)
    assert res_out['hash_match'] is False
    assert "outliers" in res_out['detections']
    
    # Check 3: drift_units
    res_drift = simulate_attack("drift_units", out_path)
    assert res_drift['hash_match'] is False
    
def test_clean_dataset(tmp_path):
    out_path, _ = generate_benchmark(out_dir=tmp_path, seed=42, n_per_city=10)
    df = pd.read_parquet(out_path)
    report = scan_dataset(df)
    # Should be clean or at most suspicious if false alarm
    assert report.status in ["CLEAN", "SUSPICIOUS"]
