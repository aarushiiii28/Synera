"""Space-biology testbed (Track A, REAL NASA OSDR data): design, per-gene results, power, consistency.

All numbers come from ``artifacts/results/space_biology.json`` and ``osdr_genes.json``, which are written by
``scripts/build_space_biology.py`` from the real expression files. Nothing here is a constant.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.core.deps import read_result_json

router = APIRouter(prefix="/space-biology", tags=["Space Biology"])


def _report() -> dict:
    rep = read_result_json("space_biology.json")
    if not rep:
        raise HTTPException(404, "Track A results not built yet: run  python scripts/build_space_biology.py")
    return rep


@router.get("/overview", summary="2x2 design, counts by type, power limit and cross-tissue caveat")
def overview():
    rep = _report()
    ov = rep["overview"]
    power = rep["power"]
    n_hits = ov["counts_by_type"]["SYNERGISTIC"] + ov["counts_by_type"]["ANTAGONISTIC"]
    return {
        **ov,
        "interaction_counts": ov["counts_by_type"],
        "evidence_level": rep["consistency"]["evidence_level"],
        "consistency": rep["consistency"],
        "power": {"minimum_detectable_log2_80pct_power": power["minimum_detectable_log2_80pct_power"],
                  "note": power["minimum_detectable_note"], "by_log2_effect": power["by_log2_effect"],
                  "provenance": power["provenance"]},
        "positive_controls": rep["positive_controls"], "null_calibration": rep["null_calibration_osd211"], "pc1": rep["pc1"],
        "statement": ("No gene shows a statistically significant radiation x unloading interaction after FDR control. "
                      "The table below is an exploratory ranking, not a list of findings."
                      if n_hits == 0 else "Genes with q below the FDR threshold are listed as candidate findings."),
    }


@router.get("/genes", summary="Per-gene interaction results (all tested genes; compact form for the volcano)")
def genes(sort: str = Query("p", pattern="^(p|q|b_AB)$"), limit: int = Query(200, ge=1, le=30000),
          offset: int = Query(0, ge=0), compact: bool = False, search: str | None = Query(None, max_length=40)):
    data = read_result_json("osdr_genes.json")
    if data is None:
        raise HTTPException(404, "Track A gene table not built yet: run  python scripts/build_space_biology.py")
    if search:
        s = search.lower()
        data = [g for g in data if s in g["gene_symbol"].lower() or s in g["ensembl_id"].lower() or s in g.get("name", "").lower()]
    if sort == "q":
        data = sorted(data, key=lambda g: (g["q"], g["p"]))
    elif sort == "b_AB":
        data = sorted(data, key=lambda g: abs(g["b_AB"]), reverse=True)
    if compact:   # [gene, b_AB, -log10 p, type, q] for plotting every tested gene
        return {"total": len(data), "columns": ["gene", "b_AB", "neg_log10_p", "type", "q"],
                "rows": [[g["gene_symbol"], g["b_AB"], g["neg_log10_p"], g["type"], g["q"]] for g in data[offset:offset + limit]]}
    return {"total": len(data), "items": data[offset:offset + limit]}
