import io
import logging
import numpy as np
import soundfile as sf
import librosa

logger = logging.getLogger("echosentinel.audio_processor")

TARGET_SAMPLE_RATE = 16000
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MIN_DURATION_SECONDS = 0.5               # Minimum 0.5s for meaningful speech
MAX_DURATION_SECONDS = 60.0              # Maximum 60s per chunk / upload
SILENCE_RMS_THRESHOLD = 0.005           # Minimum RMS energy
SILENCE_PEAK_THRESHOLD = 0.01           # Minimum peak amplitude

def decode_and_preprocess_audio(
    audio_bytes: bytes,
    target_sr: int = TARGET_SAMPLE_RATE,
    min_duration: float = MIN_DURATION_SECONDS,
    max_duration: float = MAX_DURATION_SECONDS,
    return_meta: bool = False,
):
    """
    Decodes audio bytes (WAV, FLAC, OGG, MP3, etc.), converts to mono,
    resamples to target_sr (16kHz), validates against silence/corruption/size/duration,
    and normalizes amplitude.

    Returns a 1D float32 numpy array, or (waveform, orig_sr) if return_meta=True.
    Raises ValueError with descriptive user-facing message on invalid input.
    """
    if not audio_bytes or len(audio_bytes) == 0:
        raise ValueError("Audio file is empty.")

    if len(audio_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Audio file size exceeds maximum limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.")

    if len(audio_bytes) < 44:
        raise ValueError("Audio chunk is too small to contain valid audio data.")

    audio_buffer = io.BytesIO(audio_bytes)
    waveform = None
    sr = None

    # Step 1: Try decoding with soundfile (fastest for WAV/FLAC/OGG)
    try:
        audio_buffer.seek(0)
        data, file_sr = sf.read(audio_buffer, dtype="float32")
        waveform = data
        sr = file_sr
    except Exception as sf_err:
        logger.debug(f"Soundfile decode failed: {sf_err}. Trying librosa fallback...")

    # Step 2: Try librosa fallback if soundfile failed (handles MP3, AAC, etc.)
    if waveform is None:
        try:
            audio_buffer.seek(0)
            data, file_sr = librosa.load(audio_buffer, sr=target_sr, mono=True)
            waveform = data
            sr = target_sr
        except Exception as librosa_err:
            logger.warning(f"Audio decoding failed on both engines: {librosa_err}")
            raise ValueError("Audio decoding failed. Please upload a standard WAV, FLAC, MP3, or OGG format.")

    if waveform is None or len(waveform) == 0:
        raise ValueError("Audio file contains no readable audio samples.")

    # Step 3: Ensure mono downmix
    if waveform.ndim > 1:
        waveform = np.mean(waveform, axis=-1 if waveform.shape[-1] < waveform.shape[0] else 0)

    waveform = waveform.astype(np.float32)

    # Step 4: Validate numerical integrity (no NaN or Inf)
    if not np.all(np.isfinite(waveform)):
        raise ValueError("Audio waveform contains invalid numerical values (NaN or Inf).")

    orig_sr = sr or target_sr

    # Step 5: Resample if sample rate does not match target
    if sr is not None and sr != target_sr:
        try:
            waveform = librosa.resample(waveform, orig_sr=sr, target_sr=target_sr)
        except Exception as resample_err:
            logger.warning(f"Librosa resampling failed ({resample_err}); applying linear interpolation.")
            old_indices = np.linspace(0, len(waveform) - 1, len(waveform))
            new_len = int(len(waveform) * (target_sr / sr))
            new_indices = np.linspace(0, len(waveform) - 1, new_len)
            waveform = np.interp(new_indices, old_indices, waveform).astype(np.float32)

    # Step 6: Duration validation
    duration = len(waveform) / target_sr
    if duration < min_duration:
        raise ValueError(
            f"Audio duration ({duration:.2f}s) is too short for analysis. Minimum duration is {min_duration}s."
        )

    if duration > max_duration:
        raise ValueError(
            f"Audio duration ({duration:.2f}s) exceeds maximum allowed limit of {max_duration:.0f}s."
        )

    # Step 7: Silence and low-volume check
    peak_amp = float(np.max(np.abs(waveform)))
    rms_energy = float(np.sqrt(np.mean(np.square(waveform))))

    if peak_amp < SILENCE_PEAK_THRESHOLD or rms_energy < SILENCE_RMS_THRESHOLD:
        raise ValueError("Audio does not contain enough meaningful speech for analysis.")

    # Step 8: Amplitude normalization (preserve dynamics without saturation)
    waveform = (waveform / peak_amp * 0.95).astype(np.float32)

    if return_meta:
        return waveform, orig_sr
    return waveform
