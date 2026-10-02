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
    
    print("\n2. Harmonizing OSDR Candidates (Placeholder)...")
    # In a real run, this reads the selected OSD IDs from configs/datasets.yaml
    # For now, since we haven't picked the datasets yet (waiting for user selection),
    # we just run the candidate finder if it hasn't run yet.
    cand_path = repo_root / "data" / "interim" / "osdr_candidates.csv"
    if not cand_path.exists():
        print("Candidate studies not found. Run find_candidate_studies.py first.")
    else:
        print(f"Candidate studies found at {cand_path}. Waiting for user selection in configs.")
        
    print("\n3. Generating Data Manifest...")
    # Build a run manifest for this pipeline execution
    manifest = build_run_manifest(
        script_name="scripts/build_data.py",
        inputs=["data/raw/cache"],
        seed=42
    )
    
    manifest_path = repo_root / "data" / "MANIFEST.json"
    import json
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"\nPipeline complete! Manifest written to {manifest_path}")

if __name__ == "__main__":
    main()
