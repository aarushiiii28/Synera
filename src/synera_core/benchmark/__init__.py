"""Benchmark and synthetic ground-truth subpackage."""

from synera_core.benchmark.generator import generate_benchmark_dataset
from synera_core.benchmark.evaluate import evaluate_interaction_recovery

__all__ = ["generate_benchmark_dataset", "evaluate_interaction_recovery"]
