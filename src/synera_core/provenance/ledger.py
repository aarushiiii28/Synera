"""Permissioned, signed, hash-chained append-only evidence ledger backed by SQLite."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from synera_core.provenance.hashing import sha256_obj
from synera_core.provenance.merkle import merkle_proof, merkle_root

# Canonical block types for Synera provenance tracking
BLOCK_TYPES = {
    "GENESIS",
    "DATASET_REGISTERED",
    "MODEL_REGISTERED",
    "EXPERIMENT_RUN",
    "FINDING_VALIDATED",
    "FINDING_VERIFIED",
    "FINDING_REJECTED",
    "INTEGRITY_ALERT",
}


@dataclass(frozen=True)
class Block:
    """Immutable representation of a ledger block."""

    index: int
    timestamp: str
    block_type: str
    prev_hash: str
    merkle_root: str
    payload: dict[str, Any]
    payload_hash: str
    block_hash: str
    signature: str
    signer: str

    def to_dict(self) -> dict[str, Any]:
        """Convert block to dictionary format."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "block_type": self.block_type,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "payload": self.payload,
            "payload_hash": self.payload_hash,
            "block_hash": self.block_hash,
            "signature": self.signature,
            "signer": self.signer,
        }

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class Ledger:
    """Append-only cryptographic evidence ledger with Ed25519 signing.

    Features:
    - Domain-separated Merkle trees for batch artifact hashing
    - Cryptographic hash chaining: prev_hash -> header -> block_hash
    - Ed25519 digital signature per block over block_hash
    - SQLite append-only triggers forbidding UPDATE and DELETE
    - Concurrency-safe appends via threading.Lock + BEGIN IMMEDIATE

    Note on anchoring stretch goal:
    The head block hash can be periodically anchored to an external trust root:
    1. OpenTimestamps: calendars create Bitcoin Merkle tree proofs of timestamp existence.
    2. EVM Testnet (e.g. Sepolia): calling an anchor contract `recordHead(bytes32 blockHash)`
       to create immutable on-chain timestamps.
    """

    def __init__(self, db_path: str | Path, key_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.key_path = Path(key_path)
        self._lock = threading.Lock()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_keys()
        self._init_db()

    def _init_keys(self) -> None:
        """Load or create Ed25519 keypair with 0600 permissions."""
        if not self.key_path.exists():
            self._private_key = Ed25519PrivateKey.generate()
            pem = self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(self.key_path, "wb") as f:
                f.write(pem)
            try:
                os.chmod(self.key_path, 0o600)
            except OSError:
                pass
        else:
            with open(self.key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(f.read(), password=None)

        public_bytes = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self._signer_hex = public_bytes.hex()

    def _init_db(self) -> None:
        """Create schema and enforce append-only database triggers."""
        with sqlite3.connect(self.db_path, isolation_level=None) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS blocks (
                    block_index INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    block_type TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    merkle_root TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    block_hash TEXT NOT NULL UNIQUE,
                    signature TEXT NOT NULL,
                    signer TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_blocks_update
                BEFORE UPDATE ON blocks
                BEGIN
                    SELECT RAISE(ABORT, 'Blocks are immutable and cannot be updated');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_blocks_delete
                BEFORE DELETE ON blocks
                BEGIN
                    SELECT RAISE(ABORT, 'Blocks are immutable and cannot be deleted');
                END;
                """
            )

    @property
    def signer(self) -> str:
        """Public key hex of the ledger signer."""
        return self._signer_hex

    def append(
        self,
        block_type: str,
        payload: dict[str, Any],
        artifact_hashes: list[str] = (),
        timestamp: str | None = None,
    ) -> Block:
        """Append a new signed block to the ledger in a transaction.

        Args:
            block_type: One of canonical BLOCK_TYPES.
            payload: User dictionary payload.
            artifact_hashes: Optional list of SHA-256 artifact hashes to Merkle-root.
            timestamp: Optional UTC ISO string (defaults to current time).

        Returns:
            Newly created and verified Block instance.
        """
        with self._lock, sqlite3.connect(self.db_path, isolation_level=None, timeout=60.0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT block_index, block_hash FROM blocks ORDER BY block_index DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if row is None:
                    idx = 0
                    prev_hash = "0" * 64
                else:
                    idx = row[0] + 1
                    prev_hash = row[1]

                ts = timestamp or datetime.now(UTC).isoformat()
                full_payload = {**payload, "artifact_hashes": list(artifact_hashes)}
                m_root = merkle_root(full_payload["artifact_hashes"])
                p_hash = sha256_obj(full_payload)
                header = {
                    "index": idx,
                    "timestamp": ts,
                    "block_type": block_type,
                    "prev_hash": prev_hash,
                    "merkle_root": m_root,
                    "payload_hash": p_hash,
                }
                b_hash = sha256_obj(header)
                sig = self._private_key.sign(bytes.fromhex(b_hash)).hex()

                cursor.execute(
                    """
                    INSERT INTO blocks (
                        block_index, timestamp, block_type, prev_hash,
                        merkle_root, payload_json, payload_hash,
                        block_hash, signature, signer
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idx,
                        ts,
                        block_type,
                        prev_hash,
                        m_root,
                        json.dumps(full_payload, sort_keys=True, ensure_ascii=False),
                        p_hash,
                        b_hash,
                        sig,
                        self._signer_hex,
                    ),
                )
                conn.execute("COMMIT")
                return Block(
                    index=idx,
                    timestamp=ts,
                    block_type=block_type,
                    prev_hash=prev_hash,
                    merkle_root=m_root,
                    payload=full_payload,
                    payload_hash=p_hash,
                    block_hash=b_hash,
                    signature=sig,
                    signer=self._signer_hex,
                )
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def get(self, index: int) -> Block:
        """Retrieve block by index."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT block_index, timestamp, block_type, prev_hash, merkle_root,
                       payload_json, payload_hash, block_hash, signature, signer
                FROM blocks WHERE block_index = ?
                """,
                (index,),
            )
            row = cursor.fetchone()
            if row is None:
                raise IndexError(f"Block at index {index} not found")
            return self._row_to_block(row)

    def head(self) -> Block | None:
        """Retrieve the latest block in the chain, or None if empty."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT block_index, timestamp, block_type, prev_hash, merkle_root,
                       payload_json, payload_hash, block_hash, signature, signer
                FROM blocks ORDER BY block_index DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            return self._row_to_block(row) if row else None

    def height(self) -> int:
        """Return the current number of blocks in the ledger."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM blocks")
            return int(cursor.fetchone()[0])

    def iter_blocks(self, start: int = 0) -> Iterator[Block]:
        """Yield blocks sequentially starting from given index."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT block_index, timestamp, block_type, prev_hash, merkle_root,
                       payload_json, payload_hash, block_hash, signature, signer
                FROM blocks WHERE block_index >= ? ORDER BY block_index ASC
                """,
                (start,),
            )
            for row in cursor.fetchall():
                yield self._row_to_block(row)

    def find_by_artifact(self, artifact_hash: str) -> list[tuple[Block, list[tuple[str, str]]]]:
        """Find blocks containing artifact_hash and generate Merkle audit proofs for each."""
        matches: list[tuple[Block, list[tuple[str, str]]]] = []
        for block in self.iter_blocks():
            hashes = block.payload.get("artifact_hashes", [])
            if artifact_hash in hashes:
                idx = hashes.index(artifact_hash)
                proof = merkle_proof(hashes, idx)
                matches.append((block, proof))
        return matches

    def verify(self) -> dict[str, Any]:
        """Verify the cryptographic integrity of the entire chain.

        Checks:
        1. prev_hash linkage (PREV_HASH_MISMATCH)
        2. payload deterministic hash match (PAYLOAD_TAMPERED)
        3. Merkle root of artifact_hashes match (MERKLE_MISMATCH)
        4. block_hash header recomputation match (HASH_MISMATCH)
        5. Ed25519 digital signature validity (BAD_SIGNATURE)

        Returns:
            {"valid": bool, "height": int, "head": str | None, "issues": list[dict]}
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT block_index, timestamp, block_type, prev_hash, merkle_root,
                       payload_json, payload_hash, block_hash, signature, signer
                FROM blocks ORDER BY rowid ASC
                """
            )
            rows = cursor.fetchall()

        if not rows:
            return {"valid": True, "height": 0, "head": None, "issues": []}

        issues: list[dict[str, Any]] = []
        expected_prev = "0" * 64

        for row in rows:
            try:
                block = self._row_to_block(row)
            except ValueError:
                # A payload that no longer parses is itself tampering; report it instead of crashing.
                issues.append({"index": row[0], "code": "PAYLOAD_TAMPERED", "detail": "payload is not valid JSON"})
                expected_prev = row[7]
                continue

            # 1. Check prev_hash linkage
            if block.prev_hash != expected_prev:
                issues.append(
                    {
                        "index": block.index,
                        "code": "PREV_HASH_MISMATCH",
                        "detail": (
                            f"prev_hash '{block.prev_hash}' does not match "
                            f"expected '{expected_prev}'"
                        ),
                    }
                )

            # 2. Check payload integrity
            expected_payload_hash = sha256_obj(block.payload)
            if block.payload_hash != expected_payload_hash:
                issues.append(
                    {
                        "index": block.index,
                        "code": "PAYLOAD_TAMPERED",
                        "detail": (
                            f"payload_hash '{block.payload_hash}' != "
                            f"recomputed '{expected_payload_hash}'"
                        ),
                    }
                )

            # 3. Check Merkle root of artifact hashes
            artifacts = block.payload.get("artifact_hashes", [])
            expected_merkle_root = merkle_root(artifacts)
            if block.merkle_root != expected_merkle_root:
                issues.append(
                    {
                        "index": block.index,
                        "code": "MERKLE_MISMATCH",
                        "detail": (
                            f"merkle_root '{block.merkle_root}' != "
                            f"recomputed '{expected_merkle_root}'"
                        ),
                    }
                )

            # 4. Check block_hash recomputation
            header = {
                "index": block.index,
                "timestamp": block.timestamp,
                "block_type": block.block_type,
                "prev_hash": block.prev_hash,
                "merkle_root": block.merkle_root,
                "payload_hash": block.payload_hash,
            }
            expected_block_hash = sha256_obj(header)
            if block.block_hash != expected_block_hash:
                issues.append(
                    {
                        "index": block.index,
                        "code": "HASH_MISMATCH",
                        "detail": (
                            f"block_hash '{block.block_hash}' != "
                            f"recomputed '{expected_block_hash}'"
                        ),
                    }
                )

            # 5. Check Ed25519 digital signature
            try:
                pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(block.signer))
                pubkey.verify(bytes.fromhex(block.signature), bytes.fromhex(block.block_hash))
            except (InvalidSignature, ValueError) as e:
                issues.append(
                    {
                        "index": block.index,
                        "code": "BAD_SIGNATURE",
                        "detail": f"Signature verification failed: {e}",
                    }
                )

            expected_prev = block.block_hash

        head_block = self._row_to_block(rows[-1])
        return {
            "valid": len(issues) == 0,
            "height": len(rows),
            "head": head_block.block_hash,
            "issues": issues,
        }

    @staticmethod
    def _row_to_block(row: tuple[Any, ...]) -> Block:
        """Parse database row into Block instance."""
        return Block(
            index=row[0],
            timestamp=row[1],
            block_type=row[2],
            prev_hash=row[3],
            merkle_root=row[4],
            payload=json.loads(row[5]),
            payload_hash=row[6],
            block_hash=row[7],
            signature=row[8],
            signer=row[9],
        )


# Backward compatibility alias
ProvenanceLedger = Ledger
