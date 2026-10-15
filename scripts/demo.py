"""`make demo`: verify the evidence, make sure the database is seeded, start the API and the web app.

    python scripts/demo.py [--quick] [--no-web]

1. verifies the ledger chain and the data manifest, 2. seeds the application database from the real pipeline
if it is empty or stale, 3. starts the API (8000) and the web app (5173), 4. prints the URLs.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="fewer bootstrap resamples when seeding")
    ap.add_argument("--no-web", action="store_true")
    args = ap.parse_args()

    from backend.app.db.database import engine, migrate_db
    from backend.app.db.models import Run
    from synera_core.pipeline.registry import get_registry
    from synera_core.provenance.manifest import verify_manifest
    from synera_core.provenance.store import open_ledger
    from synera_core.security.pipeline_integrity import current_src_tree_hash

    ledger = open_ledger()
    v = ledger.verify()
    audit = verify_manifest(ledger)
    bad = [a for a in audit if not a["ok"]]
    print(f"1. ledger {v['height']} blocks, chain {'VALID' if v['valid'] else 'BROKEN'}; manifest {len(audit) - len(bad)}/{len(audit)} files verified")
    if not v["valid"] or bad:
        print("   evidence check FAILED; the demo will show the BLOCKED states honestly")

    migrate_db()
    with Session(engine) as s:
        runs = s.exec(select(Run).where(Run.status == "COMPLETED")).all()
    stale = any(r.src_tree_hash != current_src_tree_hash() for r in runs)
    have = {r.dataset_id for r in runs}
    need = {d for d, sp in get_registry().items() if sp.runnable}
    if not need <= have or stale:
        print(f"2. seeding the database ({'code changed since the last run' if stale else 'no completed runs'}) ...")
        from scripts.seed_db import seed
        seed(quick=args.quick, force=stale)
    else:
        print("2. database already seeded and current")

    py = sys.executable
    api = subprocess.Popen([py, "-m", "uvicorn", "backend.app.main:app", "--port", "8000"], cwd=ROOT)
    web = None
    if not args.no_web:
        npm = shutil.which("npm")
        if npm:
            web = subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "frontend")
    time.sleep(2)
    print("\n3. SYNERA is running")
    print("   web   http://localhost:5173")
    print("   api   http://127.0.0.1:8000/docs")
    print("   (Ctrl+C to stop)")
    try:
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in (web, api):
            if p and p.poll() is None:
                p.terminate()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
