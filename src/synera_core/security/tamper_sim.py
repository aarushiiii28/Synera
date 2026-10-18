"""Tamper simulator: the demo attacks. They operate ONLY on temporary copies, never on registered data.

For a dataset and an attack mode the simulator produces a tampered copy, then runs the *same* integrity
machinery the pipeline uses: the SHA-256 comparison (cryptographic) and the statistical detector ensemble
(advisory). The hash verdict is what blocks a result; the detectors show what statistics can and cannot see.

Modes
    bit_flip         flip one bit of the dataset file (byte-level change; statistical scan not applicable)
    subtle_edit      shift cells by +0.3 SD, inside physical limits  (statistically near-invisible)
    row_edit         multiply cells by 10 (decimal-shift / fat-finger edit)
    inject_outliers  push several columns of some rows to +/-4 robust SD
    drift_units      Celsius -> Fahrenheit on a temperature column
    poison_labels    flip a binary factor label
    swap_model       perturb trained model weights (hash AND behavioural verification)
    ledger_tamper    edit one ledger block payload on a COPY of the ledger and verify the chain
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from synera_core.pipeline.registry import get_spec
from synera_core.provenance.hashing import sha256_dataframe, sha256_file
from synera_core.provenance.ledger import Ledger
from synera_core.security.poisoning import Baseline, scan_dataset

MODES = ["bit_flip", "subtle_edit", "row_edit", "inject_outliers", "drift_units", "poison_labels", "swap_model", "ledger_tamper"]
DESCRIPTIONS = {
    "bit_flip": "One bit of the dataset file is flipped.",
    "subtle_edit": "A fraction of cells is shifted by +0.3 standard deviations, staying inside physical limits.",
    "row_edit": "A fraction of cells is multiplied by 10 (a decimal-shift edit).",
    "inject_outliers": "A fraction of rows gets four columns pushed to +/-4 robust standard deviations.",
    "drift_units": "A temperature column is converted from Celsius to Fahrenheit.",
    "poison_labels": "A fraction of a binary factor label is flipped.",
    "swap_model": "The weights of a trained model are perturbed and the model re-verified.",
    "ledger_tamper": "One ledger block payload is edited on a temporary copy of the ledger.",
}
BLOCKING_VERDICT = "RESULT BLOCKED FROM VERIFIED STATUS"


def _frame_for(dataset_id: str) -> tuple[pd.DataFrame, Path, str]:
    """Return (numeric dataframe to tamper, source file, kind)."""
    spec = get_spec(dataset_id)
    p = spec.abs_path
    if not p.exists():
        raise FileNotFoundError(f"dataset file missing: {p.name}")
    if spec.kind == "factorial":
        expr = pd.read_parquet(p)
        return expr.T.reset_index(drop=True).astype(float), p, "factorial"
    df = pd.read_parquet(p)
    return df, p, spec.kind


def _is_measure(s: pd.Series) -> bool:
    """A real-valued measurement column (booleans and strings are flags/labels, not measurements)."""
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _measure_columns(df: pd.DataFrame) -> list[str]:
    """Numeric, non-boolean columns, chosen from the dtypes at once (a per-column loop is slow on 24,000-gene tables)."""
    return [c for c, t in df.dtypes.items() if pd.api.types.is_numeric_dtype(t) and not pd.api.types.is_bool_dtype(t)]


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in _measure_columns(df) if c != "outcome"] or list(df.columns[:1])


# What is identical between attacks on the same file is computed once: the original's fingerprint and the detectors' baseline.
_ORIGINAL_HASH: dict[tuple, str] = {}
_BASELINES: dict[tuple, tuple] = {}


def _scan(clean: pd.DataFrame, tampered: pd.DataFrame, meta: pd.DataFrame | None, kind: str, cache_key: tuple | None = None) -> dict[str, Any]:
    if kind == "factorial":                      # 21 samples x ~25k genes: scan principal-component scores
        key = (cache_key, "factorial") if cache_key else None
        if key and key in _BASELINES:
            mu, vt, base = _BASELINES[key]
        else:
            Xc = clean.to_numpy(float)
            mu = Xc.mean(0)
            _, _, vt = np.linalg.svd(Xc - mu, full_matrices=False)
            cols = [f"PC{i + 1}" for i in range(5)]
            base = Baseline.from_frame(pd.DataFrame((Xc - mu) @ vt[:5].T, columns=cols))
            if key:
                _BASELINES[key] = (mu, vt, base)
        cols = [f"PC{i + 1}" for i in range(5)]
        rep = scan_dataset(pd.DataFrame((tampered.to_numpy(float) - mu) @ vt[:5].T, columns=cols), baseline=base)
    else:
        num = _measure_columns(clean)
        base = Baseline.from_frame(clean[num], meta=meta[0] if meta else None)
        extra = [c for c in ("city", "date") if c in tampered.columns]
        rep = scan_dataset(tampered[[*extra, *num]], meta=meta[1] if meta else None, baseline=base)
    return {"status": rep.status, "checks": [{k: c[k] for k in ("name", "status", "score", "detail", "blocking")} for c in rep.checks]}


def _model_demo(seed: int) -> dict[str, Any]:
    """Train a small MLP on the benchmark data, register it in a *temporary* ledger, swap its weights, re-verify."""
    import torch
    import torch.nn as nn

    from synera_core.pipeline.registry import get_spec as gs
    from synera_core.security.model_verify import register_model, verify_model

    spec = gs("benchmark_track_b")
    df = pd.read_parquet(spec.abs_path)
    X = df[["heat_index", "pm25", "rh", "o3"]].to_numpy(np.float32)
    y = df["outcome"].to_numpy(np.float32)
    torch.manual_seed(seed)
    net = nn.Sequential(nn.Linear(4, 16), nn.ReLU(), nn.Linear(16, 1))
    opt = torch.optim.Adam(net.parameters(), lr=0.01)
    Xt, yt = torch.tensor(X), torch.tensor(y)
    for _ in range(150):
        opt.zero_grad()
        nn.functional.mse_loss(net(Xt).squeeze(-1), yt).backward()
        opt.step()
    tmp = Path(tempfile.mkdtemp(prefix="synera_model_"))
    wpath = tmp / "model.pt"
    torch.save(net.state_dict(), wpath)

    def predict(path: Path, Xin: np.ndarray) -> np.ndarray:
        m = nn.Sequential(nn.Linear(4, 16), nn.ReLU(), nn.Linear(16, 1))
        m.load_state_dict(torch.load(path, weights_only=True))
        with torch.no_grad():
            return m(torch.tensor(Xin, dtype=torch.float32)).squeeze(-1).numpy()

    probe, hx, hy = X[:25], X[-500:], y[-500:]
    led = Ledger(tmp / "demo_ledger.db", tmp / "demo.key")
    ref = register_model(led, wpath, predict, probe, hx, hy, sha256_file(spec.abs_path), seed, {"torch": torch.__version__})
    before = verify_model(wpath, predict, ref, probe, hx, hy)
    sd = torch.load(wpath, weights_only=True)
    sd["0.weight"] = sd["0.weight"] + 1e-3 * torch.randn_like(sd["0.weight"])
    torch.save(sd, wpath)
    after = verify_model(wpath, predict, ref, probe, hx, hy)
    shutil.rmtree(tmp, ignore_errors=True)
    return {"before": before, "after": after, "reference": {k: v for k, v in ref.items() if k != "versions"}}


def _ledger_demo(real_ledger: Ledger) -> dict[str, Any]:
    """Copy the real ledger, edit one payload in the copy (triggers dropped, as an attacker with disk access would), verify both."""
    tmp = Path(tempfile.mkdtemp(prefix="synera_ledger_"))
    copy = tmp / "ledger_copy.db"
    shutil.copy(real_ledger.db_path, copy)
    key = tmp / "copy.key"
    shutil.copy(real_ledger.key_path, key)
    before = Ledger(copy, key).verify()
    con = sqlite3.connect(copy)
    for (name,) in con.execute("select name from sqlite_master where type='trigger'").fetchall():
        con.execute(f"drop trigger {name}")
    target = max(1, before["height"] // 2)
    row = con.execute("select payload_json from blocks where block_index = ?", (target,)).fetchone()
    forged = (row[0].rstrip()[:-1] + ',"forged":true}') if row else "{}"       # still valid JSON, but not what was signed
    con.execute("update blocks set payload_json = ? where block_index = ?", (forged, target))
    con.commit()
    con.close()
    after = Ledger(copy, key).verify()
    shutil.rmtree(tmp, ignore_errors=True)
    return {"target_block": target, "before": {k: before[k] for k in ("valid", "height", "head")},
            "after": {"valid": after["valid"], "height": after["height"], "issues": after["issues"][:5]}}


def simulate_attack(dataset_id: str, mode: str, magnitude: float = 0.05, seed: int = 0, ledger: Ledger | None = None) -> dict[str, Any]:
    """Run one attack on a temporary copy of ``dataset_id`` and report what the integrity layer sees."""
    if mode not in MODES:
        raise ValueError(f"unsupported mode '{mode}'")
    magnitude = float(min(max(magnitude, 0.001), 0.5))
    rng = np.random.default_rng(seed)
    out: dict[str, Any] = {"mode": mode, "dataset_id": dataset_id, "description": DESCRIPTIONS[mode], "magnitude": magnitude,
                           "temporary_copy": True}

    if mode == "ledger_tamper":
        from synera_core.provenance.store import open_ledger
        d = _ledger_demo(ledger or open_ledger())
        broken = not d["after"]["valid"]
        out.update({"ledger": d, "hash_match": not broken, "detections": ["ledger_chain"] if broken else [],
                    "original_hash": d["before"]["head"], "tampered_hash": (d["after"]["issues"][0]["code"] if d["after"]["issues"] else d["before"]["head"]),
                    "verdict": BLOCKING_VERDICT if broken else "NO TAMPERING DETECTED", "detectors": [], "scan_notes": None,
                    "original_untouched": True})
        return out

    if mode == "swap_model":
        m = _model_demo(seed)
        bad = not m["after"]["ok"]
        out.update({"model": m, "hash_match": not bad, "detections": [c["name"] for c in m["after"]["checks"] if not c["ok"]],
                    "original_hash": m["reference"]["weights_sha256"],
                    "tampered_hash": next((c["detail"] for c in m["after"]["checks"] if c["name"] == "weights_hash"), ""),
                    "verdict": BLOCKING_VERDICT if bad else "NO TAMPERING DETECTED", "detectors": [], "scan_notes": None,
                    "original_untouched": True})
        return out

    clean, src, kind = _frame_for(dataset_id)
    orig_file_sha = sha256_file(src)
    stat = src.stat()
    cache_key = (str(src), stat.st_mtime_ns, stat.st_size)
    if cache_key not in _ORIGINAL_HASH:
        _ORIGINAL_HASH[cache_key] = sha256_dataframe(clean)
    orig_df_hash = _ORIGINAL_HASH[cache_key]
    tampered = clean.copy()
    detections: list[str] = []
    notes = None
    meta_pair = None

    if mode == "bit_flip":
        raw = bytearray(src.read_bytes())
        pos = int(rng.integers(len(raw) // 4, len(raw) - 8))
        raw[pos] ^= 1 << int(rng.integers(0, 8))
        tmpdir = Path(tempfile.mkdtemp(prefix="synera_tamper_"))
        tmp = tmpdir / src.name
        tmp.write_bytes(bytes(raw))
        tampered_file_sha = sha256_file(tmp)
        shutil.rmtree(tmpdir, ignore_errors=True)
        tampered_df_hash = orig_df_hash
        notes = "Byte-level change: the file hash differs completely; statistical scanning is not applicable to a corrupted container."
        scan = None
        hash_changed = tampered_file_sha != orig_file_sha
    else:
        num = _numeric_cols(tampered)
        n = len(tampered)
        k = max(1, int(round(magnitude * n)))
        rows = rng.choice(n, min(k, n), replace=False)
        sd = tampered[num].std().replace(0, 1.0)
        med = tampered[num].median()
        if mode in ("subtle_edit", "row_edit", "inject_outliers", "drift_units"):
            # an integer column cannot hold a shifted or scaled value; convert only those (assigning 24,000 float columns one by one is very slow)
            ints = [c for c, t in tampered[num].dtypes.items() if not pd.api.types.is_float_dtype(t)]
            if ints:
                tampered[ints] = tampered[ints].astype(float)
        if mode == "subtle_edit":
            for r in rows:
                c = num[int(rng.integers(0, len(num)))]
                tampered.loc[tampered.index[r], c] = tampered.loc[tampered.index[r], c] + 0.3 * sd[c]
        elif mode == "row_edit":
            for r in rows:
                # multiplying a zero by 10 changes nothing, so pick a cell the edit actually changes
                nonzero = np.flatnonzero(tampered.iloc[r][num].to_numpy(float) != 0)
                c = num[int(nonzero[rng.integers(0, len(nonzero))])] if len(nonzero) else num[int(rng.integers(0, len(num)))]
                tampered.loc[tampered.index[r], c] = tampered.loc[tampered.index[r], c] * 10.0
        elif mode == "inject_outliers":
            for r in rows:
                for c in rng.choice(num, min(4, len(num)), replace=False):
                    tampered.loc[tampered.index[r], c] = med[c] + rng.choice([-1, 1]) * 4.0 * sd[c]
        elif mode == "drift_units":
            temp = next((c for c in ("tmax", "tmean") if c in tampered.columns), num[0])
            tampered.loc[tampered.index[rows], temp] = tampered.loc[tampered.index[rows], temp] * 1.8 + 32.0
        elif mode == "poison_labels":
            if kind == "factorial":
                spec = get_spec(dataset_id)
                m = pd.read_parquet(spec.abs_meta_path)
                lab = m["radiation"].to_numpy().copy()
                clean_lab = pd.DataFrame({"radiation": lab})
            else:
                ref_col = "heat_index" if "heat_index" in clean.columns else num[0]
                lab = (clean[ref_col] > clean[ref_col].median()).astype(int).to_numpy().copy()
                clean_lab = pd.DataFrame({"hot_day": lab.copy()})
            flip = lab.copy()
            flip[rows] = 1 - flip[rows]
            name = clean_lab.columns[0]
            meta_pair = (clean_lab, pd.DataFrame({name: flip}))
            orig_df_hash = sha256_dataframe(clean_lab)
            tampered_df_hash = sha256_dataframe(meta_pair[1])
        tampered_df_hash = tampered_df_hash if mode == "poison_labels" else sha256_dataframe(tampered)
        tmpdir = Path(tempfile.mkdtemp(prefix="synera_tamper_"))
        tmp = tmpdir / "tampered.parquet"
        tampered.to_parquet(tmp)
        tampered_file_sha = sha256_file(tmp)
        shutil.rmtree(tmpdir, ignore_errors=True)
        hash_changed = tampered_df_hash != orig_df_hash
        scan = _scan(clean, tampered, meta_pair, kind, cache_key)

    if hash_changed:
        detections.append("hash_mismatch")
    detectors = scan["checks"] if scan else []
    for c in detectors:
        if c["status"] != "PASS":
            detections.append(c["name"])
    assert sha256_file(src) == orig_file_sha, "original dataset file was modified during simulation"
    out.update({
        "hash_match": not hash_changed,
        "original_file_sha": orig_file_sha, "tampered_file_sha": tampered_file_sha,
        "original_dataframe_hash": orig_df_hash, "tampered_dataframe_hash": tampered_df_hash,
        "original_hash": orig_file_sha if mode == "bit_flip" else orig_df_hash,
        "tampered_hash": tampered_file_sha if mode == "bit_flip" else tampered_df_hash,
        "detections": sorted(set(detections)),
        "statistical_detections": sorted({c["name"] for c in detectors if c["status"] != "PASS"}),
        "detectors": detectors, "scan_status": scan["status"] if scan else None,
        "hash_only": hash_changed and not any(c["status"] != "PASS" for c in detectors),
        "scan_notes": notes, "original_untouched": True,
        "verdict": BLOCKING_VERDICT if hash_changed else "NO TAMPERING DETECTED",
    })
    return out
