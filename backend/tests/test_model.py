import pytest
import numpy as np
from unittest.mock import MagicMock
from model import VoiceCloneDetector, calculate_risk_level, resolve_label_mapping

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
    assert resolve_label_mapping({'0': 'bonafide', '1': 'spoof'}) == {'bonafide': 0, 'spoof': 1}

def test_label_mapping_resolution_inverted():
    assert resolve_label_mapping({'0': 'spoof', '1': 'bonafide'}) == {'bonafide': 1, 'spoof': 0}

def test_label_mapping_fails_on_unknown():
    with pytest.raises(RuntimeError, match='Cannot safely determine label mapping'):
        resolve_label_mapping({'0': 'class_a', '1': 'class_b'})

def test_label_mapping_rejects_more_than_two_classes():
    with pytest.raises(RuntimeError, match='exactly two'):
        resolve_label_mapping({'0': 'bonafide', '1': 'spoof', '2': 'noise'})

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
