#!/usr/bin/env python3
"""Compatibility entry point for the repository skill manager."""

from pathlib import Path
import runpy


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "ue-source-sage" / "scripts" / "sage.py"
runpy.run_path(str(SCRIPT), run_name="__main__")

