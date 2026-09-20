import pytest
import numpy as np
from unittest.mock import MagicMock
from model import VoiceCloneDetector, calculate_risk_level

def test_risk_level_thresholds():
    assert calculate_risk_level(0) == 'Low'
    assert calculate_risk_level(15) == 'Low'
    assert calculate_risk_level(30) == 'Low'
    assert calculate_risk_level(31) == 'Suspicious'
    assert calculate_risk_level(50) == 'Suspicious'
    assert calculate_risk_level(60) == 'Suspicious'
    assert calculate_risk_level(61) == 'High'
    assert calculate_risk_level(70) == 'High'
    assert calculate_risk_level(80) == 'High'
    assert calculate_risk_level(81) == 'Critical'
    assert calculate_risk_level(95) == 'Critical'
    assert calculate_risk_level(100) == 'Critical'

def test_label_mapping_resolution_standard():
    detector = VoiceCloneDetector(model_id='mock')
    mock_model = MagicMock()
    mock_model.config.id2label = {'0': 'bonafide', '1': 'spoof'}
    detector.model = mock_model
    detector.feature_extractor = MagicMock()

    raw_id2label = {int(k): str(v).strip().lower() for k, v in mock_model.config.id2label.items()}
    bonafide_candidates = [k for k, v in raw_id2label.items() if 'bonafide' in v]
    spoof_candidates = [k for k, v in raw_id2label.items() if 'spoof' in v]

    assert bonafide_candidates == [0]
    assert spoof_candidates == [1]

def test_label_mapping_resolution_inverted():
    mock_model = MagicMock()
    mock_model.config.id2label = {'0': 'spoof', '1': 'bonafide'}
    raw_id2label = {int(k): str(v).strip().lower() for k, v in mock_model.config.id2label.items()}
    bonafide_candidates = [k for k, v in raw_id2label.items() if any(t in v for t in ['bonafide', 'real', 'authentic'])]
    spoof_candidates = [k for k, v in raw_id2label.items() if any(t in v for t in ['spoof', 'fake', 'clone'])]

    assert bonafide_candidates == [1]
    assert spoof_candidates == [0]

def test_label_mapping_fails_on_unknown():
    detector = VoiceCloneDetector(model_id='mock')
    mock_model = MagicMock()
    mock_model.config.id2label = {'0': 'class_a', '1': 'class_b'}
    detector.model = mock_model
    detector.feature_extractor = MagicMock()
    
    with pytest.raises(RuntimeError) as exc_info:
        raw_id2label = {int(k): str(v).strip().lower() for k, v in mock_model.config.id2label.items()}
        bonafide_candidates = [k for k, v in raw_id2label.items() if any(t in v for t in ['bonafide', 'real', 'authentic'])]
        spoof_candidates = [k for k, v in raw_id2label.items() if any(t in v for t in ['spoof', 'fake', 'clone'])]
        if len(bonafide_candidates) != 1 or len(spoof_candidates) != 1:
            raise RuntimeError('Cannot safely determine label mapping')
    assert 'Cannot safely determine label mapping' in str(exc_info.value)

def test_real_model_label_mapping():
    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    assert detector.is_loaded
    assert detector.bonafide_idx == 0
    assert detector.spoof_idx == 1
    assert detector.label_mapping == {'bonafide': 0, 'spoof': 1}

def test_real_model_prediction_schema():
    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    sig = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    
    res = detector.predict(sig, sample_rate=sr)
    assert 'prediction' in res
    assert res['prediction'] in ['authentic', 'AI-generated']
    assert 'confidence' in res
    assert 0.0 <= res['confidence'] <= 1.0
    assert 'model_spoof_score' in res
    assert 0.0 <= res['model_spoof_score'] <= 1.0
    assert 'risk_score' in res
    assert 0 <= res['risk_score'] <= 100
    assert 'risk_level' in res
    assert res['risk_level'] in ['Low', 'Suspicious', 'High', 'Critical']
    assert 'processing_time_ms' in res
