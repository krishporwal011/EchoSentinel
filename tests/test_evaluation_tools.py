"""Regression coverage for offline evaluation manifest and metric helpers."""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from evaluation_tools import calculate_metrics, load_manifest, validate_manifest, write_evaluation_report
from evaluate_detector import evaluate


def _sample(sample_id: str, audio_path: str, **overrides):
    sample = {
        "sample_id": sample_id,
        "audio_path": audio_path,
        "ground_truth": "bonafide",
        "source_type": "human_recording",
        "speaker_id": "unknown",
        "source_recording_id": "unknown",
        "synthetic_generator": "not_applicable",
        "synthetic_generator_version": "not_applicable",
        "language": "unknown",
        "codec": "wav",
        "sample_rate": 16000,
        "recording_conditions": ["unknown"],
        "dataset_source": "test-dataset",
        "provenance": "unknown",
        "consent_status": "unknown",
        "partition": "development",
        "notes": "",
        "uncertainty": "unknown",
    }
    sample.update(overrides)
    return sample


def _write_manifest(path: Path, samples):
    path.write_text(json.dumps({"schema_version": 1, "samples": samples}), encoding="utf-8")


def test_bundled_fixture_manifest_validates_and_decodes_all_24():
    report = validate_manifest(ROOT / "tests/audio/evaluation_manifest.json", ROOT / "tests/audio")
    assert report["valid"] is True
    assert report["sample_count"] == 24
    assert report["decoded_count"] == 24
    assert report["exact_duplicates"] == []
    assert any(issue["code"] == "partition_independence_unverified" for issue in report["issues"])


def test_validator_rejects_duplicate_ids_missing_files_bad_labels_and_traversal(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    sf.write(root / "ok.wav", np.zeros(1600, dtype=np.float32), 16000)
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [
        _sample("duplicate", "ok.wav"),
        _sample("duplicate", "missing.wav", ground_truth="other"),
        _sample("escape", "../outside.wav"),
    ])

    report = validate_manifest(manifest, root)
    codes = {issue["code"] for issue in report["issues"]}
    assert report["valid"] is False
    assert {"duplicate_sample_id", "missing_audio", "invalid_label", "path_traversal"} <= codes


def test_validator_reports_exact_duplicate_content_and_partition_leakage(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    audio = np.linspace(-0.1, 0.1, 1600, dtype=np.float32)
    sf.write(root / "one.wav", audio, 16000)
    sf.write(root / "two.wav", audio, 16000)
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [
        _sample("one", "one.wav", speaker_id="speaker-a", source_recording_id="source-a"),
        _sample("two", "two.wav", speaker_id="speaker-a", source_recording_id="source-a", partition="test"),
    ])

    report = validate_manifest(manifest, root)
    codes = [issue["code"] for issue in report["issues"]]
    assert codes.count("duplicate_content") == 1
    assert codes.count("partition_leakage") == 2
    assert report["valid"] is False


def test_metrics_have_null_for_undefined_rates_and_auc():
    metrics = calculate_metrics([
        {"ground_truth": "bonafide", "ai_probability": 0.2},
    ])
    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["roc_auc"] is None
    assert metrics["false_positive_rate"] == 0.0


def test_manifest_rejects_unknown_schema_fields(tmp_path):
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [_sample("one", "missing.wav", invented_metadata="x")])
    _, issues = load_manifest(manifest)
    assert any(issue["code"] == "unexpected_sample_fields" for issue in issues)


def test_report_files_are_machine_readable_and_do_not_export_private_ids(tmp_path):
    row = {
        "sample_id": "opaque-1", "audio_path": "clip.wav", "ground_truth": "spoof",
        "predicted_label": "spoof", "bonafide_score": 0.1, "spoof_score": 0.9,
        "ai_probability": 0.9, "partition": "development", "quality_flags": [],
        "recording_conditions": ["unknown"], "speaker_id": "private-speaker-name",
        "source_recording_id": "private-source-id", "quality_measurements": [],
    }
    report = {"metrics": calculate_metrics([row])}
    write_evaluation_report([row], report, tmp_path)
    csv_text = (tmp_path / "per_sample_predictions.csv").read_text(encoding="utf-8")
    assert "private-speaker-name" not in csv_text
    assert "private-source-id" not in csv_text
    assert json.loads((tmp_path / "evaluation_summary.json").read_text(encoding="utf-8")) == report


def test_threshold_sweep_refuses_development_partition_before_model_loading(tmp_path):
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, [])
    try:
        evaluate(manifest, tmp_path, partition="development", sweep=True)
    except ValueError as exc:
        assert "only with --partition validation" in str(exc)
    else:
        raise AssertionError("development data must not be used for a threshold sweep")
