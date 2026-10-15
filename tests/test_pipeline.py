"""The orchestrator end to end on a tiny dataset: real steps, real replay, ledger writes, gates."""
import time

from synera_core.pipeline.gates import run_gates
from synera_core.pipeline.orchestrator import STEPS, execute_run
from synera_core.security.pipeline_integrity import current_src_tree_hash

QUICK = {"n_boot": 49, "n_ci": 20, "seed": 5}


def test_run_has_nine_real_measured_steps(tiny_registry):
    events = []
    t0 = time.time()
    res = execute_run("tiny_panel", QUICK, emit=events.append, ledger=tiny_registry["ledger"], run_id="run_test")
    wall = time.time() - t0
    assert res["status"] == "COMPLETED", res.get("error")
    done = [e for e in events if e["status"] == "DONE"]
    assert [e["step_name"] for e in done] == [n for n, _ in STEPS]
    # durations are measured, not scripted: they sum to (about) the wall clock and are not all identical
    durs = [e["duration_s"] for e in done]
    assert abs(sum(durs) - wall) < 0.35 * wall + 1.0
    assert len(set(round(d, 2) for d in durs)) > 3
    assert res["replay"]["matches"] is True
    assert res["ledger_block"] is not None
    assert tiny_registry["ledger"].verify()["valid"]


def test_simulated_findings_are_capped_and_gates_explain(tiny_registry):
    res = execute_run("tiny_panel", {**QUICK, "effect_gate": 0.02}, ledger=tiny_registry["ledger"], run_id="run_cap")
    assert res["status"] == "COMPLETED", res.get("error")
    assert all(f["status"] != "VERIFIED" for f in res["findings"])
    for f in res["findings"]:
        assert f["provenance"] == "SIMULATED"
        g8 = next(g for g in f["gates"] if g["id"] == "G8_REAL_PROVENANCE")
        assert g8["passed"] is False and "SIMULATED provenance cap" in g8["reason"]
        g7 = next(g for g in f["gates"] if g["id"] == "G7_INDEPENDENT_REPLICATION")
        assert g7["passed"] is False


def test_tampered_dataset_blocks_the_run(tiny_registry):
    p = tiny_registry["path"]
    raw = bytearray(p.read_bytes())
    raw[len(raw) // 2] ^= 1
    p.write_bytes(bytes(raw))
    res = execute_run("tiny_panel", QUICK, ledger=tiny_registry["ledger"], run_id="run_blocked")
    assert res["status"] == "BLOCKED"
    assert "integrity failure" in res["error"]
    assert any(b.block_type == "INTEGRITY_ALERT" for b in tiny_registry["ledger"].iter_blocks())
    assert tiny_registry["ledger"].verify()["valid"]          # the chain itself is still intact


def test_gates_block_on_code_drift_and_missing_replay(tiny_registry):
    res = execute_run("tiny_panel", {**QUICK, "effect_gate": 0.02}, ledger=tiny_registry["ledger"], run_id="run_g")
    if not res["findings"]:
        return
    f = res["findings"][0]
    f = {**f, "dataset_hashes": f["dataset_hashes"]}
    ctx = {"replay": res["replay"], "src_tree_hash": res["src_tree_hash"]}
    ok = run_gates(f, tiny_registry["ledger"], tiny_registry["spec"].abs_path, res["dataset_hash"], ctx, current_src_tree_hash())
    assert ok["new_status"] != "BLOCKED"
    drift = run_gates(f, tiny_registry["ledger"], tiny_registry["spec"].abs_path, res["dataset_hash"], ctx, "0" * 64)
    assert drift["new_status"] == "BLOCKED" and drift["verdict"] == "RESULT BLOCKED FROM VERIFIED STATUS"
    nodata = run_gates(f, tiny_registry["ledger"], tiny_registry["spec"].abs_path, res["dataset_hash"], {"replay": None, "src_tree_hash": None},
                       current_src_tree_hash())
    assert any(g["id"] == "G4_REPRODUCIBILITY" and not g["passed"] for g in nodata["gates"])
