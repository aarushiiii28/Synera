"""Data harmonization, alignment, and matrix standardizer.

Harmonizes heterogeneous multi-stressor measurements onto consistent coordinate
frames and standardized data matrices.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple
import numpy as np
import zipfile

import pandas as pd
from synera_core.provenance.manifest import register_file
from synera_core.provenance.ledger import Ledger
from synera_core.config import find_repo_root

def standardize_matrix(
    df: pd.DataFrame,
    feature_cols: list[str],
    impute_strategy: str = "median",
) -> pd.DataFrame:
    """Standardize numeric feature columns using robust scaling.

    Args:
        df: Input pandas DataFrame.
        feature_cols: List of column names to standardize.
        impute_strategy: Strategy to handle missing values ('median' or 'zero').

    Returns:
        DataFrame with standardized feature columns.
    """
    result = df.copy()
    for col in feature_cols:
        if col not in result.columns:
            continue
        series = result[col].astype(float)
        if impute_strategy == "median":
            series = series.fillna(series.median())
        else:
            series = series.fillna(0.0)

        std = series.std()
        if std > 0:
            result[col] = (series - series.mean()) / std
        else:
            result[col] = series - series.mean()
    return result

def harmonize_osdr(
    study_id: str,
    raw_counts_path: Path,
    metadata_path: Path,
    ledger: Ledger,
    design: str = "factorial"
) -> Tuple[Path, Path, Path]:
    """
    Harmonize OSDR transcriptomics data into standard SYNERA format.
    
    Args:
        study_id: e.g., 'OSD-379'
        raw_counts_path: Path to the raw gene expression counts or normalized data.
        metadata_path: Path to the ISA metadata mapping samples to factors.
        ledger: Provenance ledger.
        design: "factorial" (real 2x2) or "cross_study_contrast".
        
    Returns:
        Paths to (expr_parquet, meta_parquet, qc_json)
    """
    print(f"Harmonizing {study_id} with design={design}...")
    
    out_dir = find_repo_root() / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    expr_path = out_dir / f"osdr_{study_id}_expr.parquet"
    meta_path = out_dir / f"osdr_{study_id}_meta.parquet"
    qc_path = out_dir / f"osdr_{study_id}_qc.json"
    
    # Check for manual files first
    manual_dir = find_repo_root() / "data" / "raw" / "manual" / "osdr" / study_id
    counts_file = None
    isa_zip = None
    
    from synera_core.config import load_settings
    settings = load_settings()
    variant = settings.get('osdr_expression_variant', 'rRNArm')
    
    if manual_dir.exists():
        for p in manual_dir.iterdir():
            if variant == 'rRNArm' and "Normalized_Counts_rRNArm_GLbulkRNAseq.csv" in p.name:
                counts_file = p
            elif variant == 'Normalized_Counts' and "Normalized_Counts_GLbulkRNAseq.csv" in p.name and "rRNArm" not in p.name:
                counts_file = p
            elif "Normalized_Counts" in p.name and counts_file is None:
                counts_file = p
            elif p.name.endswith(".zip") and "-ISA" in p.name:
                isa_zip = p
                
    if counts_file and isa_zip:
        print(f"Using manual files from {manual_dir}, variant: {counts_file.name}")
        raw_counts_path = counts_file
        metadata_path = isa_zip
    else:
        if not raw_counts_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Missing files for {study_id}. Cannot harmonize.")

    # 1. Read Expression data
    expr_df = pd.read_csv(raw_counts_path, index_col=0)
    
    data_type = "unknown"
    if "Normalized" in raw_counts_path.name:
        data_type = "normalized_counts"
        expr_df = np.log2(expr_df + 1)
        print("Data is normalized RNA-Seq counts. Applied log2(x+1).")
    elif "Unnormalized" in raw_counts_path.name:
        data_type = "raw_counts"
        cpm = expr_df.div(expr_df.sum(axis=0), axis=1) * 1e6
        expr_df = np.log2(cpm + 1)
        print("Data is raw RNA-Seq counts. Applied log2(CPM+1).")
    else:
        data_type = "microarray"
        print("Data assumed to be microarray (already log2). Keeping as is.")

    # 2. Read Metadata from ISA zip
    s_df = None
    if str(metadata_path).endswith('.zip'):
        with zipfile.ZipFile(metadata_path) as z:
            for name in z.namelist():
                if name.startswith('s_') and name.endswith('.txt'):
                    with z.open(name) as f:
                        s_df = pd.read_csv(f, sep='\t')
                        break
    else:
        s_df = pd.read_csv(metadata_path, sep='\t' if str(metadata_path).endswith('.txt') else ',')
        
    if s_df is None:
        raise ValueError(f"Could not find ISA sample file in {metadata_path}")
        
    # Match columns
    expr_cols = list(expr_df.columns)
    sample_names = s_df['Sample Name'].tolist()
    
    overlap = [c for c in expr_cols if c in sample_names]
    if len(overlap) != len(expr_cols):
        missing = set(expr_cols) - set(overlap)
        print(f"WARNING: some expression columns not in metadata: {missing}")
        if len(overlap) == 0:
            raise ValueError(f"CRITICAL MISMATCH: 0 overlapping sample IDs for {study_id}")
            
    expr_df = expr_df[overlap].copy()
    s_df = s_df[s_df['Sample Name'].isin(overlap)].copy()
    
    # 3. Independent Low-Expression Filter
    initial_genes = expr_df.shape[0]
    mean_log2 = expr_df.mean(axis=1)
    samples_above_1 = (expr_df >= 1.0).sum(axis=1)
    keep_mask = (mean_log2 >= 1.0) & (samples_above_1 >= 3)
    expr_df = expr_df[keep_mask]
    kept_genes = expr_df.shape[0]
    print(f"Low-expression filter: kept {kept_genes} / {initial_genes} genes (dropped {initial_genes - kept_genes}).")
    
    # Parse Factors
    rad_col = next((c for c in s_df.columns if 'Ionizing Radiation' in c), None)
    grav_col = next((c for c in s_df.columns if 'Hindlimb Unloading' in c), None)
    
    if not rad_col or not grav_col:
        raise ValueError("Could not find required factor columns.")
        
    def parse_rad(x):
        x = str(x).lower().strip()
        if x in ['non-irradiated', '0 gy', '0', 'sham', 'control', 'none']:
            return 0
        return 1
        
    def parse_grav(x):
        x = str(x).lower().strip()
        if x in ['normally loaded control', '1g', 'control', 'none', 'sham']:
            return 0
        return 1
        
    s_df['radiation'] = s_df[rad_col].apply(parse_rad)
    s_df['microgravity'] = s_df[grav_col].apply(parse_grav)
    
    counts = s_df.groupby(['radiation', 'microgravity']).size().to_dict()
    c00 = counts.get((0,0), 0)
    c10 = counts.get((1,0), 0)
    c01 = counts.get((0,1), 0)
    c11 = counts.get((1,1), 0)
    print(f"Cell sizes for {study_id}: Control={c00}, Rad={c10}, HLU={c01}, Both={c11}")
    
    if c00 != 6 or c10 != 6 or c01 != 3 or c11 != 6:
        print(f"Mismatch in expected cell sizes (6/6/3/6)! Got {c00}/{c10}/{c01}/{c11}")
        raise ValueError(f"Cell sizes do not match expected 6/6/3/6 for {study_id}")
        
    meta_df = pd.DataFrame({
        "study_id": study_id,
        "sample_id": s_df['Sample Name'],
        "organism": s_df.get('Characteristics[Organism]', "Mus musculus"),
        "tissue": "Spleen" if "211" in study_id else "Skin",
        "radiation": s_df['radiation'],
        "radiation_type": s_df[rad_col],
        "microgravity": s_df['microgravity'],
        "gravity_model": s_df[grav_col],
        "batch": "A",
        "provenance": "REAL"
    })
    meta_df = meta_df.set_index('sample_id')
    meta_df = meta_df.loc[overlap].reset_index()
    
    n_samples, n_genes = expr_df.shape[1], expr_df.shape[0]
    gene_id_type = "ENSEMBL" if str(expr_df.index[0]).startswith("ENSMUS") else "Unknown"
    
    variances = expr_df.var(axis=1)
    n_const = int((variances == 0).sum())
    
    from sklearn.decomposition import PCA
    X = expr_df.T.values
    if np.isnan(X).any():
        X = np.nan_to_num(X, nan=np.nanmean(X))
    
    pca = PCA(n_components=2)
    pc = pca.fit_transform(X)
    outliers = []
    for pc_idx in range(2):
        col = pc[:, pc_idx]
        mean, std = col.mean(), col.std()
        for i, val in enumerate(col):
            if abs(val - mean) > 3 * std:
                outliers.append(overlap[i])
    outliers = list(set(outliers))
    
    qc_report = {
        "shape": f"{n_samples} samples x {n_genes} genes",
        "gene_id_type": gene_id_type,
        "value_range": f"{expr_df.min().min():.2f} to {expr_df.max().max():.2f}",
        "n_constant_genes": n_const,
        "n_per_cell": {str(k): v for k, v in counts.items()},
        "missingness": float(expr_df.isna().mean().mean()),
        "evidence_level": "VALIDATED",
        "pca_outliers": outliers,
        "variant": counts_file.name if counts_file else "unknown",
        "genes_kept": kept_genes,
        "genes_dropped": initial_genes - kept_genes
    }
    
    print("--- QC Report ---")
    for k, v in qc_report.items():
        print(f"{k}: {v}")
    print("Head (3 genes x 3 samples):")
    print(expr_df.iloc[:3, :3])
    print("-----------------")
    
    # Save
    expr_df.to_parquet(expr_path)
    meta_df.to_parquet(meta_path)
    with open(qc_path, "w") as f:
        json.dump(qc_report, f, indent=2)
        
    # Register in ledger
    register_file(ledger, expr_path, "dataset", {"study_id": study_id, "type": "expr", "design": design})
    register_file(ledger, meta_path, "dataset", {"study_id": study_id, "type": "meta", "design": design})
    register_file(ledger, qc_path, "qc_report", {"study_id": study_id})
    
    return expr_path, meta_path, qc_path
