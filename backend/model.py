import os
import time
import logging
import threading
import torch
import numpy as np
from typing import Dict, Any, Optional
import certifi

# Ensure certificates are set
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

logger = logging.getLogger("echosentinel.model")
DEFAULT_MODEL_ID = os.getenv("MODEL_ID", "HyperMoon/wav2vec2-base-960h-finetuned-deepfake")

# Select device: use CUDA if available unless overridden
def get_default_device() -> str:
    env_device = os.getenv("DEVICE")
    if env_device:
        return env_device
    return "cuda" if torch.cuda.is_available() else "cpu"

DEVICE = get_default_device()

def calculate_risk_level(risk_score: int) -> str:
    """
    Computes risk level based on calibrated threat bands:
    - 0–30: Low risk (Authentic speech patterns, minimal artifact signature)
    - 31–60: Suspicious (Elevated acoustic distortion or minor neural vocoder signatures)
    - 61–80: High (Strong deepfake signatures, trigger warning gate)
    - 81–100: Critical (Definitive synthetic/neural clone match, require step-up verification)
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
    _init_lock = threading.Lock()

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, device: str = DEVICE):
        self.model_id = model_id
        self.device = torch.device(device)
        self.model = None
        self.feature_extractor = None
        self.is_loaded = False
        self.load_error: Optional[str] = None
        self.target_sr = 16000
        self.bonafide_idx: Optional[int] = None
        self.spoof_idx: Optional[int] = None
        self.label_mapping: Dict[str, int] = {}
        self._load_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "VoiceCloneDetector":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load_model(self):
        """
        Loads pretrained Wav2Vec2 classifier once in a thread-safe manner.
        Determines and validates the exact bonafide and spoof label indices
        from the model's configuration without assuming a hardcoded mapping.
        """
        if self.is_loaded:
            return

        with self._load_lock:
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

                # Phase 2: Inspect Hugging Face model config and determine ACTUAL label mapping
                # Fail clearly if mapping cannot be determined safely. Never assume 0=bonafide, 1=spoof.
                if not hasattr(self.model.config, "id2label") or not self.model.config.id2label:
                    raise RuntimeError(
                        f"Model '{self.model_id}' configuration is missing 'id2label' mapping. "
                        "Cannot safely determine classification classes without explicit labels."
                    )

                raw_id2label = {int(k): str(v).strip().lower() for k, v in self.model.config.id2label.items()}
                logger.info(f"Model raw id2label mapping: {raw_id2label}")

                bonafide_candidates = []
                spoof_candidates = []

                for idx, label_str in raw_id2label.items():
                    if any(term in label_str for term in ["bonafide", "real", "authentic", "genuine", "human"]):
                        bonafide_candidates.append(idx)
                    elif any(term in label_str for term in ["spoof", "fake", "clone", "synthetic", "generated", "deepfake"]):
                        spoof_candidates.append(idx)

                if len(bonafide_candidates) != 1 or len(spoof_candidates) != 1:
                    raise RuntimeError(
                        f"Cannot safely determine label mapping from model config id2label: {raw_id2label}. "
                        f"Found bonafide candidates {bonafide_candidates}, spoof candidates {spoof_candidates}. "
                        "Refusing to proceed to avoid accidental label inversion."
                    )

                if bonafide_candidates[0] == spoof_candidates[0]:
                    raise RuntimeError(
                        f"Ambiguous label mapping: index {bonafide_candidates[0]} matched both authentic and spoof terms."
                    )

                self.bonafide_idx = bonafide_candidates[0]
                self.spoof_idx = spoof_candidates[0]
                self.label_mapping = {
                    "bonafide": self.bonafide_idx,
                    "spoof": self.spoof_idx,
                }

                self.is_loaded = True
                self.load_error = None
                logger.info(
                    f"Pretrained Wav2Vec2 deepfake detector loaded successfully. "
                    f"Label mapping: bonafide(authentic)={self.bonafide_idx}, spoof(AI-generated)={self.spoof_idx}"
                )
            except Exception as e:
                self.load_error = str(e)
                self.is_loaded = False
                logger.error(f"Failed to load pretrained model '{self.model_id}': {e}", exc_info=True)
                raise

    def predict(self, audio_waveform: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Runs model inference on preprocessed 16kHz mono audio waveform.
        Returns:
            {
                "prediction": "authentic" | "AI-generated",
                "confidence": float,
                "model_spoof_score": float,
                "risk_score": int (0-100),
                "risk_level": "Low" | "Suspicious" | "High" | "Critical",
                "processing_time_ms": float,
                "model_source": str
            }
        """
        start_time = time.perf_counter()

        if not self.is_loaded:
            self.load_model()

        if not self.is_loaded or self.model is None or self.bonafide_idx is None or self.spoof_idx is None:
            raise RuntimeError(f"Pretrained model is not loaded: {self.load_error or 'Unknown error'}")

        # Ensure input is float32 numpy 1D array
        if not isinstance(audio_waveform, np.ndarray):
            audio_waveform = np.array(audio_waveform, dtype=np.float32)

        if audio_waveform.ndim > 1:
            audio_waveform = audio_waveform.squeeze()

        if not np.issubdtype(audio_waveform.dtype, np.floating):
            audio_waveform = audio_waveform.astype(np.float32)

        if not np.all(np.isfinite(audio_waveform)):
            raise ValueError("Audio waveform contains non-finite values (NaN or Inf).")

        # Minimum audio length safety check (at least 0.2s of audio)
        min_samples = int(0.2 * sample_rate)
        if len(audio_waveform) < min_samples:
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

        # Extract probabilities strictly based on verified label indices
        if probabilities.ndim == 0:
            prob_spoof = float(probabilities)
            prob_bonafide = 1.0 - prob_spoof
        else:
            prob_bonafide = float(probabilities[self.bonafide_idx])
            prob_spoof = float(probabilities[self.spoof_idx])

        # Convert to prediction and confidence
        if prob_spoof >= 0.50:
            prediction = "AI-generated"
            confidence = round(prob_spoof, 4)
        else:
            prediction = "authentic"
            confidence = round(prob_bonafide, 4)

        # Risk score calculation (0 to 100 based directly on spoof probability)
        raw_risk = prob_spoof * 100.0
        risk_score = max(0, min(100, int(round(raw_risk))))
        risk_level = calculate_risk_level(risk_score)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "prediction": prediction,
            "confidence": confidence,
            "model_spoof_score": round(prob_spoof, 4),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "processing_time_ms": elapsed_ms,
            "model_source": "wav2vec2-deepfake-pretrained"
        }
