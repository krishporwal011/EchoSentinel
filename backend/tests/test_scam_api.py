import io
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from main import app
from model import VoiceCloneDetector
from transcription import TranscriptionResult

client = TestClient(app)


class StubModel:
    config = type("Config", (), {"_commit_hash": "test-revision"})


class StubDetector:
    is_loaded = True
    model_id = "test/anti-spoof"
    model = StubModel()
    label_mapping = {"bonafide": 0, "spoof": 1}
    ai_probability = 0.12
    human_probability = 0.88
    risk_level = "Low"

    def predict(self, waveform, sample_rate=16000):
        return {
            "ai_probability": self.ai_probability,
            "human_probability": self.human_probability,
            "risk_level": self.risk_level,
            "model_revision": "test-revision",
        }


def make_wav(duration=1.0, sr=16000):
    buf = io.BytesIO()
    data = (0.2 * np.sin(2 * np.pi * 220 * np.arange(int(sr * duration)) / sr)).astype(np.float32)
    sf.write(buf, data, sr, format="WAV")
    return buf.getvalue()


def test_analyze_scam_endpoint():
    # Direct test of POST /api/analyze-scam
    res = client.post("/api/analyze-scam", json={"transcript": "Please tell me your OTP to confirm your identity."})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ANALYZED"
    assert data["scam_risk_level"] in {"HIGH", "CRITICAL"}
    assert "SENSITIVE_INFORMATION_REQUEST" in data["categories"]
    assert len(data["indicators"]) >= 1


def test_analyze_scam_endpoint_security_warning():
    res = client.post("/api/analyze-scam", json={"transcript": "Never share your UPI PIN with anyone over the phone."})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ANALYZED"
    assert data["scam_risk_level"] == "LOW"
    assert "SENSITIVE_INFORMATION_REQUEST" not in data["categories"]


def test_voice_detection_with_scam_unavailable(monkeypatch):
    monkeypatch.setattr(VoiceCloneDetector, "get_instance", lambda: StubDetector())
    # Audio upload succeeds and produces voice classification even if transcription is unavailable
    response = client.post("/detect", files={"file": ("human_test.wav", make_wav(), "audio/wav")})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["prediction"]["label"] == "likely_human_recorded"
    assert "transcription" in data
    assert "scam_analysis" in data
    assert data["scam_analysis"]["status"] == "UNAVAILABLE"


def test_independent_voice_and_scam_risk(monkeypatch):
    """
    Scenario: Voice is likely human (authentic acoustic model result),
    but speech-to-text transcript contains high-risk OTP request.
    Voice and scam results must remain completely independent!
    """
    monkeypatch.setattr(VoiceCloneDetector, "get_instance", lambda: StubDetector())

    async def mock_transcribe(*args, **kwargs):
        return TranscriptionResult(
            status="completed",
            text="Please give me your OTP right now or your bank account will be blocked.",
            language="english",
            duration_seconds=3.2,
        )

    monkeypatch.setattr("main.transcribe_audio_with_openai", mock_transcribe)

    response = client.post("/detect", files={"file": ("human_sample.wav", make_wav(), "audio/wav")})
    assert response.status_code == 200
    data = response.json()

    # Voice analysis: likely authentic (human)
    assert data["prediction"]["label"] == "likely_human_recorded"
    assert data["prediction"]["risk_level"] == "low"

    # Scam analysis: high/critical risk due to OTP request + threat
    assert data["scam_analysis"]["status"] == "ANALYZED"
    assert data["scam_analysis"]["scam_risk_level"] == "CRITICAL"
    assert "SENSITIVE_INFORMATION_REQUEST" in data["scam_analysis"]["categories"]
    assert "URGENCY_AND_THREATS" in data["scam_analysis"]["categories"]
    assert data["scam_analysis"]["warning_banner"] is not None
