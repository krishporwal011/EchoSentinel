"""Isolated offline detector adapters for EchoSentinel model comparisons.

This module is intentionally not imported by the production API.
"""

from __future__ import annotations

import math
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Literal, Protocol, runtime_checkable

import numpy as np


ScoreType = Literal["logits", "softmax_uncalibrated", "sigmoid_uncalibrated", "calibrated_probability", "model_native"]
ScoreDirection = Literal["class_indexed", "higher_is_spoof", "lower_is_spoof"]
DetectorStatus = Literal["available", "not_evaluated"]
VALID_SCORE_TYPES = {
    "logits", "softmax_uncalibrated", "sigmoid_uncalibrated",
    "calibrated_probability", "model_native",
}
VALID_SCORE_DIRECTIONS = {"class_indexed", "higher_is_spoof", "lower_is_spoof"}
VALID_LABELS = {"bonafide", "spoof"}


class DetectorAdapterError(RuntimeError):
    """Base class for clear, structured adapter failures."""

    code = "detector_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class DetectorUnavailableError(DetectorAdapterError):
    code = "adapter_unavailable"


class UnsupportedInputError(DetectorAdapterError):
    code = "unsupported_input"


class InferenceFailureError(DetectorAdapterError):
    code = "inference_failed"


@dataclass(frozen=True)
class ModelMetadata:
    detector_id: str
    model_id: str
    revision: str | None
    task: str
    architecture: str | None
    license: str
    documentation_url: str
    status: DetectorStatus = "available"
    unavailable_reason: str | None = None
    expected_sample_rate: int | None = None
    expected_channels: int = 1
    expected_window_samples: int | None = None
    class_mapping: dict[str, str | int] | None = None
    score_type: ScoreType | None = None
    score_direction: ScoreDirection | None = None
    preprocessing: dict[str, object] = field(default_factory=dict)
    training_data: str | None = None

    def validate(self) -> None:
        for name in ("detector_id", "model_id", "task", "license", "documentation_url"):
            if not getattr(self, name).strip():
                raise ValueError(f"Model metadata field {name!r} must be non-empty.")
        if self.status not in {"available", "not_evaluated"}:
            raise ValueError(f"Unsupported detector status {self.status!r}.")
        if self.expected_sample_rate is not None and self.expected_sample_rate <= 0:
            raise ValueError("expected_sample_rate must be positive or None.")
        if self.expected_channels != 1:
            raise ValueError("The shared evaluation contract currently accepts mono audio only.")
        if self.expected_window_samples is not None and self.expected_window_samples <= 0:
            raise ValueError("expected_window_samples must be positive or None.")
        if self.score_type is not None and self.score_type not in VALID_SCORE_TYPES:
            raise ValueError(f"Unsupported score type {self.score_type!r}.")
        if self.score_direction is not None and self.score_direction not in VALID_SCORE_DIRECTIONS:
            raise ValueError(f"Unsupported score direction {self.score_direction!r}.")
        if self.class_mapping is not None:
            if set(self.class_mapping) != VALID_LABELS:
                raise ValueError("class_mapping must explicitly map exactly 'bonafide' and 'spoof'.")
            if len({str(value) for value in self.class_mapping.values()}) != 2:
                raise ValueError("class_mapping values must identify distinct model classes.")
        if self.status == "not_evaluated" and not self.unavailable_reason:
            raise ValueError("A not_evaluated adapter must explain why it is unavailable.")
        if self.status == "available":
            if not self.revision:
                raise ValueError("Available adapters must pin an immutable checkpoint revision.")
            if self.class_mapping is None or self.score_type is None or self.score_direction is None:
                raise ValueError("Available adapters must declare class mapping, score type, and score direction.")


@dataclass(frozen=True)
class DetectorPrediction:
    predicted_label: str
    native_scores: dict[str, float]
    score_type: ScoreType
    score_direction: ScoreDirection
    inference_ms: float

    def validate(self) -> None:
        if self.predicted_label not in VALID_LABELS:
            raise InferenceFailureError(f"Unsupported prediction label {self.predicted_label!r}.")
        if self.score_type not in VALID_SCORE_TYPES:
            raise InferenceFailureError(f"Unsupported native score type {self.score_type!r}.")
        if self.score_direction not in VALID_SCORE_DIRECTIONS:
            raise InferenceFailureError(f"Unsupported score direction {self.score_direction!r}.")
        if not self.native_scores:
            raise InferenceFailureError("Detector returned no native scores.")
        if self.score_direction == "class_indexed" and set(self.native_scores) != VALID_LABELS:
            raise InferenceFailureError("class_indexed scores must include exactly bonafide and spoof scores.")
        if not all(math.isfinite(float(value)) for value in self.native_scores.values()):
            raise InferenceFailureError("Detector returned a non-finite score.")
        if self.score_type in {"softmax_uncalibrated", "sigmoid_uncalibrated", "calibrated_probability"}:
            if not all(0 <= float(value) <= 1 for value in self.native_scores.values()):
                raise InferenceFailureError(f"{self.score_type} values must be in [0, 1].")
        if self.score_type == "calibrated_probability" and self.score_direction != "class_indexed":
            raise InferenceFailureError("Calibrated class probabilities must use class_indexed score direction.")
        if self.score_type in {"softmax_uncalibrated", "calibrated_probability"}:
            if self.score_direction != "class_indexed" or not math.isclose(sum(map(float, self.native_scores.values())), 1.0, rel_tol=0.0, abs_tol=1e-4):
                raise InferenceFailureError(f"{self.score_type} class scores must be class-indexed and sum to one.")
        if self.inference_ms < 0 or not math.isfinite(self.inference_ms):
            raise InferenceFailureError("Inference duration must be a finite non-negative value.")

    def spoof_score_for_auc(self) -> float | None:
        """Return a continuous spoof-oriented score only when its semantics are explicit."""
        if self.score_direction == "class_indexed":
            if "spoof" in self.native_scores:
                return float(self.native_scores["spoof"])
            return None
        if len(self.native_scores) != 1:
            raise InferenceFailureError("Directional scalar scores must contain exactly one named score.")
        value = float(next(iter(self.native_scores.values())))
        return value if self.score_direction == "higher_is_spoof" else -value


@runtime_checkable
class DetectorAdapter(Protocol):
    metadata: ModelMetadata

    def load(self, *, device: str = "cpu", offline: bool = True, revision: str | None = None) -> None: ...

    def predict(self, waveform: np.ndarray, sample_rate: int) -> DetectorPrediction: ...


class DetectorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, type[DetectorAdapter]] = {}

    def register(self, adapter_cls: type[DetectorAdapter]) -> type[DetectorAdapter]:
        metadata = adapter_cls.metadata
        metadata.validate()
        if metadata.detector_id in self._factories:
            raise ValueError(f"Detector {metadata.detector_id!r} is already registered.")
        self._factories[metadata.detector_id] = adapter_cls
        return adapter_cls

    def create(self, detector_id: str) -> DetectorAdapter:
        try:
            return self._factories[detector_id]()
        except KeyError as exc:
            raise DetectorUnavailableError(f"No adapter is registered for {detector_id!r}.") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


REGISTRY = DetectorRegistry()


@REGISTRY.register
class CurrentEchoSentinelAdapter:
    PINNED_MODEL_ID = "HyperMoon/wav2vec2-base-960h-finetuned-deepfake"
    # Observed from this repository's existing local evaluation report.
    PINNED_REVISION = "c73de548282dd35b6dec0844b924e3a931f3abfc"
    metadata = ModelMetadata(
        detector_id="current",
        model_id=PINNED_MODEL_ID,
        revision=PINNED_REVISION,
        task="binary speech anti-spoofing: bonafide vs spoof",
        architecture="Wav2Vec2ForSequenceClassification",
        license="unknown; review upstream model and training-data terms",
        documentation_url="https://huggingface.co/HyperMoon/wav2vec2-base-960h-finetuned-deepfake",
        expected_sample_rate=16000,
        expected_channels=1,
        class_mapping={"bonafide": "bonafide index resolved from model id2label at load", "spoof": "spoof index resolved from model id2label at load"},
        score_type="softmax_uncalibrated",
        score_direction="class_indexed",
        preprocessing={
            "shared_input": "mono float32 at 16000 Hz, peak-normalized by existing decode_and_preprocess_audio to 0.95",
            "model_input": "existing Wav2Vec2 feature extractor with its configured normalization",
            "source_code": "backend/audio_processor.py and backend/model.py",
        },
        training_data="Not verified from local project documentation.",
    )

    def __init__(self) -> None:
        self.detector = None
        self.load_duration_ms: float | None = None
        self.resolved_class_mapping: dict[str, int] | None = None
        self.preprocessing_details: dict[str, object] | None = None

    def load(self, *, device: str = "cpu", offline: bool = True, revision: str | None = None) -> None:
        if device != "cpu":
            raise UnsupportedInputError("This comparison runner currently supports CPU only.")
        if not offline:
            raise UnsupportedInputError("This comparison adapter only permits offline checkpoint loading.")
        requested_revision = revision if revision is not None else self.PINNED_REVISION
        if requested_revision != self.PINNED_REVISION:
            raise DetectorUnavailableError(
                f"Requested revision {requested_revision!r} does not match the adapter pin {self.PINNED_REVISION!r}."
            )
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        started = time.perf_counter()
        try:
            import torch
            from transformers import AutoFeatureExtractor
            try:
                from transformers import AutoModelForAudioClassification as ModelClass
            except ImportError:
                from transformers import Wav2Vec2ForSequenceClassification as ModelClass
            from model import VoiceCloneDetector
            from model import resolve_label_mapping

            feature_extractor = AutoFeatureExtractor.from_pretrained(
                self.PINNED_MODEL_ID,
                revision=self.PINNED_REVISION,
                local_files_only=True,
            )
            try:
                model = ModelClass.from_pretrained(
                    self.PINNED_MODEL_ID,
                    revision=self.PINNED_REVISION,
                    local_files_only=True,
                )
            except Exception:
                from transformers import Wav2Vec2ForSequenceClassification
                model = Wav2Vec2ForSequenceClassification.from_pretrained(
                    self.PINNED_MODEL_ID,
                    revision=self.PINNED_REVISION,
                    local_files_only=True,
                )
            if not getattr(model.config, "id2label", None):
                raise RuntimeError("Pinned checkpoint does not define id2label; refusing ambiguous class mapping.")
            if int(getattr(model.config, "num_labels", len(model.config.id2label))) != 2:
                raise RuntimeError("Pinned checkpoint is not a two-class detector.")
            mapping = resolve_label_mapping(model.config.id2label)
            model.to(torch.device("cpu"))
            model.eval()
            detector = VoiceCloneDetector(model_id=self.PINNED_MODEL_ID, device="cpu")
            detector.model = model
            detector.feature_extractor = feature_extractor
            detector.is_loaded = True
            detector.target_sr = 16000
            detector.label_mapping = mapping
            detector.bonafide_idx = mapping["bonafide"]
            detector.spoof_idx = mapping["spoof"]
            self.detector = detector
            self.resolved_class_mapping = dict(mapping)
            extractor_details = feature_extractor.to_dict() if hasattr(feature_extractor, "to_dict") else {}
            self.preprocessing_details = {
                **self.metadata.preprocessing,
                "checkpoint_revision_used_for_extractor_and_model": self.PINNED_REVISION,
                "feature_extractor_config": json.loads(json.dumps(extractor_details, default=str)),
            }
        except Exception as exc:
            self.detector = None
            raise DetectorUnavailableError(f"Current detector could not load from the local cache: {type(exc).__name__}: {exc}") from exc
        elapsed = (time.perf_counter() - started) * 1000
        self.load_duration_ms = elapsed
        actual_revision = getattr(self.detector.model.config, "_commit_hash", None)
        if actual_revision != self.PINNED_REVISION:
            self.detector = None
            raise DetectorUnavailableError(
                f"Cached checkpoint revision {actual_revision!r} does not match required pin {self.PINNED_REVISION!r}."
            )

    def predict(self, waveform: np.ndarray, sample_rate: int) -> DetectorPrediction:
        validate_waveform(waveform, sample_rate, self.metadata.expected_sample_rate)
        if self.detector is None:
            raise DetectorUnavailableError("Current detector has not been loaded.")
        try:
            result = self.detector.predict(waveform, sample_rate=sample_rate)
        except DetectorAdapterError:
            raise
        except Exception as exc:
            raise InferenceFailureError(str(exc)) from exc
        prediction = DetectorPrediction(
            predicted_label="spoof" if result["prediction"] == "AI-generated" else "bonafide",
            native_scores={
                "bonafide": float(result["human_probability"]),
                "spoof": float(result["ai_probability"]),
            },
            score_type="softmax_uncalibrated",
            score_direction="class_indexed",
            inference_ms=float(result["processing_time_ms"]),
        )
        prediction.validate()
        return prediction


class UnavailableDetectorAdapter:
    """Metadata-only registration; does not load, fetch, or emulate a model."""

    metadata: ModelMetadata

    def load(self, *, device: str = "cpu", offline: bool = True, revision: str | None = None) -> None:
        raise DetectorUnavailableError(self.metadata.unavailable_reason or "Checkpoint is unavailable locally.")

    def predict(self, waveform: np.ndarray, sample_rate: int) -> DetectorPrediction:
        raise DetectorUnavailableError(self.metadata.unavailable_reason or "Checkpoint is unavailable locally.")


@REGISTRY.register
class Sara1708UnavailableAdapter(UnavailableDetectorAdapter):
    metadata = ModelMetadata(
        detector_id="sara1708_wav2vec2",
        model_id="Sara1708/deepfake-audio-wav2vec2",
        revision=None,
        task="synthetic/deepfake speech classification",
        architecture="Wav2Vec2-base backbone with mean pooling and 2-class linear head",
        license="Apache-2.0 (model card declaration; verify upstream terms before deployment)",
        documentation_url="https://huggingface.co/Sara1708/deepfake-audio-wav2vec2",
        status="not_evaluated",
        unavailable_reason="No local checkpoint or verified immutable revision is configured; downloads are disabled.",
        expected_sample_rate=16000,
        expected_channels=1,
        expected_window_samples=64000,
        class_mapping=None,
        score_type=None,
        score_direction=None,
        preprocessing={"documented_input": "raw mono waveform, 16 kHz, 4-second windows; adapter implementation not enabled until checkpoint and output mapping are verified"},
        training_data="ASVspoof 2019 LA training partition (model card).",
    )


@REGISTRY.register
class AASISTLUnavailableAdapter(UnavailableDetectorAdapter):
    metadata = ModelMetadata(
        detector_id="aasist_l",
        model_id="clovaai/aasist AASIST-L checkpoint",
        revision=None,
        task="audio anti-spoofing",
        architecture="AASIST-L spectro-temporal graph attention network",
        license="MIT (official source repository; verify checkpoint provenance)",
        documentation_url="https://github.com/clovaai/aasist",
        status="not_evaluated",
        unavailable_reason="The official checkpoint is not present locally and this benchmark is offline; checkpoint hash and runtime output mapping are not pinned.",
        expected_sample_rate=16000,
        expected_channels=1,
        expected_window_samples=64600,
        class_mapping=None,
        score_type=None,
        score_direction=None,
        preprocessing={"documented_input": "official AASIST-L config specifies nb_samp=64600; checkpoint-specific loading and score interpretation are not configured"},
        training_data="ASVspoof 2019 Logical Access (official repository).",
    )


def validate_waveform(waveform: np.ndarray, sample_rate: int, expected_sample_rate: int | None = None) -> None:
    if not isinstance(waveform, np.ndarray):
        raise UnsupportedInputError("waveform must be a numpy array.")
    if waveform.dtype != np.float32:
        raise UnsupportedInputError(f"waveform must use float32; received {waveform.dtype}.")
    if waveform.ndim != 1 or waveform.size == 0:
        raise UnsupportedInputError("waveform must be a non-empty mono 1D array.")
    if not np.isfinite(waveform).all():
        raise UnsupportedInputError("waveform contains NaN or infinite values.")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise UnsupportedInputError("sample_rate must be a positive integer.")
    if expected_sample_rate is not None and sample_rate != expected_sample_rate:
        raise UnsupportedInputError(f"This adapter requires {expected_sample_rate} Hz audio; received {sample_rate} Hz.")


def metadata_as_dict(metadata: ModelMetadata) -> dict[str, object]:
    metadata.validate()
    return asdict(metadata)
