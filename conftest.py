"""
conftest.py — Root pytest configuration.

Adds the project root to sys.path so that `src.*` imports resolve
correctly without requiring PYTHONPATH=. when running pytest from
the repository root.
"""

import sys
import os

# Insert repo root at the front of sys.path so "src.*" imports work
sys.path.insert(0, os.path.dirname(__file__))
