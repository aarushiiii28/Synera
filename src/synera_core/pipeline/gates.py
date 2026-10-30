"""The VERIFIED gate: every condition, evaluated live, with pass/fail and the reason.

A finding is VERIFIED only if *all* gates pass. Integrity-critical failures (G1 data, G2 chain, G3 inclusion,
G4 replay/code drift, G5 blocking security check) make the result ``BLOCKED``; every other failed gate simply
leaves the finding at its current status and states why. Statistical detectors (IsolationForest, MCD,
autoencoder, KS/PSI, label-flip) are advisory: they appear in the evidence but never block on their own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from synera_core.provenance.hashing import sha256_file, sha256_obj
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.merkle import verify_proof

# Evidence levels that satisfy G7: a separate dataset, or later data that was never used to find the pair (checked with the engine's unchanged rules).
REPLICATION_LEVELS = ("INDEPENDENT_REPLICATION", "LATER_DATA_REPLICATION")
INTEGRITY_GATES = {"G1_DATA_INTEGRITY", "G2_LEDGER_CHAIN", "G3_LEDGER_INCLUSION", "G4_REPRODUCIBILITY", "G5_SECURITY_BLOCKING"}


def finding_hash(finding: dict[str, Any]) -> str:
    """Hash of the scientific content of a finding (never its mutable status), recorded in the ledger."""
    core = {
        "id": finding["id"], "dataset_hashes": finding.get("dataset_hashes"), "stressors": finding["stressors"],
        "feature": finding.get("feature"), "type": finding["type"],
        "effect": finding["effect"], "p": finding["stats"]["p"], "n": finding["stats"]["n"],
        "methods": finding["methods"], "config": finding.get("config"),
    }
    return sha256_obj(core)


def _gate(gid: str, label: str, passed: bool, reason: str, **extra: Any) -> dict[str, Any]:
    return {"id": gid, "label": label, "passed": bool(passed), "reason": reason, "integrity": gid in INTEGRITY_GATES, **extra}


def run_gates(finding: dict[str, Any], ledger: Ledger, dataset_path: Path | None, expected_dataset_hash: str | None,
              run: dict[str, Any] | None, current_src_hash: str | None) -> dict[str, Any]:
    """Evaluate the VERIFIED conditions for ``finding`` (a dict as stored by the API)."""
    gates: list[dict[str, Any]] = []

    # G1 - the dataset on disk is byte-identical to what was registered
    if dataset_path is not None and expected_dataset_hash:
        actual = sha256_file(dataset_path) if dataset_path.exists() else ""
        gates.append(_gate("G1_DATA_INTEGRITY", "Dataset hash matches the ledger", actual == expected_dataset_hash,
                           "SHA-256 of the dataset equals the registered hash" if actual == expected_dataset_hash else
                           f"hash mismatch: registered {expected_dataset_hash[:12]}..., on disk {actual[:12] or 'missing'}...",
                           expected=expected_dataset_hash, actual=actual))
    else:
        gates.append(_gate("G1_DATA_INTEGRITY", "Dataset hash matches the ledger", False, "no registered dataset hash to compare against"))

    # G2 - the ledger chain verifies end to end
    v = ledger.verify()
    gates.append(_gate("G2_LEDGER_CHAIN", "Ledger chain valid", v["valid"],
                       f"chain of {v['height']} blocks verifies" if v["valid"] else f"{len(v['issues'])} issue(s): {v['issues'][:2]}",
                       height=v["height"], head=v["head"]))

    # G3 - the finding's hash is included in a ledger block (Merkle proof)
    fh = finding_hash({**finding, "dataset_hashes": finding.get("dataset_hashes")})
    proof_ok, block_idx, proof = False, None, []
    for blk, pf in ledger.find_by_artifact(fh):
        if verify_proof(fh, pf, blk.merkle_root):
            proof_ok, block_idx, proof = True, blk.index, pf
            break
    gates.append(_gate("G3_LEDGER_INCLUSION", "Finding hash included in the ledger (Merkle proof)", proof_ok,
                       f"inclusion proven in block {block_idx}" if proof_ok else "finding hash is not in any ledger block",
                       finding_hash=fh, block_index=block_idx, merkle_proof=[{"side": s, "hash": h} for s, h in proof]))

    # G4 - the run replayed to an identical result and the code is unchanged
    replay = (run or {}).get("replay") or {}
    drift = bool(current_src_hash and run and run.get("src_tree_hash") and current_src_hash != run["src_tree_hash"])
    g4 = bool(replay.get("matches")) and not drift
    gates.append(_gate("G4_REPRODUCIBILITY", "Replay reproduces the result; code unchanged", g4,
                       ("replay hash identical" if g4 else
                        ("code changed since the run (source tree hash differs)" if drift else
                         "replay did not match" if replay else "no replay recorded for this run")),
                       original=replay.get("original_hash"), replay=replay.get("replay_hash")))

    # G5 - no blocking security check (statistical detectors are advisory)
    sec = finding.get("security") or {}
    blocking = [c for c in sec.get("checks", []) if c.get("blocking") and c.get("status") == "FAIL"]
    advisory = [c["name"] for c in sec.get("checks", []) if not c.get("blocking") and c.get("status") != "PASS"]
    gates.append(_gate("G5_SECURITY_BLOCKING", "No blocking security failure", not blocking,
                       "no integrity-critical check failed" + (f"; advisory warnings: {', '.join(advisory)}" if advisory else "")
                       if not blocking else f"blocking failure: {[c['name'] for c in blocking]}",
                       advisory=advisory))

    # G6 - statistical validation
    status = finding.get("status")
    g6 = status in ("VALIDATED", "VERIFIED")
    gates.append(_gate("G6_STATISTICAL_VALIDATION", "Statistically validated", g6,
                       "passes FDR, effect gate, CI and method agreement" if g6 else f"status is {status}: not fully validated"))

    # G7 - replication
    rep = finding.get("replication") or {}
    level = finding.get("evidence_level") or rep.get("evidence_level")
    g7 = bool(rep.get("replicated")) and level in REPLICATION_LEVELS
    if not rep:
        why = "no replication was attempted"
    elif not rep.get("replicated"):
        why = f"did not replicate ({level})"
    elif level not in REPLICATION_LEVELS:
        why = f"replicated only as {level}: not independent"
    elif level == "LATER_DATA_REPLICATION":
        why = "kept again on later data that was not used to find it (same grid operator, later period)"
    else:
        why = "replicated in an independent dataset"
    gates.append(_gate("G7_INDEPENDENT_REPLICATION", "Replicated in an independent dataset or on later data", g7, why, evidence_level=level))

    # G8 - provenance cap
    real = finding.get("provenance") == "REAL"
    gates.append(_gate("G8_REAL_PROVENANCE", "Built from REAL data", real,
                       "real data" if real else "SIMULATED provenance cap: findings from simulated data are capped at VALIDATED"))

    failed_integrity = [g for g in gates if g["integrity"] and not g["passed"]]
    allowed = all(g["passed"] for g in gates)
    if failed_integrity:
        new_status = "BLOCKED"
    elif allowed:
        new_status = "VERIFIED"
    else:
        new_status = status if status in ("CANDIDATE", "VALIDATED", "REJECTED") else "VALIDATED"
    reasons = [f"{g['label']}: {g['reason']}" for g in gates if not g["passed"]]
    return {"gates": gates, "allowed": allowed, "new_status": new_status, "reasons": reasons,
            "verdict": "RESULT BLOCKED FROM VERIFIED STATUS" if failed_integrity else None}
