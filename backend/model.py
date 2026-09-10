import os
import time
import logging
import torch
import numpy as np
from typing import Dict, Any, Optional
import certifi

# Ensure certificates are set
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

logger = logging.getLogger("echosentinel.model")
DEFAULT_MODEL_ID = os.getenv("MODEL_ID", "HyperMoon/wav2vec2-base-960h-finetuned-deepfake")
DEVICE = os.getenv("DEVICE", "cpu")

def calculate_risk_level(risk_score: int) -> str:
    """
    Computes risk level based on EXACT hackathon risk bands:
    0–30: Low
    31–60: Suspicious
    61–80: High
    81–100: Critical
    """
    if risk_score <= 30:
        return "Low"
    elif risk_score <= 60:
        return "Suspicious"
    elif risk_score <= 80:
        return "High"
    else:
        return "Critical"

class VoiceCloneDetector:
    _instance: Optional["VoiceCloneDetector"] = None

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, device: str = DEVICE):
        self.model_id = model_id
        self.device = torch.device(device)
        self.model = None
        self.feature_extractor = None
        self.is_loaded = False
        self.load_error: Optional[str] = None
        self.target_sr = 16000

    @classmethod
    def get_instance(cls) -> "VoiceCloneDetector":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self):
        """Loads pretrained Wav2Vec2 classifier once."""
        if self.is_loaded:
            return

        from transformers import AutoFeatureExtractor
        try:
            from transformers import AutoModelForAudioClassification as ModelClass
        except ImportError:
            from transformers import Wav2Vec2ForSequenceClassification as ModelClass

        try:
            logger.info(f"Loading pretrained Wav2Vec2 model: {self.model_id} on {self.device}...")
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(self.model_id)
            try:
                self.model = ModelClass.from_pretrained(self.model_id)
            except Exception:
                from transformers import Wav2Vec2ForSequenceClassification
                self.model = Wav2Vec2ForSequenceClassification.from_pretrained(self.model_id)

            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            logger.info(f"Pretrained Wav2Vec2 deepfake detector loaded successfully. id2label: {self.model.config.id2label}")
        except Exception as e:
            self.load_error = str(e)
            logger.error(f"Failed to load pretrained model '{self.model_id}': {e}", exc_info=True)
            self.is_loaded = False

    def predict(self, audio_waveform: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Runs model inference on preprocessed 16kHz mono audio waveform.
        Returns:
            {
                "prediction": "authentic" | "AI-generated",
                "confidence": float,
                "risk_score": int (0-100),
                "risk_level": "Low" | "Suspicious" | "High" | "Critical",
                "processing_time_ms": float,
                "model_source": str
            }
        """
        start_time = time.perf_counter()

        if not self.is_loaded:
            self.load_model()

        if not self.is_loaded or self.model is None:
            # If real model cannot be loaded, report explicit error without crashing
            raise RuntimeError(f"Pretrained model is not loaded: {self.load_error or 'Unknown error'}")

        # Ensure input is float32 numpy 1D array
        if audio_waveform.ndim > 1:
            audio_waveform = audio_waveform.squeeze()

        # Minimum audio length safety check (at least 0.2s of audio)
        min_samples = int(0.2 * sample_rate)
        if len(audio_waveform) < min_samples:
            # Pad with silence if slightly too short
            padded = np.zeros(min_samples, dtype=np.float32)
            padded[:len(audio_waveform)] = audio_waveform
            audio_waveform = padded

        # Extract features using Wav2Vec2FeatureExtractor
        inputs = self.feature_extractor(
            audio_waveform,
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True
        )

        input_values = inputs.input_values.to(self.device)
        attention_mask = inputs.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        with torch.no_grad():
            if attention_mask is not None:
                outputs = self.model(input_values, attention_mask=attention_mask)
            else:
                outputs = self.model(input_values)
            
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()

        # Dynamically map labels from model config (do not hardcode label indices)
        id2label = {int(k): str(v).lower() for k, v in self.model.config.id2label.items()}
        bonafide_idx = None
        spoof_idx = None

        for idx, name in id2label.items():
            if any(term in name for term in ["bonafide", "real", "authentic", "genuine"]):
                bonafide_idx = idx
            elif any(term in name for term in ["spoof", "fake", "clone", "synthetic", "generated"]):
                spoof_idx = idx

        if bonafide_idx is None:
            bonafide_idx = 0
        if spoof_idx is None:
            spoof_idx = 1 if len(id2label) > 1 else 0

        # Extract probabilities
        if probabilities.ndim == 0:
            prob_spoof = float(probabilities)
            prob_bonafide = 1.0 - prob_spoof
        else:
            prob_bonafide = float(probabilities[bonafide_idx])
            prob_spoof = float(probabilities[spoof_idx])

        # Convert to prediction and confidence
        if prob_spoof >= 0.50:
            prediction = "AI-generated"
            confidence = round(prob_spoof, 4)
        else:
            prediction = "authentic"
            confidence = round(prob_bonafide, 4)

        # Risk score calculation (0 to 100 based on spoof likelihood)
        raw_risk = prob_spoof * 100.0
        risk_score = max(0, min(100, int(round(raw_risk))))
        risk_level = calculate_risk_level(risk_score)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "prediction": prediction,
            "confidence": confidence,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "processing_time_ms": elapsed_ms,
            "model_source": "wav2vec2-deepfake-pretrained"
        }
