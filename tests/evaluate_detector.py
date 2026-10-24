#!/usr/bin/env python3
"""Reproducible offline evaluation using the EchoSentinel model and preprocessing."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio_processor import decode_and_preprocess_audio
from audio_quality import analyze_audio_quality
from model import VoiceCloneDetector
from evaluation_tools import (
    calculate_metrics,
    grouped_metrics,
    load_manifest,
    threshold_sweep,
    validate_manifest,
    write_evaluation_report,
)


REAL_WORLD_LIMITATION = (
    "Exploratory fixture results only; these metrics are not estimates of real-world performance."
)
PRODUCTION_DECISION_THRESHOLD = 0.5
DEFAULT_THRESHOLDS = [round(i / 20, 2) for i in range(21)]


def _selected_samples(samples: list[dict[str, Any]], partition: str | None) -> list[dict[str, Any]]:
    return [sample for sample in samples if partition is None or sample.get("partition") == partition]


def evaluate(
    manifest_path: Path,
    dataset_root: Path,
    partition: str | None = None,
    output_dir: Path | None = None,
    sweep: bool = False,
    thresholds: list[float] | None = None,
) -> dict[str, Any]:
    if sweep and partition != "validation":
        raise ValueError("Threshold sweeps are allowed only with --partition validation.")
    if sweep and thresholds is not None and any(not 0 <= value <= 1 for value in thresholds):
        raise ValueError("Every sweep threshold must be between 0 and 1.")

    validation = validate_manifest(manifest_path, dataset_root)
    if not validation["valid"]:
        raise ValueError(f"Manifest validation failed: {json.dumps(validation['issues'], sort_keys=True)}")
    samples, structural_issues = load_manifest(manifest_path)
    if structural_issues:
        raise ValueError(f"Manifest structure is invalid: {json.dumps(structural_issues, sort_keys=True)}")
    selected = _selected_samples(samples, partition)
    if not selected:
        raise ValueError(f"No samples found for partition {partition!r}.")
    if sweep and not any(sample.get("partition") == "validation" for sample in selected):
        raise ValueError("No validation partition samples are available for threshold analysis.")

    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    rows: list[dict[str, Any]] = []
    for sample in selected:
        relative_path = Path(sample["audio_path"])
        if relative_path.is_absolute():
            # Legacy mode keeps absolute paths, but manifest paths must always be relative.
            audio_path = relative_path
        else:
            audio_path = dataset_root / relative_path
        waveform, details = decode_and_preprocess_audio(audio_path.read_bytes(), return_details=True)
        prediction = detector.predict(waveform, sample_rate=details["sample_rate"])
        ai_score = float(prediction["ai_probability"])
        bonafide_score = float(prediction["human_probability"])
        if not (0 <= ai_score <= 1 and 0 <= bonafide_score <= 1):
            raise RuntimeError(f"Model returned an invalid score for sample {sample['sample_id']}.")
        predicted = "spoof" if ai_score >= bonafide_score else "bonafide"

        quality = analyze_audio_quality(
            details["analysis_waveform"],
            sample_rate=details["sample_rate"],
            native_sample_rate=details["source_sample_rate"],
        )
        measurement = {item["id"]: item["value"] for item in quality.get("measurements", [])}
        row = {
            "sample_id": sample["sample_id"],
            "audio_path": sample["audio_path"],
            "partition": sample["partition"],
            "ground_truth": sample["ground_truth"],
            "predicted_label": predicted,
            "bonafide_score": bonafide_score,
            "spoof_score": ai_score,
            "ai_probability": ai_score,
            "duration_seconds": details["duration_seconds"],
            "source_sample_rate": details["source_sample_rate"],
            "source_channels": details["channels"],
            "model_sample_rate": details["sample_rate"],
            "model_waveform_samples": int(waveform.shape[0]),
            "model_waveform_shape": [int(waveform.shape[0])],
            "model_tensor_shape": [1, int(waveform.shape[0])],
            "model_waveform_dtype": str(waveform.dtype),
            "quality_rating": quality["quality_rating"],
            "quality_score": quality["quality_score"],
            "quality_reliability": quality["reliability"],
            "quality_flags": quality.get("flags", []),
            "clipped_samples_percent": measurement.get("clipped_samples"),
            "peak_level_dbfs": measurement.get("peak_level"),
            "level_variation_db": quality.get("level_variation_db"),
            "dynamic_range_db": quality.get("dynamic_range_db"),
            "high_frequency_share_percent": measurement.get("high_frequency_share"),
            "quality_measurements": quality.get("measurements", []),
            "recording_conditions": sample.get("recording_conditions", ["unknown"]),
            "synthetic_generator": sample.get("synthetic_generator"),
            "language": sample.get("language"),
        }
        rows.append(row)
        print(
            f"{sample['sample_id']}\tactual={row['ground_truth']}\tpredicted={predicted}"
            f"\tbonafide={bonafide_score:.6f}\tspoof={ai_score:.6f}"
        )

    metrics = calculate_metrics(rows, PRODUCTION_DECISION_THRESHOLD)
    report: dict[str, Any] = {
        "model": detector.model_id,
        "model_revision": getattr(detector.model.config, "_commit_hash", None),
        "label_mapping": detector.label_mapping,
        "partition": partition or "all_manifest_partitions",
        "threshold": PRODUCTION_DECISION_THRESHOLD,
        "metrics": metrics,
        "groups": grouped_metrics(rows, PRODUCTION_DECISION_THRESHOLD),
        "false_positives": [row["sample_id"] for row in rows if row["ground_truth"] == "bonafide" and row["predicted_label"] == "spoof"],
        "false_negatives": [row["sample_id"] for row in rows if row["ground_truth"] == "spoof" and row["predicted_label"] == "bonafide"],
        "sample_predictions": rows,
        "validation_warnings": [issue for issue in validation["issues"] if issue["severity"] == "warning"],
        "performance_statement": REAL_WORLD_LIMITATION,
    }
    if sweep:
        report["threshold_sweep"] = threshold_sweep(rows, thresholds or DEFAULT_THRESHOLDS)
        report["threshold_sweep_note"] = "Exploratory validation-partition analysis only; no production threshold is selected or changed."
    if output_dir is not None:
        write_evaluation_report(rows, report, output_dir)
        print(f"Wrote {output_dir / 'per_sample_predictions.csv'}")
        print(f"Wrote {output_dir / 'evaluation_summary.json'}")
    print(json.dumps({"partition": report["partition"], "metrics": metrics, "false_positives": report["false_positives"], "false_negatives": report["false_negatives"], "performance_statement": REAL_WORLD_LIMITATION}, indent=2, allow_nan=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/audio/evaluation_manifest.json")
    parser.add_argument("--dataset-root", type=Path, default=ROOT / "tests/audio")
    parser.add_argument("--partition", choices=("development", "validation", "test"))
    parser.add_argument("--threshold-sweep", action="store_true", help="Explore thresholds; requires --partition validation.")
    parser.add_argument("--thresholds", help="Optional comma-separated sweep thresholds in [0,1]; default is 0.00 through 1.00 by 0.05.")
    parser.add_argument("--output-dir", type=Path, help="Optional destination for per-sample CSV and JSON summary.")
    parser.add_argument("--detectors", help="Run registered offline adapters instead of the legacy single-model evaluator; comma-separated IDs, e.g. current,sara1708_wav2vec2,aasist_l.")
    args = parser.parse_args()
    try:
        if args.detectors:
            if args.threshold_sweep:
                raise ValueError("--threshold-sweep belongs to the legacy evaluator; registered comparison currently reports adapter-declared decisions only.")
            from compare_detectors import compare_detectors
            comparison = compare_detectors(
                args.manifest,
                args.dataset_root,
                [value.strip() for value in args.detectors.split(",") if value.strip()],
                args.partition,
            )
            output = (args.output_dir / "model_comparison.json") if args.output_dir else Path("/tmp/echosentinel-model-comparison.json")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(comparison, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
            print(json.dumps({"output": str(output), "models": {key: {"status": value["availability_status"], "coverage": value["coverage"], "metrics": value["metrics"]} for key, value in comparison["models"].items()}, "paired_comparison": comparison["paired_comparison"]}, indent=2, allow_nan=False))
            return 0
        thresholds = [float(value) for value in args.thresholds.split(",")] if args.thresholds else None
        evaluate(args.manifest, args.dataset_root, args.partition, args.output_dir, args.threshold_sweep, thresholds)
    except Exception as exc:
        parser.exit(2, f"Evaluation failed: {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
