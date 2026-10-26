"""Main data pipeline. Idempotent: fetch (or read cache) -> harmonize -> QC -> hash -> ledger -> MANIFEST.

    python scripts/build_data.py          # or:  make data

Only raw files that actually exist are used. If an OSDR study's files are missing the study is reported as
BLOCKED (never substituted). A second run is fully offline: HTTP responses are cached under data/raw/cache,
and every artifact is registered in the ledger idempotently by its SHA-256.
"""
from __future__ import annotations

import subprocess
import sys

import pandas as pd
import yaml

from synera_core.config import find_repo_root
from synera_core.data.harmonize import harmonize_osdr
from synera_core.provenance.manifest import build_run_manifest, register_file
from synera_core.provenance.hashing import sha256_file
from synera_core.provenance.store import open_ledger


def main() -> int:
    root = find_repo_root()
    ledger = open_ledger()
    manifest = root / "data" / "MANIFEST.json"
    blocked: list[str] = []

    print("1. Environmental stressor panel (Open-Meteo; cached after first run)")
    env_path = root / "data" / "processed" / "env_panel.parquet"
    try:
        subprocess.run([sys.executable, str(root / "scripts" / "build_env_data.py")], check=True, cwd=root)
    except subprocess.CalledProcessError as exc:
        if not env_path.exists():
            blocked.append(f"BLOCKED: environmental panel could not be built and none exists ({exc})")
        else:
            print("   fetch failed; using the existing tracked panel")
    if env_path.exists():
        register_file(ledger, env_path, "dataset", {"description": "Environmental stressor panel", "provenance": "REAL"},
                      manifest_path=manifest)

    print("1b. US weekly mortality x weather x air pollution (real health outcome; built by scripts/build_health_panel.py)")
    hp = root / "data" / "processed" / "us_mortality_panel.parquet"
    for p in (hp, hp.with_name("us_mortality_panel_qc.json"), hp.with_name("us_heart_panel.parquet"), hp.with_name("us_stroke_panel.parquet")):
        if p.exists():
            register_file(ledger, p, "dataset", {"description": "US weekly mortality x weather x air pollution (Track C)", "provenance": "REAL"},
                          manifest_path=manifest)
    if not hp.exists():
        print("   panel missing: run  python scripts/build_health_panel.py")

    print("1c. India daily electricity supplied x weather (real non-health outcome; built by scripts/build_india_grid_panel.py)")
    for stem in ("india_grid", "india_grid_b"):
        for p in (root / "data" / "processed" / f"{stem}_panel.parquet", root / "data" / "processed" / f"{stem}_panel_qc.json"):
            if p.exists():
                register_file(ledger, p, "dataset", {"description": "India daily electricity supplied x weather (Track D)", "provenance": "REAL"},
                              manifest_path=manifest)
            else:
                print(f"   {p.name} missing: run  python scripts/build_india_grid_panel.py")

    print("2. NASA OSDR studies (real files in data/raw/manual/osdr/<ID>/)")
    cfg = yaml.safe_load((root / "configs" / "datasets.yaml").read_text())
    for role in ("discovery", "replication"):
        sid = cfg[role]
        try:
            tissue = next((d.get("tissue") for d in cfg.get("datasets", []) if d["id"] == sid.lower() and "tissue" in d), None)
            harmonize_osdr(sid, None, None, ledger, tissue=tissue)
        except FileNotFoundError as exc:
            # Raw files are not committed (data/raw is ignored). If the processed tables exist they are registered as they are.
            procs = [root / "data" / "processed" / f"osdr_{sid}_{k}" for k in ("expr.parquet", "meta.parquet", "qc.json")]
            if all(p.exists() for p in procs):
                for p in procs:
                    register_file(ledger, p, "dataset", {"study_id": sid, "provenance": "REAL", "note": "registered from tracked processed tables"},
                                  manifest_path=manifest)
                print(f"   {sid}: raw files absent; registered the existing processed tables")
            else:
                blocked.append(f"BLOCKED: {sid} ({role}): {exc}")
                print(f"   {blocked[-1]}")
        except Exception as exc:  # reported, never silently replaced by anything
            blocked.append(f"BLOCKED: {sid} ({role}): {exc}")
            print(f"   {blocked[-1]}")

    print("3. Reference data")
    sym = root / "data" / "reference" / "mouse_ensembl_symbols.tsv"
    if sym.exists():
        register_file(ledger, sym, "dataset", {"type": "reference", "source": "mygene.info"}, manifest_path=manifest)
    else:
        print("   gene symbol map missing: run  python scripts/build_gene_symbols.py")
    geo = root / "data" / "reference" / "ne_110m_admin_0_countries.geojson"
    if geo.exists():
        register_file(ledger, geo, "dataset", {"type": "reference", "source": "Natural Earth 110m"}, manifest_path=manifest)

    print("4. Run manifest (code, config and environment fingerprint)")
    rm = build_run_manifest(config={"script": "scripts/build_data.py"}, dataset_hashes={}, model_hashes={},
                            seed=20260929, repo_root=root)
    out = root / "artifacts" / "reports" / "run_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import json
    out.write_text(json.dumps(rm, indent=2, default=str))

    print("\nSummary")
    env = root / "data" / "processed" / "env_panel.parquet"
    if env.exists():
        d = pd.read_parquet(env)
        miss = d[["pm25", "pm10", "o3", "no2", "uv"]].isna().mean().mean()
        print(f"  env_panel      rows={len(d):5d}  {d['date'].min():%Y-%m-%d}..{d['date'].max():%Y-%m-%d}  missing(AQ)={miss:.1%}  sha={sha256_file(env)[:12]}")
    for sid in (cfg["discovery"], cfg["replication"]):
        p = root / "data" / "processed" / f"osdr_{sid}_expr.parquet"
        if p.exists():
            e = pd.read_parquet(p)
            print(f"  {sid:14s} genes={e.shape[0]:5d} samples={e.shape[1]:3d}  sha={sha256_file(p)[:12]}")
    print(f"  ledger height  {ledger.height()}   chain valid: {ledger.verify()['valid']}")
    for b in blocked:
        print(" ", b)
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
