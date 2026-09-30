"""Data and file integrity verification using SHA-256 hashes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict


def compute_file_sha256(file_path: Path | str, chunk_size: int = 65536) -> str:
    """Compute cryptographic SHA-256 hash of a file.

    Args:
        file_path: Path to target file.
        chunk_size: Block size for incremental hashing.

    Returns:
        Hexadecimal string of SHA-256 digest.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Target file does not exist: {path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_file_integrity(file_path: Path | str, expected_hash: str) -> bool:
    """Check whether a file matches its expected SHA-256 digest."""
    return compute_file_sha256(file_path).lower() == expected_hash.strip().lower()
