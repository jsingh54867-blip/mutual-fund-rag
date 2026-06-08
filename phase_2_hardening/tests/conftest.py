"""Shared pytest configuration and fixtures for Phase 2 tests."""

import sys
from pathlib import Path

# Ensure project root is on sys.path for all test modules
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
