"""
Diagnostic script: test acoustic transformations on 4.flac to understand the false positive.
"""

import math
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import scipy.signal as signal

import sys
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from model import VoiceCloneDetector

def main():
    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    data_4, sr_4 = sf.read("tests/audio/temp_4.flac")

    print("--- Resampling & Filtering Experiments on 4.flac ---")

    # Experiment 1: librosa default
    w1 = librosa.resample(data_4, orig_sr=sr_4, target_sr=16000)
    res1 = detector.predict(w1)
    print(f"1. librosa default:               Spoof Score = {res1['model_spoof_score']*100:.2f}%")

    # Experiment 2: scipy resample_poly
    g = math.gcd(16000, sr_4)
    up = 16000 // g
    down = sr_4 // g
    w2 = signal.resample_poly(data_4, up, down).astype(np.float32)
    res2 = detector.predict(w2)
    print(f"2. scipy resample_poly:           Spoof Score = {res2['model_spoof_score']*100:.2f}%")

    # Experiment 3: Pre-filter with brickwall 7kHz lowpass before downsampling
    sos = signal.butter(10, 7000, btype="lowpass", fs=sr_4, output="sos")
    data_4_filtered = signal.sosfilt(sos, data_4).astype(np.float32)
    w3 = librosa.resample(data_4_filtered, orig_sr=sr_4, target_sr=16000)
    res3 = detector.predict(w3)
    print(f"3. 7kHz lowpass + librosa:        Spoof Score = {res3['model_spoof_score']*100:.2f}%")

    # Experiment 4: Standardize amplitude (zero mean, unit variance)
    w4 = (w1 - np.mean(w1)) / (np.std(w1) + 1e-7)
    res4 = detector.predict(w4)
    print(f"4. Z-score normalized:            Spoof Score = {res4['model_spoof_score']*100:.2f}%")

    # Experiment 5: Pitch shift
    for semitone in [-3, -2, -1, 1, 2, 3]:
        w_pitch = librosa.effects.pitch_shift(w1, sr=16000, n_steps=semitone)
        res_p = detector.predict(w_pitch)
        print(f"5. Pitch shift {semitone:+d} st:           Spoof Score = {res_p['model_spoof_score']*100:.2f}%")

    # Experiment 6: Test individual 1-second slices of 4.flac
    print("\n--- Testing 1-second sequential slices of 4.flac ---")
    for start_sec in range(int(len(w1)/16000)):
        sub = w1[start_sec*16000 : (start_sec+1)*16000]
        res_sub = detector.predict(sub)
        print(f"Slice {start_sec}-{start_sec+1}s: Spoof Score = {res_sub['model_spoof_score']*100:.2f}% ({res_sub['prediction']})")

if __name__ == "__main__":
    main()
