"""Scientific validation subpackage."""

from synera_core.validation.multitest import benjamini_hochberg
from synera_core.validation.bootstrap import bootstrap_ci
from synera_core.validation.replication import evaluate_replication
from synera_core.validation.confidence import calculate_confidence_score

__all__ = [
    "benjamini_hochberg",
    "bootstrap_ci",
    "evaluate_replication",
    "calculate_confidence_score",
]
