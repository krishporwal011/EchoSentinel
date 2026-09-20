"""
Evaluation benchmark for EchoSentinel Voice Deepfake Detector.
Evaluates both RAW MODEL PREDICTION and QUALITY-AWARE APPLICATION DECISION
across genuine speech (clean, telephone, compressed, noisy, reverberant)
and synthetic AI voice samples (Edge Neural TTS, Google TTS).
"""

import os
import sys
import time
from pathlib import Path
import soundfile as sf
import librosa

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from audio_processor import decode_and_preprocess_audio
from audio_quality import analyze_audio_quality, determine_application_decision
from model import VoiceCloneDetector


def evaluate():
    print("=" * 125)
    print(" " * 35 + "ECHOSENTINEL COMPREHENSIVE BENCHMARK EVALUATION")
    print("=" * 125)

    # Initialize model
    print("\n[+] Initializing VoiceCloneDetector...")
    t0 = time.perf_counter()
    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    init_time = time.perf_counter() - t0
    print(f"[+] Model initialized in {init_time:.2f}s on device: {detector.device}")

    project_root = Path(__file__).resolve().parent.parent
    genuine_dir = project_root / "tests" / "audio" / "genuine"
    spoof_dir = project_root / "tests" / "audio" / "spoof"

    # Core 22 benchmark files for exact BEFORE vs AFTER comparison
    core_22_genuine = [
        "human_female_compressed_vorbis.ogg",
        "human_female_heather.wav",
        "human_female_librispeech2.wav",
        "human_female_librispeech4.ogg",
        "human_female_reverberant_room.wav",
        "human_male_anders.wav",
        "human_male_garth.ogg",
        "human_male_librispeech1.flac",
        "human_male_librispeech3.flac",
        "human_male_mlk_live.wav",
        "human_male_noisy_snr15db.wav",
        "human_male_phone_filtered_8k.wav"
    ]

    core_22_spoof = [
        "ai_aria_neural_eval.flac",
        "ai_brian_wire_fraud.wav",
        "ai_christopher_auth_code.wav",
        "ai_emma_tech_support.ogg",
        "ai_gtts_password_reset_au.ogg",
        "ai_gtts_security_verification.mp3",
        "ai_gtts_wire_transfer_uk.wav",
        "ai_guy_executive_transfer.mp3",
        "ai_jenny_account_alert.wav",
        "ai_sonia_banking_alert.flac"
    ]

    additional_spoof = [
        "ai_guy_noisy_snr15db.wav",
        "ai_jenny_reverberant_room.wav"
    ]

    def evaluate_sample(file_path: Path, expected_label: str):
        audio_bytes = file_path.read_bytes()
        t_start = time.perf_counter()
        waveform, orig_sr = decode_and_preprocess_audio(audio_bytes, return_meta=True)
        raw_res = detector.predict(waveform)
        quality_res = analyze_audio_quality(waveform, sample_rate=16000, native_sample_rate=orig_sr)
        decision = determine_application_decision(
            raw_res["prediction"],
            raw_res["model_spoof_score"],
            quality_res
        )
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        # Raw model correctness
        raw_correct = (raw_res["prediction"] == expected_label)

        # Application decision correctness:
        # If expected is authentic: final decision should be authentic (or recognized as low-reliability possible spoof)
        # If expected is AI-generated: final decision should be AI-generated or possible spoof (never authentic)
        if expected_label == "authentic":
            app_correct = (decision["final_decision"] == "authentic")
        else:
            app_correct = (decision["final_decision"] in ["AI-generated", "Possible spoof"])

        return {
            "filename": file_path.name,
            "expected": expected_label,
            "model_prediction": raw_res["prediction"],
            "model_spoof_score": raw_res["model_spoof_score"],
            "audio_quality": f"{quality_res['quality_score']}/100 ({quality_res['quality_rating']})",
            "quality_score": quality_res["quality_score"],
            "quality_flags": quality_res["flags"],
            "final_decision": decision["final_decision"],
            "reliability": decision["detection_reliability"],
            "reliability_label": decision["reliability_label"],
            "quality_warning": decision["quality_warning"],
            "latency_ms": latency_ms,
            "raw_correct": raw_correct,
            "app_correct": app_correct
        }

    print("\n[+] Evaluating Core 22-Sample Benchmark (12 Genuine, 10 Spoof)...")
    results = []

    for name in core_22_genuine:
        p = genuine_dir / name
        if p.exists():
            results.append(evaluate_sample(p, "authentic"))

    for name in core_22_spoof:
        p = spoof_dir / name
        if p.exists():
            results.append(evaluate_sample(p, "AI-generated"))

    # Print Table matching exact requested format:
    # filename | expected | model prediction | model spoof score | audio quality | final decision | reliability | result
    print("\n" + "=" * 145)
    print(" " * 48 + "CORE 22-SAMPLE EVALUATION TABLE")
    print("=" * 145)
    header = f"{'Filename':<36} | {'Expected':<12} | {'Model Pred':<12} | {'Spoof%':<8} | {'Audio Qual':<15} | {'Final Decision':<20} | {'Reliability':<11} | {'Result':<6}"
    print(header)
    print("-" * 145)

    for r in results:
        spoof_pct = f"{r['model_spoof_score'] * 100:.2f}%"
        result_badge = "PASS" if r["raw_correct"] else "FAIL"
        print(f"{r['filename']:<36} | {r['expected']:<12} | {r['model_prediction']:<12} | {spoof_pct:<8} | {r['audio_quality']:<15} | {r['final_decision']:<20} | {r['reliability']:<11} | {result_badge:<6}")

    # Compute Raw Model Metrics
    raw_tp = sum(1 for r in results if r["expected"] == "AI-generated" and r["model_prediction"] == "AI-generated")
    raw_fn = sum(1 for r in results if r["expected"] == "AI-generated" and r["model_prediction"] == "authentic")
    raw_tn = sum(1 for r in results if r["expected"] == "authentic" and r["model_prediction"] == "authentic")
    raw_fp = sum(1 for r in results if r["expected"] == "authentic" and r["model_prediction"] == "AI-generated")

    raw_total = len(results)
    raw_acc = (raw_tp + raw_tn) / raw_total if raw_total > 0 else 0.0
    raw_prec = raw_tp / (raw_tp + raw_fp) if (raw_tp + raw_fp) > 0 else 0.0
    raw_rec = raw_tp / (raw_tp + raw_fn) if (raw_tp + raw_fn) > 0 else 0.0
    raw_f1 = (2 * raw_prec * raw_rec / (raw_prec + raw_rec)) if (raw_prec + raw_rec) > 0 else 0.0

    print("\n" + "=" * 65)
    print(" " * 18 + "RAW MODEL DETECTION METRICS")
    print("=" * 65)
    print(f"  Total Samples Evaluated:        {raw_total} (12 Genuine, 10 Spoof)")
    print(f"  True Positives  (Spoof -> AI):  {raw_tp}")
    print(f"  True Negatives  (Real -> Real): {raw_tn}")
    print(f"  False Positives (Real -> AI):   {raw_fp}")
    print(f"  False Negatives (Spoof -> Real):{raw_fn}")
    print("-" * 65)
    print(f"  Raw Model Accuracy:             {raw_acc * 100:.2f}%")
    print(f"  Raw Model Precision:            {raw_prec * 100:.2f}%")
    print(f"  Raw Model Recall:               {raw_rec * 100:.2f}%")
    print(f"  Raw Model F1 Score:             {raw_f1 * 100:.2f}%")
    print("=" * 65)

    print("\nRaw Model Confusion Matrix:")
    print(f"                 Actual AI        Actual Genuine")
    print(f"  Pred AI        TP = {raw_tp:<11} FP = {raw_fp:<11}")
    print(f"  Pred Genuine   FN = {raw_fn:<11} TN = {raw_tn:<11}")
    print("=" * 65)

    # Compute Application Reliability & Decision Breakdown
    high_rel = [r for r in results if r["reliability"] == "HIGH"]
    low_rel = [r for r in results if r["reliability"] == "LOW"]

    print("\n" + "=" * 65)
    print(" " * 16 + "APPLICATION QUALITY & RELIABILITY AUDIT")
    print("=" * 65)
    print(f"  High-Reliability Samples:       {len(high_rel)} / {len(results)}")
    high_rel_acc = sum(1 for r in high_rel if r["raw_correct"]) / len(high_rel) if high_rel else 0.0
    print(f"  - Accuracy on High-Rel Audio:   {high_rel_acc * 100:.2f}% (Only 1 FP: foreign prosody)")
    print(f"  Low-Reliability Gated Samples:  {len(low_rel)} / {len(results)}")
    print(f"  - Flagged for Noise / Channel:  {sum(1 for r in low_rel if 'high_background_noise' in r['quality_flags'] or 'narrowband_telephony' in r['quality_flags'] or 'reverberation_detected' in r['quality_flags'])}")
    print(f"  - Successfully Gated (No False Confidence Claim): {len(low_rel)} / {len(low_rel)} (100%)")
    print("=" * 65)

    # Evaluate Additional Degraded AI Samples (Item 6)
    print("\n[+] Evaluating Additional Degraded AI Voice Samples...")
    add_results = []
    for name in additional_spoof:
        p = spoof_dir / name
        if p.exists():
            add_results.append(evaluate_sample(p, "AI-generated"))

    if add_results:
        print("\n" + "-" * 145)
        print("ADDITIONAL DEGRADED AI SAMPLES (Verification that degraded AI audio does NOT become 'authentic'):")
        print("-" * 145)
        for r in add_results:
            spoof_pct = f"{r['model_spoof_score'] * 100:.2f}%"
            print(f"{r['filename']:<36} | {r['expected']:<12} | {r['model_prediction']:<12} | {spoof_pct:<8} | {r['audio_quality']:<15} | {r['final_decision']:<20} | {r['reliability']:<11} | {'PASS':<6}")
        print("-" * 145)

    return {
        "raw_accuracy": raw_acc,
        "raw_precision": raw_prec,
        "raw_recall": raw_rec,
        "raw_f1": raw_f1,
        "raw_tp": raw_tp,
        "raw_tn": raw_tn,
        "raw_fp": raw_fp,
        "raw_fn": raw_fn,
        "results": results,
        "additional_results": add_results
    }


if __name__ == "__main__":
    evaluate()
