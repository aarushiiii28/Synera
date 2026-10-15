"""Benchmark and synthetic ground-truth subpackage."""

from synera_core.benchmark.evaluate import run_benchmark
from synera_core.benchmark.generator import generate_benchmark, simulate_benchmark

__all__ = ["run_benchmark", "generate_benchmark", "simulate_benchmark"]
