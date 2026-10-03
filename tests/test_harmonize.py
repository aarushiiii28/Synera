import os
import json
import zipfile
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from synera_core.data.harmonize import harmonize_osdr
from synera_core.provenance.ledger import Ledger
from synera_core.config import find_repo_root

@pytest.fixture
def mock_ledger(tmp_path):
    db_path = tmp_path / "synera.db"
    key_path = tmp_path / "signer.key"
    return Ledger(db_path, key_path)

def test_harmonize_osdr_with_fixtures(tmp_path, mock_ledger):
    # Create tiny expression file
    counts_path = tmp_path / "GLDS-999_rna_seq_Normalized_Counts_GLbulkRNAseq.csv"
    
    # We must have the 21 samples required for 6/6/3/6 check, or mock the sizes.
    # Actually, the harmonization script currently hardcodes the 6/6/3/6 check:
    # "if c00 != 6 or c10 != 6 or c01 != 3 or c11 != 6: raise ValueError"
    # Let's create the 21 samples.
    
    # 6 control, 6 rad, 3 hlu, 6 both
    sample_names = []
    sample_names += [f"S_C_{i}" for i in range(6)]
    sample_names += [f"S_R_{i}" for i in range(6)]
    sample_names += [f"S_H_{i}" for i in range(3)]
    sample_names += [f"S_B_{i}" for i in range(6)]
    
    expr_df = pd.DataFrame(
        np.random.rand(5, 21) * 100,
        index=["ENSMUSG00000000001", "ENSMUSG00000000002", "ENSMUSG00000000003", "ENSMUSG00000000004", "ENSMUSG00000000005"],
        columns=sample_names
    )
    expr_df.to_csv(counts_path)
    
    # Create tiny ISA zip file
    isa_path = tmp_path / "OSD-999_metadata_OSD-999-ISA.zip"
    s_txt = "Source Name\tSample Name\tFactor Value[Hindlimb Unloading]\tFactor Value[Ionizing Radiation]\n"
    
    for s in sample_names:
        if "S_C_" in s:
            s_txt += f"Source\t{s}\tNormally Loaded Control\tnon-irradiated\n"
        elif "S_R_" in s:
            s_txt += f"Source\t{s}\tNormally Loaded Control\tcobalt-57 gamma radiation\n"
        elif "S_H_" in s:
            s_txt += f"Source\t{s}\tHindlimb Unloaded\tnon-irradiated\n"
        elif "S_B_" in s:
            s_txt += f"Source\t{s}\tHindlimb Unloaded\tcobalt-57 gamma radiation\n"
            
    with zipfile.ZipFile(isa_path, 'w') as zf:
        zf.writestr("s_OSD-999.txt", s_txt)
        
    # Run harmonization
    # Make sure we don't accidentally read manual files by using a fake study ID
    expr_out, meta_out, qc_out = harmonize_osdr("OSD-999", counts_path, isa_path, mock_ledger)
    
    assert expr_out.exists()
    assert meta_out.exists()
    assert qc_out.exists()
    
    out_expr = pd.read_parquet(expr_out)
    out_meta = pd.read_parquet(meta_out)
    
    # shape check
    assert out_expr.shape == (5, 21)
    assert len(out_meta) == 21
    
    with open(qc_out, "r") as f:
        qc = json.load(f)
    assert qc["shape"] == "21 samples x 5 genes"
    assert qc["evidence_level"] == "VALIDATED"
