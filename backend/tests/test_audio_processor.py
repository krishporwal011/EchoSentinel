import io
import pytest
import numpy as np
import soundfile as sf
from audio_processor import decode_and_preprocess_audio, MAX_FILE_SIZE_BYTES

def make_wav_bytes(signal: np.ndarray, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, signal, sr, format='WAV')
    return buf.getvalue()

def test_empty_audio_bytes():
    with pytest.raises(ValueError, match='empty'):
        decode_and_preprocess_audio(b'')

def test_tiny_audio_bytes():
    with pytest.raises(ValueError, match='too small'):
        decode_and_preprocess_audio(b'RIFF1234')

def test_corrupted_audio_bytes():
    corrupted = b'RIFF' + b'\x00' * 100
    with pytest.raises(ValueError, match='Audio decoding failed'):
        decode_and_preprocess_audio(corrupted)

def test_silent_audio_rejected():
    sr = 16000
    silence = np.zeros(sr * 2, dtype=np.float32)
    wav_bytes = make_wav_bytes(silence, sr)
    with pytest.raises(ValueError, match='Audio does not contain enough meaningful speech for analysis.'):
        decode_and_preprocess_audio(wav_bytes)

def test_low_volume_audio_rejected():
    sr = 16000
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    # Extremely low amplitude (inaudible whisper/noise)
    tiny_sig = (1e-4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    wav_bytes = make_wav_bytes(tiny_sig, sr)
    with pytest.raises(ValueError, match='Audio does not contain enough meaningful speech for analysis.'):
        decode_and_preprocess_audio(wav_bytes)

def test_short_duration_rejected():
    sr = 16000
    t = np.linspace(0, 0.3, int(sr * 0.3), endpoint=False)  # 0.3s < 0.5s min
    sig = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    wav_bytes = make_wav_bytes(sig, sr)
    with pytest.raises(ValueError, match='too short'):
        decode_and_preprocess_audio(wav_bytes, min_duration=0.5)

def test_long_duration_rejected():
    sr = 16000
    t = np.linspace(0, 5.0, sr * 5, endpoint=False)
    sig = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    wav_bytes = make_wav_bytes(sig, sr)
    with pytest.raises(ValueError, match='exceeds maximum allowed limit'):
        decode_and_preprocess_audio(wav_bytes, max_duration=4.0)

def test_valid_audio_preprocessing():
    sr = 22050  # non-target sample rate to test resampling
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    sig = (0.4 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    wav_bytes = make_wav_bytes(sig, sr)

    processed = decode_and_preprocess_audio(wav_bytes, target_sr=16000)
    assert isinstance(processed, np.ndarray)
    assert processed.ndim == 1
    assert processed.dtype == np.float32
    # 2 seconds at 16000 Hz = 32000 samples (+/- 1 sample due to resampling boundary)
    assert abs(len(processed) - 32000) <= 2
    # Normalized peak ~ 0.95
    assert np.isclose(np.max(np.abs(processed)), 0.95, atol=0.01)

def test_stereo_to_mono_downmixing():
    sr = 16000
    t = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False)
    left = 0.3 * np.sin(2 * np.pi * 300 * t)
    right = 0.3 * np.sin(2 * np.pi * 600 * t)
    stereo = np.stack([left, right], axis=1).astype(np.float32)
    wav_bytes = make_wav_bytes(stereo, sr)

    processed = decode_and_preprocess_audio(wav_bytes, target_sr=16000)
    assert processed.ndim == 1
