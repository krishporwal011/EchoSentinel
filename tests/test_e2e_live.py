"""Opt-in checks against the local running EchoSentinel API (never an external host)."""

import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests


API_BASE_URL = os.getenv("ECHOSENTINEL_API_BASE_URL", "http://127.0.0.1:8037").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _assert_loopback_url(url: str) -> None:
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not hostname:
        pytest.fail("ECHOSENTINEL_API_BASE_URL must be a valid local HTTP(S) URL.")
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname.lower() == "localhost"
    if not is_loopback:
        pytest.fail("Live E2E tests are restricted to localhost/loopback; no external service is contacted.")


@pytest.fixture(scope="module", autouse=True)
def local_api_ready():
    _assert_loopback_url(API_BASE_URL)
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
    except requests.RequestException as exc:
        pytest.skip(f"Local EchoSentinel API unavailable at {API_BASE_URL}: {exc}")
    if response.status_code == 503:
        pytest.skip(f"Local EchoSentinel API is reachable at {API_BASE_URL}, but its model is unavailable.")
    assert response.status_code == 200, f"Health endpoint returned HTTP {response.status_code}: {response.text}"
    health = response.json()
    assert health.get("model_loaded") is True, f"API health did not confirm a loaded model: {health}"


def test_live_audio_upload_uses_current_nested_response_contract():
    audio_path = PROJECT_ROOT / "tests" / "audio" / "genuine" / "human_female_heather.wav"
    assert audio_path.is_file(), f"Required local audio fixture is missing: {audio_path}"

    with audio_path.open("rb") as audio_file:
        response = requests.post(
            f"{API_BASE_URL}/detect",
            files={"file": (audio_path.name, audio_file, "audio/wav")},
            timeout=90,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["processing_status"] == "completed"
    assert data["model"]["inference_completed"] is True
    assert data["prediction"]["label"] in {
        "likely_ai_generated",
        "likely_human_recorded",
        "inconclusive",
    }
    assert data["prediction"]["probability_type"] == "uncalibrated_softmax"
    ai_score = data["prediction"]["ai_probability"]
    human_score = data["prediction"]["human_probability"]
    assert 0 <= ai_score <= 1
    assert 0 <= human_score <= 1
    assert ai_score + human_score == pytest.approx(1.0, abs=1e-4)
    assert data["audio"]["duration_seconds"] > 0
    assert data["audio"]["sample_rate"] == 16000


def test_live_api_returns_structured_error_for_unsupported_file_type():
    response = requests.post(
        f"{API_BASE_URL}/detect",
        files={"file": ("not-audio.txt", b"not audio", "text/plain")},
        timeout=15,
    )
    assert response.status_code == 415
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "unsupported_media_type"
    assert data["error"]["message"]


def test_live_api_returns_structured_error_for_corrupt_audio():
    response = requests.post(
        f"{API_BASE_URL}/detect",
        files={"file": ("corrupt.wav", b"not a valid wav file", "audio/wav")},
        timeout=30,
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "invalid_audio"
    assert "decod" in data["error"]["message"].lower()
