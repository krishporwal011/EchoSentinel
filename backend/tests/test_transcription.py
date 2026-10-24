import pytest
import httpx
from unittest.mock import patch, AsyncMock
from transcription import transcribe_audio_with_openai, TranscriptionResult


@pytest.mark.anyio
async def test_transcribe_empty_audio():
    res = await transcribe_audio_with_openai(b"", api_key="test-key")
    assert res.status == "error"
    assert "empty" in res.message.lower()
    assert res.text is None


@pytest.mark.anyio
async def test_transcribe_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    res = await transcribe_audio_with_openai(b"dummy-audio-bytes", api_key="")
    assert res.status == "unavailable"
    assert "not configured" in res.message.lower()
    assert res.text is None


@pytest.mark.anyio
async def test_transcribe_success_mock():
    mock_response = httpx.Response(
        200,
        json={
            "text": "Please share your 6-digit OTP code to verify your transaction.",
            "language": "english",
            "duration": 4.5,
        },
        request=httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions"),
    )

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: mock_response))
    res = await transcribe_audio_with_openai(
        b"mock-audio-content",
        api_key="valid-mock-key",
        client=client,
    )
    await client.aclose()

    assert res.status == "completed"
    assert "OTP" in res.text
    assert res.language == "english"
    assert res.duration_seconds == 4.5


@pytest.mark.anyio
async def test_transcribe_authentication_error():
    mock_response = httpx.Response(
        401,
        json={"error": {"message": "Invalid API Key"}},
        request=httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions"),
    )

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: mock_response))
    res = await transcribe_audio_with_openai(
        b"mock-audio-content",
        api_key="invalid-key",
        client=client,
    )
    await client.aclose()

    assert res.status == "error"
    assert "authentication failed" in res.message.lower()
    assert res.text is None


@pytest.mark.anyio
async def test_transcribe_rate_limit_error():
    mock_response = httpx.Response(
        429,
        json={"error": {"message": "Rate limit reached"}},
        request=httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions"),
    )

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: mock_response))
    res = await transcribe_audio_with_openai(
        b"mock-audio-content",
        api_key="valid-key",
        client=client,
    )
    await client.aclose()

    assert res.status == "error"
    assert "rate limit" in res.message.lower()
    assert res.text is None


@pytest.mark.anyio
async def test_transcribe_timeout_error():
    def mock_handler(req):
        raise httpx.ReadTimeout("Request timed out", request=req)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    res = await transcribe_audio_with_openai(
        b"mock-audio-content",
        api_key="valid-key",
        client=client,
    )
    await client.aclose()

    assert res.status == "error"
    assert "timed out" in res.message.lower()
    assert res.text is None


# -----------------------------------------------------------------------------
# Local Whisper & Unified Transcription Tests
# -----------------------------------------------------------------------------

import io
import numpy as np
import soundfile as sf
from transcription import LocalWhisperProvider, transcribe_audio
from scam_detector import SessionTranscriptBuffer, analyze_scam_intent, merge_chunk_text


def generate_test_wav(duration: float = 1.0, sr: int = 16000, frequency: float = 440.0) -> bytes:
    buf = io.BytesIO()
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    waveform = 0.3 * np.sin(2 * np.pi * frequency * t)
    sf.write(buf, waveform, sr, format="WAV")
    return buf.getvalue()


def test_local_whisper_empty_audio():
    provider = LocalWhisperProvider()
    res = provider.transcribe(b"")
    assert res.status == "error"
    assert "empty" in res.message.lower()
    assert res.provider == "local"


def test_local_whisper_invalid_audio():
    provider = LocalWhisperProvider()
    provider.is_loaded = True
    res = provider.transcribe(b"CORRUPTED_NON_AUDIO_DATA_BYTES")
    assert res.status == "error"
    assert "failed" in res.message.lower() or "decoding" in res.message.lower()
    assert res.provider == "local"


def test_local_whisper_missing_model():
    provider = LocalWhisperProvider()
    provider.is_loaded = False
    provider.load_error = "Checkpoint not found on disk"
    # Mock load_model returning False
    provider.load_model = lambda *args, **kwargs: False
    res = provider.transcribe(generate_test_wav())
    assert res.status == "unavailable"
    assert "not loaded" in res.message.lower()


def test_local_whisper_valid_audio_mocked():
    provider = LocalWhisperProvider()
    provider.is_loaded = True
    provider.pipeline = lambda audio_dict, **kwargs: {"text": "Please tell me your OTP to confirm your KYC."}
    res = provider.transcribe(generate_test_wav(duration=1.5))
    assert res.status == "completed"
    assert "OTP" in res.text
    assert res.provider == "local"
    assert res.duration_seconds is not None


def test_local_whisper_transcription_failure():
    provider = LocalWhisperProvider()
    provider.is_loaded = True

    def failing_pipeline(*args, **kwargs):
        raise RuntimeError("GPU execution out of memory")

    provider.pipeline = failing_pipeline
    res = provider.transcribe(generate_test_wav(duration=1.5))
    assert res.status == "error"
    assert "error" in res.message.lower()


@pytest.mark.anyio
async def test_unified_transcribe_audio_dispatcher():
    # Test local provider dispatch with mock
    provider = LocalWhisperProvider.get_instance()
    original_transcribe = provider.transcribe
    try:
        provider.transcribe = lambda audio, filename: TranscriptionResult(
            status="completed",
            text="Your account will be blocked today.",
            duration_seconds=2.5,
            provider="local",
        )
        res = await transcribe_audio(generate_test_wav(), provider="local")
        assert res.status == "completed"
        assert "blocked" in res.text
        assert res.provider == "local"
    finally:
        provider.transcribe = original_transcribe


def test_chunk_ordering_and_duplicate_prevention():
    buffer = SessionTranscriptBuffer(session_id="test_stream_01")
    # Chunk 1
    t1 = buffer.add_chunk(sequence_id=1, text="Please tell me the")
    assert t1 == "Please tell me the"

    # Chunk 2 overlaps with "tell me the OTP right now"
    t2 = buffer.add_chunk(sequence_id=2, text="tell me the OTP right now.")
    assert t2 == "Please tell me the OTP right now."

    # Chunk 3
    t3 = buffer.add_chunk(sequence_id=3, text="right now or your account will be suspended.")
    assert t3 == "Please tell me the OTP right now. or your account will be suspended."


def test_chunk_boundary_word_handling():
    # Boundary words that overlap should be deduplicated
    merged = merge_chunk_text("Your KYC has expired update", "update it immediately or face suspension")
    assert merged == "Your KYC has expired update it immediately or face suspension"


def test_scam_detection_from_recognized_text():
    # Recognized text passed to scam detector
    recognized_text = "Apne mobile par aaya hua OTP bataiye."
    scam_result = analyze_scam_intent(recognized_text)
    assert scam_result.status == "ANALYZED"
    assert scam_result.scam_risk_level in {"HIGH", "CRITICAL"}
    assert "SENSITIVE_INFORMATION_REQUEST" in scam_result.categories
    assert len(scam_result.indicators) >= 1


def test_transcription_unavailable_never_classified_as_safe():
    # When transcription is unavailable, scam detector must preserve UNAVAILABLE / UNKNOWN
    scam_result = analyze_scam_intent("")
    assert scam_result.status == "UNAVAILABLE"
    assert scam_result.scam_risk_level == "UNKNOWN"
    assert scam_result.scam_risk_score is None


def test_negation_and_security_warnings_not_flagged():
    safe_text = "Our support team will never ask for your password or UPI PIN."
    res = analyze_scam_intent(safe_text)
    assert res.status == "ANALYZED"
    assert res.scam_risk_level == "LOW"
    assert "SENSITIVE_INFORMATION_REQUEST" not in res.categories

