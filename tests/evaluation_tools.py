"""Offline manifest validation and reporting helpers for EchoSentinel evaluation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable

import librosa
import numpy as np
import soundfile as sf


MANIFEST_VERSION = 1
SUPPORTED_LABELS = {"bonafide", "spoof"}
SUPPORTED_SOURCE_TYPES = {"human_recording", "synthetic_speech", "unknown"}
SUPPORTED_PARTITIONS = {"development", "validation", "test"}
REQUIRED_FIELDS = {
    "sample_id", "audio_path", "ground_truth", "source_type", "speaker_id",
    "source_recording_id", "synthetic_generator", "synthetic_generator_version",
    "language", "codec", "sample_rate", "recording_conditions", "dataset_source",
    "provenance", "consent_status", "partition", "notes", "uncertainty",
}
UNKNOWN_MARKERS = {"", "unknown", "unk", "n/a", "na", "not provided"}


def _unknown(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in UNKNOWN_MARKERS)


def _read_audio_metadata(path: Path) -> dict[str, Any]:
    """Decode samples to verify readability and inspect source rate/channel/duration."""
    try:
        data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    except Exception:
        # librosa provides a decoder fallback for formats not supported by libsndfile.
        data, sample_rate = librosa.load(path, sr=None, mono=False)
        if data.ndim == 1:
            channels, frames = 1, len(data)
        else:
            channels = data.shape[0] if data.shape[0] <= 8 and data.shape[1] > 8 else data.shape[1]
            frames = max(data.shape)
        if frames == 0:
            raise ValueError("decoded audio contains no samples")
        if not np.all(np.isfinite(data)):
            raise ValueError("decoded audio contains NaN or infinite samples")
        return {
            "sample_rate": int(sample_rate), "channels": int(channels),
            "frames": int(frames), "duration_seconds": float(frames / sample_rate),
        }

    if data.shape[0] == 0:
        raise ValueError("decoded audio contains no samples")
    if not np.all(np.isfinite(data)):
        raise ValueError("decoded audio contains NaN or infinite samples")
    return {
        "sample_rate": int(sample_rate), "channels": int(data.shape[1]),
        "frames": int(data.shape[0]),
        "duration_seconds": float(data.shape[0] / sample_rate),
    }


def load_manifest(manifest_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load a versioned JSON manifest and return samples plus structural issues."""
    issues: list[dict[str, Any]] = []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], [{"severity": "error", "code": "manifest_read_error", "message": str(exc)}]
    if not isinstance(payload, dict) or payload.get("schema_version") != MANIFEST_VERSION:
        return [], [{"severity": "error", "code": "unsupported_schema", "message": f"Expected a manifest object with schema_version={MANIFEST_VERSION}."}]
    extra_root_fields = sorted(payload.keys() - {"schema_version", "samples"})
    if extra_root_fields:
        issues.append({"severity": "error", "code": "unexpected_manifest_fields", "fields": extra_root_fields, "message": "Manifest contains fields not defined by schema version 1."})
    samples = payload.get("samples")
    if not isinstance(samples, list):
        return [], [{"severity": "error", "code": "invalid_samples", "message": "Manifest field 'samples' must be an array."}]
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            issues.append({"severity": "error", "code": "invalid_sample", "index": index, "message": "Each sample must be a JSON object."})
            continue
        missing = sorted(REQUIRED_FIELDS - sample.keys())
        if missing:
            issues.append({
                "severity": "error", "code": "missing_fields", "sample_id": sample.get("sample_id", f"row-{index + 1}"),
                "fields": missing, "message": "Required fields must be present; use null or 'unknown' for unavailable metadata.",
            })
        extra = sorted(sample.keys() - REQUIRED_FIELDS)
        if extra:
            issues.append({"severity": "error", "code": "unexpected_sample_fields", "sample_id": sample.get("sample_id", f"row-{index + 1}"), "fields": extra, "message": "Sample contains fields not defined by schema version 1."})
    return [s for s in samples if isinstance(s, dict)], issues


def validate_manifest(manifest_path: Path, dataset_root: Path) -> dict[str, Any]:
    """Validate paths, labels, metadata, decoding, hashes, and known partition leakage."""
    dataset_root = dataset_root.resolve()
    samples, issues = load_manifest(manifest_path)
    ids: dict[str, int] = {}
    hashes: dict[str, list[str]] = defaultdict(list)
    speaker_partitions: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    source_partitions: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    metadata_gaps: list[dict[str, Any]] = []
    inspected: list[dict[str, Any]] = []
    unknown_identity_count = 0

    for index, sample in enumerate(samples):
        sample_id = sample.get("sample_id")
        display_id = sample_id if isinstance(sample_id, str) and sample_id.strip() else f"row-{index + 1}"
        if not isinstance(sample_id, str) or not sample_id.strip():
            issues.append({"severity": "error", "code": "invalid_sample_id", "sample_id": display_id, "message": "sample_id must be a non-empty string."})
        elif sample_id in ids:
            issues.append({"severity": "error", "code": "duplicate_sample_id", "sample_id": display_id, "message": f"sample_id is duplicated (rows {ids[sample_id] + 1} and {index + 1})."})
        else:
            ids[sample_id] = index

        label = sample.get("ground_truth")
        if label not in SUPPORTED_LABELS:
            issues.append({"severity": "error", "code": "invalid_label", "sample_id": display_id, "message": "ground_truth must be 'bonafide' or 'spoof'."})
        if sample.get("source_type") not in SUPPORTED_SOURCE_TYPES:
            issues.append({"severity": "error", "code": "invalid_source_type", "sample_id": display_id, "message": "source_type must be human_recording, synthetic_speech, or unknown."})
        if sample.get("partition") not in SUPPORTED_PARTITIONS:
            issues.append({"severity": "error", "code": "invalid_partition", "sample_id": display_id, "message": "partition must be development, validation, or test."})

        for field in ("speaker_id", "source_recording_id", "synthetic_generator", "synthetic_generator_version", "language", "codec"):
            value = sample.get(field)
            if value is not None and not isinstance(value, str):
                issues.append({"severity": "error", "code": "invalid_metadata_type", "sample_id": display_id, "fields": [field], "message": f"{field} must be a string or null."})
        for field in ("dataset_source", "provenance", "consent_status", "notes", "uncertainty"):
            if not isinstance(sample.get(field), str):
                issues.append({"severity": "error", "code": "invalid_metadata_type", "sample_id": display_id, "fields": [field], "message": f"{field} must be a string; use 'unknown' when unavailable."})
        sample_rate = sample.get("sample_rate")
        if sample_rate is not None and (isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0):
            issues.append({"severity": "error", "code": "invalid_sample_rate", "sample_id": display_id, "message": "sample_rate must be a positive integer or null."})

        conditions = sample.get("recording_conditions")
        if not isinstance(conditions, list) or not conditions or not all(isinstance(x, str) and x.strip() for x in conditions):
            issues.append({"severity": "error", "code": "invalid_recording_conditions", "sample_id": display_id, "message": "recording_conditions must be a non-empty array of non-empty strings; use ['unknown'] when unavailable."})

        relative = sample.get("audio_path")
        if not isinstance(relative, str) or not relative.strip():
            issues.append({"severity": "error", "code": "invalid_audio_path", "sample_id": display_id, "message": "audio_path must be a non-empty relative path."})
            continue
        candidate = Path(relative)
        if candidate.is_absolute() or PureWindowsPath(relative).is_absolute():
            issues.append({"severity": "error", "code": "absolute_audio_path", "sample_id": display_id, "message": "audio_path must be relative to dataset_root."})
            continue
        resolved = (dataset_root / candidate).resolve()
        if not resolved.is_relative_to(dataset_root):
            issues.append({"severity": "error", "code": "path_traversal", "sample_id": display_id, "message": "audio_path resolves outside dataset_root (including through symlinks)."})
            continue
        if not resolved.is_file():
            issues.append({"severity": "error", "code": "missing_audio", "sample_id": display_id, "message": "Audio file does not exist under dataset_root."})
            continue

        try:
            info = _read_audio_metadata(resolved)
            digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
            hashes[digest].append(display_id)
            inspected.append({"sample_id": display_id, "audio_path": relative, **info})
            manifest_rate = sample.get("sample_rate")
            if manifest_rate is not None and manifest_rate != info["sample_rate"]:
                issues.append({"severity": "warning", "code": "sample_rate_mismatch", "sample_id": display_id, "message": f"Manifest sample_rate={manifest_rate} differs from decoded rate={info['sample_rate']} Hz."})
        except Exception as exc:
            issues.append({"severity": "error", "code": "audio_decode_error", "sample_id": display_id, "message": f"Could not decode audio ({type(exc).__name__}); the file may be corrupt or use an unavailable codec."})

        for field in ("speaker_id", "source_recording_id", "synthetic_generator", "synthetic_generator_version", "language", "codec", "dataset_source", "provenance", "consent_status"):
            if _unknown(sample.get(field)):
                metadata_gaps.append({"sample_id": display_id, "field": field})
        if _unknown(sample.get("speaker_id")) or _unknown(sample.get("source_recording_id")):
            unknown_identity_count += 1

        # Identifiers are scoped to a dataset source; unknown identifiers never count as distinct.
        scope = str(sample.get("dataset_source", "unknown"))
        partition = sample.get("partition")
        speaker = sample.get("speaker_id")
        source_id = sample.get("source_recording_id")
        if partition in SUPPORTED_PARTITIONS and not _unknown(speaker):
            speaker_partitions[(scope, str(speaker))][partition].append(display_id)
        if partition in SUPPORTED_PARTITIONS and not _unknown(source_id):
            source_partitions[(scope, str(source_id))][partition].append(display_id)

    duplicate_hashes = [
        {"sample_ids": sample_ids, "sha256": digest}
        for digest, sample_ids in hashes.items() if len(sample_ids) > 1
    ]
    for duplicate in duplicate_hashes:
        issues.append({"severity": "error", "code": "duplicate_content", "sample_ids": duplicate["sample_ids"], "message": "Samples have identical SHA-256 content."})

    leakage = []
    for field_name, mapping in (("speaker_id", speaker_partitions), ("source_recording_id", source_partitions)):
        for (scope, _identifier), partitions in mapping.items():
            if len(partitions) > 1:
                leakage.append({
                    "field": field_name, "dataset_source": scope,
                    "partitions": sorted(partitions),
                    "sample_ids": sorted(sample_id for values in partitions.values() for sample_id in values),
                })
    for item in leakage:
        issues.append({"severity": "error", "code": "partition_leakage", **item, "message": f"Known {item['field']} appears in more than one partition."})

    if metadata_gaps:
        issues.append({"severity": "warning", "code": "missing_provenance", "message": "Some provenance, consent, or source metadata is unknown; see metadata_gaps."})
    if unknown_identity_count:
        issues.append({"severity": "warning", "code": "partition_independence_unverified", "message": "Unknown speaker/source IDs are not assumed distinct; partition independence cannot be fully verified."})

    errors = sum(issue["severity"] == "error" for issue in issues)
    return {
        "valid": errors == 0,
        "manifest": manifest_path.name,
        "dataset_root": dataset_root.name,
        "sample_count": len(samples),
        "decoded_count": len(inspected),
        "issues": issues,
        "metadata_gaps": metadata_gaps,
        "partition_leakage": leakage,
        "exact_duplicates": duplicate_hashes,
        "near_duplicate_check": {"performed": False, "reason": "No validated audio fingerprinting method is included in the installed project dependencies."},
        "samples": inspected,
    }


def discover_legacy_fixtures(project_root: Path) -> list[dict[str, Any]]:
    """Preserve the original genuine/spoof directory evaluation as a fallback."""
    samples = []
    for folder, label, source_type in (("genuine", "bonafide", "human_recording"), ("spoof", "spoof", "synthetic_speech")):
        for path in sorted((project_root / "tests" / "audio" / folder).glob("*")):
            if path.is_file():
                samples.append({
                    "sample_id": path.stem, "audio_path": str(path), "ground_truth": label,
                    "source_type": source_type, "speaker_id": None, "source_recording_id": None,
                    "synthetic_generator": None, "synthetic_generator_version": None,
                    "language": None, "codec": path.suffix.lstrip("."), "sample_rate": None,
                    "recording_conditions": ["unknown"], "dataset_source": "unknown",
                    "provenance": None, "consent_status": "unknown", "partition": "development",
                    "notes": "Legacy fixture discovery; provenance not documented.", "uncertainty": "unknown",
                })
    return samples


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    """Two-sided 95% Wilson interval for a binomial proportion."""
    if total <= 0:
        return None
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    return [max(0.0, center - margin), min(1.0, center + margin)]


def calculate_metrics(rows: list[dict[str, Any]], threshold: float = 0.5) -> dict[str, Any]:
    """Calculate binary metrics; undefined denominators and AUC are JSON null."""
    tp = sum(r["ground_truth"] == "spoof" and r["ai_probability"] >= threshold for r in rows)
    fn = sum(r["ground_truth"] == "spoof" and r["ai_probability"] < threshold for r in rows)
    fp = sum(r["ground_truth"] == "bonafide" and r["ai_probability"] >= threshold for r in rows)
    tn = sum(r["ground_truth"] == "bonafide" and r["ai_probability"] < threshold for r in rows)
    n = len(rows)
    counts = {
        "accuracy": (tp + tn, n), "precision": (tp, tp + fp), "recall": (tp, tp + fn),
        "f1": (2 * tp, 2 * tp + fp + fn), "false_positive_rate": (fp, fp + tn),
        "false_negative_rate": (fn, fn + tp),
    }
    metrics = {name: _ratio(*pair) for name, pair in counts.items()}
    metrics["confidence_intervals_95_wilson"] = {
        "accuracy": wilson_interval(tp + tn, n),
        "precision": wilson_interval(tp, tp + fp),
        "recall": wilson_interval(tp, tp + fn),
        "false_positive_rate": wilson_interval(fp, fp + tn),
        "false_negative_rate": wilson_interval(fn, fn + tp),
        "f1": None,
    }
    labels = {r["ground_truth"] for r in rows}
    score_values = [r["ai_probability"] for r in rows]
    if labels == SUPPORTED_LABELS and all(np.isfinite(s) and 0 <= s <= 1 for s in score_values):
        try:
            from sklearn.metrics import roc_auc_score
            metrics["roc_auc"] = float(roc_auc_score([r["ground_truth"] == "spoof" for r in rows], score_values))
        except ImportError:
            metrics["roc_auc"] = None
            metrics["roc_auc_note"] = "scikit-learn is unavailable; AUC was not calculated."
    else:
        metrics["roc_auc"] = None
        metrics["roc_auc_note"] = "ROC-AUC requires both classes and finite scores in [0, 1]."
    metrics.update({
        "sample_count": n,
        "class_counts": {"bonafide": sum(r["ground_truth"] == "bonafide" for r in rows), "spoof": sum(r["ground_truth"] == "spoof" for r in rows)},
        "confusion_matrix": {"labels": ["bonafide", "spoof"], "matrix": [[tn, fp], [fn, tp]]},
        "threshold": threshold,
    })
    return metrics


def threshold_sweep(rows: list[dict[str, Any]], thresholds: Iterable[float]) -> list[dict[str, Any]]:
    output = []
    for threshold in thresholds:
        result = calculate_metrics(rows, float(threshold))
        output.append({
            "threshold": float(threshold),
            "tn": result["confusion_matrix"]["matrix"][0][0],
            "fp": result["confusion_matrix"]["matrix"][0][1],
            "fn": result["confusion_matrix"]["matrix"][1][0],
            "tp": result["confusion_matrix"]["matrix"][1][1],
            **{k: result[k] for k in ("false_positive_rate", "false_negative_rate", "precision", "recall", "accuracy")},
        })
    return output


def grouped_metrics(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for field in ("recording_conditions", "synthetic_generator", "language"):
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            values = row.get(field)
            if field == "recording_conditions":
                keys = values if isinstance(values, list) and values else ["unknown"]
            else:
                keys = ["unknown" if _unknown(values) else str(values)]
            for key in keys:
                buckets[str(key)].append(row)
        groups[field] = {key: calculate_metrics(items, threshold) for key, items in sorted(buckets.items())}
    return groups


CSV_FIELDS = [
    "sample_id", "audio_path", "partition", "ground_truth", "predicted_label", "bonafide_score", "spoof_score",
    "duration_seconds", "source_sample_rate", "source_channels", "model_sample_rate", "model_waveform_samples",
    "model_waveform_dtype", "quality_rating", "quality_score", "quality_reliability", "quality_flags",
    "clipped_samples_percent", "level_variation_db", "dynamic_range_db", "high_frequency_share_percent",
    "quality_measurements_json", "recording_conditions", "synthetic_generator", "language",
]


def write_evaluation_report(rows: list[dict[str, Any]], report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "per_sample_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            values = {field: row.get(field, "") for field in CSV_FIELDS}
            for field in ("quality_flags", "recording_conditions"):
                values[field] = ",".join(row.get(field, []) or [])
            values["quality_measurements_json"] = json.dumps(row.get("quality_measurements", []), sort_keys=True, separators=(",", ":"))
            writer.writerow(values)
    (output_dir / "evaluation_summary.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
