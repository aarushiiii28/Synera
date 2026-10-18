"""Tamper simulator: real hashes, honest detector reporting, originals never touched."""
import pytest

from synera_core.provenance.hashing import sha256_file
from synera_core.security import tamper_sim
from synera_core.security.tamper_sim import simulate_attack


@pytest.fixture()
def reg(tiny_registry, monkeypatch):
    monkeypatch.setattr(tamper_sim, "get_spec", lambda i: tiny_registry["spec"])
    return tiny_registry


def _differ(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


def test_bit_flip_changes_hash_completely_and_leaves_original(reg):
    before = sha256_file(reg["path"])
    r = simulate_attack("tiny_panel", "bit_flip", seed=1, ledger=reg["ledger"])
    assert r["hash_match"] is False and r["verdict"] == "RESULT BLOCKED FROM VERIFIED STATUS"
    assert r["original_hash"] == before
    assert _differ(r["original_hash"], r["tampered_hash"]) >= 30      # a real SHA-256 avalanche, not a string edit
    assert sha256_file(reg["path"]) == before


@pytest.mark.parametrize("mode", ["subtle_edit", "row_edit", "inject_outliers", "drift_units", "poison_labels"])
def test_every_table_attack_changes_the_dataframe_hash(reg, mode):
    before = sha256_file(reg["path"])
    r = simulate_attack("tiny_panel", mode, magnitude=0.1, seed=2, ledger=reg["ledger"])
    assert r["hash_match"] is False
    assert _differ(r["original_hash"], r["tampered_hash"]) >= 30
    assert "hash_mismatch" in r["detections"]
    assert sha256_file(reg["path"]) == before


def test_attacks_work_on_frames_with_boolean_flag_columns(reg):
    """The real benchmark data carries boolean QC flag columns; they must be left alone, not 'edited'."""
    import pandas as pd
    df = pd.read_parquet(reg["path"])
    df["flag_temp"] = False
    df.to_parquet(reg["path"], index=False)
    for mode in ("subtle_edit", "row_edit", "inject_outliers"):
        r = simulate_attack("tiny_panel", mode, magnitude=0.05, seed=4, ledger=reg["ledger"])
        assert r["hash_match"] is False


def test_attacks_work_on_frames_with_integer_columns(reg):
    """Integer measurement columns (e.g. a wind or UV index stored as int) must be editable, not crash with a 500."""
    import pandas as pd
    df = pd.read_parquet(reg["path"])
    first = next(c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]) and c != "outcome")
    df[first] = df[first].round().astype("int64")
    df.to_parquet(reg["path"], index=False)
    for mode in ("subtle_edit", "row_edit", "inject_outliers", "drift_units"):
        r = simulate_attack("tiny_panel", mode, magnitude=0.2, seed=5, ledger=reg["ledger"])
        assert r["hash_match"] is False


def test_different_modes_do_not_return_identical_results(reg):
    a = simulate_attack("tiny_panel", "subtle_edit", magnitude=0.05, seed=3, ledger=reg["ledger"])
    b = simulate_attack("tiny_panel", "row_edit", magnitude=0.05, seed=3, ledger=reg["ledger"])
    assert a["tampered_hash"] != b["tampered_hash"]
    assert a["description"] != b["description"]


def test_swap_model_detected_by_hash_and_behaviour(reg, monkeypatch):
    from synera_core.pipeline import registry
    spec = reg["spec"]
    monkeypatch.setattr(registry, "get_spec", lambda i: spec)
    r = simulate_attack("tiny_panel", "swap_model", seed=0, ledger=reg["ledger"])
    names = set(r["detections"])
    assert "weights_hash" in names and "probe_predictions" in names
    assert r["model"]["before"]["ok"] is True


def test_ledger_tamper_breaks_the_copy_not_the_real_chain(reg):
    for i in range(4):
        reg["ledger"].append("DATASET_REGISTERED", {"i": i}, artifact_hashes=[f"{i:064x}"])
    r = simulate_attack("tiny_panel", "ledger_tamper", ledger=reg["ledger"])
    assert r["ledger"]["before"]["valid"] is True
    assert r["ledger"]["after"]["valid"] is False
    assert reg["ledger"].verify()["valid"] is True


def test_a_row_edit_always_changes_the_data(reg):
    """Multiplying a zero by 10 is a no-op, which would show 'no tampering' for a real edit: the simulator must pick a cell that changes."""
    import pandas as pd
    df = pd.read_parquet(reg["path"])
    cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != "outcome"]
    df.loc[:, cols] = 0.0
    for i in range(len(df)):                      # almost every cell is zero, but every row has one real value: a naive random pick would usually hit a zero
        df.iloc[i, df.columns.get_loc(cols[i % len(cols)])] = 2.0
    df.to_parquet(reg["path"], index=False)
    for seed in range(8):
        r = simulate_attack("tiny_panel", "row_edit", magnitude=0.001, seed=seed, ledger=reg["ledger"])
        assert r["hash_match"] is False, f"seed {seed}: the edit changed nothing"
