"""Tampering simulation harness for security red-teaming.

Simulates adversarial attacks (file bit flips, payload alteration, ledger forgery)
to demonstrate that SYNERA's cryptographic checks correctly block compromised findings.
"""

from __future__ import annotations

from pathlib import Path


def simulate_bit_flip(file_path: Path | str, byte_offset: int = 0) -> None:
    """Invert a single byte in a file to simulate bit-level corruption or tampering.

    Args:
        file_path: Target file path to corrupt.
        byte_offset: Offset position to flip.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Cannot tamper with non-existent file: {path}")

    with open(path, "r+b") as f:
        f.seek(byte_offset)
        byte = f.read(1)
        if byte:
            flipped = bytes([byte[0] ^ 0xFF])
            f.seek(byte_offset)
            f.write(flipped)
