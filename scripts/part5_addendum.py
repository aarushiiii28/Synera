import pandas as pd
import numpy as np
from scipy import stats
import zipfile
from synera_core.config import find_repo_root
from synera_core.validation.multitest import bh_fdr
from synera_core.benchmark.generator import generate_benchmark
from synera_core.discovery.interactions import factorial_interaction

repo_root = find_repo_root()

def fit_additive(expr, meta, moderate=True, use_lib_size=False):
    A = meta['radiation'].to_numpy(float)
    B = meta['microgravity'].to_numpy(float)
    if use_lib_size:
        lib = np.log2(meta['lib_size'].values + 1)
        X = np.column_stack([np.ones_like(A), A, B, lib])
    else:
        X = np.column_stack([np.ones_like(A), A, B])
        
    XtX_inv = np.linalg.pinv(X.T @ X)
    Yv = expr.values
    beta = XtX_inv @ X.T @ Yv.T
    
    resid = Yv.T - (X @ beta)
    df_res = len(meta) - X.shape[1]
    s2 = (resid ** 2).sum(axis=0) / df_res
    
    if moderate:
        # Estimate prior_df and prior_var using method of moments on s2
        # E(s2) = prior_var
        # Var(s2) = 2 * prior_var^2 / prior_df
        # So prior_df = 2 * E(s2)^2 / Var(s2)
        s2_mean = np.mean(s2)
        s2_var = np.var(s2)
        prior_df = 2 * (s2_mean**2) / (s2_var + 1e-9)
        prior_var = s2_mean
        
        # Limit prior_df to reasonable bounds to avoid extreme shrinkage
        prior_df = np.clip(prior_df, 0.1, 100)
        
        s2_t = (prior_df * prior_var + df_res * s2) / (prior_df + df_res)
        d = df_res + prior_df
    else:
        s2_t = s2
        d = df_res
        
    se_A = np.sqrt(XtX_inv[1, 1] * s2_t)
    se_B = np.sqrt(XtX_inv[2, 2] * s2_t)
    
    with np.errstate(divide="ignore", invalid="ignore"):
        t_A = beta[1] / se_A
        t_B = beta[2] / se_B
        
    p_A = 2 * stats.t.sf(np.abs(t_A), d)
    p_B = 2 * stats.t.sf(np.abs(t_B), d)
    
    return p_A, p_B, beta[1], beta[2], (prior_df if moderate else None), (prior_var if moderate else None)

def main():
    print("=== ADDENDUM ===")
    
    # Tasks 1 & 2
    for study in ["OSD-211", "OSD-237"]:
        print(f"\\n--- {study} ---")
        expr = pd.read_parquet(repo_root / f"data/processed/osdr_{study}_expr.parquet")
        meta = pd.read_parquet(repo_root / f"data/processed/osdr_{study}_meta.parquet")
        sample_col = 'sample_id' if 'sample_id' in meta.columns else 'index'
        meta = meta.set_index(sample_col).loc[expr.columns].reset_index(names='sample_id')
        
        lib_sizes = (2**expr - 1).sum(axis=0)
        meta['lib_size'] = lib_sizes.values
        
        # Fixed prior (from Part 4)
        pA_mod_fixed, pB_mod_fixed, _, _ = _fit_additive_fixed_prior(expr, meta)
        
        # Estimated prior
        pA_est, pB_est, _, _, df_est, var_est = fit_additive(expr, meta, moderate=True, use_lib_size=False)
        print(f"Estimated prior df: {df_est:.2f}, prior var: {var_est:.4f}")
        
        qA_f = bh_fdr(pA_mod_fixed); qB_f = bh_fdr(pB_mod_fixed)
        qA_e = bh_fdr(pA_est); qB_e = bh_fdr(pB_est)
        
        print(f"Fixed Prior - Rad hits: {np.sum(qA_f<0.05)}, HLU hits: {np.sum(qB_f<0.05)}")
        print(f"Est Prior   - Rad hits: {np.sum(qA_e<0.05)}, HLU hits: {np.sum(qB_e<0.05)}")
        
        # Covariate: lib_size
        pA_lib, pB_lib, _, _, _, _ = fit_additive(expr, meta, moderate=True, use_lib_size=True)
        qA_lib = bh_fdr(pA_lib); qB_lib = bh_fdr(pB_lib)
        print(f"With LibSize- Rad hits: {np.sum(qA_lib<0.05)}, HLU hits: {np.sum(qB_lib<0.05)}")
        
        # Show the 9 OSD-237 skin genes mean expr and per-group read counts
        if study == "OSD-237":
            hits_idx = np.where((qA_f<0.05) | (qB_f<0.05))[0]
            genes = expr.index[hits_idx]
            print("\\nOSD-237 Hit Genes Mean Expression & Counts:")
            for g in genes:
                mean_expr = expr.loc[g].mean()
                mean_counts = (2**expr.loc[g] - 1).groupby([meta['radiation'].values, meta['microgravity'].values]).mean()
                print(f"Gene: {g}, Mean Log2: {mean_expr:.2f}, Mean Counts: {mean_counts.to_dict()}")

    # Task 3: Driver of PC1 in OSD-237
    print("\\n--- PC1 Driver OSD-237 ---")
    expr = pd.read_parquet(repo_root / "data/processed/osdr_OSD-237_expr.parquet")
    meta = pd.read_parquet(repo_root / "data/processed/osdr_OSD-237_meta.parquet")
    sample_col = 'sample_id' if 'sample_id' in meta.columns else 'index'
    meta = meta.set_index(sample_col).loc[expr.columns].reset_index(names='sample_id')
    
    from sklearn.decomposition import PCA
    pca = PCA(n_components=1)
    X = np.nan_to_num(expr.T.values)
    pc1 = pca.fit_transform(X)[:, 0]
    
    manual_dir = repo_root / "data/raw/manual/osdr/OSD-237"
    isa_zip = list(manual_dir.glob("*-ISA.zip"))[0]
    s_df = None
    with zipfile.ZipFile(isa_zip) as z:
        for name in z.namelist():
            if name.startswith('s_') and name.endswith('.txt'):
                with z.open(name) as f:
                    s_df = pd.read_csv(f, sep='\\t')
                    break
    s_df = s_df.set_index('Sample Name').loc[meta['sample_id']]
    
    best_p = 1.0
    best_col = None
    for col in s_df.columns:
        vals = s_df[col].dropna()
        if len(vals) < 5 or s_df[col].nunique() < 2: continue
        
        try:
            if pd.api.types.is_numeric_dtype(s_df[col]):
                _, p = stats.pearsonr(pc1, s_df[col].fillna(s_df[col].mean()))
            else:
                groups = [pc1[s_df[col]==c] for c in s_df[col].unique() if len(pc1[s_df[col]==c])>1]
                if len(groups) > 1:
                    _, p = stats.f_oneway(*groups)
                else:
                    p = 1.0
                    
            if p < best_p:
                best_p = p
                best_col = col
        except:
            pass
    print(f"Driver of PC1 (47% var): {best_col} (p={best_p:.4e})")

    # Task 4: Benchmark moderation on vs off
    print("\\n--- Benchmark Moderation On vs Off ---")
    data_path, _ = generate_benchmark(seed=888, n_per_city=50) # Use standard benchmark but we'll mock a 2x2
    # The prompt asks to "include a moderation-on versus moderation-off comparison for the factorial engine 
    # using a simulated 2x2 with 6/6/3/6 cells, reporting FDR and power for both."
    
    # We will generate a synthetic 2x2 dataset with 6/6/3/6 cells.
    rng = np.random.default_rng(123)
    n_genes = 5000
    n_samples = 21
    labels_A = np.array([0]*12 + [1]*9)
    labels_B = np.array([0]*6 + [1]*6 + [0]*3 + [1]*6) # 6/6/3/6
    
    Y = rng.normal(0, 1, (n_genes, n_samples))
    # Plant 100 interaction effects
    Y[:100, (labels_A==1) & (labels_B==1)] += 2.0
    
    meta_sim = pd.DataFrame({'rad': labels_A, 'grav': labels_B})
    
    res_on = factorial_interaction(pd.DataFrame(Y.T), meta_sim, 'rad', 'grav', moderate=True)
    res_off = factorial_interaction(pd.DataFrame(Y.T), meta_sim, 'rad', 'grav', moderate=False)
    
    q_on = bh_fdr(res_on['p_AB'].values)
    q_off = bh_fdr(res_off['p_AB'].values)
    
    tp_on = np.sum((q_on[:100] < 0.05))
    fp_on = np.sum((q_on[100:] < 0.05))
    tp_off = np.sum((q_off[:100] < 0.05))
    fp_off = np.sum((q_off[100:] < 0.05))
    
    power_on = tp_on / 100
    fdr_on = fp_on / (tp_on + fp_on + 1e-9)
    power_off = tp_off / 100
    fdr_off = fp_off / (tp_off + fp_off + 1e-9)
    
    print(f"Moderation ON : Power = {power_on:.2f}, FDR = {fdr_on:.2f}")
    print(f"Moderation OFF: Power = {power_off:.2f}, FDR = {fdr_off:.2f}")

def _fit_additive_fixed_prior(expr, meta):
    # original logic
    A = meta['radiation'].to_numpy(float)
    B = meta['microgravity'].to_numpy(float)
    X = np.column_stack([np.ones_like(A), A, B])
    XtX_inv = np.linalg.pinv(X.T @ X)
    Yv = expr.values
    beta = XtX_inv @ X.T @ Yv.T
    
    resid = Yv.T - (X @ beta)
    df_res = len(meta) - 3
    s2 = (resid ** 2).sum(axis=0) / df_res
    
    prior_df = 4.0
    s0 = np.nanmedian(s2)
    s2_t = (prior_df * s0 + df_res * s2) / (prior_df + df_res)
    d = df_res + prior_df
        
    se_A = np.sqrt(XtX_inv[1, 1] * s2_t)
    se_B = np.sqrt(XtX_inv[2, 2] * s2_t)
    
    t_A = beta[1] / se_A
    t_B = beta[2] / se_B
        
    p_A = 2 * stats.t.sf(np.abs(t_A), d)
    p_B = 2 * stats.t.sf(np.abs(t_B), d)
    return p_A, p_B, beta[1], beta[2]

if __name__ == "__main__":
    main()
