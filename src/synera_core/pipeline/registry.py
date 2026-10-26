"""Dataset registry: the datasets the platform knows about, where their files live, and how to load them.

Ids are stable API identifiers:

    env_panel          REAL      8 cities x 518 days of weather + air quality (covariates only, no outcome)
    benchmark_track_b  SIMULATED planted-interaction outcome on the real covariates (Track B)
    osd-211            REAL      NASA OSDR spleen RNA-seq, radiation x hindlimb unloading (Track A, discovery)
    osd-237            REAL      NASA OSDR skin RNA-seq, same design (Track A, replication tissue)
    us_mortality       REAL      CDC weekly deaths x EPA air x ERA5 weather, 50 US states 2014-2019 (Track C, real health outcome)
    india_grid         REAL      Grid-India daily electricity supplied x ERA5 weather, 8 Indian states 2019-2024 (Track D, real non-health outcome)
    india_grid_b       REAL      the same for 8 other Indian states (a check across states)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

from synera_core.benchmark.generator import STRESSORS, generate_benchmark
from synera_core.config import find_repo_root, get_settings
from synera_core.provenance.hashing import sha256_file
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import register_file

INDIA_GRID_STRESSORS = ("tmax", "rh", "wind", "solar", "cloud")
BENCHMARK_SNR = 2.0
BENCHMARK_SEED = 20260929


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    name: str
    track: str
    kind: str                # covariates | panel | factorial
    provenance: str          # REAL | SIMULATED
    path: str                # repo-relative
    meta_path: str | None = None
    description: str = ""
    role: str = ""
    units: str = "raw"       # raw (physical units) | standardised (per-city z-scores): physical-range checks need raw units
    stressors: tuple[str, ...] = ()    # columns the engine tests; empty means the ten standard environmental stressors

    @property
    def stressor_cols(self) -> list[str]:
        return list(self.stressors) if self.stressors else list(STRESSORS)

    @property
    def abs_path(self) -> Path:
        return find_repo_root() / self.path

    @property
    def abs_meta_path(self) -> Path | None:
        return (find_repo_root() / self.meta_path) if self.meta_path else None

    @property
    def runnable(self) -> bool:
        return self.kind in ("panel", "factorial")

    def to_dict(self) -> dict:
        return asdict(self)


def _bench_name() -> str:
    return f"data/synthetic/benchmark_snr{BENCHMARK_SNR}_seed{BENCHMARK_SEED}.parquet"


def get_registry() -> dict[str, DatasetSpec]:
    return {
        s.id: s for s in (
            DatasetSpec("env_panel", "Environmental stressor panel", "B", "covariates", "REAL",
                        "data/processed/env_panel.parquet",
                        description="Daily weather (Open-Meteo archive) and air quality for 8 cities, Aug 2022 - Dec 2023. "
                                    "Covariates only: it has no health or biological outcome."),
            DatasetSpec("benchmark_track_b", "Engine benchmark (planted interactions)", "B", "panel", "SIMULATED",
                        _bench_name(),
                        description=f"Real covariates with a SIMULATED outcome (SNR {BENCHMARK_SNR}, seed {BENCHMARK_SEED}) that has "
                                    "known synergistic, antagonistic and non-linear interactions. Measures the engine, not nature.",
                        units="standardised"),
            DatasetSpec("us_mortality", "US weekly deaths x weather x air pollution", "C", "panel", "REAL",
                        "data/processed/us_mortality_panel.parquet",
                        description="REAL health outcome: CDC weekly all-cause deaths for 50 US states, 2014-2019, joined to ERA5 weather and "
                                    "EPA air-pollution monitors. The outcome is excess mortality in % over each state's own trend and season."),
            DatasetSpec("us_heart", "US weekly heart-disease deaths x weather x air pollution", "C", "panel", "REAL",
                        "data/processed/us_heart_panel.parquet",
                        description="REAL health outcome: CDC weekly deaths from heart disease, 46 US states, 2014-2019, same weather and air-pollution "
                                    "inputs as us_mortality. Excess deaths in % over each state's own trend and season, minus the national value that week."),
            DatasetSpec("us_stroke", "US weekly stroke deaths x weather x air pollution", "C", "panel", "REAL",
                        "data/processed/us_stroke_panel.parquet",
                        description="REAL health outcome: CDC weekly deaths from cerebrovascular disease (stroke), 38 US states with enough data, 2014-2019, "
                                    "same inputs as us_mortality."),
            DatasetSpec("india_grid", "India daily electricity demand x weather (8 large states)", "D", "panel", "REAL",
                        "data/processed/india_grid_panel.parquet", stressors=INDIA_GRID_STRESSORS,
                        description="REAL outcome from a non-health system: daily electricity supplied to 8 large Indian states (Grid-India, 2019 to Apr 2024), "
                                    "joined to state-level ERA5 weather (Hunt and Bloomfield, Zenodo 14983362, CC BY 4.0). The outcome is the % above each "
                                    "state's own trend, season and weekday. Measures grid stress, not health."),
            DatasetSpec("india_grid_b", "India daily electricity demand x weather (8 other states)", "D", "panel", "REAL",
                        "data/processed/india_grid_b_panel.parquet", stressors=INDIA_GRID_STRESSORS,
                        description="The same construction on 8 different Indian states, built to check whether what India (8 states) shows repeats elsewhere. "
                                    "Same source, same period, different states: a replication across states, not across data sources."),
            DatasetSpec("osd-211", "NASA OSDR OSD-211: spleen RNA-seq", "A", "factorial", "REAL",
                        "data/processed/osdr_OSD-211_expr.parquet", "data/processed/osdr_OSD-211_meta.parquet",
                        description="Mouse spleen, chronic low-dose radiation x hindlimb unloading (2x2).", role="discovery"),
            DatasetSpec("osd-237", "NASA OSDR OSD-237: skin RNA-seq", "A", "factorial", "REAL",
                        "data/processed/osdr_OSD-237_expr.parquet", "data/processed/osdr_OSD-237_meta.parquet",
                        description="Mouse skin from the same animals, same 2x2 design.", role="replication tissue"),
        )
    }


def get_spec(dataset_id: str) -> DatasetSpec:
    reg = get_registry()
    if dataset_id not in reg:
        raise KeyError(dataset_id)
    return reg[dataset_id]


def ensure_benchmark_dataset(ledger: Ledger) -> Path:
    """Create (deterministically) and register the canonical Track B dataset if it does not exist yet."""
    spec = get_spec("benchmark_track_b")
    if not spec.abs_path.exists():
        generate_benchmark(snr=BENCHMARK_SNR, seed=BENCHMARK_SEED, out_dir=spec.abs_path.parent, ledger=ledger)
    register_file(ledger, spec.abs_path, "dataset", {"provenance": "SIMULATED", "snr": BENCHMARK_SNR, "seed": BENCHMARK_SEED})
    return spec.abs_path


def load_panel(spec: DatasetSpec) -> pd.DataFrame:
    """Panel dataframe sorted by (city, date) with complete stressor rows (never imputed)."""
    df = pd.read_parquet(spec.abs_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=[*spec.stressor_cols, "outcome"]).sort_values(["city", "date"]).reset_index(drop=True)
    return df


def summarize(spec: DatasetSpec) -> dict:
    """Facts about the dataset computed from the file (counts, date range); empty dict when the file is missing."""
    p = spec.abs_path
    if not p.exists():
        return {"available": False}
    out: dict = {"available": True, "sha256": sha256_file(p), "bytes": p.stat().st_size}
    if spec.kind in ("covariates", "panel"):
        d = pd.read_parquet(p)
        out.update({"rows": int(len(d)), "cities": int(d["city"].nunique()),
                    "date_start": str(pd.to_datetime(d["date"]).min().date()), "date_end": str(pd.to_datetime(d["date"]).max().date()),
                    "features": len(spec.stressor_cols)})
    else:
        e = pd.read_parquet(p)
        out.update({"features": int(e.shape[0]), "samples": int(e.shape[1])})
    return out


def settings_snapshot() -> dict:
    s = get_settings()
    return {"alpha": s.alpha, **s.discovery.model_dump(), "seed": s.seeds.global_seed,
            "expression_variant": s.osdr_expression_variant, "expression_filter": s.expression_filter.model_dump()}
