import os
import hashlib
from pathlib import Path
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import register_file
from synera_core.config import find_repo_root

repo_root = find_repo_root()
db_path = repo_root / "artifacts" / "synera.db"
key_path = repo_root / "configs" / "signer.key"
ledger = Ledger(db_path, key_path)

manual_dir = repo_root / "data" / "raw" / "manual" / "osdr"

for study_id in ["OSD-211", "OSD-237"]:
    study_dir = manual_dir / study_id
    if not study_dir.exists():
        continue
    for p in study_dir.iterdir():
        if p.is_file():
            size = p.stat().st_size
            sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
            print(f"File: {p.name}, Size: {size} bytes, SHA256: {sha256}")
            register_file(ledger, p, kind="raw_data", meta={"study_id": study_id, "provenance": "REAL"})
