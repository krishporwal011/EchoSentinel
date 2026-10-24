#!/usr/bin/env python3
"""Validate an EchoSentinel evaluation manifest without changing dataset files."""

import argparse
import json
import sys
from pathlib import Path

from evaluation_tools import validate_manifest


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=project_root / "tests/audio/evaluation_manifest.json")
    parser.add_argument("--dataset-root", type=Path, default=project_root / "tests/audio")
    parser.add_argument("--report", type=Path, help="Optional path for a JSON validation report.")
    args = parser.parse_args()

    report = validate_manifest(args.manifest, args.dataset_root)
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
