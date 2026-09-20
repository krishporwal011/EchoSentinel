"""
Audio Quality and Acoustic Channel Analysis Engine for EchoSentinel.
Evaluates recording SNR, background noise floor, room reverberation,
telephone narrowband frequency cutoffs, waveform clipping, and dynamic range.
Provides audio quality scoring, detection reliability gating, and actionable user warnings.
"""

import logging
from typing import Dict, List, Optional, Any
import numpy as np
import librosa

logger = logging.getLogger("echosentinel.audio_quality")


def analyze_audio_quality(
    waveform: np.ndarray,
    sample_rate: int = 16000,
    native_sample_rate: Optional[int] = None
) -> Dict[str, Any]:
    """
    Analyzes physical acoustic characteristics of input audio to detect channel degradation
    such as low SNR, high noise floor, room reverberation, clipping, or narrowband telephone filtering.

    Returns a structured dictionary with:
      - quality_score (int 10-100)
      - quality_rating ("good", "fair", "poor", "degraded")
      - reliability ("HIGH", "MEDIUM", "LOW")
      - flags (list of str)
      - warning_message (Optional[str])
      - snr_db (float)
      - dynamic_range_db (float)
    """
    if waveform is None or len(waveform) == 0:
        return {
            "quality_score": 10,
            "quality_rating": "degraded",
            "reliability": "LOW",
            "flags": ["empty_audio"],
            "warning_message": "Audio file is empty or corrupted.",
            "snr_db": 0.0,
            "dynamic_range_db": 0.0
        }

    # Ensure 1D float32 mono
    if waveform.ndim > 1:
        waveform = np.mean(waveform, axis=-1)
    waveform = waveform.astype(np.float32)

    # 1. Clipping detection
    clip_ratio = float(np.mean(np.abs(waveform) >= 0.999))
    is_clipped = clip_ratio > 0.005

    # 2. Frame-level RMS energy (25ms window, 10ms hop)
    frame_len = max(128, int(sample_rate * 0.025))
    hop_len = max(64, int(sample_rate * 0.010))
    frames = librosa.util.frame(waveform, frame_length=frame_len, hop_length=hop_len)
    frame_rms = np.sqrt(np.mean(np.square(frames), axis=0))

    if len(frame_rms) == 0:
        return {
            "quality_score": 10,
            "quality_rating": "degraded",
            "reliability": "LOW",
            "flags": ["audio_too_short"],
            "warning_message": "Audio duration is too short for quality analysis.",
            "snr_db": 0.0,
            "dynamic_range_db": 0.0
        }

    p95 = float(np.percentile(frame_rms, 95))
    p10 = float(np.percentile(frame_rms, 10))
    p05 = float(np.percentile(frame_rms, 5))
    dyn_range = float(20.0 * np.log10(max(p95, 1e-6) / max(p05, 1e-6)))
    snr_est = float(20.0 * np.log10(max(p95, 1e-6) / max(p10, 1e-6)))

    # 3. Spectral analysis & Telephony/Narrowband check
    stft = np.abs(librosa.stft(waveform))
    freqs = librosa.fft_frequencies(sr=sample_rate)
    above_4k = freqs >= 3800
    mid_band = (freqs >= 500) & (freqs < 3000)

    energy_above_4k = float(np.sum(stft[above_4k, :] ** 2))
    energy_mid = float(np.sum(stft[mid_band, :] ** 2)) + 1e-9
    high_mid_db = float(10.0 * np.log10(max(energy_above_4k, 1e-12) / energy_mid))

    is_narrowband = (native_sample_rate is not None and native_sample_rate <= 8000) or (high_mid_db < -35.0)

    # 4. Background noise flatness in quiet frames
    flatness = librosa.feature.spectral_flatness(y=waveform)
    quiet_idx = np.where(frame_rms <= np.percentile(frame_rms, 25))[0]
    if len(quiet_idx) > 0 and quiet_idx[-1] < flatness.shape[1]:
        noise_flatness = float(np.mean(flatness[0, quiet_idx]))
    else:
        noise_flatness = float(np.mean(flatness))

    is_noisy = (dyn_range < 24.0 and noise_flatness > 0.05) or (snr_est < 16.0)

    # 5. Room reverberation: energy envelope autocorrelation tail at 50ms - 200ms
    rms_centered = frame_rms - np.mean(frame_rms)
    autocorr = np.correlate(rms_centered, rms_centered, mode="full")
    autocorr = autocorr[len(autocorr) // 2:]
    autocorr = autocorr / (autocorr[0] + 1e-9)
    env_tail = float(np.mean(np.abs(autocorr[5:20]))) if len(autocorr) >= 20 else 0.0

    is_reverberant = (env_tail >= 0.30)
    is_abnormal_dyn = (dyn_range < 18.0)

    # Compile flags and human-readable guidance
    flags: List[str] = []
    warnings: List[str] = []

    if is_narrowband:
        flags.append("narrowband_telephony")
        warnings.append("Narrowband/telephone-quality audio detected. Low-bandwidth recording may distort voice characteristics. Please record using a standard wideband microphone.")

    if is_noisy:
        flags.append("high_background_noise")
        warnings.append("High background noise detected. Low signal-to-noise ratio may obscure voice authenticity. Try recording in a quieter environment.")

    if is_reverberant:
        flags.append("reverberation_detected")
        warnings.append("Strong room reverberation or echo detected. Acoustic reflections reduce detector reliability. Try recording closer to the microphone or in an acoustically treated room.")

    if is_clipped:
        flags.append("severe_clipping")
        warnings.append("Severe audio clipping detected. Reduce microphone input gain to avoid waveform saturation.")

    if is_abnormal_dyn and not is_noisy:
        flags.append("abnormal_dynamic_range")
        warnings.append("Abnormal dynamic range detected. The recording may be over-compressed or gated.")

    # Calculate overall quality score (10 to 100)
    score = 100
    if is_narrowband:
        score -= 35
    if is_noisy:
        score -= 35
    if is_reverberant:
        score -= 30
    if is_clipped:
        score -= 25
    if is_abnormal_dyn:
        score -= 15
    score = max(10, min(100, score))

    # Determine qualitative rating & reliability tier
    critical_degradation_flags = {"narrowband_telephony", "high_background_noise", "reverberation_detected", "severe_clipping"}
    has_critical_degradation = bool(set(flags).intersection(critical_degradation_flags))

    if len(flags) == 0 and score >= 80:
        quality_rating = "good"
        reliability = "HIGH"
    elif not has_critical_degradation and score >= 65:
        quality_rating = "fair"
        reliability = "MEDIUM"
    elif score >= 40:
        quality_rating = "poor"
        reliability = "LOW"
    else:
        quality_rating = "degraded"
        reliability = "LOW"

    # Enforce LOW reliability if critical acoustic degradation is present
    if has_critical_degradation:
        reliability = "LOW"

    warning_message = " ".join(warnings) if warnings else None

    return {
        "quality_score": score,
        "quality_rating": quality_rating,
        "reliability": reliability,
        "flags": flags,
        "warning_message": warning_message,
        "snr_db": round(snr_est, 1),
        "dynamic_range_db": round(dyn_range, 1),
        "env_tail": round(env_tail, 3),
        "high_mid_db": round(high_mid_db, 1),
        "noise_flatness": round(noise_flatness, 4),
        "is_clipped": is_clipped,
        "is_narrowband": is_narrowband,
        "is_noisy": is_noisy,
        "is_reverberant": is_reverberant
    }


def determine_application_decision(
    raw_model_prediction: str,
    raw_spoof_score: float,
    audio_quality: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Combines raw model prediction with acoustic quality analysis to produce an honest,
    calibrated application decision without overriding the model blindly.
    """
    reliability = audio_quality.get("reliability", "HIGH")
    flags = audio_quality.get("flags", [])
    warning = audio_quality.get("warning_message")

    if reliability == "LOW":
        if raw_model_prediction == "AI-generated":
            final_decision = "Possible spoof"
            reliability_label = "Low due to degraded audio"
            reason = warning or "Background noise / reverberation / narrowband recording may affect detection."
            status = "needs_better_recording"
        else:
            final_decision = "Authentic"
            reliability_label = "Low due to degraded audio"
            reason = warning or "Degraded audio quality may obscure voice cloning artifacts."
            status = "needs_better_recording"
    elif reliability == "MEDIUM":
        if raw_model_prediction == "AI-generated":
            final_decision = "AI-generated"
            reliability_label = "Moderate (some acoustic coloration)"
            reason = warning
            status = "analyzed"
        else:
            final_decision = "authentic"
            reliability_label = "Moderate (some acoustic coloration)"
            reason = warning
            status = "analyzed"
    else:
        final_decision = raw_model_prediction
        reliability_label = "High"
        reason = None
        status = "analyzed"

    return {
        "final_decision": final_decision,
        "detection_reliability": reliability,
        "reliability_label": reliability_label,
        "quality_warning": reason,
        "status": status
    }

