"""
src/paths.py — Centralized project-root path resolution.

This module provides a single ROOT_DIR constant and helper functions
so that all path resolution in the project is relative to the repository
root, not to the current working directory or __file__ location.

Usage:
    from src.paths import ROOT_DIR, config_path, schema_path

    p = config_path("assets.yml")           # -> <root>/config/assets.yml
    s = schema_path("snapshot.schema.json") # -> <root>/schemas/snapshot.schema.json
    o = output_path("report.md")            # -> <root>/out/report.md
"""

from pathlib import Path

# The repository root is two levels above this file:
#   src/paths.py  →  src/  →  <root>/
ROOT_DIR: Path = Path(__file__).resolve().parent.parent


def config_path(filename: str) -> Path:
    """Returns the absolute path to a file inside the config/ directory."""
    return ROOT_DIR / "config" / filename


def schema_path(filename: str) -> Path:
    """Returns the absolute path to a file inside the schemas/ directory."""
    return ROOT_DIR / "schemas" / filename


def output_path(filename: str) -> Path:
    """Returns the absolute path to a file inside the out/ directory."""
    return ROOT_DIR / "out" / filename


def tests_path(filename: str) -> Path:
    """Returns the absolute path to a file inside the tests/ directory."""
    return ROOT_DIR / "tests" / filename
