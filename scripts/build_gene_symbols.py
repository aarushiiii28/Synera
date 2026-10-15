"""Build data/reference/mouse_ensembl_symbols.tsv: Ensembl gene id -> official symbol and name.

Source: MyGene.info batch query API (https://mygene.info/v3/query), which aggregates NCBI Gene / Ensembl.
The OSDR processed count tables only carry Ensembl ids, so this map is what lets the UI show readable
gene names. The retrieved table is hashed and registered in the provenance ledger (idempotent).
Run:  python scripts/build_gene_symbols.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synera_core.provenance.ledger import Ledger  # noqa: E402
from synera_core.provenance.manifest import register_file  # noqa: E402

OUT = ROOT / "data" / "reference" / "mouse_ensembl_symbols.tsv"
URL = "https://mygene.info/v3/query"


def main() -> None:
    ids: set[str] = set()
    for study in ("OSD-211", "OSD-237"):
        ids.update(pd.read_parquet(ROOT / "data" / "processed" / f"osdr_{study}_expr.parquet").index.astype(str))
    ids_l = sorted(ids)
    rows, raw_hits = [], 0
    with httpx.Client(timeout=60, headers={"User-Agent": "SYNERA/1.0 (research)"}) as client:
        for i in range(0, len(ids_l), 1000):
            chunk = ids_l[i:i + 1000]
            r = client.post(URL, data={"q": ",".join(chunk), "scopes": "ensembl.gene", "species": "mouse",
                                       "fields": "symbol,name"})
            r.raise_for_status()
            for hit in r.json():
                raw_hits += 1
                if hit.get("notfound"):
                    continue
                rows.append({"ensembl_id": hit["query"], "symbol": hit.get("symbol", ""), "name": hit.get("name", "")})
            print(f"  {min(i + 1000, len(ids_l))}/{len(ids_l)}")
    df = pd.DataFrame(rows).drop_duplicates("ensembl_id").sort_values("ensembl_id")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, sep="\t", index=False)
    meta = {"source": URL, "retrieved": dt.datetime.now(dt.UTC).isoformat(), "queried": len(ids_l), "mapped": len(df)}
    (OUT.with_suffix(".source.json")).write_text(json.dumps(meta, indent=2))
    ledger = Ledger(ROOT / "artifacts" / "ledger.db", ROOT / "configs" / "signer.key")
    h, _ = register_file(ledger, OUT, "dataset", meta, manifest_path=ROOT / "data" / "MANIFEST.json")
    print(f"mapped {len(df)}/{len(ids_l)} ids; sha256={h}")


if __name__ == "__main__":
    main()
