import io
import pytest
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from main import app
from model import VoiceCloneDetector

client = TestClient(app)

def make_test_wav(duration: float = 1.5, sr: int = 16000, freq: float = 440.0, silence: bool = False) -> bytes:
    buf = io.BytesIO()
    if silence:
        data = np.zeros(int(sr * duration), dtype=np.float32)
    else:
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        data = (0.35 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(buf, data, sr, format='WAV')
    return buf.getvalue()

def test_root_endpoint():
    response = client.get('/')
    assert response.status_code == 200
    data = response.json()
    assert 'service' in data
    assert 'model_loaded' in data

def test_health_endpoint_healthy():
    detector = VoiceCloneDetector.get_instance()
    detector.load_model()
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    assert data['model_loaded'] is True

def test_health_endpoint_unavailable_when_unloaded():
    detector = VoiceCloneDetector.get_instance()
    original_loaded = detector.is_loaded
    try:
        detector.is_loaded = False
        response = client.get('/health')
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'unavailable'
        assert data['model_loaded'] is False
    finally:
        detector.is_loaded = original_loaded

def test_detect_simulation_genuine():
    response = client.post('/detect?simulate=genuine')
    assert response.status_code == 200
    data = response.json()
    assert data['prediction'] == 'authentic'
    assert data['risk_level'] == 'Low'
    assert data['model_source'] == 'demo_simulation'

def test_detect_simulation_clone():
    response = client.post('/detect?simulate=clone')
    assert response.status_code == 200
    data = response.json()
    assert data['prediction'] == 'AI-generated'
    assert data['risk_level'] == 'Critical'
    assert data['risk_score'] >= 81

def test_detect_empty_file():
    files = {'file': ('empty.wav', b'', 'audio/wav')}
    response = client.post('/detect', files=files)
    assert response.status_code == 400
    assert 'empty' in response.json()['detail'].lower()

def test_detect_silent_audio():
    silent_wav = make_test_wav(duration=1.5, silence=True)
    files = {'file': ('silent.wav', silent_wav, 'audio/wav')}
    response = client.post('/detect', files=files)
    assert response.status_code == 400
    assert response.json()['detail'] == 'Audio does not contain enough meaningful speech for analysis.'

def test_detect_corrupted_audio():
    garbage = b'RIFF' + b'\xff\xfe\xfd\x00' * 150
    files = {'file': ('corrupt.wav', garbage, 'audio/wav')}
    response = client.post('/detect', files=files)
    assert response.status_code == 400
    assert any(w in response.json()['detail'].lower() for w in ['failed', 'decoding', 'invalid', 'corrupt'])

def test_detect_valid_audio():
    valid_wav = make_test_wav(duration=2.0)
    files = {'file': ('test.wav', valid_wav, 'audio/wav')}
    response = client.post('/detect', files=files)
    assert response.status_code == 200
    data = response.json()
    assert data['prediction'] in ['authentic', 'AI-generated', 'Possible spoof']
    assert data['raw_model_prediction'] in ['authentic', 'AI-generated']
    assert 0 <= data['risk_score'] <= 100
    assert data['risk_level'] in ['Low', 'Suspicious', 'High', 'Critical']
    assert 'model_spoof_score' in data
    assert 'confidence' in data
    assert 'audio_quality_score' in data
    assert 'detection_reliability' in data

def test_cors_headers():
    response = client.options(
        '/detect',
        headers={
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'POST',
        }
    )
    assert response.headers.get('access-control-allow-origin') == 'http://localhost:3000'
