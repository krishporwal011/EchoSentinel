import os
import certifi

# Ensure SSL certificates are properly located for Hugging Face and requests on macOS
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="EchoSentinel API",
    description="AI-Powered Real-Time Voice-Cloning Detection and Prevention Prototype API",
    version="1.0.0",
)

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from audio_processor import decode_and_preprocess_audio
from model import VoiceCloneDetector, calculate_risk_level

class DetectResponse(BaseModel):
    prediction: str  # "authentic" or "AI-generated"
    confidence: float
    risk_score: int  # 0 - 100
    risk_level: str  # "Low", "Suspicious", "High", "Critical"
    processing_time_ms: Optional[float] = None
    model_source: Optional[str] = "wav2vec2-deepfake"
    notice: Optional[str] = "Detection is probabilistic, not certain."

@app.on_event("startup")
def startup_event():
    # Warm up / lazy load model in background or on first call
    try:
        detector = VoiceCloneDetector.get_instance()
        # Trigger background initialization
        detector.load_model()
    except Exception as e:
        print(f"Model startup notice: {e}")

@app.get("/")
def read_root():
    detector = VoiceCloneDetector.get_instance()
    return {
        "status": "ok",
        "service": "EchoSentinel API",
        "model_loaded": detector.is_loaded,
        "model_id": detector.model_id,
        "notice": "Detection is probabilistic, not certain."
    }

@app.get("/health")
def health_check():
    detector = VoiceCloneDetector.get_instance()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "model_loaded": detector.is_loaded,
        "disclaimer": "Detection is probabilistic, not certain. Does not prove speaker identity."
    }

@app.post("/detect", response_model=DetectResponse)
async def detect_audio(
    file: UploadFile = File(...),
    simulate: Optional[str] = Query(None, description="Optional simulation flag: 'genuine' or 'clone'")
):
    """
    Receives an audio chunk (WAV, FLAC, OGG, MP3) via multipart/form-data.
    Executes real Wav2Vec2 deepfake classification and converts output into
    risk_score (0-100) and risk_level (Low, Suspicious, High, Critical).
    """
    if simulate == "genuine":
        return DetectResponse(
            prediction="authentic",
            confidence=0.93,
            risk_score=12,
            risk_level="Low",
            processing_time_ms=10.0,
            model_source="demo_simulation",
            notice="Demo simulation: not real inference."
        )
    elif simulate == "clone":
        return DetectResponse(
            prediction="AI-generated",
            confidence=0.88,
            risk_score=88,
            risk_level="Critical",
            processing_time_ms=10.0,
            model_source="demo_simulation",
            notice="Demo simulation: not real inference."
        )

    if not file:
        raise HTTPException(status_code=400, detail="No audio file provided.")

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty.")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to read uploaded audio stream.")

    # 1. Preprocess and decode audio to 16kHz mono float32
    try:
        waveform = decode_and_preprocess_audio(content, target_sr=16000)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=400, detail="Audio decoding failed. Please upload a standard WAV, FLAC, or OGG format.")

    # 2. Run real Wav2Vec2 inference
    detector = VoiceCloneDetector.get_instance()
    try:
        result = detector.predict(waveform, sample_rate=16000)
        return DetectResponse(
            prediction=result["prediction"],
            confidence=result["confidence"],
            risk_score=result["risk_score"],
            risk_level=result["risk_level"],
            processing_time_ms=result.get("processing_time_ms"),
            model_source=result.get("model_source", "wav2vec2-deepfake"),
            notice="Detection is probabilistic, not certain."
        )
    except Exception as model_err:
        # Graceful fallback if model is still downloading or initializing
        print(f"Inference exception: {model_err}")
        raise HTTPException(
            status_code=503,
            detail="AI inference engine is currently initializing. Please retry in a few seconds."
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
