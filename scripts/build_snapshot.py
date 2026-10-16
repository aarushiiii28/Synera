"""Record the real API's answers as static JSON files, so the web app can be hosted with no server (e.g. on Vercel).

    python scripts/build_snapshot.py                      # writes frontend/public/snapshot/
    python scripts/build_snapshot.py --out some/dir

Nothing is invented: every file is the response of the real FastAPI app, called in-process. The recording runs in a
temporary copy of the project, so the re-verify and attack calls it makes never touch your real database or ledger.
Forecasts are served from the cache (SYNERA_OFFLINE=1) so the risk brief is honestly tagged as cached, not live.
The browser side (frontend/src/lib/snapshot.ts) must use the same file naming: see ``slug`` below.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "/api/v1"


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", s).strip("_")


def outer(out: Path) -> int:
    """Copy what the API needs into a temp dir and re-run this script there."""
    tmp = Path(tempfile.mkdtemp(prefix="synera_snapshot_"))
    try:
        for d in ("backend", "configs", "data", "scripts", "src"):
            shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__", "venv"))
        shutil.copy(ROOT / "pyproject.toml", tmp / "pyproject.toml")
        shutil.copytree(ROOT / "artifacts", tmp / "artifacts", ignore=shutil.ignore_patterns("benchmark_cache", "*.log", "*.err"))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(tmp / "src"), str(tmp)]), SYNERA_OFFLINE="1")
        r = subprocess.run([sys.executable, str(tmp / "scripts" / "build_snapshot.py"), "--inner", "--out", str(out)], cwd=tmp, env=env)
        return r.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def inner(out: Path) -> int:
    from fastapi.testclient import TestClient

    import backend.app.api.v1.security as security
    from backend.app.main import app

    security.SIMULATE_RATE_LIMIT_PER_MIN = 10**9     # the limiter exists to protect a public server, not this recording

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    written: dict[str, int] = {}

    def save(name: str, data) -> None:
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        (out / f"{name}.json").write_text(text, encoding="utf-8")
        written[name] = len(text)

    with TestClient(app) as c:
        def get(path: str):
            r = c.get(API + path)
            return r.json() if r.status_code == 200 else None

        def record(path: str, name: str | None = None):
            data = get(path)
            if data is None:
                print(f"  skip {path}")
                return None
            save(name or slug(path), data)
            return data

        for p in ("/health", "/ledger/head", "/ledger/verify", "/runs/steps", "/stressors", "/space-biology/overview",
                  "/space-biology/genes?limit=20", "/space-biology/genes?compact=true&limit=30000", "/benchmark/results",
                  "/experiments", "/security/modes", "/security/false-alarm-rates", "/risk/regions"):
            record(p)

        # --- datasets
        datasets = record("/datasets") or []
        for d in datasets:
            record(f"/datasets/{d['id']}")
            r = c.post(f"{API}/datasets/{d['id']}/verify")
            if r.status_code == 200:
                save(f"verify_dataset_{slug(d['id'])}", r.json())
            record(f"/interactions/matrix?dataset_id={d['id']}")
            record(f"/interactions/network?dataset_id={d['id']}")

        # --- runs (every run, newest first, plus each one with its events)
        runs = get("/runs") or []
        save("all_runs", runs)
        for r in runs:
            record(f"/runs/{r['id']}")

        # --- findings (full registry, then per-finding evidence)
        listing = get("/findings?limit=200") or {"items": [], "total": 0, "counts": {}}
        save("all_findings", listing)
        for f in listing["items"]:
            record(f"/findings/{f['id']}")
            if f.get("has_surface"):
                record(f"/findings/{f['id']}/surface")
            record(f"/findings/{f['id']}/forest")
            r = c.post(f"{API}/findings/{f['id']}/verify")
            if r.status_code == 200:
                save(f"verify_finding_{slug(f['id'])}", r.json())

        # --- ledger
        blocks = get("/ledger/blocks?limit=200&order=asc") or {"items": [], "total": 0}
        save("all_blocks", blocks)
        hashes: set[str] = set(re.findall(r"\b[0-9a-f]{64}\b", json.dumps(blocks) + json.dumps(datasets) + json.dumps(listing) + json.dumps(runs)))
        proofs = 0
        for h in sorted(hashes):
            r = c.get(f"{API}/ledger/proof/{h}")
            if r.status_code == 200:
                save(f"ledger_proof_{h}", r.json())
                proofs += 1
        print(f"  {proofs} merkle proofs recorded from {len(hashes)} candidate hashes")

        # --- risk briefs (cached forecast, so the page says so)
        for region in get("/risk/regions") or []:
            record(f"/risk/assessment?region={region['id']}")

        # --- attacks: one recorded outcome per dataset and mode (default 5% magnitude, seed 1)
        modes = [m["mode"] for m in get("/security/modes") or []]
        t0 = time.time()
        for d in datasets:
            for m in modes:
                r = c.post(f"{API}/security/simulate-tamper", json={"dataset_id": d["id"], "mode": m, "magnitude": 0.05, "seed": 1})
                if r.status_code == 200:
                    save(f"tamper_{slug(d['id'])}_{slug(m)}", r.json())
        print(f"  attacks recorded in {time.time() - t0:.0f}s")

        # --- every tested gene, compact, so the gene search works without a server
        genes_path = Path("artifacts/results/osdr_genes.json")
        if genes_path.exists():
            genes = json.loads(genes_path.read_text(encoding="utf-8"))
            save("all_genes", [[g["ensembl_id"], g["gene_symbol"], g.get("name", ""), g["b_AB"], g["p"], g["q"], g["neg_log10_p"],
                                g["neg_log10_q"], g["type"], g.get("replication_b_AB"), g.get("replication_p"),
                                g.get("same_sign_in_replication"), g.get("passed_filter_both")] for g in genes])

        h = get("/health") or {}
        save("meta", {"generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "ledger_height": (h.get("ledger") or {}).get("height"),
                      "files": len(written)})

    total = sum(written.values())
    print(f"snapshot: {len(written)} files, {total / 1e6:.1f} MB -> {out}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "frontend" / "public" / "snapshot"))
    ap.add_argument("--inner", action="store_true")
    a = ap.parse_args()
    out_dir = Path(a.out).resolve()
    sys.exit(inner(out_dir) if a.inner else outer(out_dir))
