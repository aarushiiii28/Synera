"""Data file SHA-256 manifest manager, run manifest generator, and provenance auditor."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synera_core.provenance.hashing import sha256_file, sha256_obj
from synera_core.provenance.ledger import Block, Ledger


def register_file(
    ledger: Ledger,
    path: str | Path,
    kind: str = "dataset",
    meta: dict[str, Any] | None = None,
    manifest_path: str | Path = "data/MANIFEST.json",
) -> tuple[str, Block]:
    """Compute sha256 of file, append registration block to ledger, and update manifest.

    Idempotent: if artifact hash already exists in the ledger, reuses existing block.

    Args:
        ledger: The active Ledger instance.
        path: Path to target file.
        kind: 'dataset' or 'model'.
        meta: Metadata dictionary.
        manifest_path: Path to MANIFEST.json file.

    Returns:
        Tuple of (sha256_hex, Block).
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_hash = sha256_file(file_path)

    # Determine canonical block type
    if kind.upper() in ("MODEL", "MODEL_REGISTERED"):
        block_type = "MODEL_REGISTERED"
    else:
        block_type = "DATASET_REGISTERED"

    # Idempotency check: see if ledger already holds this artifact hash
    existing = ledger.find_by_artifact(file_hash)
    if existing:
        block = existing[0][0]
    else:
        payload = {
            "path": file_path.as_posix(),
            "sha256": file_hash,
            "kind": kind,
            "meta": meta or {},
        }
        block = ledger.append(
            block_type=block_type,
            payload=payload,
            artifact_hashes=[file_hash],
        )

    # Update manifest file
    m_path = Path(manifest_path)
    manifest_data: dict[str, Any] = {
        "version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "files": {},
    }
    if m_path.is_file():
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                if "files" not in manifest_data:
                    manifest_data["files"] = {}
        except (json.JSONDecodeError, OSError):
            manifest_data = {
                "version": "1.0.0",
                "generated_at": datetime.now(UTC).isoformat(),
                "files": {},
            }

    manifest_data["files"][file_path.as_posix()] = {
        "sha256": file_hash,
        "kind": kind,
        "block_index": block.index,
        "meta": meta or {},
    }
    manifest_data["generated_at"] = datetime.now(UTC).isoformat()

    m_path.parent.mkdir(parents=True, exist_ok=True)
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True, ensure_ascii=False)

    return file_hash, block


def verify_manifest(
    ledger: Ledger,
    manifest_path: str | Path = "data/MANIFEST.json",
) -> list[dict[str, Any]]:
    """Verify each manifest entry against on-disk file hash AND ledger record.

    Returns:
        List of dicts: {path, expected, actual, ok, ledger_block}
    """
    m_path = Path(manifest_path)
    if not m_path.is_file():
        return []

    with open(m_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    entries = manifest_data.get("files", {})
    results: list[dict[str, Any]] = []

    for path_str, val in entries.items():
        if isinstance(val, dict):
            expected = val.get("sha256")
        else:
            expected = str(val)

        p = Path(path_str)
        if p.is_file():
            actual: str | None = sha256_file(p)
        else:
            actual = None

        matches = ledger.find_by_artifact(expected) if expected else []
        ledger_block = matches[0][0] if matches else None

        ok = bool(actual is not None and expected and actual == expected and ledger_block is not None)

        results.append(
            {
                "path": path_str,
                "expected": expected,
                "actual": actual,
                "ok": ok,
                "ledger_block": ledger_block,
            }
        )

    return results


def _hash_directory_tree(dir_path: Path) -> str:
    """Compute deterministic SHA-256 over directory tree contents and relative paths."""
    if not dir_path.is_dir():
        return sha256_obj({})

    files = sorted([p for p in dir_path.rglob("*") if p.is_file() and "__pycache__" not in p.parts])
    tree_items: list[tuple[str, str]] = []
    for f in files:
        rel = f.relative_to(dir_path).as_posix()
        tree_items.append((rel, sha256_file(f)))
    return sha256_obj(tree_items)


def build_run_manifest(
    config: dict[str, Any],
    dataset_hashes: list[str] | dict[str, str],
    model_hashes: list[str] | dict[str, str],
    seed: int | None = None,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    """Build deterministic computational run manifest capturing complete environment and inputs."""
    root = Path(repo_root)

    # Git commit hash
    git_commit = "nogit"
    try:
        git_commit = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
            )
            .decode("utf-8")
            .strip()
        )
    except (subprocess.SubprocessError, OSError):
        pass

    # Source code tree hash
    src_dir = root / "src" / "synera_core"
    src_tree_hash = _hash_directory_tree(src_dir)

    # Configs directory hash
    configs_dir = root / "configs"
    configs_hash = _hash_directory_tree(configs_dir)

    # pyproject.toml hash
    pyproject_file = root / "pyproject.toml"
    pyproject_hash = sha256_file(pyproject_file) if pyproject_file.is_file() else ""

    # Python & key library versions
    def _pkg_version(mod_name: str) -> str:
        try:
            mod = __import__(mod_name)
            return str(getattr(mod, "__version__", "installed"))
        except ImportError:
            return "not-installed"

    env_versions = {
        "python": sys.version.split()[0],
        "numpy": _pkg_version("numpy"),
        "pandas": _pkg_version("pandas"),
        "scipy": _pkg_version("scipy"),
        "cryptography": _pkg_version("cryptography"),
        "scikit-learn": _pkg_version("sklearn"),
    }

    manifest = {
        "git_commit": git_commit,
        "src_tree_hash": src_tree_hash,
        "configs_hash": configs_hash,
        "pyproject_hash": pyproject_hash,
        "env_versions": env_versions,
        "seed": seed,
        "dataset_hashes": dataset_hashes,
        "model_hashes": model_hashes,
        "config": config,
    }
    return manifest


def compute_result_hash(manifest: dict[str, Any], outputs_digest: str) -> str:
    """Compute deterministic result hash binding run manifest to outputs."""
    return sha256_obj({"manifest": manifest, "outputs_digest": outputs_digest})


# Backward compatibility helpers
def generate_manifest(data_root: Path | str) -> dict[str, Any]:
    """Scan directory and generate SHA-256 manifest for all contained files."""
    root = Path(data_root)
    files_map: dict[str, str] = {}
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file() and path.name != "MANIFEST.json":
                rel = path.relative_to(root).as_posix()
                files_map[rel] = sha256_file(path)

    return {
        "version": "1.0.0",
        "file_count": len(files_map),
        "files": files_map,
    }


def save_manifest(manifest_data: dict[str, Any], output_path: Path | str) -> None:
    """Save manifest dictionary to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True)
