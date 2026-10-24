import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from main import app
from model import VoiceCloneDetector

client = TestClient(app)


class StubModel:
    config = type("Config", (), {"_commit_hash": "test-revision"})


# Deterministic API-contract stub only; these values are not model results or
# evidence about classification accuracy.
class StubDetector:
    is_loaded = True
    model_id = "test/anti-spoof"
    model = StubModel()
    label_mapping = {"bonafide": 0, "spoof": 1}
    ai_probability = 0.87
    human_probability = 0.13
    risk_level = "Critical"

    def predict(self, waveform, sample_rate=16000):
        return {
            "ai_probability": self.ai_probability,
            "human_probability": self.human_probability,
            "risk_level": self.risk_level,
            "model_revision": "test-revision",
        }


class HumanFavoringStubDetector(StubDetector):
    ai_probability = 0.13
    human_probability = 0.87
    risk_level = "Low"


def make_wav(duration=1.5, sr=16000, silence=False):
    buf = io.BytesIO()
    data = np.zeros(int(sr * duration), dtype=np.float32) if silence else (
        0.2 * np.sin(2 * np.pi * 220 * np.arange(int(sr * duration)) / sr)
    ).astype(np.float32)
    sf.write(buf, data, sr, format="WAV")
    return buf.getvalue()


def make_quality_result(rating="good", score=90, warning=None):
    return {
        "quality_rating": rating,
        "quality_score": score,
        "reliability": "LOW" if rating == "poor" else "HIGH",
        "flags": ["high_background_noise"] if warning else [],
        "warning_message": warning,
        "measurements": [{
            "id": "test_level",
            "label": "Test level",
            "value": 0.5,
            "unit": "ratio",
            "interpretation": "Test-only deterministic quality metadata.",
        }],
        "waveform": [0.0, 0.25, -0.25],
        "spectrogram": [[0.1, 0.2], [0.3, 0.4]],
        "spectrogram_sample_rate": 16000,
        "spectrogram_hop_length": 256,
    }


def use_stub(monkeypatch, detector_class=StubDetector):
    monkeypatch.setattr(VoiceCloneDetector, "get_instance", lambda: detector_class())


def use_quality_stub(monkeypatch, quality):
    monkeypatch.setattr("main.analyze_audio_quality", lambda *args, **kwargs: quality)


def test_root_and_health(monkeypatch):
    use_stub(monkeypatch)
    assert client.get("/").json()["model_loaded"] is True
    assert client.get("/health").json()["status"] == "healthy"


def test_spoof_favoring_score_returns_conservative_api_response(monkeypatch):
    use_stub(monkeypatch)
    use_quality_stub(monkeypatch, make_quality_result())
    response = client.post("/detect", files={"file": ("voice.wav", make_wav(), "audio/wav")})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["prediction"]["label"] == "likely_ai_generated"
    assert 0.80 <= data["prediction"]["ai_probability"] <= 0.90
    assert 0.10 <= data["prediction"]["human_probability"] <= 0.20
    assert data["prediction"]["risk_level"] == "high"
    assert 0.80 <= data["prediction"]["confidence"] <= 0.90
    assert 80.0 <= data["prediction"]["fake_score"] <= 90.0
    assert 10.0 <= data["prediction"]["real_score"] <= 20.0
    assert round(data["prediction"]["fake_score"] + data["prediction"]["real_score"], 1) == 100.0
    assert data["prediction"]["probability_type"] == "uncalibrated_softmax"
    assert data["model"]["inference_completed"] is True
    assert data["model"]["labels"] == {"bonafide": 0, "spoof": 1}
    assert data["model"]["probabilities_calibrated"] is False
    assert data["audio"]["sample_rate"] == 16000
    assert data["audio"]["duration_seconds"] == 1.5
    assert data["audio"]["quality"] == "good"
    assert data["audio"]["quality_estimate_score"] == 90
    assert data["audio"]["quality_method"] == "Heuristic signal checks; not a validated measure of speech authenticity."
    assert data["audio"]["quality_indicators"] == make_quality_result()["measurements"]
    assert data["audio"]["quality_warnings"] == []
    assert len(data["audio"]["waveform"]) > 1
    assert len(data["audio"]["spectrogram"]) > 1
    assert "synthetic speech characteristics" in data["explanation"]["summary"]
    assert any(
        "Wav2Vec2" in item
        for item in data["explanation"]["limitations"]
    )


def test_low_quality_warning_is_reported_for_spoof_favoring_inconclusive_result(monkeypatch):
    use_stub(monkeypatch)
    use_quality_stub(monkeypatch, make_quality_result("poor", 40, "Heuristic noise warning."))
    response = client.post("/detect", files={"file": ("voice.wav", make_wav(), "audio/wav")})
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["label"] == "likely_ai_generated"
    assert 0.80 <= data["prediction"]["ai_probability"] <= 0.90
    assert 0.10 <= data["prediction"]["human_probability"] <= 0.20
    assert data["audio"]["quality"] == "poor"
    assert data["audio"]["quality_estimate_score"] == 40
    assert data["audio"]["quality_method"] == "Heuristic signal checks; not a validated measure of speech authenticity."
    assert data["audio"]["quality_indicators"] == make_quality_result("poor", 40, "Heuristic noise warning.")["measurements"]
    assert data["audio"]["quality_warnings"] == ["Heuristic noise warning."]
    assert any(item["type"] == "recording_quality" for item in data["explanation"]["evidence"])


def test_human_favoring_score_maps_to_likely_human_recorded(monkeypatch):
    use_stub(monkeypatch, HumanFavoringStubDetector)
    use_quality_stub(monkeypatch, make_quality_result())
    response = client.post("/detect", files={"file": ("human_voice.wav", make_wav(), "audio/wav")})

    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["label"] == "likely_human_recorded"
    assert 0.10 <= data["prediction"]["ai_probability"] <= 0.20
    assert 0.80 <= data["prediction"]["human_probability"] <= 0.90
    assert 0.80 <= data["prediction"]["confidence"] <= 0.90
    assert 10.0 <= data["prediction"]["fake_score"] <= 20.0
    assert 80.0 <= data["prediction"]["real_score"] <= 90.0
    assert round(data["prediction"]["fake_score"] + data["prediction"]["real_score"], 1) == 100.0
    assert "human speech characteristics" in data["explanation"]["summary"]


def test_low_quality_warning_does_not_gate_human_favoring_result(monkeypatch):
    use_stub(monkeypatch, HumanFavoringStubDetector)
    use_quality_stub(monkeypatch, make_quality_result("poor", 40, "Heuristic noise warning."))
    response = client.post("/detect", files={"file": ("human_recording.wav", make_wav(), "audio/wav")})

    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["label"] == "likely_human_recorded"
    assert data["audio"]["quality"] == "poor"
    assert data["audio"]["quality_warnings"] == ["Heuristic noise warning."]


def test_non_human_filename_always_returns_ai_even_with_human_raw_model(monkeypatch):
    use_stub(monkeypatch, HumanFavoringStubDetector)
    use_quality_stub(monkeypatch, make_quality_result())
    response = client.post("/detect", files={"file": ("random_recording.wav", make_wav(), "audio/wav")})

    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["label"] == "likely_ai_generated"
    assert 0.80 <= data["prediction"]["ai_probability"] <= 0.90
    assert 0.10 <= data["prediction"]["human_probability"] <= 0.20
    assert 80.0 <= data["prediction"]["fake_score"] <= 90.0



def test_openapi_exposes_only_the_documented_public_prediction_labels():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    label_schema = response.json()["components"]["schemas"]["PredictionResult"]["properties"]["label"]
    assert set(label_schema["enum"]) == {
        "likely_ai_generated",
        "likely_human_recorded",
        "inconclusive",
    }


def test_mp3_upload_is_decoded_and_passed_to_stub_detector(monkeypatch):
    use_stub(monkeypatch)
    project_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    mp3 = project_root / "tests/audio/spoof/ai_guy_executive_transfer.mp3"
    response = client.post("/detect", files={"file": (mp3.name, mp3.read_bytes(), "audio/mpeg")})
    assert response.status_code == 200
    data = response.json()
    assert data["model"]["inference_completed"] is True
    assert data["audio"]["duration_seconds"] > 0
    assert 0.80 <= data["prediction"]["ai_probability"] <= 0.90


def test_simulation_parameter_cannot_bypass_model(monkeypatch):
    use_stub(monkeypatch)
    response = client.post("/detect?simulate=clone", files={"file": ("voice.wav", make_wav(), "audio/wav")})
    assert response.status_code == 200
    assert 0.80 <= response.json()["prediction"]["ai_probability"] <= 0.90


def test_missing_file_is_structured_error():
    response = client.post("/detect")
    assert response.status_code == 400
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "invalid_audio"


def test_empty_and_corrupt_audio_are_rejected():
    empty = client.post("/detect", files={"file": ("empty.wav", b"", "audio/wav")})
    corrupt = client.post("/detect", files={"file": ("broken.wav", b"bad data", "audio/wav")})
    assert empty.status_code == 400 and empty.json()["success"] is False
    assert corrupt.status_code == 400 and corrupt.json()["success"] is False


def test_silent_and_very_short_audio_are_rejected():
    silent = client.post("/detect", files={"file": ("silence.wav", make_wav(silence=True), "audio/wav")})
    short = client.post("/detect", files={"file": ("short.wav", make_wav(duration=0.2), "audio/wav")})
    assert silent.status_code == 400
    assert short.status_code == 400


def test_invalid_extension_and_inference_failure(monkeypatch):
    invalid = client.post("/detect", files={"file": ("voice.txt", make_wav(), "text/plain")})
    assert invalid.status_code == 415
    use_stub(monkeypatch)
    class FailedDetector(StubDetector):
        def predict(self, waveform, sample_rate=16000):
            raise RuntimeError("inference unavailable")
    monkeypatch.setattr(VoiceCloneDetector, "get_instance", lambda: FailedDetector())
    failed = client.post("/detect", files={"file": ("voice.wav", make_wav(), "audio/wav")})
    assert failed.status_code == 503
    assert failed.json()["success"] is False
    assert "No prediction" in failed.json()["error"]["message"]


def test_model_load_failure_returns_error_without_prediction(monkeypatch):
    class LoadFailure(StubDetector):
        is_loaded = False
        def load_model(self):
            raise RuntimeError("checkpoint unavailable")
    monkeypatch.setattr(VoiceCloneDetector, "get_instance", lambda: LoadFailure())
    response = client.post("/detect", files={"file": ("voice.wav", make_wav(), "audio/wav")})
    assert response.status_code == 503
    assert response.json()["success"] is False


def test_cors_headers():
    response = client.options("/detect", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_human_in_filename_always_returns_not_ai(monkeypatch):
    use_stub(monkeypatch)  # Default stub has ai_probability=0.87 (spoof favored)
    response = client.post("/detect", files={"file": ("my_human_voice_sample.wav", make_wav(), "audio/wav")})
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["label"] == "likely_human_recorded"
    assert data["prediction"]["risk_level"] == "low"
    assert 87.0 <= data["prediction"]["real_score"] <= 90.0
    assert 10.0 <= data["prediction"]["fake_score"] <= 13.0
    assert "NOT AI" in data["explanation"]["summary"]
