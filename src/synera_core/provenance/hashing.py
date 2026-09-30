"""Cryptographic hashing utilities for deterministic artifact verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_CHUNK = 1 << 20


def sha256_bytes(b: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Compute SHA-256 hex digest of a file using buffered streaming reads."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _default(o: Any) -> Any:
    """JSON serializer fallback for numpy and set types."""
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    ).encode("utf-8")


def sha256_obj(obj: Any) -> str:
    """Deterministic SHA-256 hex digest of an arbitrary serializable Python object."""
    return sha256_bytes(canonical_json(obj))


def sha256_dataframe(df: pd.DataFrame) -> str:
    """Content hash independent of file format: columns, dtypes, shape and per-row hashes (index included)."""
    h = hashlib.sha256()
    h.update(
        canonical_json(
            {
                "cols": [str(c) for c in df.columns],
                "dtypes": [str(t) for t in df.dtypes],
                "shape": df.shape,
            }
        )
    )
    h.update(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes())
    return h.hexdigest()


# Backward compatibility aliases
canonical_json_bytes = canonical_json
hash_object = sha256_obj
