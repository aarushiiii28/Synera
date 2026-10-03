"""Part 4 diagnostics script."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from synera_core.discovery.interactions import factorial_interaction
from synera_core.validation.multitest import bh_fdr
from synera_core.config import find_repo_root

repo_root = find_repo_root()

def run_diagnostics():
    print("=== SYNERA Part 4 Diagnostics ===")
    
    # 1. Positive controls on real OSD-211 and OSD-237
    for study in ["OSD-211", "OSD-237"]:
        print(f"\\n--- {study} Positive Controls ---")
        expr = pd.read_parquet(repo_root / f"data/processed/osdr_{study}_expr.parquet")
        meta = pd.read_parquet(repo_root / f"data/processed/osdr_{study}_meta.parquet")
        meta = meta.set_index('sample_id').loc[expr.columns].reset_index()
        
        res = factorial_interaction(expr.T, meta, 'radiation', 'microgravity')
        q_A = bh_fdr(2 * stats.t.sf(np.abs(res['b_A'] / (res['sigma'] * np.sqrt(1/12))), res['df'])) # rough approx for t-stat, actually wait...
        # The interactions.py doesn't return se_A or p_A. 
        # I'll just re-calculate it using statsmodels for all features? No, that's slow.
        # Let's extract the correct p-values from the design matrix.
        
        A = meta['radiation'].to_numpy(float)
        B = meta['microgravity'].to_numpy(float)
        X = np.column_stack([np.ones_like(A), A, B, A * B])
        XtX_inv = np.linalg.pinv(X.T @ X)
        
        se_A = np.sqrt(XtX_inv[1, 1] * (res['sigma']**2))
        se_B = np.sqrt(XtX_inv[2, 2] * (res['sigma']**2))
        
        t_A = res['b_A'] / se_A
        t_B = res['b_B'] / se_B
        
        p_A = 2 * stats.t.sf(np.abs(t_A), res['df'])
        p_B = 2 * stats.t.sf(np.abs(t_B), res['df'])
        
        q_A = bh_fdr(p_A)
        q_B = bh_fdr(p_B)
        
        hits_A = (q_A < 0.05).sum()
        hits_B = (q_B < 0.05).sum()
        print(f"Radiation (b_A) hits at q<0.05: {hits_A}")
        print(f"HLU (b_B) hits at q<0.05: {hits_B}")
        
        if hits_A < 5 or hits_B < 5:
            print(f"WARNING: Hits are near zero for {study}. Checking sample labels...")
            for _, row in meta.iterrows():
                sample_col = 'sample_id' if 'sample_id' in row else 'index'
                print(f"Sample: {row[sample_col]}, Rad: {row['radiation']}, HLU: {row['microgravity']}")
            
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2)
        X = expr.T.values
        if np.isnan(X).any():
            X = np.nan_to_num(X, nan=np.nanmean(X))
        pc = pca.fit_transform(X)
        
        plt.figure(figsize=(6,4))
        colors = []
        for i, row in meta.iterrows():
            if row['radiation'] == 0 and row['microgravity'] == 0: colors.append('green')
            elif row['radiation'] == 1 and row['microgravity'] == 0: colors.append('red')
            elif row['radiation'] == 0 and row['microgravity'] == 1: colors.append('blue')
            else: colors.append('purple')
        plt.scatter(pc[:,0], pc[:,1], c=colors)
        plt.title(f"PCA colored by group ({study})")
        plt.savefig(repo_root / f"artifacts/pca_{study}.png")
        print(f"Saved {study} PCA to artifacts/pca_{study}.png")
                
        # 4. Report the 20 genes with smallest interaction p-value
        res['p_A'] = p_A
        res['p_B'] = p_B
        res['q_A'] = q_A
        res['q_B'] = q_B
        res['q_AB'] = bh_fdr(res['p_AB'])
        
        top20 = res.sort_values('p_AB').head(20)
        print(f"\\nTop 20 genes for {study} (smallest interaction p-value):")
        print(top20[['b_AB', 'p_AB', 'q_AB']])
        
        plt.figure(figsize=(6, 4))
        plt.hist(res['p_AB'].dropna(), bins=50, color='blue', alpha=0.7)
        plt.title(f"Interaction p-value Histogram ({study})")
        plt.savefig(repo_root / f"artifacts/pvals_{study}.png")
        print(f"Saved {study} histogram to artifacts/pvals_{study}.png")
        
    # 2. Null calibration: 200 permutations on OSD-211
    print(f"\\n--- Null Calibration (200 permutations) ---")
    expr = pd.read_parquet(repo_root / f"data/processed/osdr_OSD-211_expr.parquet")
    meta = pd.read_parquet(repo_root / f"data/processed/osdr_OSD-211_meta.parquet")
    meta = meta.set_index('sample_id').loc[expr.columns].reset_index()
    
    rng = np.random.default_rng(42)
    all_p_null = []
    hits_per_perm = []
    
    for _ in range(200):
        # Permute within the 2x2 structure (actually it just says permute labels)
        meta_perm = meta.copy()
        
        # Keep exact cell sizes by shuffling the combined group labels
        groups = list(zip(meta['radiation'], meta['microgravity']))
        rng.shuffle(groups)
        
        meta_perm['rad_perm'] = [g[0] for g in groups]
        meta_perm['grav_perm'] = [g[1] for g in groups]
        
        res_null = factorial_interaction(expr.T, meta_perm, 'rad_perm', 'grav_perm')
        p_vals = res_null['p_AB'].dropna().values
        q_vals = bh_fdr(p_vals)
        hits = (q_vals < 0.05).sum()
        hits_per_perm.append(hits)
        all_p_null.extend(p_vals)
        
    all_p_null = np.array(all_p_null)
    # Histogram
    plt.figure(figsize=(6, 4))
    plt.hist(all_p_null, bins=10, color='orange', edgecolor='black')
    plt.title("Pooled Null p-value Histogram (200 perms)")
    plt.savefig(repo_root / "artifacts/null_pooled_hist.png")
    
    # KS test against uniform
    ks_stat, ks_p = stats.kstest(all_p_null, 'uniform')
    
    mean_hits = np.mean(hits_per_perm)
    frac_any_hits = np.mean(np.array(hits_per_perm) > 0)
    print(f"KS stat against uniform: {ks_stat:.4f} (p={ks_p:.4g})")
    print(f"Mean hits at q<0.05 per permutation: {mean_hits:.4f}")
    print(f"Fraction of perms with >= 1 hit: {frac_any_hits:.4f}")
    
    # 3. Power check (Minimum detectable effect)
    print(f"\\n--- Power Check (MDE) ---")
    
    for effect_size in [0.5, 1.0, 1.5]:
        expr_sim = expr.copy()
        
        # Pick 200 random genes
        rng_sim = np.random.default_rng(42)
        target_genes = rng_sim.choice(expr_sim.index, 200, replace=False)
        
        # Spike interaction
        # We need the true A and B
        A_true = meta['radiation'].values
        B_true = meta['microgravity'].values
        interaction_term = A_true * B_true
        
        for g in target_genes:
            expr_sim.loc[g] += effect_size * interaction_term
            
        res_sim = factorial_interaction(expr_sim.T, meta, 'radiation', 'microgravity')
        q_sim = bh_fdr(res_sim['p_AB'].values)
        res_sim['q_AB'] = q_sim
        
        hits_sim = (res_sim.loc[target_genes, 'q_AB'] < 0.05).sum()
        recovery = hits_sim / 200.0
        print(f"Spike b_AB = {effect_size:.1f}: Recovery rate at q<0.05 = {recovery:.4f}")

if __name__ == "__main__":
    run_diagnostics()
