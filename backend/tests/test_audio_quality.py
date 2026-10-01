"""
Unit and integration tests for EchoSentinel Audio Quality & Reliability Gating Engine.
Validates clean speech, noise, reverberation, and telephony detection across genuine and AI speech.
"""

import pytest
import numpy as np
import soundfile as sf
import librosa
from pathlib import Path

from audio_quality import analyze_audio_quality, determine_application_decision


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GENUINE_DIR = PROJECT_ROOT / "tests" / "audio" / "genuine"
SPOOF_DIR = PROJECT_ROOT / "tests" / "audio" / "spoof"


def test_clean_genuine_speech():
    """Clean studio human speech should achieve high audio quality score and HIGH reliability."""
    p = GENUINE_DIR / "human_male_anders.wav"
    d, sr = sf.read(str(p))
    quality = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)

    assert quality["quality_score"] >= 80
    assert quality["reliability"] == "HIGH"
    assert quality["quality_rating"] == "good"
    assert len(quality["flags"]) == 0
    assert quality["warning_message"] is None

    decision = determine_application_decision("authentic", 0.0007, quality)
    assert decision["final_decision"] == "authentic"
    assert decision["detection_reliability"] == "HIGH"
    assert decision["quality_warning"] is None


def test_genuine_with_background_noise():
    """Genuine speech with +15dB SNR noise should be flagged for background noise with LOW reliability."""
    p = GENUINE_DIR / "human_male_noisy_snr15db.wav"
    d, sr = sf.read(str(p))
    quality = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)

    assert "high_background_noise" in quality["flags"]
    assert quality["reliability"] == "LOW"
    assert quality["quality_score"] < 75
    assert quality["warning_message"] is not None
    assert "background noise" in quality["warning_message"].lower()

    # Crucial test: When model outputs "AI-generated" on noisy audio,
    # the application does NOT blindly classify it as authentic,
    # nor does it claim high confidence. It returns "Possible spoof" with low reliability.
    decision = determine_application_decision("AI-generated", 0.9999, quality)
    assert decision["final_decision"] == "Possible spoof"
    assert decision["detection_reliability"] == "LOW"
    assert "low due to degraded audio" in decision["reliability_label"].lower()
    assert decision["quality_warning"] is not None


def test_genuine_with_reverberation():
    """Genuine speech with room reverberation should be flagged with LOW reliability."""
    p = GENUINE_DIR / "human_female_reverberant_room.wav"
    d, sr = sf.read(str(p))
    quality = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)

    assert "reverberation_detected" in quality["flags"]
    assert quality["reliability"] == "LOW"
    assert "reverberation" in quality["warning_message"].lower()

    decision = determine_application_decision("AI-generated", 0.9999, quality)
    assert decision["final_decision"] == "Possible spoof"
    assert decision["detection_reliability"] == "LOW"
    assert "low due to degraded audio" in decision["reliability_label"].lower()


def test_telephone_band_speech():
    """Narrowband/telephone filtered speech should be flagged for telephony with LOW reliability."""
    p = GENUINE_DIR / "human_male_phone_filtered_8k.wav"
    d, sr = sf.read(str(p))
    quality = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)

    assert "narrowband_telephony" in quality["flags"]
    assert quality["reliability"] == "LOW"
    assert "telephone" in quality["warning_message"].lower()

    decision = determine_application_decision("AI-generated", 0.9926, quality)
    assert decision["final_decision"] == "Possible spoof"
    assert decision["detection_reliability"] == "LOW"


def test_clean_ai_speech():
    """Clean neural/AI speech should have high quality score and HIGH reliability."""
    p = SPOOF_DIR / "ai_guy_executive_transfer.mp3"
    d, sr = librosa.load(str(p), sr=16000, mono=True)
    quality = analyze_audio_quality(d, sample_rate=16000, native_sample_rate=24000)

    assert quality["quality_score"] >= 80
    assert quality["reliability"] == "HIGH"
    assert len(quality["flags"]) == 0

    decision = determine_application_decision("AI-generated", 0.9998, quality)
    assert decision["final_decision"] == "AI-generated"
    assert decision["detection_reliability"] == "HIGH"
    assert decision["quality_warning"] is None


def test_ai_speech_with_noise():
    """AI speech corrupted by noise must NOT silently become 'authentic'; must flag degradation."""
    p = SPOOF_DIR / "ai_guy_noisy_snr15db.wav"
    d, sr = sf.read(str(p))
    quality = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)

    assert "high_background_noise" in quality["flags"]
    assert quality["reliability"] == "LOW"

    # Must NOT become authentic
    decision = determine_application_decision("AI-generated", 0.9999, quality)
    assert decision["final_decision"] != "authentic"
    assert decision["final_decision"] == "Possible spoof"
    assert decision["detection_reliability"] == "LOW"


def test_ai_speech_with_reverberation():
    """AI speech in a reverberant room must flag reverberation and report low reliability."""
    p = SPOOF_DIR / "ai_jenny_reverberant_room.wav"
    d, sr = sf.read(str(p))
    quality = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)

    assert "reverberation_detected" in quality["flags"]
    assert quality["reliability"] == "LOW"

    # Must NOT become authentic
    decision = determine_application_decision("AI-generated", 0.9999, quality)
    assert decision["final_decision"] != "authentic"
    assert decision["final_decision"] == "Possible spoof"
    assert decision["detection_reliability"] == "LOW"


def test_empty_audio_quality_handling():
    """Empty or None audio array should gracefully return degraded rating without raising exception."""
    res = analyze_audio_quality(np.array([], dtype=np.float32), sample_rate=16000)
    assert res["quality_score"] == 10
    assert res["quality_rating"] == "degraded"
    assert res["reliability"] == "LOW"
    assert "empty_audio" in res["flags"]
