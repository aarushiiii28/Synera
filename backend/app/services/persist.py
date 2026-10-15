"""Persistence helpers: registry -> Dataset rows, pipeline results -> Run / Finding / SecurityReport rows."""

from __future__ import annotations

import json
import time
from typing import Any

from sqlmodel import Session, delete
from synera_core.pipeline.registry import get_registry, summarize
from synera_core.provenance.ledger import Ledger

from backend.app.core.deps import read_result_json
from backend.app.db.models import Dataset, ExperimentSummary, Finding, Run, SecurityReport


def sync_datasets(session: Session, ledger: Ledger) -> None:
    """Upsert one Dataset row per registry entry with facts computed from the files themselves."""
    for spec in get_registry().values():
        s = summarize(spec)
        qc: dict[str, Any] = {}
        if spec.kind == "factorial" and spec.abs_path.exists():
            qcp = spec.abs_path.with_name(spec.abs_path.name.replace("_expr.parquet", "_qc.json"))
            if qcp.exists():
                qc = json.loads(qcp.read_text())
        block = None
        if s.get("available"):
            hits = ledger.find_by_artifact(s["sha256"])
            block = hits[0][0].index if hits else None
        row = Dataset(
            id=spec.id, name=spec.name, track=spec.track, kind=spec.kind, provenance=spec.provenance,
            hash=s.get("sha256", ""), features_count=int(s.get("features", 0)),
            samples_count=int(s.get("samples", s.get("rows", 0))), description=spec.description, role=spec.role,
            runnable=spec.runnable, path=spec.path, created_at=time.time(), summary=s, qc=qc, ledger_block=block,
        )
        session.merge(row)
    session.commit()


def finding_row(f: dict) -> Finding:
    a, b = (f["stressors"] + ["", ""])[:2]
    return Finding(
        id=f["id"], run_id=f["run_id"], dataset_id=f["dataset_ids"][0], track=f["track"], provenance=f["provenance"],
        evidence_level=f["evidence_level"], stressor_a=a, stressor_b=b, feature=f.get("feature"),
        interaction_type=f["type"], status=f["status"], q_value=float(f["stats"]["q"]),
        effect_size=float(f["effect"].get("effect_size") if f["effect"].get("effect_size") is not None else abs(f["effect"]["b_AB"])),
        created_at=time.time(), effect=f["effect"], stats=f["stats"], methods=f["methods"], replication=f.get("replication"),
        security=f["security"], confidence=f.get("confidence"), surface=f.get("surface"), gates=f.get("gates", []),
        history=f.get("history", []), dataset_hashes=f.get("dataset_hashes", {}), config=f.get("config", {}),
    )


def persist_run(session: Session, result: dict) -> None:
    """Write the final state of a pipeline run. Findings of the same dataset and pair are replaced."""
    run = session.get(Run, result["run_id"])
    if run is None:
        run = Run(id=result["run_id"], dataset_id=result["dataset_id"], status="RUNNING", created_at=time.time())
    run.status = result["status"]
    run.finished_at = time.time()
    run.config_hash = result["config_hash"]
    run.dataset_hash = result.get("dataset_hash") or run.dataset_hash
    run.result_hash = result.get("result_hash")
    run.ledger_block = result.get("ledger_block")
    run.src_tree_hash = result.get("src_tree_hash")
    run.runtime_s = result.get("runtime_s")
    run.error = result.get("error")
    run.params, run.summary = result["params"], result.get("summary") or {}
    run.stage_counts, run.security = result.get("stage_counts"), result.get("security")
    run.replay, run.consistency, run.pairs = result.get("replay"), result.get("consistency"), result.get("pairs")
    session.add(run)

    if result["status"] in ("COMPLETED",):
        # Replace the findings this dataset's previous runs produced, then insert the new ones.
        session.exec(delete(Finding).where(Finding.dataset_id == result["dataset_id"]))
        for f in result["findings"]:
            session.merge(finding_row(f))
        session.add(ExperimentSummary(run_id=run.id, dataset_id=run.dataset_id, config_hash=run.config_hash,
                                      result_hash=run.result_hash or "", status=run.status, ledger_block=run.ledger_block,
                                      runtime_s=run.runtime_s, created_at=time.time()))
    far = (read_result_json("benchmark.json") or {}).get("security", {}).get("clean_false_alarm_rate", {})
    if result.get("security"):
        session.add(SecurityReport(id=f"sec_{result['run_id']}", dataset_id=result["dataset_id"], run_id=result["run_id"],
                                   status=result["security"]["status"], created_at=time.time(),
                                   false_alarm_rates=far, checks=result["security"]["checks"]))
    session.commit()


def finding_dict(row: Finding) -> dict:
    """Public representation of a finding."""
    return {
        "id": row.id, "run_id": row.run_id, "track": row.track, "provenance": row.provenance, "evidence_level": row.evidence_level,
        "dataset_id": row.dataset_id, "stressors": [row.stressor_a, row.stressor_b], "feature": row.feature,
        "type": row.interaction_type, "status": row.status, "effect": row.effect, "stats": row.stats, "methods": row.methods,
        "replication": row.replication, "security": {"status": row.security.get("status"), "checks": row.security.get("checks", [])},
        "confidence": row.confidence, "gates": row.gates, "history": row.history, "has_surface": row.surface is not None,
        "q_value": row.q_value, "effect_size": row.effect_size,
    }
