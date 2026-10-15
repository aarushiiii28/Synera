"""`make reproduce`: re-run every recorded analysis and compare its outputs digest with the ledger.

For each EXPERIMENT_RUN block in the ledger the analysis is re-executed from the registered inputs with the
recorded parameters. The digest of the fresh outputs (floats rounded to 8 significant digits) must equal the
one the ledger recorded. Mismatches are reported, never hidden, and the process exits non-zero.
No ledger blocks are written by this script.
"""
from __future__ import annotations

import sys
import time

from synera_core.pipeline.orchestrator import recompute_digest
from synera_core.provenance.manifest import verify_manifest
from synera_core.provenance.store import open_ledger


def main() -> int:
    ledger = open_ledger()
    v = ledger.verify()
    print(f"ledger: {v['height']} blocks, chain {'VALID' if v['valid'] else 'BROKEN'}")
    audit = verify_manifest(ledger)
    bad = [a for a in audit if not a["ok"]]
    print(f"manifest: {len(audit) - len(bad)}/{len(audit)} files match their hash and ledger record")
    for a in bad:
        print(f"  MISMATCH {a['path']}: expected {str(a['expected'])[:12]}… actual {str(a['actual'])[:12]}…")

    latest: dict[str, dict] = {}
    for b in ledger.iter_blocks():
        if b.block_type == "EXPERIMENT_RUN" and b.payload.get("outputs_digest"):
            latest[b.payload["dataset_id"]] = {**b.payload, "block": b.index}
    if not latest:
        print("no recorded runs: run  make seed  first")
        return 1

    rows, failed = [], bool(bad) or not v["valid"]
    for ds, rec in latest.items():
        t = time.time()
        fresh = recompute_digest(ds, rec["params"])
        ok = fresh == rec["outputs_digest"]
        failed |= not ok
        rows.append((ds, rec["block"], rec["outputs_digest"][:12], fresh[:12], "MATCH" if ok else "MISMATCH", time.time() - t))
    print(f"\n{'dataset':20s}{'block':>6s}  {'recorded':14s}{'recomputed':14s}{'verdict':10s}{'seconds':>8s}")
    for r in rows:
        print(f"{r[0]:20s}{r[1]:6d}  {r[2]:14s}{r[3]:14s}{r[4]:10s}{r[5]:8.1f}")
    print("\nREPRODUCED" if not failed else "\nNOT REPRODUCED: see mismatches above")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
