"""Test configuration loading and repository root resolution."""

from pathlib import Path
from synera_core.config import get_settings, find_repo_root


def test_find_repo_root():
    root = find_repo_root()
    assert (root / "pyproject.toml").exists()
    assert (root / "configs" / "settings.yaml").exists()


def test_get_settings():
    settings = get_settings()
    assert settings.seeds.global_seed == 20260929
    assert settings.alpha == 0.05
    assert settings.fdr_method == "bh"
    assert settings.min_abs_effect == 0.5
    assert settings.confidence_weights.stat == 0.35
    assert settings.confidence_weights.trust == 0.15

    # Check path resolution
    resolved = settings.resolve_path(settings.paths.data_dir)
    assert resolved.exists()
