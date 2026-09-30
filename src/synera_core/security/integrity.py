"""Data and file integrity verification using SHA-256 hashes and ledger integration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synera_core.provenance.hashing import sha256_file
from synera_core.provenance.ledger import Ledger


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


@dataclass(frozen=True)
class IntegrityResult:
    """Result of an artifact integrity verification check."""

    artifact: str
    expected_hash: str
    actual_hash: str
    ok: bool
    block_index: int | None
    checked_at: str
    detail: str


class IntegrityGuard:
    """Active dataset and artifact security integrity watchdog.

    Audits files against expected ledger provenance records and automatically
    emits deduplicated INTEGRITY_ALERT blocks on tamper detection.
    """

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger
        self._alerted: set[tuple[str, str]] = set()

    def check_dataset(
        self,
        path: str | Path,
        expected_hash: str | None = None,
    ) -> IntegrityResult:
        """Check dataset file integrity against ledger record and flag mismatches.

        On mismatch, automatically appends an INTEGRITY_ALERT block to the ledger
        (deduplicated for repeated checks of the same artifact + actual_hash).

        Args:
            path: Path to dataset file on disk.
            expected_hash: Optional expected SHA-256 string. If omitted, searches ledger.

        Returns:
            IntegrityResult instance.
        """
        file_path = Path(path)
        checked_at = datetime.now(UTC).isoformat()
        artifact_key = file_path.as_posix()

        if not file_path.is_file():
            actual_hash = ""
            expected = expected_hash or ""
            ok = False
            detail = f"File not found: {file_path}"
            block_index = None
        else:
            actual_hash = sha256_file(file_path)
            expected = expected_hash or ""
            block_index = None

            # Look up expected hash in ledger if not explicitly provided
            if not expected:
                for block in reversed(list(self.ledger.iter_blocks())):
                    p = block.payload
                    p_path = p.get("path")
                    if p_path and (
                        p_path == artifact_key
                        or Path(p_path).name == file_path.name
                    ):
                        expected = p.get("sha256") or (
                            p.get("artifact_hashes", [None])[0] or ""
                        )
                        block_index = block.index
                        break

            if not expected:
                ok = False
                detail = f"No prior registration record found for {artifact_key}"
            elif actual_hash == expected:
                ok = True
                detail = "OK"
            else:
                ok = False
                detail = (
                    f"Hash mismatch for {artifact_key}: "
                    f"expected {expected}, got {actual_hash}"
                )

        if not ok:
            # Check deduplication in memory and in existing ledger alerts
            dedupe_key = (artifact_key, actual_hash)
            already_alerted = dedupe_key in self._alerted

            if not already_alerted:
                for block in self.ledger.iter_blocks():
                    if block.block_type == "INTEGRITY_ALERT":
                        p = block.payload
                        if (
                            p.get("artifact") == artifact_key
                            and p.get("actual_hash") == actual_hash
                        ):
                            already_alerted = True
                            break

            if not already_alerted:
                self._alerted.add(dedupe_key)
                alert_payload = {
                    "artifact": artifact_key,
                    "expected_hash": expected,
                    "actual_hash": actual_hash,
                    "detail": detail,
                    "checked_at": checked_at,
                }
                alert_block = self.ledger.append(
                    block_type="INTEGRITY_ALERT",
                    payload=alert_payload,
                    artifact_hashes=[actual_hash] if actual_hash else [],
                )
                if block_index is None:
                    block_index = alert_block.index

        return IntegrityResult(
            artifact=artifact_key,
            expected_hash=expected,
            actual_hash=actual_hash,
            ok=ok,
            block_index=block_index,
            checked_at=checked_at,
            detail=detail,
        )

    def guard_verified_status(self, finding: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate whether finding meets strict criteria for VERIFIED status.

        Refuses VERIFIED status if:
        1. Ledger chain is invalid.
        2. Any linked artifact fails validation or has active integrity alerts.
        3. Security report is missing or status is not CLEAN.

        Args:
            finding: Candidate finding dictionary.

        Returns:
            Tuple of (allowed: bool, reasons: list[str]).
        """
        reasons: list[str] = []

        # 1. Verify ledger chain
        verify_status = self.ledger.verify()
        if not verify_status["valid"]:
            reasons.append(
                f"Ledger chain validation failed: {verify_status['issues']}"
            )

        # 2. Check linked artifacts
        linked_hashes = (
            finding.get("artifact_hashes")
            or finding.get("artifacts")
            or finding.get("dataset_hashes")
            or []
        )
        for h in linked_hashes:
            matches = self.ledger.find_by_artifact(h)
            if not matches:
                reasons.append(f"Linked artifact '{h}' is not registered in ledger")

            # Check if any INTEGRITY_ALERT exists for this artifact
            for block in self.ledger.iter_blocks():
                if block.block_type == "INTEGRITY_ALERT":
                    p = block.payload
                    if p.get("expected_hash") == h or p.get("actual_hash") == h:
                        reasons.append(
                            f"Linked artifact '{h}' has recorded INTEGRITY_ALERT (block {block.index})"
                        )
                        break

        linked_paths = finding.get("dataset_paths") or finding.get("datasets") or []
        for path in linked_paths:
            res = self.check_dataset(path)
            if not res.ok:
                reasons.append(f"Linked dataset '{path}' failed integrity check: {res.detail}")

        # 3. Check security report
        sec_report = finding.get("security_report")
        if sec_report is None:
            reasons.append("Security report is missing; must be CLEAN")
        elif isinstance(sec_report, dict):
            status = sec_report.get("status", "").upper()
            if status != "CLEAN":
                reasons.append(f"Security report status is '{status}', expected 'CLEAN'")
        elif str(sec_report).upper() != "CLEAN":
            reasons.append(f"Security report status is '{sec_report}', expected 'CLEAN'")

        return len(reasons) == 0, reasons


def guard_verified_status(
    finding: dict[str, Any],
    ledger: Ledger | None = None,
) -> tuple[bool, list[str]]:
    """Standalone helper function to guard VERIFIED status."""
    if ledger is None:
        return False, ["No ledger instance supplied for verification"]
    guard = IntegrityGuard(ledger)
    return guard.guard_verified_status(finding)
