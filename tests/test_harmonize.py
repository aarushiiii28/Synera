import json
import zipfile
import pytest
import pandas as pd
import numpy as np

from synera_core.data.harmonize import harmonize_osdr
from synera_core.provenance.ledger import Ledger

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
        
    # Run harmonization into a temporary directory (never into the real data/processed).
    # A fake study id guarantees no manual files are picked up.
    out_dir = tmp_path / "data" / "processed"
    expr_out, meta_out, qc_out = harmonize_osdr(
        "OSD-999", counts_path, isa_path, mock_ledger, out_dir=out_dir, raw_root=tmp_path / "no_manual",
    )

    assert expr_out.parent == out_dir
    assert expr_out.exists() and meta_out.exists() and qc_out.exists()

    out_expr = pd.read_parquet(expr_out)
    out_meta = pd.read_parquet(meta_out)

    # The filter drops low-expression genes; every kept gene comes from the input file.
    assert out_expr.shape[1] == 21
    assert set(out_expr.index) <= set(expr_df.index)
    assert len(out_meta) == 21
    assert out_meta["provenance"].eq("REAL").all()

    with open(qc_out, "r") as f:
        qc = json.load(f)
    assert qc["n_per_cell"] == {"rad=0,hlu=0": 6, "rad=1,hlu=0": 6, "rad=0,hlu=1": 3, "rad=1,hlu=1": 6}
    assert "evidence_level" not in qc


def test_harmonize_rejects_thin_cells(tmp_path, mock_ledger):
    names = [f"S_C_{i}" for i in range(4)] + [f"S_H_{i}" for i in range(4)] + [f"S_R_{i}" for i in range(4)] + ["S_B_0"]
    pd.DataFrame(np.random.rand(5, len(names)) * 100, index=[f"ENSMUSG0000000000{i}" for i in range(5)], columns=names) \
        .to_csv(tmp_path / "GLDS-998_rna_seq_Normalized_Counts_GLbulkRNAseq.csv")
    s_txt = "Source Name\tSample Name\tFactor Value[Hindlimb Unloading]\tFactor Value[Ionizing Radiation]\n"
    for s in names:
        hlu = "Hindlimb Unloaded" if ("_H_" in s or "_B_" in s) else "Normally Loaded Control"
        rad = "gamma" if ("_R_" in s or "_B_" in s) else "non-irradiated"
        s_txt += f"Source\t{s}\t{hlu}\t{rad}\n"
    with zipfile.ZipFile(tmp_path / "OSD-998_metadata_OSD-998-ISA.zip", "w") as zf:
        zf.writestr("s_OSD-998.txt", s_txt)
    with pytest.raises(ValueError, match="every 2x2 cell"):
        harmonize_osdr("OSD-998", tmp_path / "GLDS-998_rna_seq_Normalized_Counts_GLbulkRNAseq.csv",
                       tmp_path / "OSD-998_metadata_OSD-998-ISA.zip", mock_ledger,
                       out_dir=tmp_path / "data" / "processed", raw_root=tmp_path / "no_manual")
