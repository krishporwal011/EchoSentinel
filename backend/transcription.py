import io
import logging
import os
import re
from typing import Any, Dict, Literal, Optional

import httpx
import numpy as np
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from audio_processor import (
    MAX_FILE_SIZE_BYTES,
    SILENCE_RMS_THRESHOLD,
    TARGET_SAMPLE_RATE,
    decode_and_preprocess_audio,
)

logger = logging.getLogger("echosentinel.transcription")

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB
DEFAULT_OPENAI_MODEL = "whisper-1"
DEFAULT_LOCAL_MODEL = "openai/whisper-tiny"

# Contextual vocabulary hints for banking, OTP, UPI, and security context
CONTEXT_PROMPT = (
    "English and Hindi-English code-switching. "
    "Terminology: OTP, one-time password, UPI PIN, Google Pay, PhonePe, Paytm, "
    "banking PIN, CVV, debit card, credit card, net banking, password, KYC, "
    "account blocked, AnyDesk, TeamViewer, QuickSupport, verification code."
)


class TranscriptionResult(BaseModel):
    status: Literal["completed", "unavailable", "error", "skipped"]
    text: Optional[str] = None
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    message: Optional[str] = None
    provider: Optional[str] = None


# -----------------------------------------------------------------------------
# Local Whisper Speech-to-Text Provider (Mac M1 Metal MPS / CPU)
# -----------------------------------------------------------------------------

class LocalWhisperProvider:
    """
    Configurable local Whisper Speech-to-Text provider using Hugging Face Transformers.
    Runs locally on Apple Silicon (MPS) or CPU without requiring external API keys.
    Preloaded/cached locally so model is not redownloaded on every start.
    """

    _instance: Optional["LocalWhisperProvider"] = None

    def __init__(self):
        self.model_id: str = os.getenv("LOCAL_WHISPER_MODEL", DEFAULT_LOCAL_MODEL)
        self.device: str = self._resolve_device()
        self.is_loaded: bool = False
        self.load_error: Optional[str] = None
        self.pipeline: Any = None

    @classmethod
    def get_instance(cls) -> "LocalWhisperProvider":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _resolve_device() -> str:
        pref = os.getenv("LOCAL_WHISPER_DEVICE", "auto").lower()
        if pref in {"cpu", "mps", "cuda"}:
            return pref
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def load_model(self, model_id: Optional[str] = None) -> bool:
        """
        Loads the local Whisper ASR pipeline into memory.
        Uses cached weights without re-downloading if already present.
        """
        if model_id:
            self.model_id = model_id

        self.device = self._resolve_device()
        self.load_error = None

        try:
            from transformers import pipeline

            logger.info("Initializing Local Whisper ASR pipeline with %s on %s...", self.model_id, self.device)
            self.pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_id,
                device=self.device,
            )
            self.is_loaded = True
            logger.info("Local Whisper ASR pipeline ready on %s.", self.device)
            return True
        except Exception as exc:
            self.is_loaded = False
            self.load_error = str(exc)
            logger.warning("Local Whisper model load failed on %s: %s. Trying CPU fallback...", self.device, exc)
            if self.device != "cpu":
                try:
                    from transformers import pipeline
                    self.device = "cpu"
                    self.pipeline = pipeline(
                        "automatic-speech-recognition",
                        model=self.model_id,
                        device="cpu",
                    )
                    self.is_loaded = True
                    self.load_error = None
                    logger.info("Local Whisper ASR pipeline ready on CPU fallback.")
                    return True
                except Exception as cpu_exc:
                    self.is_loaded = False
                    self.load_error = str(cpu_exc)
                    logger.error("Local Whisper failed completely: %s", cpu_exc)
            return False

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
    ) -> TranscriptionResult:
        """
        Synchronously transcribes audio bytes using the local Whisper model.
        Decodes using soundfile/librosa, checks for silence, and generates transcript.
        """
        if not audio_bytes or len(audio_bytes) == 0:
            return TranscriptionResult(
                status="error",
                text=None,
                message="Audio content is empty.",
                provider="local",
            )

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            return TranscriptionResult(
                status="error",
                text=None,
                message=f"Audio file size ({len(audio_bytes)} bytes) exceeds the 25 MB limit.",
                provider="local",
            )

        if not self.is_loaded:
            success = self.load_model()
            if not success:
                return TranscriptionResult(
                    status="unavailable",
                    text=None,
                    message=f"Local Whisper model is not loaded: {self.load_error or 'Unknown initialization error'}",
                    provider="local",
                )

        try:
            waveform, details = decode_and_preprocess_audio(audio_bytes, return_details=True)
        except ValueError as val_err:
            return TranscriptionResult(
                status="error",
                text=None,
                message=str(val_err),
                provider="local",
            )
        except Exception as exc:
            return TranscriptionResult(
                status="error",
                text=None,
                message=f"Audio decoding failed: {exc}",
                provider="local",
            )

        # Silence check: if audio energy is negligible, do not invoke pipeline (prevents silence hallucinations)
        rms = float(np.sqrt(np.mean(waveform ** 2))) if len(waveform) > 0 else 0.0
        if rms < SILENCE_RMS_THRESHOLD:
            return TranscriptionResult(
                status="completed",
                text="",
                duration_seconds=round(details.get("duration_seconds", 0.0), 2),
                message="No audible speech recognized in silence segment.",
                provider="local",
            )

        try:
            # Pass decoded float32 16kHz audio dictionary directly to transformers pipeline
            audio_input = {
                "raw": waveform.astype(np.float32),
                "sampling_rate": TARGET_SAMPLE_RATE,
            }
            res = self.pipeline(
                audio_input,
                generate_kwargs={"task": "transcribe"},
            )
            raw_text = (res.get("text") or "").strip()

            # Filter out single-token silence artifacts like "you" or "[BLANK_AUDIO]" on very low volume
            if rms < SILENCE_RMS_THRESHOLD * 2 and raw_text.lower() in {"you", "you.", "[blank_audio]"}:
                raw_text = ""

            from scam_detector import clean_repetitions
            raw_text = clean_repetitions(raw_text)

            return TranscriptionResult(
                status="completed",
                text=raw_text,
                duration_seconds=round(details.get("duration_seconds", 0.0), 2),
                message="Audio successfully transcribed." if raw_text else "No audible speech recognized.",
                provider="local",
            )
        except Exception as exc:
            logger.error("Local Whisper inference error: %s", exc)
            return TranscriptionResult(
                status="error",
                text=None,
                message=f"Local transcription error: {str(exc)}",
                provider="local",
            )


# -----------------------------------------------------------------------------
# OpenAI Audio Speech-to-Text Provider (Remote Cloud API)
# -----------------------------------------------------------------------------

async def transcribe_audio_with_openai(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    content_type: str = "audio/wav",
    api_key: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> TranscriptionResult:
    """
    Transcribe audio bytes using OpenAI's official Audio Speech-to-Text API.
    Handles empty audio, silence, timeouts, auth errors, and missing credentials.
    """
    if not audio_bytes or len(audio_bytes) == 0:
        return TranscriptionResult(
            status="error",
            text=None,
            message="Audio content is empty.",
            provider="openai",
        )

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return TranscriptionResult(
            status="error",
            text=None,
            message=f"Audio file size ({len(audio_bytes)} bytes) exceeds the 25 MB transcription limit.",
            provider="openai",
        )

    effective_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    if not effective_key:
        return TranscriptionResult(
            status="unavailable",
            text=None,
            message="OpenAI API key is not configured. Set OPENAI_API_KEY in backend/.env to enable transcription.",
            provider="openai",
        )

    # In automated tests without an explicit mock client, do not consume API credits
    if client is None and "PYTEST_CURRENT_TEST" in os.environ and not os.getenv("ALLOW_LIVE_OPENAI_TESTS"):
        return TranscriptionResult(
            status="unavailable",
            text=None,
            message="Transcription skipped in test runner to prevent API credit consumption.",
            provider="openai",
        )

    base_name, ext = os.path.splitext(filename)
    if not ext:
        ext = ".wav"
        filename = f"{base_name}{ext}"

    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/m4a",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
    }
    effective_mime = mime_map.get(ext.lower(), content_type or "audio/wav")
    model_name = os.getenv("OPENAI_TRANSCRIBE_MODEL", DEFAULT_OPENAI_MODEL)

    headers = {
        "Authorization": f"Bearer {effective_key}",
    }

    files = {
        "file": (filename, audio_bytes, effective_mime),
    }
    data = {
        "model": model_name,
        "prompt": CONTEXT_PROMPT,
        "response_format": "verbose_json",
    }

    own_client = client is None
    http_client = client or httpx.AsyncClient(timeout=25.0)

    try:
        resp = await http_client.post(
            OPENAI_TRANSCRIPTION_URL,
            headers=headers,
            files=files,
            data=data,
        )

        if resp.status_code == 200:
            payload = resp.json()
            raw_text = payload.get("text", "").strip()
            from scam_detector import clean_repetitions
            raw_text = clean_repetitions(raw_text)
            language = payload.get("language")
            duration = payload.get("duration")

            return TranscriptionResult(
                status="completed",
                text=raw_text,
                language=language,
                duration_seconds=round(float(duration), 2) if duration is not None else None,
                message="Audio successfully transcribed." if raw_text else "No audible speech recognized.",
                provider="openai",
            )

        if resp.status_code == 401:
            return TranscriptionResult(
                status="error",
                text=None,
                message="OpenAI authentication failed. Please verify your OPENAI_API_KEY in backend/.env.",
                provider="openai",
            )

        if resp.status_code == 429:
            return TranscriptionResult(
                status="error",
                text=None,
                message="OpenAI API rate limit or quota exceeded. Please wait or check your account limits.",
                provider="openai",
            )

        err_msg = f"OpenAI transcription failed with HTTP {resp.status_code}."
        try:
            err_json = resp.json()
            if "error" in err_json and "message" in err_json["error"]:
                err_msg = err_json["error"]["message"]
        except Exception:
            pass

        return TranscriptionResult(
            status="error",
            text=None,
            message=err_msg,
            provider="openai",
        )

    except httpx.TimeoutException:
        return TranscriptionResult(
            status="error",
            text=None,
            message="Connection to OpenAI transcription API timed out. Please try again.",
            provider="openai",
        )
    except httpx.RequestError as exc:
        return TranscriptionResult(
            status="error",
            text=None,
            message=f"Network error contacting OpenAI API: {exc.__class__.__name__}",
            provider="openai",
        )
    except Exception as exc:
        logger.error("Unexpected error in OpenAI transcription: %s", exc)
        return TranscriptionResult(
            status="error",
            text=None,
            message=f"Transcription error: {str(exc)}",
            provider="openai",
        )
    finally:
        if own_client:
            await http_client.aclose()


# -----------------------------------------------------------------------------
# Unified Transcription Dispatcher
# -----------------------------------------------------------------------------

async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    content_type: str = "audio/wav",
    provider: Optional[str] = None,
) -> TranscriptionResult:
    """
    Unified entry point for transcribing audio.
    Supports provider selection: 'local' (offline Whisper), 'openai' (cloud Whisper API), or 'auto'.
    - 'local': Uses LocalWhisperProvider (zero API cost, Mac M1 MPS / CPU accelerated).
    - 'openai': Uses official OpenAI Audio API.
    - 'auto': Attempts local Whisper first. If unavailable, falls back to OpenAI if key exists.
    """
    effective_provider = (provider or os.getenv("TRANSCRIPTION_PROVIDER", "auto")).strip().lower()

    if effective_provider == "openai":
        return await transcribe_audio_with_openai(
            audio_bytes,
            filename=filename,
            content_type=content_type,
        )

    if effective_provider == "local":
        local_inst = LocalWhisperProvider.get_instance()
        return await run_in_threadpool(local_inst.transcribe, audio_bytes, filename)

    # In automated generic tests without explicit provider, default to unavailable to avoid test slowdown
    if "PYTEST_CURRENT_TEST" in os.environ and not os.getenv("ALLOW_LIVE_WHISPER_TESTS"):
        return TranscriptionResult(
            status="unavailable",
            text=None,
            message="Transcription skipped in test runner to preserve speed.",
            provider="auto",
        )

    # 'auto' mode: try local Whisper first; if not loadable, fallback to OpenAI
    local_inst = LocalWhisperProvider.get_instance()
    if local_inst.is_loaded or local_inst.load_error is None:
        try:
            result = await run_in_threadpool(local_inst.transcribe, audio_bytes, filename)
            if result.status in {"completed", "error"}:
                return result
        except Exception as exc:
            logger.warning("Local Whisper auto-transcription attempt failed: %s", exc)

    # Fallback to OpenAI if configured
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        return await transcribe_audio_with_openai(
            audio_bytes,
            filename=filename,
            content_type=content_type,
        )

    # If neither is available, return informative unavailable status
    return TranscriptionResult(
        status="unavailable",
        text=None,
        message=(
            "No transcription provider available. "
            "To use local transcription, install or cache the local Whisper model. "
            "Alternatively, configure OPENAI_API_KEY in backend/.env."
        ),
        provider="none",
    )
