"""Shared fixtures for unit tests."""

import sys
from pathlib import Path

# Ensure tests/_factories.py and other root-level test helpers are importable
sys.path.insert(0, str(Path(__file__).parent.parent))
