"""Cryptographic evidence ledger for tamper-evident provenance tracking."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from synera_core.provenance.hashing import hash_object


class ProvenanceLedger:
    """Append-only cryptographic ledger storing SHA-256 chained evidence entries."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema with block index, hashes, and payload."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    block_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    signature TEXT
                )
                """
            )
            conn.commit()

    def get_latest_hash(self) -> str:
        """Retrieve entry hash of the most recent block, or genesis hash if empty."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT entry_hash FROM ledger_entries ORDER BY block_index DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row[0] if row else "0" * 64
