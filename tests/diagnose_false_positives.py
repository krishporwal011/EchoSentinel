"""
Diagnostic script for EchoSentinel false positive investigation.
Analyzes acoustic properties, tests reproducibility, checks codec impacts,
and tests pre-processing / spectral hypotheses.
"""

import os
import sys
import io
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import torch

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from audio_processor import decode_and_preprocess_audio
from model import VoiceCloneDetector

def run_diagnostic():
    print("=" * 80)
    print("         ECHOSENTINEL FALSE POSITIVE DEEP DIVE INVESTIGATION")
    print("=" * 80)

    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    project_root = Path(__file__).resolve().parent.parent
    fp_files = [
        ("human_female_librispeech4.ogg", project_root / "tests/audio/genuine/human_female_librispeech4.ogg"),
        ("human_male_mlk_live.wav", project_root / "tests/audio/genuine/human_male_mlk_live.wav")
    ]

    print("\n--- STEP 1: REPRODUCIBILITY VERIFICATION ---")
    for name, path in fp_files:
        raw_bytes = path.read_bytes()
        print(f"\nTesting {name} (5 independent passes):")
        for i in range(5):
            waveform = decode_and_preprocess_audio(raw_bytes)
            
            # Extract raw logits directly from model
            inputs = detector.feature_extractor(waveform, sampling_rate=16000, return_tensors="pt", padding=True)
            input_values = inputs.input_values.to(detector.device)
            with torch.no_grad():
                outputs = detector.model(input_values)
                logits = outputs.logits.squeeze().cpu().numpy()
                probs = torch.softmax(outputs.logits, dim=-1).squeeze().cpu().numpy()
            
            pred = detector.predict(waveform)
            print(f"  Run {i+1}: Logits [bonafide={logits[detector.bonafide_idx]:.4f}, spoof={logits[detector.spoof_idx]:.4f}] | "
                  f"Prob Spoof={probs[detector.spoof_idx]:.6f} | Pred={pred['prediction']} | SpoofScore={pred['model_spoof_score']}")

    print("\n--- STEP 2: ACOUSTIC PROFILE COMPARISON ---")
    genuine_dir = project_root / "tests/audio/genuine"
    all_genuine = sorted(genuine_dir.glob("*.*"))
    
    header = f"{'Filename':<30} | {'Codec':<7} | {'SR':<5} | {'Peak':<6} | {'RMS':<6} | {'SNR(dB)':<7} | {'Centroid':<8} | {'ZCR':<6} | {'Spoof%':<7} | {'Result':<5}"
    print(header)
    print("-" * 105)
    
    for p in all_genuine:
        info = sf.info(str(p))
        data, sr = sf.read(str(p))
        mono = np.mean(data, axis=-1) if data.ndim > 1 else data
        peak = float(np.max(np.abs(mono)))
        rms = float(np.sqrt(np.mean(mono**2)))
        
        # Estimate noise floor (10th percentile energy in 25ms frames)
        frame_len = int(sr * 0.025)
        hop_len = int(sr * 0.010)
        frames = librosa.util.frame(mono, frame_length=frame_len, hop_length=hop_len)
        frame_rms = np.sqrt(np.mean(frames**2, axis=0))
        noise_floor = float(np.percentile(frame_rms, 10))
        snr_est = 20 * np.log10(max(rms, 1e-9) / max(noise_floor, 1e-9))
        
        spec_cent = float(np.mean(librosa.feature.spectral_centroid(y=mono, sr=sr)))
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(mono)))
        
        processed = decode_and_preprocess_audio(p.read_bytes())
        res = detector.predict(processed)
        is_pass = "PASS" if res["prediction"] == "authentic" else "FAIL"
        spoof_pct = f"{res['model_spoof_score'] * 100:.2f}%"
        
        print(f"{p.name:<30} | {info.format:<7} | {sr:<5} | {peak:<6.3f} | {rms:<6.3f} | {snr_est:<7.1f} | {spec_cent:<8.1f} | {zcr:<6.3f} | {spoof_pct:<7} | {is_pass:<5}")

    print("\n--- STEP 3: CODEC CONVERSION EXPERIMENT ---")
    # Does saving human_female_librispeech4 as uncompressed WAV change the model output?
    temp_flac = project_root / "tests/audio/temp_4.flac"
    if temp_flac.exists():
        flac_data, flac_sr = sf.read(str(temp_flac))
        flac_mono = np.mean(flac_data, axis=-1) if flac_data.ndim > 1 else flac_data
        
        # 1. Test original 48kHz FLAC
        res_flac = detector.predict(decode_and_preprocess_audio(temp_flac.read_bytes()))
        print(f"4.flac (Original FLAC 48kHz, lossless): Spoof Score = {res_flac['model_spoof_score']*100:.2f}% ({res_flac['prediction']})")
        
        # 2. Resample to 16kHz WAV lossless PCM_16
        wav_16k_buf = io.BytesIO()
        data_16k = librosa.resample(flac_mono, orig_sr=flac_sr, target_sr=16000)
        sf.write(wav_16k_buf, data_16k, 16000, format="WAV", subtype="PCM_16")
        wav_16k_bytes = wav_16k_buf.getvalue()
        res_wav = detector.predict(decode_and_preprocess_audio(wav_16k_bytes))
        print(f"4.flac -> 16kHz WAV (lossless PCM_16):   Spoof Score = {res_wav['model_spoof_score']*100:.2f}% ({res_wav['prediction']})")
        
        # 3. Save as OGG Vorbis 16kHz
        ogg_buf = io.BytesIO()
        sf.write(ogg_buf, data_16k, 16000, format="OGG", subtype="VORBIS")
        res_ogg = detector.predict(decode_and_preprocess_audio(ogg_buf.getvalue()))
        print(f"4.flac -> 16kHz OGG Vorbis:             Spoof Score = {res_ogg['model_spoof_score']*100:.2f}% ({res_ogg['prediction']})")

    # Does MLK in FLAC vs WAV change?
    mlk_flac = project_root / "tests/audio/temp_mlk.flac"
    if mlk_flac.exists():
        res_mlk_flac = detector.predict(decode_and_preprocess_audio(mlk_flac.read_bytes()))
        print(f"MLK (Original FLAC from HF):            Spoof Score = {res_mlk_flac['model_spoof_score']*100:.2f}% ({res_mlk_flac['prediction']})")

    # Does human_male_garth.ogg (which passed) change when converted to WAV?
    garth_p = project_root / "tests/audio/genuine/human_male_garth.ogg"
    garth_data, garth_sr = sf.read(str(garth_p))
    garth_wav_buf = io.BytesIO()
    sf.write(garth_wav_buf, garth_data, garth_sr, format="WAV")
    res_garth_wav = detector.predict(decode_and_preprocess_audio(garth_wav_buf.getvalue()))
    print(f"Garth OGG -> WAV:                       Spoof Score = {res_garth_wav['model_spoof_score']*100:.2f}% ({res_garth_wav['prediction']})")

    print("\n--- STEP 4: ACOUSTIC FILTERING EXPERIMENTS ON MLK LIVE ---")
    # Test bandpass filter (300Hz - 3400Hz telephone band, and 80Hz - 7000Hz speech band)
    mlk_data, mlk_sr = sf.read(str(project_root / "tests/audio/genuine/human_male_mlk_live.wav"))
    mlk_16k = librosa.resample(mlk_data, orig_sr=mlk_sr, target_sr=16000)
    
    # Raw without preprocessing
    res_mlk_raw = detector.predict(mlk_16k)
    print(f"MLK 16k Raw:                            Spoof Score = {res_mlk_raw['model_spoof_score']*100:.2f}%")
    
    # High-pass filter at 150 Hz to remove rumble/hum
    from scipy.signal import butter, sosfilt
    sos_hp = butter(4, 150, btype='highpass', fs=16000, output='sos')
    mlk_hp = sosfilt(sos_hp, mlk_16k).astype(np.float32)
    res_mlk_hp = detector.predict(mlk_hp)
    print(f"MLK Highpass (150Hz cutoff):            Spoof Score = {res_mlk_hp['model_spoof_score']*100:.2f}%")

    # Low-pass filter at 4000 Hz to remove high-frequency tape hiss
    sos_lp = butter(4, 4000, btype='lowpass', fs=16000, output='sos')
    mlk_lp = sosfilt(sos_lp, mlk_hp).astype(np.float32)
    res_mlk_lp = detector.predict(mlk_lp)
    print(f"MLK Bandpass (150Hz - 4000Hz):          Spoof Score = {res_mlk_lp['model_spoof_score']*100:.2f}%")

    print("\n============================================================")

if __name__ == "__main__":
    run_diagnostic()
