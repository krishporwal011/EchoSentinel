import io
import numpy as np
import soundfile as sf
from audio_processor import decode_and_preprocess_audio
from model import VoiceCloneDetector

def run_test():
    print("Initializing VoiceCloneDetector singleton...")
    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    assert detector.is_loaded, f"Failed to load model: {detector.load_error}"
    print("Detector loaded successfully!")

    # Create a 3-second test speech-like synthetic signal (mixed tones)
    sr = 16000
    t = np.linspace(0, 3, sr * 3, endpoint=False)
    sig = (
        0.3 * np.sin(2 * np.pi * 220 * t) +
        0.2 * np.sin(2 * np.pi * 440 * t) +
        0.1 * np.sin(2 * np.pi * 880 * t)
    ).astype(np.float32)

    buf = io.BytesIO()
    sf.write(buf, sig, sr, format="WAV")
    raw_wav_bytes = buf.getvalue()

    print(f"Preprocessing test audio chunk ({len(raw_wav_bytes)} bytes)...")
    waveform = decode_and_preprocess_audio(raw_wav_bytes, target_sr=16000)
    print(f"Preprocessed waveform shape: {waveform.shape}")

    print("Executing model inference...")
    result = detector.predict(waveform, sample_rate=16000)
    print("Inference Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Validate output schema
    assert "prediction" in result and result["prediction"] in ["authentic", "AI-generated"]
    assert "confidence" in result and 0.0 <= result["confidence"] <= 1.0
    assert "risk_score" in result and 0 <= result["risk_score"] <= 100
    assert "risk_level" in result and result["risk_level"] in ["Low", "Suspicious", "High", "Critical"]
    print("\nAll model test assertions passed successfully!")

if __name__ == "__main__":
    run_test()
