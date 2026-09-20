import os
import certifi
from contextlib import asynccontextmanager
import logging

# Ensure SSL certificates are properly located for Hugging Face and requests
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

logger = logging.getLogger("echosentinel.api")

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from audio_processor import decode_and_preprocess_audio, MAX_FILE_SIZE_BYTES
from audio_quality import analyze_audio_quality, determine_application_decision
from model import VoiceCloneDetector

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Warm up AI detector model
    logger.info("Initializing EchoSentinel AI Model on startup...")
    detector = VoiceCloneDetector.get_instance()
    try:
        detector.load_model()
        logger.info(f"Model loaded successfully on device: {detector.device}")
    except Exception as e:
        logger.error(f"Failed to load AI model on startup: {e}")
    yield
    # Shutdown logic
    logger.info("Shutting down EchoSentinel API server...")

app = FastAPI(
    title="EchoSentinel API",
    description="AI-Powered Real-Time Voice-Cloning Detection and Prevention Prototype API",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS with origin normalization (strip whitespace and trailing slashes)
raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
allowed_origins = set()
for o in raw_origins:
    cleaned = o.strip().rstrip("/")
    if cleaned:
        allowed_origins.add(cleaned)

# Always permit standard local development origins
allowed_origins.add("http://localhost:3000")
allowed_origins.add("http://127.0.0.1:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DetectResponse(BaseModel):
    prediction: str  # Final application prediction: "authentic", "AI-generated", "Possible spoof"
    raw_model_prediction: Optional[str] = None  # Raw model output: "authentic" or "AI-generated"
    confidence: float
    model_spoof_score: Optional[float] = None  # Raw model probability of spoof (0.0 to 1.0)
    risk_score: int  # 0 - 100
    risk_level: str  # "Low", "Suspicious", "High", "Critical"
    audio_quality_score: Optional[int] = 100  # 10 - 100
    audio_quality_rating: Optional[str] = "good"  # "good", "fair", "poor", "degraded"
    detection_reliability: Optional[str] = "HIGH"  # "HIGH", "MEDIUM", "LOW"
    reliability_label: Optional[str] = "High"
    quality_flags: Optional[List[str]] = []
    quality_warning: Optional[str] = None
    processing_time_ms: Optional[float] = None
    model_source: Optional[str] = "wav2vec2-deepfake"
    notice: Optional[str] = "Detection is probabilistic, not certain."
    status: Optional[str] = "analyzed"

@app.get("/")
def read_root():
    detector = VoiceCloneDetector.get_instance()
    return {
        "status": "ok" if detector.is_loaded else "degraded",
        "service": "EchoSentinel API",
        "model_loaded": detector.is_loaded,
        "model_id": detector.model_id,
        "notice": "Detection is probabilistic, not certain."
    }

@app.get("/health")
def health_check(response: Response):
    detector = VoiceCloneDetector.get_instance()
    if not detector.is_loaded:
        response.status_code = 503
        return {
            "status": "unavailable",
            "version": "1.0.0",
            "model_loaded": False,
            "error": detector.load_error or "AI model is initializing or failed to load.",
            "disclaimer": "Detection is probabilistic, not certain. Does not prove speaker identity."
        }
    return {
        "status": "healthy",
        "version": "1.0.0",
        "model_loaded": True,
        "model_id": detector.model_id,
        "disclaimer": "Detection is probabilistic, not certain. Does not prove speaker identity."
    }

@app.post("/detect", response_model=DetectResponse)
async def detect_audio(
    file: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    simulate: Optional[str] = Query(None, description="Optional simulation flag: 'genuine' or 'clone'")
):
    """
    Receives an audio chunk (WAV, FLAC, OGG, MP3) via multipart/form-data.
    Accepts either 'file' or 'audio' form field name.
    Executes real Wav2Vec2 deepfake classification and converts output into
    model_spoof_score, risk_score (0-100), and risk_level (Low, Suspicious, High, Critical).
    """
    if simulate == "genuine":
        return DetectResponse(
            prediction="authentic",
            raw_model_prediction="authentic",
            confidence=0.93,
            model_spoof_score=0.07,
            risk_score=7,
            risk_level="Low",
            audio_quality_score=95,
            audio_quality_rating="good",
            detection_reliability="HIGH",
            reliability_label="High",
            quality_flags=[],
            quality_warning=None,
            processing_time_ms=10.0,
            model_source="demo_simulation",
            notice="Demo simulation: not real inference.",
            status="analyzed"
        )
    elif simulate == "clone":
        return DetectResponse(
            prediction="AI-generated",
            raw_model_prediction="AI-generated",
            confidence=0.88,
            model_spoof_score=0.88,
            risk_score=88,
            risk_level="Critical",
            audio_quality_score=95,
            audio_quality_rating="good",
            detection_reliability="HIGH",
            reliability_label="High",
            quality_flags=[],
            quality_warning=None,
            processing_time_ms=10.0,
            model_source="demo_simulation",
            notice="Demo simulation: not real inference.",
            status="analyzed"
        )

    upload_file = file or audio
    if not upload_file or not upload_file.filename:
        raise HTTPException(status_code=400, detail="No audio file provided.")

    try:
        content = await upload_file.read()
    except Exception as e:
        logger.error(f"Failed to read upload stream: {e}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded audio stream.")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    if len(content) > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Audio file size exceeds maximum allowed limit of {max_mb}MB."
        )

    # 1. Preprocess and decode audio to 16kHz mono float32 with native sample rate metadata
    try:
        waveform, orig_sr = decode_and_preprocess_audio(content, target_sr=16000, return_meta=True)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as err:
        logger.warning(f"Audio decode error: {err}")
        raise HTTPException(
            status_code=400,
            detail="Audio decoding failed. Please upload a standard WAV, FLAC, MP3, or OGG format."
        )

    # 2. Analyze acoustic channel quality & physical degradation
    quality_res = analyze_audio_quality(waveform, sample_rate=16000, native_sample_rate=orig_sr)

    # 3. Run real Wav2Vec2 inference
    detector = VoiceCloneDetector.get_instance()
    if not detector.is_loaded:
        try:
            detector.load_model()
        except Exception as load_err:
            logger.error(f"Model on-demand load failed: {load_err}")
            raise HTTPException(
                status_code=503,
                detail="AI inference engine is currently unavailable. Please retry in a moment."
            )

    try:
        raw_result = detector.predict(waveform, sample_rate=16000)
        decision = determine_application_decision(
            raw_result["prediction"],
            raw_result.get("model_spoof_score", 0.0),
            quality_res
        )

        return DetectResponse(
            prediction=decision["final_decision"],
            raw_model_prediction=raw_result["prediction"],
            confidence=raw_result["confidence"],
            model_spoof_score=raw_result.get("model_spoof_score"),
            risk_score=raw_result["risk_score"],
            risk_level=raw_result["risk_level"],
            audio_quality_score=quality_res["quality_score"],
            audio_quality_rating=quality_res["quality_rating"],
            detection_reliability=decision["detection_reliability"],
            reliability_label=decision["reliability_label"],
            quality_flags=quality_res["flags"],
            quality_warning=decision["quality_warning"],
            processing_time_ms=raw_result.get("processing_time_ms"),
            model_source=raw_result.get("model_source", "wav2vec2-deepfake"),
            notice="Detection is probabilistic, not certain. Does not prove speaker identity.",
            status=decision["status"]
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as model_err:
        logger.error(f"Inference exception: {model_err}")
        raise HTTPException(
            status_code=503,
            detail="AI inference engine encountered an unexpected error processing this audio."
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
