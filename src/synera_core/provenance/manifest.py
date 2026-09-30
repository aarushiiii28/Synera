"""Data file SHA-256 manifest manager and auditor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any
from synera_core.security.integrity import compute_file_sha256


def generate_manifest(data_root: Path | str) -> Dict[str, Any]:
    """Scan directory and generate SHA-256 manifest for all contained files.

    Args:
        data_root: Directory to scan recursively.

    Returns:
        Manifest dictionary containing relative paths and file hashes.
    """
    root = Path(data_root)
    files_map: Dict[str, str] = {}
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file() and path.name != "MANIFEST.json":
                rel = path.relative_to(root).as_posix()
                files_map[rel] = compute_file_sha256(path)

    return {
        "version": "1.0.0",
        "file_count": len(files_map),
        "files": files_map,
    }


def save_manifest(manifest_data: Dict[str, Any], output_path: Path | str) -> None:
    """Save manifest dictionary to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True)
