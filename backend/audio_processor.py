import io
import logging
import numpy as np
import soundfile as sf
import librosa

logger = logging.getLogger("echosentinel.audio_processor")
TARGET_SAMPLE_RATE = 16000

def decode_and_preprocess_audio(audio_bytes: bytes, target_sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """
    Decodes audio bytes (WAV, FLAC, OGG, MP3, etc.), converts to mono,
    resamples to target_sr (16kHz), and normalizes amplitude.
    Returns a 1D float32 numpy array.
    """
    if not audio_bytes or len(audio_bytes) < 44:
        raise ValueError("Audio chunk is empty or too small to be valid.")

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

    # Step 2: Try librosa fallback if soundfile failed
    if waveform is None:
        try:
            audio_buffer.seek(0)
            data, file_sr = librosa.load(audio_buffer, sr=target_sr, mono=True)
            waveform = data
            sr = target_sr
        except Exception as librosa_err:
            raise ValueError(f"Could not decode audio chunk: {librosa_err}")

    # Step 3: Ensure mono
    if waveform.ndim > 1:
        # Multi-channel: average across channels
        waveform = np.mean(waveform, axis=-1 if waveform.shape[-1] < waveform.shape[0] else 0)

    waveform = waveform.astype(np.float32)

    # Step 4: Resample if sample rate does not match target
    if sr is not None and sr != target_sr:
        try:
            waveform = librosa.resample(waveform, orig_sr=sr, target_sr=target_sr)
        except Exception as resample_err:
            logger.warning(f"Librosa resampling failed ({resample_err}); applying linear interpolation.")
            old_indices = np.linspace(0, len(waveform) - 1, len(waveform))
            new_len = int(len(waveform) * (target_sr / sr))
            new_indices = np.linspace(0, len(waveform) - 1, new_len)
            waveform = np.interp(new_indices, old_indices, waveform).astype(np.float32)

    # Step 5: Amplitude normalization (prevent clipping / scale extremes)
    max_amp = np.max(np.abs(waveform))
    if max_amp > 1e-6:
        # Scale to max amplitude ~0.95 to preserve dynamic range without saturation
        waveform = waveform / max_amp * 0.95
    else:
        logger.debug("Audio chunk contains near-zero or silent signal.")

    return waveform
