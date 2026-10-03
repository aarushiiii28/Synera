import pandas as pd
import numpy as np
from pathlib import Path
import json
import time
from synera_core.benchmark.generator import generate_benchmark
import statsmodels.formula.api as smf
from synera_core.benchmark.generator import generate_benchmark
from synera_core.security.poisoning import scan_dataset
from synera_core.config import find_repo_root

def block_bootstrap_p(df, v1, v2, model, n_boot=200):
    # simple moving block bootstrap by city
    boot_stats = []
    cities = df['city'].unique()
    for _ in range(n_boot):
        boot_df = pd.concat([df[df['city']==c].sample(frac=1.0, replace=True) for c in cities])
        try:
            m = smf.ols(model.formula, data=boot_df).fit()
            boot_stats.append(m.f_pvalue) # approx
        except:
            pass
    if len(boot_stats) == 0: return 1.0
    return np.mean(np.array(boot_stats) < model.f_pvalue)

def evaluate_benchmark(seeds=50, snrs=[1.0, 2.0, 5.0], out_dir=None):
    if out_dir is None:
        out_dir = find_repo_root() / "artifacts" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    features = ["heat_index", "pm25", "rh", "o3", "drought_index", "pm10", "no2", "uv", "wind", "precip"]
    pairs = []
    for i in range(len(features)):
        for j in range(i+1, len(features)):
            pairs.append((features[i], features[j]))
            
    for snr in snrs:
        for seed in range(seeds):
            start_t = time.time()
            data_path, truth_path = generate_benchmark(snr=snr, seed=seed, n_per_city=20)
            
            df = pd.read_parquet(data_path)
            with open(truth_path) as f:
                truth = json.load(f)
                
            true_pairs = set()
            true_types = {}
            for t in truth['interactions']:
                pair = tuple(sorted([t['var1'], t['var2']]))
                true_pairs.add(pair)
                true_types[pair] = t['type']
                
            hits_naive = []
            hits_full = []
            
            predictions = {}
            for v1, v2 in pairs:
                # 1. Naive continuous_interaction
                from synera_core.discovery.continuous import continuous_interaction
                res = continuous_interaction("outcome", v1, v2, df)
                p_naive = min(res['p_bilinear'], res['p_nonlinear']) if not np.isnan(res['p_bilinear']) and not np.isnan(res['p_nonlinear']) else 1.0
                
                # 2. Full Stack
                # HAC robust
                m1, m2 = res['models'][1], res['models'][2]
                try:
                    # HAC test for bilinear interaction
                    hac_m1 = m1.get_robustcov_results(cov_type='HAC', maxlags=1)
                    p_hac = hac_m1.pvalues.get("A:B", 1.0)
                except:
                    p_hac = 1.0
                    
                # Effect size gate
                effect_size = np.max(np.abs(res['z_gap']))
                pass_effect = effect_size > 0.5
                
                # Second opinions (stubs / proxies)
                from synera_core.discovery.gbm_interactions import run_gbm_interactions
                from synera_core.discovery.neural import run_neural_interactions
                gbm_res = run_gbm_interactions(df[[v1, v2]], df['outcome'])
                nn_res = run_neural_interactions(df[[v1, v2]], df['outcome'])
                
                # Combine
                p_full = max(p_naive, p_hac) # require both
                
                predictions[(v1, v2)] = {
                    "p_naive": p_naive,
                    "p_full": p_full,
                    "pass_effect": pass_effect,
                    "type": res['type']
                }
                
            # Multiple testing correction
            from synera_core.validation.multitest import bh_fdr
            q_naive = bh_fdr(np.array([predictions[p]["p_naive"] for p in pairs]))
            q_full = bh_fdr(np.array([predictions[p]["p_full"] for p in pairs]))
            
            for i, pair in enumerate(pairs):
                if q_naive[i] < 0.05:
                    hits_naive.append(pair)
                if q_full[i] < 0.05 and predictions[pair]["pass_effect"]:
                    hits_full.append(pair)
                    
            def calc_metrics(hits, label):
                hits_set = set(hits)
                tp = len(hits_set.intersection(true_pairs))
                fp = len(hits_set - true_pairs)
                fn = len(true_pairs - hits_set)
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                fdr = fp / (tp + fp) if (tp + fp) > 0 else "n/a"
                
                type_correct = 0
                for pair in hits_set.intersection(true_pairs):
                    pred_type = predictions[pair]['type']
                    if pred_type == true_types[pair] or (true_types[pair] in ["SYNERGISTIC", "ANTAGONISTIC"] and pred_type == "bilinear") or (true_types[pair] == "NONLINEAR" and pred_type == "nonlinear"):
                        type_correct += 1
                type_acc = type_correct / tp if tp > 0 else 0.0
                return {"precision": precision, "recall": recall, "fdr": fdr, "type_acc": type_acc, "power": recall}
                
            res_naive = calc_metrics(hits_naive, "naive")
            res_full = calc_metrics(hits_full, "full")
            
            runtime = time.time() - start_t
            
            results.append({
                "snr": snr,
                "seed": seed,
                "naive_precision": res_naive["precision"],
                "naive_recall": res_naive["recall"],
                "naive_fdr": res_naive["fdr"],
                "full_precision": res_full["precision"],
                "full_recall": res_full["recall"],
                "full_fdr": res_full["fdr"],
                "full_type_acc": res_full["type_acc"],
                "runtime": runtime
            })
            
    df_res = pd.DataFrame(results)
    
    # Poisoning robustness sweep
    poison_results = []
    print("Running poisoning sweep...")
    snr = 2.0
    for poison_frac in [0.01, 0.05, 0.10, 0.20]:
        for seed in range(5):
            data_path, _ = generate_benchmark(snr=snr, seed=seed+100, n_per_city=20)
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
            
    # false alarm on 100 clean seeds
    false_alarms = 0
    for seed in range(100):
        data_path, _ = generate_benchmark(snr=2.0, seed=seed+500, n_per_city=20)
        df = pd.read_parquet(data_path)
        report = scan_dataset(df)
        if report.status != "CLEAN":
            false_alarms += 1
            
    out = {
        "benchmark_summary": df_res.groupby("snr").mean(numeric_only=True).to_dict(orient="index"),
        "poison_summary": pd.DataFrame(poison_results).groupby("poison_frac").mean(numeric_only=True).to_dict(orient="index"),
        "false_alarm_rate": false_alarms / 100.0
    }
    
    with open(out_dir / "benchmark.json", "w") as f:
        json.dump(out, f, indent=2)
        
    print(f"Saved benchmark results to {out_dir / 'benchmark.json'}")
    return out

if __name__ == "__main__":
    evaluate_benchmark(seeds=5, snrs=[1.0, 2.0, 5.0]) # reduced seeds for time
