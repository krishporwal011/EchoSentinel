"""No-weight safety and contract tests for isolated detector adapters."""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from compare_detectors import compare_detectors
from detector_adapters import (
    AASISTLUnavailableAdapter,
    CurrentEchoSentinelAdapter,
    DetectorAdapterError,
    DetectorPrediction,
    DetectorRegistry,
    DetectorUnavailableError,
    InferenceFailureError,
    ModelMetadata,
    REGISTRY,
    Sara1708UnavailableAdapter,
    UnsupportedInputError,
    validate_waveform,
)


def _metadata(detector_id="test-failure", **kwargs):
    values = dict(
        detector_id=detector_id,
        model_id="local/test-double",
        revision="test-revision",
        task="test binary spoof detection",
        architecture="test double",
        license="test-only",
        documentation_url="https://example.invalid/test-double",
        expected_sample_rate=16000,
        class_mapping={"bonafide": "human", "spoof": "synthetic"},
        score_type="softmax_uncalibrated",
        score_direction="class_indexed",
    )
    values.update(kwargs)
    return ModelMetadata(**values)


def test_registered_models_include_current_and_explicit_unavailable_candidates():
    assert set(REGISTRY.ids()) == {"current", "sara1708_wav2vec2", "aasist_l"}
    assert REGISTRY.create("current").metadata.status == "available"
    sara = REGISTRY.create("sara1708_wav2vec2")
    aasist = REGISTRY.create("aasist_l")
    assert isinstance(sara, Sara1708UnavailableAdapter)
    assert isinstance(aasist, AASISTLUnavailableAdapter)
    assert sara.metadata.status == "not_evaluated"
    assert aasist.metadata.status == "not_evaluated"
    for adapter in (sara, aasist):
        try:
            adapter.load(device="cpu", offline=True)
        except DetectorUnavailableError as exc:
            assert exc.code == "adapter_unavailable"
        else:
            raise AssertionError("unavailable adapter must not claim to load")


def test_metadata_validation_requires_explicit_class_mapping_and_known_score_semantics():
    _metadata().validate()
    for invalid in (
        _metadata(class_mapping={"spoof": 1}),
        _metadata(score_type="made_up"),
        _metadata(score_direction="made_up"),
        _metadata(expected_sample_rate=0),
        _metadata(status="not_evaluated"),
    ):
        try:
            invalid.validate()
        except ValueError:
            pass
        else:
            raise AssertionError("invalid metadata must be rejected")


def test_registry_rejects_duplicate_ids_and_unknown_ids():
    registry = DetectorRegistry()

    class First:
        metadata = _metadata("duplicate-id")

    class Second:
        metadata = _metadata("duplicate-id")

    registry.register(First)
    try:
        registry.register(Second)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate adapter registration must fail")
    try:
        registry.create("not-registered")
    except DetectorUnavailableError as exc:
        assert exc.code == "adapter_unavailable"
    else:
        raise AssertionError("unknown adapter must fail clearly")


def test_prediction_validates_score_type_direction_mapping_and_ranges():
    prediction = DetectorPrediction("spoof", {"bonafide": 0.1, "spoof": 0.9}, "softmax_uncalibrated", "class_indexed", 1.5)
    prediction.validate()
    assert prediction.spoof_score_for_auc() == 0.9
    # A single spoof score is sufficient; no bonafide score is fabricated.
    one_score = DetectorPrediction("spoof", {"spoof_score": 1.3}, "model_native", "higher_is_spoof", 2.0)
    one_score.validate()
    assert one_score.native_scores == {"spoof_score": 1.3}
    assert one_score.spoof_score_for_auc() == 1.3
    for invalid in (
        DetectorPrediction("unknown", {"spoof": 0.8}, "model_native", "higher_is_spoof", 1.0),
        DetectorPrediction("spoof", {"spoof": float("nan")}, "model_native", "higher_is_spoof", 1.0),
        DetectorPrediction("spoof", {"spoof": 1.2}, "softmax_uncalibrated", "higher_is_spoof", 1.0),
        DetectorPrediction("spoof", {"bonafide": 0.2}, "softmax_uncalibrated", "class_indexed", 1.0),
        DetectorPrediction("spoof", {"bonafide": 0.2, "spoof": 0.2}, "softmax_uncalibrated", "class_indexed", 1.0),
    ):
        try:
            invalid.validate()
        except InferenceFailureError:
            pass
        else:
            raise AssertionError("invalid prediction must be rejected")


def test_waveform_contract_rejects_bad_shapes_rates_and_nonfinite_values():
    waveform = np.zeros(16000, dtype=np.float32)
    validate_waveform(waveform, 16000, 16000)
    invalid = (
        (waveform.astype(np.float64), 16000),
        (np.zeros((1, 10), dtype=np.float32), 16000),
        (np.array([], dtype=np.float32), 16000),
        (np.array([float("nan")], dtype=np.float32), 16000),
        (waveform, 8000),
    )
    for data, rate in invalid:
        try:
            validate_waveform(data, rate, 16000)
        except UnsupportedInputError:
            pass
        else:
            raise AssertionError("invalid input must be rejected")


def test_current_adapter_maps_existing_wrapper_labels_and_scores_without_relabeling():
    class FakeModel:
        def predict(self, waveform, sample_rate):
            assert sample_rate == 16000
            assert waveform.dtype == np.float32
            return {
                "prediction": "AI-generated",
                "human_probability": 0.12,
                "ai_probability": 0.88,
                "processing_time_ms": 5.25,
            }

    adapter = CurrentEchoSentinelAdapter()
    adapter.detector = FakeModel()
    result = adapter.predict(np.zeros(16000, dtype=np.float32), 16000)
    assert result.predicted_label == "spoof"
    assert result.native_scores == {"bonafide": 0.12, "spoof": 0.88}
    assert result.score_type == "softmax_uncalibrated"
    assert result.score_direction == "class_indexed"


def test_current_adapter_refuses_network_and_unpinned_revision():
    adapter = CurrentEchoSentinelAdapter()
    for kwargs, error in (
        ({"offline": False}, UnsupportedInputError),
        ({"revision": "different-revision"}, DetectorUnavailableError),
    ):
        try:
            adapter.load(**kwargs)
        except error:
            pass
        else:
            raise AssertionError("adapter must enforce offline use and its checkpoint revision pin")


def test_comparison_reports_failures_unavailable_adapters_and_json_serialization(tmp_path):
    root = tmp_path / "audio"
    root.mkdir()
    time_axis = np.arange(16000, dtype=np.float32) / 16000
    sf.write(root / "clip.wav", 0.1 * np.sin(2 * np.pi * 220 * time_axis), 16000)
    manifest = tmp_path / "manifest.json"
    sample = {
        "sample_id": "opaque-clip", "audio_path": "clip.wav", "ground_truth": "bonafide",
        "source_type": "human_recording", "speaker_id": "unknown", "source_recording_id": "unknown",
        "synthetic_generator": "not_applicable", "synthetic_generator_version": "not_applicable",
        "language": "unknown", "codec": "wav", "sample_rate": 16000,
        "recording_conditions": ["unknown"], "dataset_source": "local-test", "provenance": "unknown",
        "consent_status": "unknown", "partition": "development", "notes": "", "uncertainty": "unknown",
    }
    manifest.write_text(json.dumps({"schema_version": 1, "samples": [sample]}), encoding="utf-8")

    class FailingAdapter:
        metadata = _metadata()

        def load(self, *, device="cpu", offline=True, revision=None):
            assert device == "cpu" and offline is True
            assert revision == "test-revision"

        def predict(self, waveform, sample_rate):
            raise InferenceFailureError("deliberate test double failure")

    saved_registry = REGISTRY._factories.copy()
    try:
        REGISTRY.register(FailingAdapter)
        report = compare_detectors(manifest, root, ["test-failure", "sara1708_wav2vec2"], "development")
    finally:
        REGISTRY._factories = saved_registry
    failed = report["models"]["test-failure"]
    unavailable = report["models"]["sara1708_wav2vec2"]
    assert failed["attempted_samples"] == 1
    assert failed["failed_inferences"] == 1
    assert failed["coverage"] == 0.0
    assert failed["failure_reasons"] == {"inference_failed": 1}
    assert unavailable["availability_status"] == "not_evaluated"
    assert unavailable["attempted_samples"] == 0
    assert report["paired_comparison"]["available"] is False
    serialized = json.dumps(report, allow_nan=False)
    assert "deliberate test double failure" in serialized
    saved = json.loads(serialized)
    assert saved["models"]["sara1708_wav2vec2"]["model"]["class_mapping"] is None
    assert saved["per_sample_results"][-1]["status"] == "not_evaluated"


def test_fake_detector_test_does_not_create_model_performance_metrics():
    adapter = Sara1708UnavailableAdapter()
    assert adapter.metadata.status == "not_evaluated"
    assert adapter.metadata.class_mapping is None
    assert adapter.metadata.score_type is None
    assert adapter.metadata.score_direction is None


def test_paired_metrics_are_computed_per_detector_pair_not_only_all_model_intersection(tmp_path):
    root = tmp_path / "audio"
    root.mkdir()
    samples = []
    time_axis = np.arange(16000, dtype=np.float32) / 16000
    for index, frequency in enumerate((180, 240, 330)):
        filename = f"clip-{index}.wav"
        sf.write(root / filename, 0.1 * np.sin(2 * np.pi * frequency * time_axis), 16000)
        samples.append({
            "sample_id": f"clip-{index}", "audio_path": filename, "ground_truth": "bonafide",
            "source_type": "human_recording", "speaker_id": "unknown", "source_recording_id": "unknown",
            "synthetic_generator": "not_applicable", "synthetic_generator_version": "not_applicable",
            "language": "unknown", "codec": "wav", "sample_rate": 16000,
            "recording_conditions": ["unknown"], "dataset_source": "local-test", "provenance": "unknown",
            "consent_status": "unknown", "partition": "development", "notes": "", "uncertainty": "unknown",
        })
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "samples": samples}), encoding="utf-8")

    success_indices = {
        "pair-left": {0, 1},
        "pair-middle": {1, 2},
        "pair-right": {0, 2},
    }
    saved_registry = REGISTRY._factories.copy()
    try:
        for detector_id, allowed in success_indices.items():
            class PairAdapter:
                metadata = _metadata(detector_id)
                allowed_indices = set(allowed)

                def __init__(self):
                    self.index = 0

                def load(self, *, device="cpu", offline=True, revision=None):
                    assert device == "cpu" and offline

                def predict(self, waveform, sample_rate):
                    current = self.index
                    self.index += 1
                    if current not in self.allowed_indices:
                        raise InferenceFailureError("sample intentionally unavailable for pair coverage test")
                    return DetectorPrediction(
                        "bonafide", {"bonafide": 0.9, "spoof": 0.1},
                        "softmax_uncalibrated", "class_indexed", 1.0,
                    )

            PairAdapter.__name__ = f"Adapter_{detector_id.replace('-', '_')}"
            REGISTRY.register(PairAdapter)

        report = compare_detectors(manifest, root, list(success_indices), "development")
    finally:
        REGISTRY._factories = saved_registry
    pairs = report["paired_comparison"]["pairs"]
    assert report["paired_comparison"]["available"] is True
    assert set(pairs) == {"pair-left__vs__pair-middle", "pair-left__vs__pair-right", "pair-middle__vs__pair-right"}
    assert all(pair["sample_count"] == 1 for pair in pairs.values())
    assert {pair["sample_ids"][0] for pair in pairs.values()} == {"clip-0", "clip-1", "clip-2"}
