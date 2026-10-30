"""Finding objects and the finding lifecycle.

    CANDIDATE  survived conditional selection (q < alpha) but lacks full validation
    VALIDATED  + effect >= pre-specified gate, bootstrap CI clears the gate, >= 2 of 3 methods agree
    VERIFIED   + replicated (in an independent dataset, or on later data that was not used to find it) + provenance REAL + trust (security CLEAN, ledger valid, replay matches)
    REJECTED   statistically detectable but below the pre-specified minimal effect, or failed replication
    BLOCKED    any integrity failure ("result blocked from verified status")

VERIFIED means "statistically validated with verified computational provenance". It never means
"biologically proven". Findings built from SIMULATED data are capped at VALIDATED.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

EVIDENCE_LEVELS = ("INDEPENDENT_REPLICATION", "LATER_DATA_REPLICATION", "CROSS_TISSUE_SAME_COHORT", "INTERNAL_REPLICATION", "HYPOTHESIS_ONLY")
STATUSES = ("CANDIDATE", "VALIDATED", "VERIFIED", "BLOCKED", "REJECTED")


class PipelineStage(str):
    DATA_INGESTION = "DATA_INGESTION"
    DISCOVERY = "DISCOVERY"
    VALIDATION = "VALIDATION"
    EXPORT = "EXPORT"


class FindingState(str):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class EffectModel(BaseModel):
    b_AB: float
    ci_low: float
    ci_high: float
    cohens_d: float = 0.0
    effect_size: Optional[float] = None       # std of the interaction surface / SD(outcome)
    eff_ci_low: Optional[float] = None
    eff_ci_high: Optional[float] = None


class StatsModel(BaseModel):
    p: float
    q: float
    n: int
    df: float
    p_naive: Optional[float] = None
    p_hac: Optional[float] = None
    q_marginal: Optional[float] = None
    p_bilinear: Optional[float] = None
    p_nonlinear: Optional[float] = None
    lambda_boot: Optional[float] = None


class MethodsModel(BaseModel):
    parametric: bool
    gbm: bool
    nid: bool
    gbm_rank: Optional[int] = None
    nid_rank: Optional[int] = None


class ReplicationModel(BaseModel):
    evidence_level: str
    n_shared: int = 0
    concordance: Optional[float] = None
    binomial_p: Optional[float] = None
    replication_rate: float = 0.0
    pi1: Optional[float] = None
    replicated: bool = False
    detail: str = ""


class ConfidenceModel(BaseModel):
    score: float
    components: Dict[str, float]


class SecurityModel(BaseModel):
    status: str
    checks: List[Dict[str, Any]] = []


class Finding(BaseModel):
    id: str
    track: str
    provenance: str = Field(..., pattern="^(REAL|SIMULATED)$")
    evidence_level: str
    dataset_ids: List[str]
    stressors: List[str]
    feature: Optional[str] = None
    type: str
    effect: EffectModel
    stats: StatsModel
    methods: MethodsModel
    replication: Optional[ReplicationModel] = None
    security: SecurityModel
    confidence: Optional[ConfidenceModel] = None
    status: str = Field(..., pattern="^(CANDIDATE|VALIDATED|VERIFIED|BLOCKED|REJECTED)$")
    history: List[str] = []
    run_id: Optional[str] = None
    gates: List[Dict[str, Any]] = []
    surface: Optional[Dict[str, Any]] = None
    min_abs_effect: float = 0.5               # gate on |b_AB| (log2 scale, factorial designs)
    effect_gate: Optional[float] = None       # gate on standardised effect (panel designs)

    def evaluate_status(self) -> None:
        """Apply the lifecycle rules to the stored evidence (security failure always wins)."""
        if self.status == "BLOCKED" or self.security.status in ("COMPROMISED", "TAMPERED"):
            self.status = "BLOCKED"
            return
        if self.security.status not in ("CLEAN", "SUSPICIOUS"):
            self.status = "BLOCKED"
            return

        if self.effect_gate is not None and self.effect.effect_size is not None:
            strong = self.effect.effect_size >= self.effect_gate and (self.effect.eff_ci_low or 0.0) >= self.effect_gate
        else:
            strong = abs(self.effect.b_AB) >= self.min_abs_effect and not (self.effect.ci_low < 0 < self.effect.ci_high)
        robust = sum([self.methods.parametric, self.methods.gbm, self.methods.nid]) >= 2

        if not strong:
            self.status = "REJECTED" if (self.replication and self.replication.replication_rate == 0 and
                                         self.replication.n_shared > 0) else "CANDIDATE"
            return
        self.status = "VALIDATED" if robust else "CANDIDATE"

        trust = (self.confidence.components.get("trust", 0) == 1) if self.confidence else False
        if (self.status == "VALIDATED" and self.provenance == "REAL" and self.replication
                and self.replication.replicated and trust):
            self.status = "VERIFIED"
