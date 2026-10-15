"""First-run setup for a fresh checkout or container (idempotent):

    registers tracked datasets in the ledger -> Track A / benchmark results if missing -> seeds the database.

The Track B benchmark report is a ~30 minute job and is NOT run here; the page shows "not computed" until
`make benchmark` has been run.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run([sys.executable, *args], cwd=ROOT, check=False)


def main() -> None:
    run("scripts/build_data.py")
    if not (ROOT / "data" / "reference" / "mouse_ensembl_symbols.tsv").exists():
        run("scripts/build_gene_symbols.py")
    if not (ROOT / "artifacts" / "results" / "space_biology.json").exists():
        run("scripts/build_space_biology.py")
    run("scripts/seed_db.py", *sys.argv[1:])


if __name__ == "__main__":
    main()
