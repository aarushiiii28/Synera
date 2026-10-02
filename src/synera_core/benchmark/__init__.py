"""Benchmark and synthetic ground-truth subpackage."""

from synera_core.benchmark.evaluate import evaluate_interaction_recovery
from synera_core.benchmark.generator import generate_benchmark_dataset

__all__ = ["evaluate_interaction_recovery", "generate_benchmark_dataset"]
