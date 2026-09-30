"""Merkle tree implementation for batch artifact provenance verification."""

from __future__ import annotations

import hashlib
from typing import List, Optional


def compute_merkle_root(leaf_hashes: List[str]) -> str:
    """Compute Merkle tree root hash from a list of leaf SHA-256 hashes.

    Args:
        leaf_hashes: List of hexadecimal SHA-256 strings.

    Returns:
        Hexadecimal string of Merkle root digest.
    """
    if not leaf_hashes:
        return hashlib.sha256(b"").hexdigest()

    current_level = sorted(leaf_hashes)
    while len(current_level) > 1:
        next_level: List[str] = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            combined = hashlib.sha256(
                bytes.fromhex(left) + bytes.fromhex(right)
            ).hexdigest()
            next_level.append(combined)
        current_level = next_level

    return current_level[0]
