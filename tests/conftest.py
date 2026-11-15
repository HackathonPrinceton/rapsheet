"""Shared test setup. Tests that need the downloaded FDA database are skipped when it is not there."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from service import record  # noqa: E402

needs_data = pytest.mark.skipif(not record.has_data(), reason="needs the FDA database (make pull)")
