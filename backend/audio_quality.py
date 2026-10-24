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


def build_audio_visuals(waveform: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
    """Return bounded waveform/spectrogram data for display, never as proof of spoofing."""
    mono = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if mono.size == 0:
        return {"waveform": [], "spectrogram": []}

    waveform_bins = min(512, mono.size)
    waveform_points = []
    for block in np.array_split(mono, waveform_bins):
        waveform_points.append(round(float(np.mean(block)), 5))

    stft = np.abs(librosa.stft(mono, n_fft=512, hop_length=256))
    db = librosa.amplitude_to_db(stft + 1e-8, ref=np.max)
    db = np.clip((db + 60.0) / 60.0, 0.0, 1.0)
    row_indices = np.linspace(0, db.shape[0] - 1, 48).astype(int)
    col_indices = np.linspace(0, db.shape[1] - 1, 96).astype(int)
    spectrogram = np.round(db[np.ix_(row_indices, col_indices)], 3).tolist()
    return {
        "waveform": waveform_points,
        "spectrogram": spectrogram,
        "spectrogram_sample_rate": sample_rate,
        "spectrogram_hop_length": 256,
    }


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
    level_variation_db = float(20.0 * np.log10(max(p95, 1e-6) / max(p10, 1e-6)))

    # 3. Spectral analysis & Telephony/Narrowband check
    stft = np.abs(librosa.stft(waveform))
    freqs = librosa.fft_frequencies(sr=sample_rate)
    above_4k = freqs >= 3800
    mid_band = (freqs >= 500) & (freqs < 3000)

    energy_above_4k = float(np.sum(stft[above_4k, :] ** 2))
    energy_mid = float(np.sum(stft[mid_band, :] ** 2)) + 1e-9
    high_mid_db = float(10.0 * np.log10(max(energy_above_4k, 1e-12) / energy_mid))

    is_narrowband = native_sample_rate is not None and native_sample_rate <= 8000
    total_spectral_energy = float(np.sum(stft ** 2)) + 1e-12
    high_frequency_share = float(energy_above_4k / total_spectral_energy)

    # 4. Background noise flatness in quiet frames
    flatness = librosa.feature.spectral_flatness(y=waveform)
    quiet_idx = np.where(frame_rms <= np.percentile(frame_rms, 25))[0]
    if len(quiet_idx) > 0 and quiet_idx[-1] < flatness.shape[1]:
        noise_flatness = float(np.mean(flatness[0, quiet_idx]))
    else:
        noise_flatness = float(np.mean(flatness))

    # These are recording-quality heuristics, not validated speech/noise separation.
    is_noisy = (dyn_range < 24.0 and noise_flatness > 0.05) or (level_variation_db < 16.0)

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

    peak_dbfs = float(20.0 * np.log10(max(float(np.max(np.abs(waveform))), 1e-6)))
    measurements = [
        {
            "id": "source_sample_rate",
            "label": "Source sample rate",
            "value": int(native_sample_rate) if native_sample_rate is not None else sample_rate,
            "unit": "Hz",
            "interpretation": "The model input is resampled to 16 kHz; resampling cannot restore frequencies absent from the source.",
        },
        {
            "id": "clipped_samples",
            "label": "Samples at digital peak",
            "value": round(clip_ratio * 100.0, 4),
            "unit": "%",
            "interpretation": "A non-zero value means some samples reached the clipping range. This is a recording-quality observation, not evidence of AI generation.",
        },
        {
            "id": "peak_level",
            "label": "Peak level",
            "value": round(peak_dbfs, 1),
            "unit": "dBFS",
            "interpretation": "Measured peak amplitude relative to digital full scale.",
        },
        {
            "id": "level_variation",
            "label": "Frame-level variation",
            "value": round(level_variation_db, 1),
            "unit": "dB",
            "interpretation": "A rough variation between quiet and loud frames; this is not a measured signal-to-noise ratio.",
        },
        {
            "id": "high_frequency_share",
            "label": "Energy above 3.8 kHz",
            "value": round(high_frequency_share * 100.0, 2),
            "unit": "%",
            "interpretation": "A descriptive spectral measurement. No universal range proves speech is synthetic.",
        },
    ]

    return {
        "quality_score": score,
        "quality_rating": quality_rating,
        "reliability": reliability,
        "flags": flags,
        "warning_message": warning_message,
        "snr_db": None,
        "level_variation_db": round(level_variation_db, 1),
        "dynamic_range_db": round(dyn_range, 1),
        "env_tail": round(env_tail, 3),
        "high_mid_db": round(high_mid_db, 1),
        "noise_flatness": round(noise_flatness, 4),
        "is_clipped": is_clipped,
        "is_narrowband": is_narrowband,
        "is_noisy": is_noisy,
        "is_reverberant": is_reverberant,
        "measurements": measurements,
        **build_audio_visuals(waveform, sample_rate),
    }


def determine_application_decision(
    raw_model_prediction: str,
    raw_spoof_score: float,
    audio_quality: Dict[str, Any]
) -> Dict[str, Any]:
    """Return a normalized decision, withholding a class when quality is unreliable.

    Reliability is a heuristic recording-quality tier, not model confidence. The live
    API currently returns the model class and quality indicators separately.
    """
    reliability = audio_quality.get("reliability", "HIGH")
    warning = audio_quality.get("warning_message")
    normalized_prediction = str(raw_model_prediction).strip().lower().replace("_", " ").replace("-", " ")
    if normalized_prediction in {"authentic", "bonafide", "bona fide", "human", "likely human recorded"}:
        model_decision = "authentic"
    elif normalized_prediction in {"ai generated", "spoof", "synthetic", "likely ai generated"}:
        model_decision = "ai_generated"
    else:
        model_decision = "inconclusive"

    if reliability == "LOW":
        final_decision = "inconclusive"
        reliability_label = "Low due to heuristic recording-quality checks"
        status = "needs_better_recording"
    else:
        final_decision = model_decision
        reliability_label = "Moderate" if reliability == "MEDIUM" else "High"
        status = "analyzed"

    # `raw_spoof_score` is retained for backward compatibility; it is not calibrated.
    _ = raw_spoof_score

    return {
        "final_decision": final_decision,
        "detection_reliability": reliability,
        "reliability_label": reliability_label,
        "quality_warning": warning,
        "status": status
    }

