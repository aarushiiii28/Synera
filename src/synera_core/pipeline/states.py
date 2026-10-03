"""State and Finding objects for SYNERA pipeline."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

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
    cohens_d: float

class StatsModel(BaseModel):
    p: float
    q: float
    n: int
    df: float

class MethodsModel(BaseModel):
    parametric: bool
    gbm: bool
    nid: bool

class ReplicationModel(BaseModel):
    evidence_level: str
    n_shared: int
    concordance: float
    binomial_p: float
    replication_rate: float
    pi1: float

class ConfidenceModel(BaseModel):
    score: float
    components: Dict[str, float]

class SecurityModel(BaseModel):
    status: str

class Finding(BaseModel):
    id: str
    track: str
    provenance: str = Field(..., pattern="^(REAL|SIMULATED)$")
    evidence_level: str
    dataset_ids: List[str]
    stressors: List[str]
    feature: str
    type: str
    effect: EffectModel
    stats: StatsModel
    methods: MethodsModel
    replication: Optional[ReplicationModel] = None
    security: SecurityModel
    confidence: Optional[ConfidenceModel] = None
    status: str = Field(..., pattern="^(CANDIDATE|VALIDATED|VERIFIED|BLOCKED|REJECTED)$")
    history: List[str] = []
    
    def evaluate_status(self):
        """Update status based on rules."""
        if self.status == "BLOCKED" or self.security.status != "CLEAN":
            self.status = "BLOCKED"
            return
            
        # Check validation rules
        if abs(self.effect.b_AB) < 0.5 or (self.effect.ci_low < 0 < self.effect.ci_high):
            self.status = "CANDIDATE"
        else:
            self.status = "VALIDATED"
            
        # Check verification
        if self.status == "VALIDATED" and self.replication and self.replication.replication_rate > 0:
            if self.confidence and self.confidence.components.get("trust", 0) == 1:
                self.status = "VERIFIED"
                
        if self.status == "CANDIDATE":
            if self.replication and self.replication.replication_rate == 0:
                self.status = "REJECTED"
