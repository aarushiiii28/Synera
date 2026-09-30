"""Comprehensive test suite for cryptographic provenance layer.

Validates:
- Deterministic canonical hashing (JSON key order, numpy types, dataframe sensitivity)
- Merkle tree roots and inclusion proofs across n=1,2,3,7,8
- Append-only signed SQLite ledger operations and Ed25519 signatures
- SQLite triggers preventing UPDATE and DELETE
- Tamper detection for all 5 threat models:
    1. edited payload
    2. edited block_hash
    3. deleted middle block
    4. swapped block order
    5. forged signature
- Concurrent writes from 8 parallel threads maintaining valid hash chain
- Manifest generation, idempotency, and verification
- IntegrityGuard detection of single-byte mutations and alert deduplication
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from synera_core.provenance.hashing import (
    canonical_json,
    sha256_bytes,
    sha256_dataframe,
    sha256_file,
    sha256_obj,
)
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import (
    build_run_manifest,
    compute_result_hash,
    register_file,
    verify_manifest,
)
from synera_core.provenance.merkle import (
    merkle_proof,
    merkle_root,
    verify_proof,
)
from synera_core.security.integrity import IntegrityGuard, guard_verified_status

# ============================================================================
# 1. Hashing Determinism Tests
# ============================================================================


def test_hashing_determinism_dict_order():
    """Ensure key insertion order does not affect canonical JSON and SHA-256."""
    d1 = {"z": 100, "a": {"b": 2, "a": 1}, "m": [3, 2, 1]}
    d2 = {"m": [3, 2, 1], "a": {"a": 1, "b": 2}, "z": 100}

    assert canonical_json(d1) == canonical_json(d2)
    assert sha256_obj(d1) == sha256_obj(d2)


def test_hashing_determinism_numpy_types():
    """Ensure NumPy scalars and arrays serialize deterministically equivalent to Python natives."""
    d_py = {
        "int": 42,
        "float": 3.14159,
        "arr": [10, 20, 30],
        "set": ["alpha", "beta"],
    }
    d_np = {
        "int": np.int64(42),
        "float": np.float64(3.14159),
        "arr": np.array([10, 20, 30]),
        "set": {"beta", "alpha"},
    }

    assert canonical_json(d_py) == canonical_json(d_np)
    assert sha256_obj(d_py) == sha256_obj(d_np)


def test_sha256_bytes_and_file(tmp_path: Path):
    """Verify sha256_file exactly matches sha256_bytes over the same content."""
    content = b"Synera Cryptographic Provenance Layer Verification Test"
    file_path = tmp_path / "test_file.bin"
    file_path.write_bytes(content)

    assert sha256_file(file_path) == sha256_bytes(content)


def test_dataframe_hash_sensitivity():
    """Verify dataframe hashing is sensitive to single-cell mutations and index changes."""
    df1 = pd.DataFrame(
        {
            "temperature": [20.5, 21.0, 21.5, 22.0],
            "radiation": [0.01, 0.02, 0.05, 0.08],
            "label": ["ctrl", "ctrl", "trt", "trt"],
        }
    )
    h1 = sha256_dataframe(df1)

    # Identical copy must yield identical hash
    assert sha256_dataframe(df1.copy()) == h1

    # Single cell floating point change
    df2 = df1.copy()
    df2.loc[1, "temperature"] = 21.0000001
    assert sha256_dataframe(df2) != h1

    # Single cell string change
    df3 = df1.copy()
    df3.loc[3, "label"] = "trt2"
    assert sha256_dataframe(df3) != h1

    # Index change
    df4 = df1.copy()
    df4.index = [10, 20, 30, 40]
    assert sha256_dataframe(df4) != h1


# ============================================================================
# 2. Merkle Tree & Audit Proof Tests
# ============================================================================


@pytest.mark.parametrize("n", [1, 2, 3, 7, 8, 15, 16])
def test_merkle_proof_round_trip(n: int):
    """Validate Merkle root and proof round-trips for power-of-two and odd counts."""
    leaves = [hashlib.sha256(f"leaf-{i}".encode()).hexdigest() for i in range(n)]
    root = merkle_root(leaves)
    assert isinstance(root, str)
    assert len(root) == 64

    for idx in range(n):
        proof = merkle_proof(leaves, idx)
        # Inclusion proof must verify against expected root
        assert verify_proof(leaves[idx], proof, root) is True

        # Tampered leaf must fail verification
        bogus_leaf = hashlib.sha256(b"tampered-leaf").hexdigest()
        assert verify_proof(bogus_leaf, proof, root) is False

        # Corrupted sibling in proof must fail
        if proof:
            corrupted_proof = list(proof)
            corrupted_sibling = (
                "0" + corrupted_proof[0][1][1:]
                if corrupted_proof[0][1][0] != "0"
                else "1" + corrupted_proof[0][1][1:]
            )
            corrupted_proof[0] = (corrupted_proof[0][0], corrupted_sibling)
            assert verify_proof(leaves[idx], corrupted_proof, root) is False


def test_merkle_empty_and_bounds():
    """Verify edge cases for empty lists and out of range indices."""
    assert merkle_root([]) == hashlib.sha256(b"").hexdigest()

    with pytest.raises(IndexError):
        merkle_proof([], 0)

    leaves = [hashlib.sha256(b"a").hexdigest(), hashlib.sha256(b"b").hexdigest()]
    with pytest.raises(IndexError):
        merkle_proof(leaves, -1)
    with pytest.raises(IndexError):
        merkle_proof(leaves, 2)


# ============================================================================
# 3. Ledger Mechanics, Append, and Append-Only Triggers
# ============================================================================


def test_ledger_append_and_verify(tmp_path: Path):
    """Test standard ledger operations: append, get, head, height, find_by_artifact, and verify."""
    db_path = tmp_path / "ledger.db"
    key_path = tmp_path / "ledger.key"
    ledger = Ledger(db_path, key_path)

    assert ledger.height() == 0
    assert ledger.head() is None
    assert ledger.verify()["valid"] is True

    # 1. Genesis block
    b0 = ledger.append(
        block_type="GENESIS",
        payload={"network": "synera-local", "version": "1.0.0"},
    )
    assert b0.index == 0
    assert b0.prev_hash == "0" * 64

    # 2. Dataset registered block with artifact hashes
    art1 = hashlib.sha256(b"artifact-one").hexdigest()
    art2 = hashlib.sha256(b"artifact-two").hexdigest()
    b1 = ledger.append(
        block_type="DATASET_REGISTERED",
        payload={"dataset_id": "nasa-osdr-123"},
        artifact_hashes=[art1, art2],
    )
    assert b1.index == 1
    assert b1.prev_hash == b0.block_hash
    assert b1.merkle_root == merkle_root([art1, art2])

    # 3. Experiment block
    b2 = ledger.append(
        block_type="EXPERIMENT_RUN",
        payload={"run_id": "exp-001", "model": "gbm-interaction"},
    )
    assert b2.index == 2
    assert ledger.height() == 3
    assert ledger.head().block_hash == b2.block_hash

    # Verification passes
    v = ledger.verify()
    assert v["valid"] is True
    assert v["height"] == 3
    assert v["head"] == b2.block_hash
    assert len(v["issues"]) == 0

    # find_by_artifact and proof verification
    matches = ledger.find_by_artifact(art1)
    assert len(matches) == 1
    found_block, proof = matches[0]
    assert found_block.index == 1
    assert verify_proof(art1, proof, found_block.merkle_root) is True


def test_sqlite_append_only_triggers(tmp_path: Path):
    """Verify SQLite triggers forbid UPDATE and DELETE on blocks table."""
    db_path = tmp_path / "ledger.db"
    key_path = tmp_path / "ledger.key"
    ledger = Ledger(db_path, key_path)
    ledger.append("GENESIS", {"genesis": True})

    # Direct raw connection attempting UPDATE
    with sqlite3.connect(db_path) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="Blocks are immutable and cannot be updated"):
            conn.execute("UPDATE blocks SET timestamp = '2099-01-01' WHERE block_index = 0")

        with pytest.raises(sqlite3.DatabaseError, match="Blocks are immutable and cannot be deleted"):
            conn.execute("DELETE FROM blocks WHERE block_index = 0")


# ============================================================================
# 4. Tamper Detection Tests (All 5 Threat Models)
# ============================================================================


def _create_three_block_ledger(tmp_path: Path) -> tuple[Path, Path, Ledger]:
    """Helper to populate a standard 3-block ledger."""
    db_path = tmp_path / "ledger.db"
    key_path = tmp_path / "ledger.key"
    ledger = Ledger(db_path, key_path)

    ledger.append("GENESIS", {"desc": "Genesis"})
    ledger.append(
        "DATASET_REGISTERED",
        {"name": "datasetA"},
        artifact_hashes=[hashlib.sha256(b"A").hexdigest()],
    )
    ledger.append(
        "EXPERIMENT_RUN",
        {"name": "exp1"},
        artifact_hashes=[hashlib.sha256(b"B").hexdigest()],
    )
    return db_path, key_path, ledger


def _copy_and_drop_triggers(src_db: Path, dst_db: Path) -> None:
    """Copy database and drop immutability triggers to simulate adversary tampering."""
    shutil.copyfile(src_db, dst_db)
    with sqlite3.connect(dst_db) as conn:
        conn.execute("DROP TRIGGER IF EXISTS prevent_blocks_update")
        conn.execute("DROP TRIGGER IF EXISTS prevent_blocks_delete")
        conn.commit()


def test_tamper_detection_edited_payload(tmp_path: Path):
    """Case 1: Adversary edits payload_json directly in SQLite."""
    src_db, key_path, _ = _create_three_block_ledger(tmp_path)
    tampered_db = tmp_path / "tampered_payload.db"
    _copy_and_drop_triggers(src_db, tampered_db)

    with sqlite3.connect(tampered_db) as conn:
        conn.execute(
            """
            UPDATE blocks
            SET payload_json = '{"name": "datasetA_malicious", "artifact_hashes": []}'
            WHERE block_index = 1
            """
        )
        conn.commit()

    tampered_ledger = Ledger(tampered_db, key_path)
    report = tampered_ledger.verify()
    assert report["valid"] is False
    codes = [issue["code"] for issue in report["issues"]]
    assert "PAYLOAD_TAMPERED" in codes


def test_tamper_detection_edited_block_hash(tmp_path: Path):
    """Case 2: Adversary edits block_hash directly in SQLite."""
    src_db, key_path, _ = _create_three_block_ledger(tmp_path)
    tampered_db = tmp_path / "tampered_hash.db"
    _copy_and_drop_triggers(src_db, tampered_db)

    with sqlite3.connect(tampered_db) as conn:
        fake_hash = "f" * 64
        conn.execute(f"UPDATE blocks SET block_hash = '{fake_hash}' WHERE block_index = 1")
        conn.commit()

    tampered_ledger = Ledger(tampered_db, key_path)
    report = tampered_ledger.verify()
    assert report["valid"] is False
    codes = [issue["code"] for issue in report["issues"]]
    assert "HASH_MISMATCH" in codes


def test_tamper_detection_deleted_middle_block(tmp_path: Path):
    """Case 3: Adversary deletes middle block 1 from database."""
    src_db, key_path, _ = _create_three_block_ledger(tmp_path)
    tampered_db = tmp_path / "tampered_delete.db"
    _copy_and_drop_triggers(src_db, tampered_db)

    with sqlite3.connect(tampered_db) as conn:
        conn.execute("DELETE FROM blocks WHERE block_index = 1")
        conn.commit()

    tampered_ledger = Ledger(tampered_db, key_path)
    report = tampered_ledger.verify()
    assert report["valid"] is False
    codes = [issue["code"] for issue in report["issues"]]
    assert "PREV_HASH_MISMATCH" in codes


def test_tamper_detection_swapped_block_order(tmp_path: Path):
    """Case 4: Adversary swaps row order of block 1 and block 2."""
    src_db, key_path, _ = _create_three_block_ledger(tmp_path)
    tampered_db = tmp_path / "tampered_swap.db"
    _copy_and_drop_triggers(src_db, tampered_db)

    with sqlite3.connect(tampered_db) as conn:
        conn.execute("CREATE TABLE blocks_temp AS SELECT * FROM blocks WHERE 0")
        conn.execute("INSERT INTO blocks_temp SELECT * FROM blocks WHERE block_index = 0")
        conn.execute("INSERT INTO blocks_temp SELECT * FROM blocks WHERE block_index = 2")
        conn.execute("INSERT INTO blocks_temp SELECT * FROM blocks WHERE block_index = 1")
        conn.execute("DROP TABLE blocks")
        conn.execute("ALTER TABLE blocks_temp RENAME TO blocks")
        conn.commit()

    tampered_ledger = Ledger(tampered_db, key_path)
    report = tampered_ledger.verify()
    assert report["valid"] is False
    codes = [issue["code"] for issue in report["issues"]]
    assert "PREV_HASH_MISMATCH" in codes


def test_tamper_detection_forged_signature(tmp_path: Path):
    """Case 5: Adversary signs block with an unauthorized keypair or corrupts signature."""
    src_db, key_path, ledger = _create_three_block_ledger(tmp_path)
    tampered_db = tmp_path / "tampered_sig.db"
    _copy_and_drop_triggers(src_db, tampered_db)

    # Forge signature using a different private key
    b1 = ledger.get(1)
    foreign_priv = Ed25519PrivateKey.generate()
    forged_sig = foreign_priv.sign(bytes.fromhex(b1.block_hash)).hex()

    with sqlite3.connect(tampered_db) as conn:
        conn.execute(
            f"UPDATE blocks SET signature = '{forged_sig}' WHERE block_index = 1"
        )
        conn.commit()

    tampered_ledger = Ledger(tampered_db, key_path)
    report = tampered_ledger.verify()
    assert report["valid"] is False
    codes = [issue["code"] for issue in report["issues"]]
    assert "BAD_SIGNATURE" in codes


# ============================================================================
# 5. Concurrency Test: 8 Parallel Threads
# ============================================================================


def test_concurrent_appends_8_threads(tmp_path: Path):
    """Validate that 8 parallel threads can concurrently append without race conditions or DB locks."""
    db_path = tmp_path / "ledger_concurrent.db"
    key_path = tmp_path / "ledger_concurrent.key"
    ledger = Ledger(db_path, key_path)

    # Initial genesis block
    ledger.append("GENESIS", {"note": "concurrent init"})

    num_threads = 8
    blocks_per_thread = 5

    def worker(worker_id: int):
        for i in range(blocks_per_thread):
            ledger.append(
                block_type="EXPERIMENT_RUN",
                payload={"worker": worker_id, "iter": i},
                artifact_hashes=[hashlib.sha256(f"w{worker_id}-i{i}".encode()).hexdigest()],
            )

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, tid) for tid in range(num_threads)]
        for f in futures:
            f.result()

    expected_total = 1 + (num_threads * blocks_per_thread)
    assert ledger.height() == expected_total

    # Verify chain integrity end-to-end
    v = ledger.verify()
    assert v["valid"] is True
    assert v["height"] == expected_total
    assert len(v["issues"]) == 0


# ============================================================================
# 6. Manifest & Registration Pipeline Tests
# ============================================================================


def test_manifest_register_and_verify(tmp_path: Path):
    """Test file registration idempotency and manifest verification against ledger."""
    db_path = tmp_path / "ledger.db"
    key_path = tmp_path / "ledger.key"
    manifest_path = tmp_path / "MANIFEST.json"
    ledger = Ledger(db_path, key_path)

    test_file = tmp_path / "nasa_sample.csv"
    test_file.write_text("gene,radiation,expression\nBRCA1,0.5,2.34\nTP53,0.5,1.12\n")

    # 1. Register file
    file_hash, block = register_file(
        ledger=ledger,
        path=test_file,
        kind="dataset",
        meta={"source": "OSDR"},
        manifest_path=manifest_path,
    )
    assert block.index == 0
    assert block.block_type == "DATASET_REGISTERED"

    # 2. Idempotency: re-registering the same file must not create a duplicate block
    file_hash2, block2 = register_file(
        ledger=ledger,
        path=test_file,
        kind="dataset",
        manifest_path=manifest_path,
    )
    assert file_hash2 == file_hash
    assert block2.index == block.index
    assert ledger.height() == 1

    # 3. Verify manifest
    audit = verify_manifest(ledger, manifest_path=manifest_path)
    assert len(audit) == 1
    assert audit[0]["ok"] is True
    assert audit[0]["actual"] == file_hash
    assert audit[0]["ledger_block"].index == block.index

    # 4. Tamper file on disk and re-verify manifest
    test_file.write_text("gene,radiation,expression\nBRCA1,0.5,9.99\nTP53,0.5,1.12\n")
    audit_tampered = verify_manifest(ledger, manifest_path=manifest_path)
    assert len(audit_tampered) == 1
    assert audit_tampered[0]["ok"] is False


def test_build_run_manifest(tmp_path: Path):
    """Test computational run manifest construction and result hash generation."""
    config = {"alpha": 0.05, "n_boot": 1000}
    d_hashes = [hashlib.sha256(b"ds1").hexdigest()]
    m_hashes = [hashlib.sha256(b"m1").hexdigest()]

    manifest = build_run_manifest(
        config=config,
        dataset_hashes=d_hashes,
        model_hashes=m_hashes,
        seed=42,
    )

    assert "git_commit" in manifest
    assert "src_tree_hash" in manifest
    assert "configs_hash" in manifest
    assert "pyproject_hash" in manifest
    assert "env_versions" in manifest
    assert manifest["seed"] == 42
    assert manifest["dataset_hashes"] == d_hashes

    res_hash = compute_result_hash(manifest, "outputs-digest-xyz")
    assert isinstance(res_hash, str)
    assert len(res_hash) == 64


# ============================================================================
# 7. IntegrityGuard & Status Verification Tests
# ============================================================================


def test_integrity_guard_one_byte_mutation_and_dedupe(tmp_path: Path):
    """Verify IntegrityGuard flags one-byte change, appends INTEGRITY_ALERT, and dedupes."""
    db_path = tmp_path / "ledger.db"
    key_path = tmp_path / "ledger.key"
    manifest_path = tmp_path / "MANIFEST.json"
    ledger = Ledger(db_path, key_path)
    guard = IntegrityGuard(ledger)

    dataset_path = tmp_path / "microgravity_data.bin"
    original_data = bytearray(b"SENSITIVE_SCIENTIFIC_DATA_BLOCK_001")
    dataset_path.write_bytes(original_data)

    # Register original dataset
    _file_hash, _ = register_file(
        ledger, dataset_path, kind="dataset", manifest_path=manifest_path
    )

    # Initial check must pass
    res_ok = guard.check_dataset(dataset_path)
    assert res_ok.ok is True
    assert res_ok.detail == "OK"
    assert ledger.height() == 1

    # Mutate exactly one byte in dataset file
    tampered_data = bytearray(original_data)
    tampered_data[10] = (tampered_data[10] + 1) % 256
    dataset_path.write_bytes(tampered_data)

    # Second check must detect violation and append INTEGRITY_ALERT block
    res_fail = guard.check_dataset(dataset_path)
    assert res_fail.ok is False
    assert res_fail.actual_hash != res_fail.expected_hash
    assert "Hash mismatch" in res_fail.detail
    assert ledger.height() == 2

    alert_block = ledger.head()
    assert alert_block.block_type == "INTEGRITY_ALERT"
    assert alert_block.payload["actual_hash"] == res_fail.actual_hash

    # Deduplication check: repeated audit of same tampered file must not duplicate alert
    res_repeat = guard.check_dataset(dataset_path)
    assert res_repeat.ok is False
    assert ledger.height() == 2  # Height stays 2 due to deduplication


def test_guard_verified_status(tmp_path: Path):
    """Verify guard_verified_status refuses VERIFIED status on integrity or security failures."""
    db_path = tmp_path / "ledger.db"
    key_path = tmp_path / "ledger.key"
    manifest_path = tmp_path / "MANIFEST.json"
    ledger = Ledger(db_path, key_path)
    guard = IntegrityGuard(ledger)

    # Register an artifact
    test_file = tmp_path / "clean_artifact.csv"
    test_file.write_text("a,b\n1,2\n")
    art_hash, _ = register_file(
        ledger, test_file, kind="dataset", manifest_path=manifest_path
    )

    # 1. Clean candidate finding passes
    valid_finding = {
        "artifact_hashes": [art_hash],
        "dataset_paths": [test_file],
        "security_report": {"status": "CLEAN"},
    }
    allowed, reasons = guard.guard_verified_status(valid_finding)
    assert allowed is True
    assert len(reasons) == 0

    # Also test standalone function
    standalone_allowed, standalone_reasons = guard_verified_status(valid_finding, ledger)
    assert standalone_allowed is True
    assert len(standalone_reasons) == 0

    # 2. Refuses if security report is not CLEAN
    bad_sec_finding = {
        "artifact_hashes": [art_hash],
        "security_report": {"status": "SUSPICIOUS_ANOMALY"},
    }
    allowed, reasons = guard.guard_verified_status(bad_sec_finding)
    assert allowed is False
    assert any("Security report" in r for r in reasons)

    # 3. Refuses if an artifact has an INTEGRITY_ALERT recorded
    ledger.append(
        block_type="INTEGRITY_ALERT",
        payload={"expected_hash": art_hash, "actual_hash": "corrupt"},
    )
    allowed, reasons = guard.guard_verified_status(valid_finding)
    assert allowed is False
    assert any("INTEGRITY_ALERT" in r for r in reasons)
