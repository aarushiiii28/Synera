"""Part 4 diagnostics 2 script."""

import pandas as pd
import numpy as np
from scipy import stats
from synera_core.validation.multitest import bh_fdr
from synera_core.config import find_repo_root
import json
import zipfile
from sklearn.decomposition import PCA

repo_root = find_repo_root()

def get_welch_t(expr, meta, factor):
    """Welch t-test for a binary factor."""
    group0 = expr.loc[:, (meta[factor] == 0).values].values
    group1 = expr.loc[:, (meta[factor] == 1).values].values
    # Welch t-test
    t_stat, p_val = stats.ttest_ind(group1, group0, axis=1, equal_var=False)
    log2fc = group1.mean(axis=1) - group0.mean(axis=1)
    return p_val, log2fc

def fit_additive(expr, meta, moderate=True):
    """Fit Y ~ rad + hlu (no interaction)"""
    A = meta['radiation'].to_numpy(float)
    B = meta['microgravity'].to_numpy(float)
    X = np.column_stack([np.ones_like(A), A, B])
    XtX_inv = np.linalg.pinv(X.T @ X)
    Yv = expr.values
    beta = XtX_inv @ X.T @ Yv.T  # shape: (3, n_features)
    
    resid = Yv.T - (X @ beta)
    df_res = len(meta) - 3
    s2 = (resid ** 2).sum(axis=0) / df_res
    
    if moderate:
        prior_df = 4.0
        s0 = np.nanmedian(s2)
        s2_t = (prior_df * s0 + df_res * s2) / (prior_df + df_res)
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
    
    return p_A, p_B, beta[1], beta[2]

def run():
    print("=== SYNERA Part 4 Diagnostics 2 ===\\n")
    
    for study in ["OSD-211", "OSD-237"]:
        print(f"--- {study} ---")
        expr = pd.read_parquet(repo_root / f"data/processed/osdr_{study}_expr.parquet")
        meta = pd.read_parquet(repo_root / f"data/processed/osdr_{study}_meta.parquet")
        meta = meta.set_index('sample_id').loc[expr.columns].reset_index()
        
        sample_col = 'sample_id' if 'sample_id' in meta.columns else 'index'
        # 5. Confirm alignment
        assert (expr.columns == meta[sample_col]).all(), "Alignment failed!"
        
        # Library sizes (original space counts)
        # We did log2(x+1) during harmonization. sum(2^x - 1) gives roughly original counts.
        lib_sizes = (2**expr - 1).sum(axis=0)
        meta['lib_size'] = lib_sizes.values
        grp_lib = meta.groupby(['radiation', 'microgravity'])['lib_size'].mean()
        print(f"Group-wise mean library size:\\n{grp_lib}")
        
        # 1. Overall-effect positive control (Additive)
        pA_mod, pB_mod, bA_mod, bB_mod = fit_additive(expr, meta, moderate=True)
        pA_unm, pB_unm, _, _ = fit_additive(expr, meta, moderate=False)
        
        pA_welch, fcA_welch = get_welch_t(expr, meta, 'radiation')
        pB_welch, fcB_welch = get_welch_t(expr, meta, 'microgravity')
        
        for name, pA, pB, bA, bB in [
            ("Moderated", pA_mod, pB_mod, bA_mod, bB_mod), 
            ("Unmoderated", pA_unm, pB_unm, bA_mod, bB_mod), 
            ("Welch", pA_welch, pB_welch, fcA_welch, fcB_welch)]:
            qA = bh_fdr(pA)
            qB = bh_fdr(pB)
            print(f"{name}: Rad hits={np.sum(qA<0.05)}, HLU hits={np.sum(qB<0.05)}")
            
        # Top 10 genes
        print("\\nTop 10 Rad (Moderated):")
        rad_df = pd.DataFrame({'log2FC': bA_mod, 'p': pA_mod, 'q': bh_fdr(pA_mod)}, index=expr.index)
        print(rad_df.sort_values('p').head(10))
        
        print("\\nTop 10 HLU (Moderated):")
        hlu_df = pd.DataFrame({'log2FC': bB_mod, 'p': pB_mod, 'q': bh_fdr(pB_mod)}, index=expr.index)
        print(hlu_df.sort_values('p').head(10))
        
        # 2. PCA
        pca = PCA(n_components=5)
        X = expr.T.values
        X = np.nan_to_num(X, nan=np.nanmean(X))
        pcs = pca.fit_transform(X)
        print(f"\\nPCA Var explained PC1-PC5: {pca.explained_variance_ratio_}")
        
        # Extract cage/batch if available
        # Need to read ISA zip for this
        manual_dir = repo_root / f"data/raw/manual/osdr/{study}"
        isa_zip = list(manual_dir.glob("*-ISA.zip"))[0]
        s_df = None
        with zipfile.ZipFile(isa_zip) as z:
            for name in z.namelist():
                if name.startswith('s_') and name.endswith('.txt'):
                    with z.open(name) as f:
                        s_df = pd.read_csv(f, sep='\t')
                        break
        s_df = s_df.set_index('Sample Name').loc[meta[sample_col]]
        cage_col = [c for c in s_df.columns if 'age' in c.lower() or 'batch' in c.lower() or 'housing' in c.lower()]
        if cage_col:
            meta['cage'] = s_df[cage_col[0]].values
        else:
            meta['cage'] = np.nan
            
        print("PC associations (p-values):")
        for i in range(5):
            pc = pcs[:, i]
            # rad
            _, p_rad = stats.ttest_ind(pc[meta['radiation']==1], pc[meta['radiation']==0])
            # hlu
            _, p_hlu = stats.ttest_ind(pc[meta['microgravity']==1], pc[meta['microgravity']==0])
            # lib
            slope, intercept, r, p_lib, se = stats.linregress(meta['lib_size'], pc)
            # cage
            p_cage = np.nan
            if not meta['cage'].isna().all():
                groups = [pc[meta['cage']==c] for c in meta['cage'].unique() if len(pc[meta['cage']==c])>0]
                if len(groups) > 1:
                    _, p_cage = stats.f_oneway(*groups)
            print(f"PC{i+1}: rad_p={p_rad:.4f}, hlu_p={p_hlu:.4f}, lib_p={p_lib:.4f}, cage_p={p_cage:.4f}")
            
        # 3. Diff Expr file check
        de_files = list(manual_dir.glob("*differential_expression*.csv"))
        if de_files:
            de_df = pd.read_csv(de_files[0])
            print(f"\\nFound Diff Expr file: {de_files[0].name}")
            print(f"Columns: {de_df.columns[:5].tolist()}...")
        else:
            print(f"\\nNEED USER: differential_expression csv for {study}")
            
    # 4. Null calibration corrected
    print("\\n--- Null Calibration (OSD-211) ---")
    expr = pd.read_parquet(repo_root / "data/processed/osdr_OSD-211_expr.parquet")
    meta = pd.read_parquet(repo_root / "data/processed/osdr_OSD-211_meta.parquet")
    meta = meta.set_index('sample_id').loc[expr.columns].reset_index()
    
    rng = np.random.default_rng(42)
    p05_fracs = []
    lambdas = []
    hits_list = []
    
    from synera_core.discovery.interactions import factorial_interaction
    
    for i in range(200):
        meta_perm = meta.copy()
        groups = list(zip(meta['radiation'], meta['microgravity']))
        rng.shuffle(groups)
        meta_perm['rad_perm'] = [g[0] for g in groups]
        meta_perm['grav_perm'] = [g[1] for g in groups]
        
        res_null = factorial_interaction(expr.T, meta_perm, 'rad_perm', 'grav_perm')
        p_vals = res_null['p_AB'].dropna().values
        
        # a) frac p < 0.05
        p05_frac = (p_vals < 0.05).mean()
        p05_fracs.append(p05_frac)
        
        # b) genomic inflation factor lambda
        chi2 = stats.chi2.ppf(1 - p_vals, 1)
        lambd = np.median(chi2) / stats.chi2.ppf(0.5, 1)
        lambdas.append(lambd)
        
        # hits
        q_vals = bh_fdr(p_vals)
        hits_idx = np.where(q_vals < 0.05)[0]
        for idx in hits_idx:
            gene = expr.index[idx]
            z_max = np.max(np.abs(stats.zscore(expr.loc[gene].values)))
            hits_list.append((gene, i, z_max))
            
    print(f"Mean frac raw p<0.05: {np.mean(p05_fracs):.4f}")
    print(f"Lambda median: {np.median(lambdas):.4f}, range: {np.min(lambdas):.4f} - {np.max(lambdas):.4f}")
    
    hit_genes = pd.DataFrame(hits_list, columns=['gene', 'perm', 'max_z'])
    if not hit_genes.empty:
        gene_counts = hit_genes['gene'].value_counts()
        print("\\nGenes with hits (showing top recurring):")
        print(gene_counts.head())
        print(f"Max |z| among hits: {hit_genes['max_z'].max():.2f}")
    else:
        print("\\n0 permutation hits at q<0.05!")
        
    print("Done.")

if __name__ == '__main__':
    run()
