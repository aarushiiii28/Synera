import pandas as pd
import numpy as np
from pathlib import Path
import json
import time
from synera_core.benchmark.generator import generate_benchmark
from synera_core.discovery.continuous import continuous_interaction
from synera_core.security.poisoning import scan_dataset
from synera_core.config import find_repo_root

def evaluate_benchmark(seeds=50, snrs=[1.0, 2.0, 5.0], out_dir=None):
    if out_dir is None:
        out_dir = find_repo_root() / "artifacts" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # We will test all pairs of continuous variables in the features list
    features = ["heat_index", "pm25", "rh", "o3", "drought_index", "pm10", "no2", "uv", "wind", "precip"]
    pairs = []
    for i in range(len(features)):
        for j in range(i+1, len(features)):
            pairs.append((features[i], features[j]))
            
    for snr in snrs:
        for seed in range(seeds):
            start_t = time.time()
            data_path, truth_path = generate_benchmark(snr=snr, seed=seed, n_per_city=50) # smaller n for speed
            
            df = pd.read_parquet(data_path)
            with open(truth_path) as f:
                truth = json.load(f)
                
            true_pairs = set()
            true_types = {}
            for t in truth['interactions']:
                pair = tuple(sorted([t['var1'], t['var2']]))
                true_pairs.add(pair)
                true_types[pair] = t['type']
                
            hits = []
            predictions = {}
            
            # Run discovery
            for v1, v2 in pairs:
                res = continuous_interaction("outcome", v1, v2, df)
                res['p_F'] = min(res['p_bilinear'], res['p_nonlinear']) if not np.isnan(res['p_bilinear']) and not np.isnan(res['p_nonlinear']) else 1.0
                predictions[(v1, v2)] = res
                
            # Multiple testing correction
            p_vals = [res['p_F'] for res in predictions.values()]
            from synera_core.validation.multitest import bh_fdr
            q_vals = bh_fdr(np.array(p_vals))
            
            for i, (v1, v2) in enumerate(pairs):
                predictions[(v1, v2)]['q_F'] = q_vals[i]
                if q_vals[i] < 0.05:
                    hits.append(tuple(sorted([v1, v2])))
                    
            hits_set = set(hits)
            
            tp = len(hits_set.intersection(true_pairs))
            fp = len(hits_set - true_pairs)
            fn = len(true_pairs - hits_set)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            fdr = fp / (tp + fp) if (tp + fp) > 0 else 0.0
            
            # Type classification accuracy (only on TPs)
            type_correct = 0
            for pair in hits_set.intersection(true_pairs):
                pred_type = predictions[pair]['type']
                if pred_type == true_types[pair] or (true_types[pair] in ["SYNERGISTIC", "ANTAGONISTIC"] and pred_type == "bilinear") or (true_types[pair] == "NONLINEAR" and pred_type == "nonlinear"):
                    type_correct += 1
            type_acc = type_correct / tp if tp > 0 else 0.0
            
            runtime = time.time() - start_t
            
            results.append({
                "snr": snr,
                "seed": seed,
                "precision": precision,
                "recall": recall,
                "fdr": fdr,
                "type_acc": type_acc,
                "runtime": runtime
            })
            
    df_res = pd.DataFrame(results)
    
    # Poisoning robustness sweep
    poison_results = []
    print("Running poisoning sweep...")
    snr = 2.0
    for poison_frac in [0.0, 0.01, 0.05, 0.10, 0.20]:
        for seed in range(5):
            data_path, _ = generate_benchmark(snr=snr, seed=seed+100, n_per_city=50)
            df = pd.read_parquet(data_path)
            
            # Inject outliers
            n_poison = int(len(df) * poison_frac)
            if n_poison > 0:
                idx = np.random.choice(df.index, n_poison, replace=False)
                df.loc[idx, 'outcome'] += np.random.normal(0, 10, n_poison) * np.std(df['outcome'])
                
            report = scan_dataset(df)
            detected = report.status != "CLEAN"
            
            poison_results.append({
                "poison_frac": poison_frac,
                "seed": seed,
                "detected": detected
            })
            
    out = {
        "benchmark_summary": df_res.groupby("snr").mean().to_dict(orient="index"),
        "poison_summary": pd.DataFrame(poison_results).groupby("poison_frac").mean().to_dict(orient="index")
    }
    
    with open(out_dir / "benchmark.json", "w") as f:
        json.dump(out, f, indent=2)
        
    print(f"Saved benchmark results to {out_dir / 'benchmark.json'}")
    return out

if __name__ == "__main__":
    evaluate_benchmark(seeds=5, snrs=[1.0, 2.0, 5.0]) # reduced seeds for time
