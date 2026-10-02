"""Model weights and serialization integrity verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from synera_core.security.integrity import compute_file_sha256


def verify_model_artifact(
    model_path: Path | str,
    expected_sha256: str,
) -> dict[str, Any]:
    """Verify serialized model artifact against recorded cryptographic hash.

    Args:
        model_path: Path to serialized model file.
        expected_sha256: Recorded SHA-256 digest.

    Returns:
        Dictionary reporting validation outcome and actual digest.
    """
    path = Path(model_path)
    if not path.exists():
        return {
            "verified": False,
            "error": f"Model artifact not found: {path}",
            "actual_hash": None,
        }

    actual = compute_file_sha256(path)
    matched = actual.lower() == expected_sha256.lower().strip()
    return {
        "verified": matched,
        "actual_hash": actual,
        "expected_hash": expected_sha256,
    }
