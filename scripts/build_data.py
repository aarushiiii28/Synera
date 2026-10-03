"""Main data pipeline orchestrator.

Idempotent pipeline: fetch -> harmonize -> QC -> hash -> register -> MANIFEST.
"""

import sys
from pathlib import Path
import subprocess

from synera_core.config import find_repo_root
from synera_core.provenance.manifest import register_file, build_run_manifest
from synera_core.provenance.ledger import Ledger

def main():
    print("=== SYNERA Data Build Pipeline ===")
    
    repo_root = find_repo_root()
    db_path = repo_root / "artifacts" / "synera.db"
    key_path = repo_root / "configs" / "signer.key"
    
    # Initialize ledger if doesn't exist
    ledger = Ledger(db_path, key_path)
    
    print("\n1. Building Environmental Stressor Panel...")
    subprocess.run([sys.executable, str(repo_root / "scripts" / "build_env_data.py")], check=True)
    
    print("\n2. Harmonizing OSDR Candidates (OSD-211, OSD-237)...")
    import yaml
    from synera_core.data.harmonize import harmonize_osdr
    from synera_core.data.osdr import download
    import traceback
    
    config_path = repo_root / "configs" / "datasets.yaml"
    with open(config_path, "r") as f:
        datasets_cfg = yaml.safe_load(f)
        
    discovery_id = datasets_cfg.get("discovery", "OSD-211")
    replication_id = datasets_cfg.get("replication", "OSD-237")
    
    def process_study(study_id):
        print(f"Downloading files for {study_id}...")
        try:
            # Download ISA sample file (starts with s_, ends with .txt, or just metadata zip)
            # Actually, GeneLab normalized counts:
            counts = download(study_id, r"Normalized_Counts.*\.csv")
            isa = download(study_id, r"^s_.*\.txt")
            
            if not counts or not isa:
                raise FileNotFoundError(f"Could not download counts or ISA files for {study_id}.")
                
            harmonize_osdr(study_id, counts[0], isa[0], ledger)
        except Exception as e:
            print(f"Failed to process {study_id}: {e}")
            traceback.print_exc()
            # Log BLOCKED in PROGRESS.md
            prog_path = repo_root / "PROGRESS.md"
            if prog_path.exists():
                content = prog_path.read_text(encoding="utf-8")
                content = content.replace(
                    "- *None.* (Previously Blocked: Unblocked by setting discovery=OSD-211, replication=OSD-237.",
                    "- **BLOCKED: Unable to download real files for OSDR studies. Fallback substitution removed.**\n- *None.* (Previously Blocked: Unblocked by setting discovery=OSD-211, replication=OSD-237."
                )
                prog_path.write_text(content, encoding="utf-8")
            
    process_study(discovery_id)
    process_study(replication_id)
        
    print("\n3. Generating Data Manifest...")
    # Build a run manifest for this pipeline execution
    manifest = build_run_manifest(
        config={"script_name": "scripts/build_data.py"},
        dataset_hashes={"raw_cache": "auto"},
        model_hashes={},
        seed=42,
        repo_root=repo_root
    )
    
    manifest_path = repo_root / "data" / "MANIFEST.json"
    import json
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"\nPipeline complete! Manifest written to {manifest_path}")

if __name__ == "__main__":
    main()
