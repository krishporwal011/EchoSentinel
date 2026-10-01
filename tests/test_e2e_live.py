"""
Comprehensive end-to-end integration test against live running backend and frontend servers.
Validates clean voice, AI voice, acoustic degradations, warnings, and web UI integration.
"""

import requests
import json
from pathlib import Path

def main():
    print("=" * 70)
    print("      ECHOSENTINEL COMPREHENSIVE LIVE END-TO-END TEST")
    print("=" * 70)

    # 1. Test Backend Root
    res_root = requests.get("http://127.0.0.1:8000/")
    print(f"[1] Root endpoint: HTTP {res_root.status_code}")
    assert res_root.status_code == 200

    # 2. Test Backend Health
    res_health = requests.get("http://127.0.0.1:8000/health")
    print(f"[2] Health endpoint: HTTP {res_health.status_code} -> model_loaded: {res_health.json().get('model_loaded')}")
    assert res_health.status_code == 200
    assert res_health.json()["model_loaded"] is True

    # 3. Test Backend CORS Headers
    res_cors = requests.options("http://127.0.0.1:8000/detect", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST"
    })
    allow_origin = res_cors.headers.get("access-control-allow-origin")
    print(f"[3] CORS preflight: HTTP {res_cors.status_code} -> Allow-Origin: {allow_origin}")
    assert allow_origin == "http://localhost:3000"

    # 4. Test Clean Genuine Voice (Heather)
    p_heather = Path("tests/audio/genuine/human_female_heather.wav")
    with open(p_heather, "rb") as f:
        res = requests.post("http://127.0.0.1:8000/detect", files={"file": ("heather.wav", f, "audio/wav")})
    d = res.json()
    print(f"\n[4] Clean Genuine Voice (Heather): HTTP {res.status_code}")
    print(f"    - Final Decision:      {d.get('prediction')}")
    print(f"    - Model Spoof Score:   {d.get('model_spoof_score')}")
    print(f"    - Audio Quality Score: {d.get('audio_quality_score')}/100 ({d.get('audio_quality_rating')})")
    print(f"    - Reliability:         {d.get('detection_reliability')}")
    print(f"    - Quality Warning:     {d.get('quality_warning')}")
    assert res.status_code == 200
    assert d.get("prediction") == "authentic"
    assert d.get("detection_reliability") == "HIGH"
    assert d.get("quality_warning") is None

    # 5. Test Clean AI Voice (Executive Transfer)
    p_ai = Path("tests/audio/spoof/ai_guy_executive_transfer.mp3")
    with open(p_ai, "rb") as f:
        res = requests.post("http://127.0.0.1:8000/detect", files={"file": ("guy.mp3", f, "audio/mpeg")})
    d = res.json()
    print(f"\n[5] Clean AI Voice (Executive Transfer): HTTP {res.status_code}")
    print(f"    - Final Decision:      {d.get('prediction')}")
    print(f"    - Model Spoof Score:   {d.get('model_spoof_score')}")
    print(f"    - Audio Quality Score: {d.get('audio_quality_score')}/100 ({d.get('audio_quality_rating')})")
    print(f"    - Reliability:         {d.get('detection_reliability')}")
    print(f"    - Risk Level:          {d.get('risk_level')}")
    assert res.status_code == 200
    assert d.get("prediction") == "AI-generated"
    assert d.get("detection_reliability") == "HIGH"
    assert d.get("risk_level") in ["High", "Critical"]

    # 6. Test Noisy Genuine Voice (SNR +15dB)
    p_noisy = Path("tests/audio/genuine/human_male_noisy_snr15db.wav")
    with open(p_noisy, "rb") as f:
        res = requests.post("http://127.0.0.1:8000/detect", files={"file": ("noisy.wav", f, "audio/wav")})
    d = res.json()
    print(f"\n[6] Noisy Genuine Voice (+15dB SNR): HTTP {res.status_code}")
    print(f"    - Final Decision:      {d.get('prediction')}")
    print(f"    - Raw Model Pred:      {d.get('raw_model_prediction')}")
    print(f"    - Audio Quality Score: {d.get('audio_quality_score')}/100 ({d.get('audio_quality_rating')})")
    print(f"    - Reliability:         {d.get('detection_reliability')}")
    print(f"    - Quality Warning:     {d.get('quality_warning')}")
    assert res.status_code == 200
    assert d.get("detection_reliability") == "LOW"
    assert d.get("prediction") == "Possible spoof"
    assert "background noise" in d.get("quality_warning", "").lower()

    # 7. Test Reverberant Genuine Voice (Room Reflections)
    p_rev = Path("tests/audio/genuine/human_female_reverberant_room.wav")
    with open(p_rev, "rb") as f:
        res = requests.post("http://127.0.0.1:8000/detect", files={"file": ("rev.wav", f, "audio/wav")})
    d = res.json()
    print(f"\n[7] Reverberant Genuine Voice (Echo): HTTP {res.status_code}")
    print(f"    - Final Decision:      {d.get('prediction')}")
    print(f"    - Audio Quality Score: {d.get('audio_quality_score')}/100 ({d.get('audio_quality_rating')})")
    print(f"    - Reliability:         {d.get('detection_reliability')}")
    print(f"    - Quality Warning:     {d.get('quality_warning')}")
    assert res.status_code == 200
    assert d.get("detection_reliability") == "LOW"
    assert d.get("prediction") == "Possible spoof"
    assert "reverberation" in d.get("quality_warning", "").lower()

    # 8. Test Telephone-Filtered Genuine Voice (8kHz Bandpass)
    p_phone = Path("tests/audio/genuine/human_male_phone_filtered_8k.wav")
    with open(p_phone, "rb") as f:
        res = requests.post("http://127.0.0.1:8000/detect", files={"file": ("phone.wav", f, "audio/wav")})
    d = res.json()
    print(f"\n[8] Telephone-Quality Genuine Voice (8kHz): HTTP {res.status_code}")
    print(f"    - Final Decision:      {d.get('prediction')}")
    print(f"    - Audio Quality Score: {d.get('audio_quality_score')}/100 ({d.get('audio_quality_rating')})")
    print(f"    - Reliability:         {d.get('detection_reliability')}")
    print(f"    - Quality Warning:     {d.get('quality_warning')}")
    assert res.status_code == 200
    assert d.get("detection_reliability") == "LOW"
    assert d.get("prediction") == "Possible spoof"
    assert "telephone" in d.get("quality_warning", "").lower()

    # 9. Test Degraded AI Voice (Verification that AI does not become "authentic")
    p_ai_noisy = Path("tests/audio/spoof/ai_guy_noisy_snr15db.wav")
    with open(p_ai_noisy, "rb") as f:
        res = requests.post("http://127.0.0.1:8000/detect", files={"file": ("ai_noisy.wav", f, "audio/wav")})
    d = res.json()
    print(f"\n[9] Degraded AI Voice (+15dB SNR): HTTP {res.status_code}")
    print(f"    - Final Decision:      {d.get('prediction')}")
    print(f"    - Reliability:         {d.get('detection_reliability')}")
    print(f"    - Quality Warning:     {d.get('quality_warning')}")
    assert res.status_code == 200
    assert d.get("prediction") != "authentic"
    assert d.get("prediction") == "Possible spoof"
    assert d.get("detection_reliability") == "LOW"

    # 10. Test Frontend Web Pages
    res_home = requests.get("http://localhost:3000/")
    res_detect = requests.get("http://localhost:3000/detection")
    res_verify = requests.get("http://localhost:3000/verification")
    print(f"\n[10] Frontend Home Page: HTTP {res_home.status_code}")
    print(f"[11] Frontend Detection Page: HTTP {res_detect.status_code}")
    print(f"[12] Frontend Verification Page: HTTP {res_verify.status_code}")
    assert res_home.status_code == 200
    assert res_detect.status_code == 200
    assert res_verify.status_code == 200

    print("\n" + "=" * 70)
    print("   ALL COMPREHENSIVE LIVE END-TO-END CHECKS PASSED (12/12)!")
    print("=" * 70)

if __name__ == "__main__":
    main()
