"""First-run setup for a fresh checkout or container (idempotent):

    restore shipped results -> registers tracked datasets in the ledger -> Track A results if missing -> seeds the database.

The Track B benchmark report is a ~30 minute job and is NOT run here. The last measured report is shipped in
``data/results/`` and copied into ``artifacts/results/`` when missing. To refresh it, run ``make benchmark`` and
copy ``artifacts/results/benchmark.json`` over the shipped file. Without either, the page shows "not computed".
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run([sys.executable, *args], cwd=ROOT, check=False)


def restore_shipped_results() -> None:
    out = ROOT / "artifacts" / "results"
    out.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "data" / "results").glob("*.json"):
        if not (out / f.name).exists():
            shutil.copy(f, out / f.name)
            print("restored shipped result", f.name)


def main() -> None:
    restore_shipped_results()
    run("scripts/build_data.py")
    if not (ROOT / "data" / "reference" / "mouse_ensembl_symbols.tsv").exists():
        run("scripts/build_gene_symbols.py")
    results = ROOT / "artifacts" / "results"
    if not (results / "space_biology.json").exists() or not (results / "osdr_genes.json").exists():
        run("scripts/build_space_biology.py")
    run("scripts/seed_db.py", *sys.argv[1:])


if __name__ == "__main__":
    main()
