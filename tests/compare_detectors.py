#!/usr/bin/env python3
"""Offline comparison runner for registered EchoSentinel detector adapters."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))

from audio_processor import decode_and_preprocess_audio
from detector_adapters import (
    DetectorAdapterError,
    DetectorPrediction,
    DetectorUnavailableError,
    REGISTRY,
    metadata_as_dict,
)
from evaluation_tools import calculate_metrics, load_manifest, validate_manifest


def _auc(rows: list[dict[str, Any]]) -> tuple[float | None, str | None]:
    scores = [row.get("spoof_score_for_auc") for row in rows]
    labels = [row["ground_truth"] == "spoof" for row in rows]
    if len(set(labels)) != 2 or any(score is None or not math.isfinite(float(score)) for score in scores):
        return None, "ROC-AUC requires both classes and a finite, explicitly spoof-oriented native score for every included sample."
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(labels, scores)), None
    except ImportError:
        return None, "scikit-learn is unavailable; ROC-AUC was not calculated."


def _classification_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Reuse the existing project's confusion/rate implementation using hard labels.
    metric_rows = [
        {"ground_truth": row["ground_truth"], "ai_probability": 1.0 if row["predicted_label"] == "spoof" else 0.0}
        for row in rows
    ]
    if not rows:
        return calculate_metrics([], threshold=0.5)
    metrics = calculate_metrics(metric_rows, threshold=0.5)
    auc, note = _auc(rows)
    metrics["roc_auc"] = auc
    if note:
        metrics["roc_auc_note"] = note
    else:
        metrics.pop("roc_auc_note", None)
    metrics.pop("threshold", None)
    metrics["decision_rule"] = "adapter-provided predicted_label; no threshold was tuned by this evaluator"
    return metrics


def _grouped_error_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for field in ("recording_conditions", "synthetic_generator", "language"):
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            raw = row.get(field)
            keys = raw if field == "recording_conditions" and isinstance(raw, list) and raw else [raw]
            for key in keys:
                name = str(key) if key not in (None, "", "unknown", "not_applicable") else "unknown"
                buckets.setdefault(name, []).append(row)
        grouped[field] = {}
        for name, items in sorted(buckets.items()):
            grouped[field][name] = {
                "metrics": _classification_metrics(items),
                "false_positive_sample_ids": [row["sample_id"] for row in items if row["ground_truth"] == "bonafide" and row["predicted_label"] == "spoof"],
                "false_negative_sample_ids": [row["sample_id"] for row in items if row["ground_truth"] == "spoof" and row["predicted_label"] == "bonafide"],
            }
    return grouped


def _summarize_one(adapter, samples: list[dict[str, Any]], dataset_root: Path) -> dict[str, Any]:
    metadata = metadata_as_dict(adapter.metadata)
    if adapter.metadata.status == "not_evaluated":
        return {
            "model": metadata,
            "availability_status": "not_evaluated",
            "unavailable_reason": adapter.metadata.unavailable_reason,
            "samples_in_scope": len(samples),
            "attempted_samples": 0,
            "successful_inferences": 0,
            "failed_inferences": 0,
            "coverage": 0.0 if samples else None,
            "failure_reasons": {},
            "metrics": None,
            "latency": {"measured": False, "reason": "No model checkpoint was loaded."},
            "memory": {"measured": False, "reason": "No model checkpoint was loaded."},
            "preprocessing": adapter.metadata.preprocessing,
            "rows": [],
        }

    load_started = time.perf_counter()
    try:
        adapter.load(device="cpu", offline=True, revision=adapter.metadata.revision)
    except DetectorAdapterError as exc:
        load_ms = (time.perf_counter() - load_started) * 1000
        return {
            "model": metadata,
            "availability_status": "load_failed",
            "unavailable_reason": None,
            "load_error": exc.as_dict(),
            "samples_in_scope": len(samples),
            "attempted_samples": 0,
            "successful_inferences": 0,
            "failed_inferences": 0,
            "coverage": 0.0 if samples else None,
            "failure_reasons": {},
            "metrics": None,
            "latency": {"measured": True, "load_ms": load_ms, "first_inference_after_load_ms": None, "warm_p50_ms": None, "warm_p95_ms": None, "reason": "Model load did not complete; inference was not attempted."},
            "memory": {"measured": False, "reason": "No reliable per-model memory measurement is available in this runner."},
            "preprocessing": adapter.metadata.preprocessing,
            "rows": [],
        }
    except Exception as exc:
        load_ms = (time.perf_counter() - load_started) * 1000
        return {
            "model": metadata,
            "availability_status": "load_failed",
            "unavailable_reason": None,
            "load_error": {"code": "model_load_failed", "message": f"{type(exc).__name__}: {exc}"},
            "samples_in_scope": len(samples),
            "attempted_samples": 0,
            "successful_inferences": 0,
            "failed_inferences": 0,
            "coverage": 0.0 if samples else None,
            "failure_reasons": {},
            "metrics": None,
            "latency": {"measured": True, "load_ms": load_ms, "first_inference_after_load_ms": None, "warm_p50_ms": None, "warm_p95_ms": None, "reason": "Model load did not complete; inference was not attempted."},
            "memory": {"measured": False, "reason": "No reliable per-model memory measurement is available in this runner."},
            "preprocessing": adapter.metadata.preprocessing,
            "rows": [],
        }
    load_ms = (time.perf_counter() - load_started) * 1000
    resolved_mapping = getattr(adapter, "resolved_class_mapping", None)
    if resolved_mapping is not None:
        metadata["resolved_class_mapping"] = resolved_mapping
    preprocessing = getattr(adapter, "preprocessing_details", None) or adapter.metadata.preprocessing

    rows: list[dict[str, Any]] = []
    elapsed_ms: list[float] = []
    failures: Counter[str] = Counter()
    attempted = 0
    for sample in samples:
        attempted += 1
        row: dict[str, Any] = {
            "sample_id": sample["sample_id"],
            "audio_path": sample["audio_path"],
            "ground_truth": sample["ground_truth"],
            "detector_id": adapter.metadata.detector_id,
            "status": "failed",
            "predicted_label": None,
            "native_scores": None,
            "score_type": adapter.metadata.score_type,
            "score_direction": adapter.metadata.score_direction,
            "spoof_score_for_auc": None,
            "inference_ms": None,
            "error": None,
            "recording_conditions": sample.get("recording_conditions", ["unknown"]),
            "synthetic_generator": sample.get("synthetic_generator"),
            "language": sample.get("language"),
        }
        try:
            path = dataset_root / sample["audio_path"]
            waveform, details = decode_and_preprocess_audio(path.read_bytes(), return_details=True)
            prediction: DetectorPrediction = adapter.predict(waveform, int(details["sample_rate"]))
            prediction.validate()
            row.update({
                "status": "success",
                "predicted_label": prediction.predicted_label,
                "native_scores": prediction.native_scores,
                "score_type": prediction.score_type,
                "score_direction": prediction.score_direction,
                "spoof_score_for_auc": prediction.spoof_score_for_auc(),
                "inference_ms": prediction.inference_ms,
                "audio_duration_seconds": details["duration_seconds"],
                "source_sample_rate": details["source_sample_rate"],
                "source_channels": details["channels"],
                "model_sample_rate": details["sample_rate"],
                "model_waveform_samples": int(waveform.size),
            })
            elapsed_ms.append(prediction.inference_ms)
        except DetectorAdapterError as exc:
            row["error"] = exc.as_dict()
            failures[exc.code] += 1
        except ValueError as exc:
            row["error"] = {"code": "unsupported_input", "message": str(exc)}
            failures["unsupported_input"] += 1
        except Exception as exc:
            row["error"] = {"code": "unexpected_evaluation_error", "message": f"{type(exc).__name__}: {exc}"}
            failures["unexpected_evaluation_error"] += 1
        rows.append(row)

    successes = [row for row in rows if row["status"] == "success"]
    latency: dict[str, Any] = {
        "measured": True,
        "load_ms": load_ms,
        "first_inference_after_load_ms": elapsed_ms[0] if elapsed_ms else None,
        "warm_inference_count": max(0, len(elapsed_ms) - 1),
        "warm_p50_ms": statistics.median(elapsed_ms[1:]) if len(elapsed_ms) > 1 else None,
        "warm_p95_ms": float(np.percentile(elapsed_ms[1:], 95)) if len(elapsed_ms) > 1 else None,
        "latency_note": "Descriptive fixture timings on CPU, not a controlled device benchmark; first call is reported separately.",
    }
    return {
        "model": metadata,
        "availability_status": "evaluated" if successes else "inference_failed",
        "unavailable_reason": None,
        "samples_in_scope": len(samples),
        "attempted_samples": attempted,
        "successful_inferences": len(successes),
        "failed_inferences": len(rows) - len(successes),
        "coverage": len(successes) / len(samples) if samples else None,
        "failure_reasons": dict(failures),
        "metrics": _classification_metrics(successes),
        "grouped_error_analysis": _grouped_error_analysis(successes),
        "latency": latency,
        "memory": {"measured": False, "reason": "No reliable per-model peak-memory measurement is available in this runner."},
        "preprocessing": preprocessing,
        "rows": rows,
    }


def compare_detectors(
    manifest_path: Path,
    dataset_root: Path,
    detector_ids: list[str],
    partition: str | None = None,
) -> dict[str, Any]:
    validation = validate_manifest(manifest_path, dataset_root)
    if not validation["valid"]:
        raise ValueError(f"Manifest validation failed: {json.dumps(validation['issues'], sort_keys=True)}")
    samples, structural_issues = load_manifest(manifest_path)
    if structural_issues:
        raise ValueError(f"Manifest structure is invalid: {json.dumps(structural_issues, sort_keys=True)}")
    samples = [sample for sample in samples if partition is None or sample.get("partition") == partition]
    if not samples:
        raise ValueError(f"No samples found for partition {partition!r}.")
    if len(set(detector_ids)) != len(detector_ids):
        raise ValueError("Detector IDs must be unique.")
    if not detector_ids:
        raise ValueError("Select at least one registered detector.")

    summaries = {}
    for detector_id in detector_ids:
        adapter = REGISTRY.create(detector_id)
        summaries[detector_id] = _summarize_one(adapter, samples, dataset_root)

    evaluated_ids = [key for key, value in summaries.items() if value["availability_status"] == "evaluated"]
    successful_ids = {
        detector_id: {row["sample_id"] for row in summaries[detector_id]["rows"] if row["status"] == "success"}
        for detector_id in evaluated_ids
    }
    pairs: dict[str, Any] = {}
    for left_id, right_id in combinations(evaluated_ids, 2):
        shared_ids = successful_ids[left_id] & successful_ids[right_id]
        pair_key = f"{left_id}__vs__{right_id}"
        pair_rows = {
            detector_id: [row for row in summaries[detector_id]["rows"] if row["sample_id"] in shared_ids]
            for detector_id in (left_id, right_id)
        }
        pairs[pair_key] = {
            "available": bool(shared_ids),
            "sample_count": len(shared_ids),
            "sample_ids": sorted(shared_ids),
            "detectors": {detector_id: _classification_metrics(rows) for detector_id, rows in pair_rows.items()},
        }
        if not shared_ids:
            pairs[pair_key]["reason"] = "No sample was successfully processed by both detectors."
    paired: dict[str, Any] = {
        "available": any(pair["available"] for pair in pairs.values()),
        "pairs": pairs,
        "reason": None if pairs else "At least two detectors must complete inference to calculate paired comparison metrics.",
    }

    rows = []
    for summary in summaries.values():
        if summary["rows"]:
            rows.extend(summary["rows"])
        elif summary["availability_status"] in {"not_evaluated", "load_failed"}:
            for sample in samples:
                error = (
                    {"code": "adapter_unavailable", "message": summary["unavailable_reason"]}
                    if summary["availability_status"] == "not_evaluated"
                    else summary["load_error"]
                )
                rows.append({
                    "sample_id": sample["sample_id"],
                    "audio_path": sample["audio_path"],
                    "ground_truth": sample["ground_truth"],
                    "detector_id": summary["model"]["detector_id"],
                    "status": summary["availability_status"],
                    "predicted_label": None,
                    "native_scores": None,
                    "score_type": summary["model"]["score_type"],
                    "score_direction": summary["model"]["score_direction"],
                    "spoof_score_for_auc": None,
                    "inference_ms": None,
                    "error": error,
                })

    return {
        "schema_version": 1,
        "evaluation_mode": "offline_cpu_only",
        "partition": partition or "all_manifest_partitions",
        "dataset": {"manifest": manifest_path.name, "dataset_root": dataset_root.name, "sample_count": len(samples)},
        "validation_warnings": [issue for issue in validation["issues"] if issue["severity"] == "warning"],
        "models": summaries,
        "paired_comparison": paired,
        "per_sample_results": rows,
        "limitations": [
            "The bundled 24 clips are development fixtures and cannot establish real-world accuracy or select a production replacement.",
            "Native model scores are not assumed calibrated; score type and direction are recorded per adapter.",
            "Alternative adapters without a local pinned checkpoint are marked not_evaluated; no model download is attempted.",
            "Latency numbers, when present, are descriptive timings from this run and not controlled device benchmarks.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/audio/evaluation_manifest.json")
    parser.add_argument("--dataset-root", type=Path, default=ROOT / "tests/audio")
    parser.add_argument("--partition", choices=("development", "validation", "test"))
    parser.add_argument("--detectors", default="current,sara1708_wav2vec2,aasist_l", help=f"Comma-separated registered IDs. Available: {', '.join(REGISTRY.ids())}")
    parser.add_argument("--output", type=Path, default=Path("/tmp/echosentinel-model-comparison.json"))
    args = parser.parse_args()
    try:
        report = compare_detectors(args.manifest, args.dataset_root, [x.strip() for x in args.detectors.split(",") if x.strip()], args.partition)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "models": {key: {"status": value["availability_status"], "coverage": value["coverage"], "metrics": value["metrics"]} for key, value in report["models"].items()}, "paired_comparison": report["paired_comparison"]}, indent=2, allow_nan=False))
    except Exception as exc:
        parser.exit(2, f"Comparison failed: {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
