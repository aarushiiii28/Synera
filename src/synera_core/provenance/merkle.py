"""Domain-separated Merkle tree implementation with inclusion proofs."""

from __future__ import annotations

import hashlib


def _leaf(h_hex: str) -> bytes:
    """Domain-separated leaf hashing (0x00 prefix) to prevent second-preimage attacks."""
    return hashlib.sha256(b"\x00" + bytes.fromhex(h_hex)).digest()


def _node(left: bytes, r: bytes) -> bytes:
    """Domain-separated internal node hashing (0x01 prefix) to prevent second-preimage attacks."""
    return hashlib.sha256(b"\x01" + left + r).digest()


def merkle_root(hashes: list[str]) -> str:
    """Compute domain-separated Merkle tree root hash from a list of hexadecimal hashes.

    If empty list is provided, returns sha256("").
    """
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    level = [_leaf(h) for h in hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0].hex()


def merkle_proof(hashes: list[str], index: int) -> list[tuple[str, str]]:
    """Generate Merkle audit path (proof) for leaf at given index.

    Returns:
        List of (side, sibling_hash_hex) tuples where side is 'L' (left) or 'R' (right).
    """
    if index < 0 or index >= len(hashes):
        raise IndexError(f"Index {index} out of range for hashes list of length {len(hashes)}")
    level = [_leaf(h) for h in hashes]
    proof: list[tuple[str, str]] = []
    idx = index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sib = idx ^ 1
        proof.append(("R" if sib > idx else "L", level[sib].hex()))
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        idx //= 2
    return proof


def verify_proof(leaf_hash: str, proof: list[tuple[str, str]], root: str) -> bool:
    """Verify that leaf_hash belongs to Merkle tree with given root using proof."""
    cur = _leaf(leaf_hash)
    for side, h in proof:
        s = bytes.fromhex(h)
        cur = _node(cur, s) if side == "R" else _node(s, cur)
    return cur.hex() == root


# Backward compatibility alias
compute_merkle_root = merkle_root
