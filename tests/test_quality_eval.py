import soundfile as sf
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from audio_quality import analyze_audio_quality

def main():
    print("--- GENUINE SAMPLES ---")
    for p in sorted(Path("tests/audio/genuine").glob("*.*")):
        d, sr = sf.read(str(p))
        q = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)
        flags_str = ", ".join(q["flags"]) if q["flags"] else "none"
        print(f"{p.name:<36} | Score: {q['quality_score']:>3} | Rating: {q['quality_rating']:<8} | Rel: {q['reliability']:<6} | Flags: {flags_str}")

    print("\n--- SPOOF SAMPLES ---")
    for p in sorted(Path("tests/audio/spoof").glob("*.*")):
        d, sr = sf.read(str(p))
        q = analyze_audio_quality(d, sample_rate=sr, native_sample_rate=sr)
        flags_str = ", ".join(q["flags"]) if q["flags"] else "none"
        print(f"{p.name:<36} | Score: {q['quality_score']:>3} | Rating: {q['quality_rating']:<8} | Rel: {q['reliability']:<6} | Flags: {flags_str}")

if __name__ == "__main__":
    main()
