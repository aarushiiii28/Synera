"""Deterministic cryptographic hashing of structured objects."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize object to deterministic, sorted UTF-8 JSON bytes."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def hash_object(obj: Any) -> str:
    """Compute SHA-256 hash of deterministically serialized data structure."""
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()
