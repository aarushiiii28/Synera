"""Data harmonization: OSDR transcriptomics -> SYNERA standard tables.

Every value written here is read from the downloaded study files (processed expression table and ISA
sample metadata). Nothing is hardcoded or generated: sample ids, factor labels and expression values all
come from files, expression columns are matched to ISA samples by name, and any mismatch fails loudly.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from synera_core.config import find_repo_root, get_settings
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import register_file

RADIATION_KEYS = ("ionizing radiation", "irradiat", "radiation", "dose", "gamma", "proton", "hze")
GRAVITY_KEYS = ("hindlimb unloading", "unloading", "microgravity", "spaceflight", "clinostat", "gravity")
RAD_CONTROL = {"non-irradiated", "0 gy", "0", "sham", "control", "none", "unirradiated", "not irradiated"}
GRAV_CONTROL = {"normally loaded control", "1g", "control", "none", "sham", "ground", "normally loaded"}


def standardize_matrix(df: pd.DataFrame, feature_cols: list[str], impute_strategy: str = "median") -> pd.DataFrame:
    """Z-score numeric feature columns (median or zero imputation of missing values)."""
    result = df.copy()
    for col in feature_cols:
        if col not in result.columns:
            continue
        series = result[col].astype(float)
        series = series.fillna(series.median() if impute_strategy == "median" else 0.0)
        std = series.std()
        result[col] = (series - series.mean()) / std if std > 0 else series - series.mean()
    return result


def _find_factor_col(columns: list[str], keys: tuple[str, ...]) -> str | None:
    factor_cols = [c for c in columns if c.lower().startswith("factor value")]
    for key in keys:
        for c in factor_cols:
            if key in c.lower():
                return c
    return None


def _read_isa_samples(metadata_path: Path) -> pd.DataFrame:
    if str(metadata_path).endswith(".zip"):
        with zipfile.ZipFile(metadata_path) as z:
            for name in z.namelist():
                if name.startswith("s_") and name.endswith(".txt"):
                    with z.open(name) as f:
                        return pd.read_csv(f, sep="\t")
        raise ValueError(f"No ISA sample table (s_*.txt) inside {metadata_path}")
    return pd.read_csv(metadata_path, sep="\t" if str(metadata_path).endswith(".txt") else ",")


def _animal_id(sample_name: str) -> str | None:
    """Animal id = trailing token of the sample name when it looks like an id (e.g. ``..._Rep3_M22`` -> ``M22``)."""
    tok = str(sample_name).rsplit("_", 1)[-1]
    return tok if re.fullmatch(r"[A-Za-z]{0,3}\d+", tok) else None


def _select_manual_files(manual_dir: Path, variant: str) -> tuple[Path | None, Path | None]:
    counts_file = isa_zip = None
    if not manual_dir.exists():
        return None, None
    for p in sorted(manual_dir.iterdir()):
        n = p.name
        if n.endswith(".zip") and "-ISA" in n:
            isa_zip = p
        elif "Normalized_Counts" in n and n.endswith(".csv"):
            rrna = "rRNArm" in n
            if (variant == "rRNArm" and rrna) or (variant != "rRNArm" and not rrna):
                counts_file = p
            elif counts_file is None:
                counts_file = p
    return counts_file, isa_zip


def harmonize_osdr(
    study_id: str,
    raw_counts_path: Path | None,
    metadata_path: Path | None,
    ledger: Ledger,
    design: str = "factorial",
    out_dir: Path | None = None,
    raw_root: Path | None = None,
    tissue: str | None = None,
    min_per_cell: int = 2,
) -> Tuple[Path, Path, Path]:
    """Harmonize one OSDR transcriptomics study.

    Manual files in ``data/raw/manual/osdr/<study_id>/`` take precedence over the paths passed in.
    Returns ``(expr_parquet, meta_parquet, qc_json)`` (samples as columns, genes as rows; log2 scale).
    """
    settings = get_settings()
    default_out = out_dir is None
    out_dir = out_dir or (find_repo_root() / "data" / "processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    # A custom out_dir (tests, scratch runs) gets its own manifest so the real one is never polluted.
    manifest = find_repo_root() / "data" / "MANIFEST.json" if default_out else out_dir.parent / "MANIFEST.json"
    raw_root = raw_root or (find_repo_root() / "data" / "raw" / "manual" / "osdr")
    expr_path = out_dir / f"osdr_{study_id}_expr.parquet"
    meta_path = out_dir / f"osdr_{study_id}_meta.parquet"
    qc_path = out_dir / f"osdr_{study_id}_qc.json"

    counts_file, isa_zip = _select_manual_files(raw_root / study_id, settings.osdr_expression_variant)
    if counts_file and isa_zip:
        raw_counts_path, metadata_path = counts_file, isa_zip
    elif raw_counts_path is None or metadata_path is None or not Path(raw_counts_path).exists() or not Path(metadata_path).exists():
        raise FileNotFoundError(f"Missing expression or ISA files for {study_id}; cannot harmonize.")
    raw_counts_path, metadata_path = Path(raw_counts_path), Path(metadata_path)

    # 1. Expression
    expr_df = pd.read_csv(raw_counts_path, index_col=0)
    if "Normalized" in raw_counts_path.name:
        data_type, transform = "normalized_counts", "log2(x+1)"
        expr_df = np.log2(expr_df + 1)
    elif "Unnormalized" in raw_counts_path.name or "Raw" in raw_counts_path.name:
        data_type, transform = "raw_counts", "log2(CPM+1)"
        expr_df = np.log2(expr_df.div(expr_df.sum(axis=0), axis=1) * 1e6 + 1)
    else:
        data_type, transform = "log2_values", "none (assumed already log2, e.g. microarray)"

    # 2. Metadata + strict sample matching
    s_df = _read_isa_samples(metadata_path)
    names = s_df["Sample Name"].astype(str).tolist()
    expr_cols = [str(c) for c in expr_df.columns]
    expr_df.columns = expr_cols
    missing_meta = sorted(set(expr_cols) - set(names))
    if missing_meta:
        raise ValueError(f"{study_id}: {len(missing_meta)} expression columns have no ISA metadata: {missing_meta[:5]}")
    s_df = s_df[s_df["Sample Name"].astype(str).isin(expr_cols)].copy()
    s_df["Sample Name"] = s_df["Sample Name"].astype(str)
    s_df = s_df.set_index("Sample Name").loc[expr_cols].reset_index()

    # 3. Independent low-expression filter (labels never used)
    ef = settings.expression_filter
    initial = expr_df.shape[0]
    keep = (expr_df.mean(axis=1) >= ef.min_mean_log2) & ((expr_df >= ef.min_log2).sum(axis=1) >= ef.min_samples)
    expr_df = expr_df[keep]

    # 4. Factors
    rad_col = _find_factor_col(list(s_df.columns), RADIATION_KEYS)
    grav_col = _find_factor_col(list(s_df.columns), GRAVITY_KEYS)
    if not rad_col or not grav_col:
        raise ValueError(f"{study_id}: could not find radiation and gravity factor columns in the ISA table")
    s_df["radiation"] = (~s_df[rad_col].astype(str).str.lower().str.strip().isin(RAD_CONTROL)).astype(int)
    s_df["microgravity"] = (~s_df[grav_col].astype(str).str.lower().str.strip().isin(GRAV_CONTROL)).astype(int)
    cells = s_df.groupby(["radiation", "microgravity"]).size()
    n_cell = {(int(a), int(b)): int(n) for (a, b), n in cells.items()}
    full = {(a, b): n_cell.get((a, b), 0) for a in (0, 1) for b in (0, 1)}
    if min(full.values()) < min_per_cell:
        raise ValueError(f"{study_id}: every 2x2 cell needs >= {min_per_cell} samples, got {full}")

    tissue_col = next((c for c in s_df.columns if any(k in c.lower() for k in ("organism part", "tissue"))), None)
    organism_col = next((c for c in s_df.columns if "organism" in c.lower() and "part" not in c.lower()), None)
    meta_df = pd.DataFrame({
        "study_id": study_id,
        "sample_id": s_df["Sample Name"],
        "animal_id": s_df["Sample Name"].map(_animal_id),
        "organism": s_df[organism_col] if organism_col else "unknown",
        "tissue": s_df[tissue_col] if tissue_col else (tissue or "unknown"),
        "radiation": s_df["radiation"],
        "radiation_type": s_df[rad_col],
        "microgravity": s_df["microgravity"],
        "gravity_model": s_df[grav_col],
        "provenance": "REAL",
    })

    # 5. QC
    from sklearn.decomposition import PCA

    X = expr_df.T.to_numpy(float)
    pca = PCA(n_components=min(5, X.shape[0] - 1)).fit(X)
    pc = pca.transform(X)
    outliers = sorted({expr_cols[i] for k in range(2) for i, v in enumerate(pc[:, k])
                       if abs(v - pc[:, k].mean()) > 3 * pc[:, k].std()})
    qc_report = {
        "study_id": study_id,
        "shape": f"{expr_df.shape[1]} samples x {expr_df.shape[0]} genes",
        "gene_id_type": "ENSEMBL" if str(expr_df.index[0]).startswith("ENS") else "unknown",
        "value_range": f"{float(expr_df.min().min()):.2f} to {float(expr_df.max().max()):.2f}",
        "data_type": data_type, "transform": transform,
        "n_constant_genes": int((expr_df.var(axis=1) == 0).sum()),
        "n_per_cell": {f"rad={a},hlu={b}": n for (a, b), n in full.items()},
        "missingness": float(expr_df.isna().mean().mean()),
        "pca_variance_explained": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "pca_outliers": outliers,
        "variant": raw_counts_path.name,
        "expression_filter": {"min_mean_log2": ef.min_mean_log2, "min_log2": ef.min_log2, "min_samples": ef.min_samples},
        "genes_kept": int(expr_df.shape[0]), "genes_dropped": int(initial - expr_df.shape[0]),
        "design": design, "provenance": "REAL",
        "raw_files": [raw_counts_path.name, metadata_path.name],
    }

    expr_df.to_parquet(expr_path)
    meta_df.to_parquet(meta_path)
    qc_path.write_text(json.dumps(qc_report, indent=2))

    # Provenance: raw inputs and every derived table
    for raw in (raw_counts_path, metadata_path):
        register_file(ledger, raw, "dataset", {"study_id": study_id, "type": "raw", "provenance": "REAL"}, manifest_path=manifest)
    for p, typ in ((expr_path, "expr"), (meta_path, "meta"), (qc_path, "qc")):
        register_file(ledger, p, "dataset", {"study_id": study_id, "type": typ, "design": design, "provenance": "REAL"},
                      manifest_path=manifest)
    return expr_path, meta_path, qc_path
