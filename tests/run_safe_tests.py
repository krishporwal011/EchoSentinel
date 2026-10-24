#!/usr/bin/env python3
"""Run tests supported by the current Python environment without installing packages.

This runner executes the stdlib-only In-The-Wild importer tests and reports
audio/model test modules as skipped when their declared runtime dependencies
are unavailable. A skip is not a passing test and does not imply inference.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_TESTS = {
    "tests/test_evaluation_tools.py": {"librosa", "numpy", "soundfile", "torch", "transformers", "certifi"},
    "tests/test_detector_adapters.py": {"numpy", "soundfile", "librosa"},
    "tests/test_quality_eval.py": {"soundfile", "librosa", "numpy"},
    "tests/test_fp_acoustics.py": {"torch", "librosa", "soundfile", "numpy", "scipy"},
    "backend/tests/test_api.py": {"torch", "transformers", "soundfile", "numpy"},
    "backend/tests/test_audio_processor.py": {"pytest", "soundfile", "numpy", "librosa"},
    "backend/tests/test_audio_quality.py": {"pytest", "soundfile", "numpy", "librosa"},
    "backend/tests/test_model.py": {"pytest", "torch", "transformers", "numpy"},
    "tests/test_e2e_live.py": {"pytest", "requests"},
}


def main() -> int:
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")
    print("Running dependency-free importer tests:")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests/test_ingest_in_the_wild.py")],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        print("FAIL: tests/test_ingest_in_the_wild.py")
        return result.returncode
    print("PASS: tests/test_ingest_in_the_wild.py")

    missing_by_module: dict[str, list[str]] = {}
    for module, requirements in DEPENDENCY_TESTS.items():
        missing = sorted(
            dependency for dependency in requirements
            if importlib.util.find_spec(dependency) is None
        )
        if missing:
            missing_by_module[module] = missing

    if missing_by_module:
        print("\nSKIPPED (requirements unavailable; not counted as passed):")
        for module, missing in missing_by_module.items():
            print(f"SKIP: {module} — missing: {', '.join(missing)}")
    runnable_but_not_executed = sorted(set(DEPENDENCY_TESTS) - set(missing_by_module))
    if runnable_but_not_executed:
        print("\nNOT RUN (requirements detected; this safe runner only executes importer tests):")
        for module in runnable_but_not_executed:
            print(f"NOT RUN: {module}")
    print("\nNo model inference or 24-fixture evaluation was run by this test command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
