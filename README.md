# EchoSentinel

> **Real-Time Voice Safety — AI-Powered Voice Cloning Detection & Prevention Prototype**

---

## 1. Problem Statement

Recent advances in generative voice synthesis, neural audio codecs, and zero-shot voice cloning allow malicious actors to replicate an individual's unique vocal timbre from just a few seconds of audio. This enables high-impact impersonation attacks targeting executive fraud, emergency authorization fraud, familial scam calls, and social engineering.

**Problem Statement:**
> *"AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks."*

Traditional defenses rely on post-call forensic audits or manual verification callbacks after damage has occurred. **EchoSentinel** introduces a real-time safety layer that continuously evaluates acoustic speech characteristics directly from live audio streams or uploaded recordings, flags synthetic speech signatures, calculates a transparent risk score, and intervenes with an immediate **Identity Verification** safeguard before sensitive flows can proceed.

---

## 2. What EchoSentinel Does

1. **Continuous Audio Capture:** Captures live microphone input via the Web Audio API or ingests uploaded audio clips.
2. **Dynamic Audio Chunking:** Seamlessly slices incoming speech into 2.5–3.0 second audio chunks, formatted as standard 16 kHz mono WAV blobs.
3. **Acoustic Preprocessing:** Normalizes amplitudes, handles multi-channel downmixing, and prepares feature tensors.
4. **Pretrained Wav2Vec2 Inference:** Runs an anti-spoofing transformer classifier (`HyperMoon/wav2vec2-base-960h-finetuned-deepfake`) trained on the ASVspoof dataset to detect synthetic artifacts.
5. **Risk Engine Scoring:** Maps bonafide vs. spoof probabilities into a calibrated 0–100 risk score and strict threat bands.
6. **Active Prevention Layer:** If risk enters the **High** (61–80) or **Critical** (81–100) band, sensitive actions are immediately blocked, and an **Identity Verification** challenge phrase modal is triggered.

---

## 3. Architecture

```
[ Microphone Input / Uploaded Clip ]
                 │
                 ▼
     [ Web Audio API Chunker ]
  (16 kHz Mono PCM, 2.5s Chunks)
                 │
                 ▼ HTTP POST (multipart/form-data)
     [ FastAPI: /detect Endpoint ]
                 │
                 ▼
      [ Audio Preprocessor ]
(soundfile / librosa resampling & normalization)
                 │
                 ▼
 [ Pretrained Wav2Vec2 Classifier ]
 (HyperMoon/wav2vec2-base-960h-finetuned-deepfake)
                 │
                 ▼
      [ Threat Risk Engine ]
  (0-30 Low | 31-60 Suspicious | 61-80 High | 81-100 Critical)
                 │
        ┌────────┴────────┐
        ▼                 ▼
   [ Low / Suspicious ]   [ High / Critical ]
        │                       │
   (Continue Flow)        (Show Warning Banner)
                                │
                                ▼
                   [ Identity Verification Modal ]
                     (Dynamic Challenge Phrase)
                                │
                      ┌─────────┴─────────┐
                      ▼                   ▼
             [ "I passed" ]         [ "Fail/Block" ]
                      │                   │
                (Unblock / Continue)  (Remain Blocked)
```

---

## 4. Technology Stack

### Frontend
- **Framework:** Next.js (App Router, React 19)
- **Language:** TypeScript
- **Styling:** Modern Vanilla CSS + Tailwind tokens (Cyber-defense dark operations UI)
- **Audio Capture:** Web Audio API (`AudioContext`, `AnalyserNode`, `ScriptProcessorNode`)
- **Visualizer:** 60 FPS HTML5 Canvas time-domain waveform
- **Icons:** Lucide React

### Backend
- **Framework:** FastAPI
- **Server:** Uvicorn (ASGI)
- **Language:** Python 3.13 (macOS arm64 compatible)
- **Validation:** Pydantic v2

### AI & Audio Processing
- **Deep Learning:** PyTorch (`torch.no_grad()`, `AutoModelForAudioClassification`)
- **Transformers:** Hugging Face Transformers (`AutoFeatureExtractor`, `Wav2Vec2`)
- **Pretrained Checkpoint:** `HyperMoon/wav2vec2-base-960h-finetuned-deepfake`
- **Audio I/O:** `soundfile`, `librosa`, `numpy`

---

## 5. Folder Structure

```
EchoSentinel/
├── README.md                   # Project documentation & architecture
├── .gitignore                  # Git ignore rules for node, python, checkpoints
│
├── frontend/                   # Next.js TypeScript web application
│   ├── package.json
│   ├── tsconfig.json
│   ├── .env.example
│   └── src/
│       ├── app/
│       │   ├── page.tsx        # Master dashboard & telemetry UI
│       │   ├── layout.tsx      # Root layout & security headers
│       │   └── globals.css     # Cyber-defense dark aesthetic & glow utilities
│       ├── components/
│       │   ├── WaveformCanvas.tsx      # 60fps HTML5 Canvas waveform
│       │   ├── RiskMeter.tsx           # 0-100 threat gauge with 4 risk bands
│       │   ├── VerificationModal.tsx   # Identity challenge prevention modal
│       │   └── DemoControls.tsx        # Interactive demo scenario simulation
│       └── lib/
│           └── audioRecorder.ts        # Web Audio API streaming & WAV chunker
│
└── backend/                    # FastAPI backend & AI inference pipeline
    ├── main.py                 # FastAPI endpoints, CORS, /detect handler
    ├── model.py                # Pretrained Wav2Vec2 model loader & inference singleton
    ├── audio_processor.py      # Audio decode, 16kHz resampling & normalization
    ├── test_inference.py       # Automated inference unit test
    ├── requirements.txt        # Pinned Python dependencies
    ├── .env.example            # Backend environment variables
    └── models/
        └── .gitkeep            # Local checkpoint storage
```

---

## 6. Setup & Installation

### Prerequisites
- macOS (Apple Silicon or Intel), Linux, or Windows
- Node.js `v20+` or `v24+`
- Python `3.10+` through `3.13+`

### Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Verify inference pipeline with the automated test:
   ```bash
   python test_inference.py
   ```

### Frontend Setup
1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```

---

## 7. How to Run

### Start the Backend Server
From the `backend` directory (with virtualenv activated):
```bash
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```
- Backend API Root: `http://localhost:8000/`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### Start the Frontend Application
From the `frontend` directory:
```bash
npm run dev -- -p 3000
```
- Frontend Web App: `http://localhost:3000`

---

## 8. `/detect` API Specification

### Endpoint: `POST /detect`
Accepts multipart form-data audio upload.

**Request:**
- Content-Type: `multipart/form-data`
- Body Parameter: `file` (WAV, FLAC, OGG, or MP3 binary audio stream)
- Query Parameter (Optional): `simulate=genuine` or `simulate=clone` (for demo simulation)

**Response Schema:**
```json
{
  "prediction": "authentic",
  "confidence": 0.93,
  "risk_score": 12,
  "risk_level": "Low",
  "processing_time_ms": 1402.52,
  "model_source": "wav2vec2-deepfake-pretrained",
  "notice": "Detection is probabilistic, not certain."
}
```

The API contract strictly guarantees the four core fields:
- `prediction`: `"authentic"` or `"AI-generated"`
- `confidence`: Float between `0.0` and `1.0`
- `risk_score`: Integer between `0` and `100`
- `risk_level`: String corresponding to the active risk band

---

## 9. Risk Bands

EchoSentinel uses calibrated risk bands to drive automated alerts and safeguards:

| Risk Score Band | Level | Indicator | Action Taken |
|---|---|:---:|---|
| **0 – 30** | **Low** | 🟢 | Voice shows authentic speech dynamics. Session continues normally. |
| **31 – 60** | **Suspicious** | 🟡 | Ambiguous acoustic artifacts detected. Logged for telemetry. |
| **61 – 80** | **High** | 🟠 | High likelihood of synthetic/cloned speech. Warning shown & verification triggered. |
| **81 – 100** | **Critical** | 🔴 | Definitive synthetic markers identified. Sensitive action blocked immediately. |

---

## 10. Demo Story & Demo Mode

For evaluation and hackathon presentations without requiring an active impersonation attack, EchoSentinel includes an interactive **Demo Mode** clearly marked with `DEMO SIMULATION ACTIVE`.

### Demo Story Flow:
1. Open EchoSentinel at `http://localhost:3000`.
2. Toggle **Demo Mode** on in the Interactive Demo Showcase card.
3. Click **1. Genuine Voice Sample**:
   - Audio feedback tone plays.
   - Dashboard evaluates: `Likely Authentic — 93% — LOW RISK 🟢`.
   - Flow status remains: `FLOW READY`.
4. Click **2. AI Cloned Voice Sample**:
   - Synthetic chirp feedback plays.
   - Dashboard evaluates: `Possible Voice Clone — 88% — CRITICAL RISK 🔴`.
   - Threat banner warns: *"This voice shows characteristics associated with synthetic or cloned speech."*
   - **Identity Verification Screen** automatically pops up with a dynamic challenge phrase (e.g., *"My secure phrase is 47 Blue Mango"*).
5. Verification Test:
   - Click **"I passed the check (Continue)"** ➔ Flow unblocks to `VERIFIED • CONTINUED`.
   - Re-test and click **"Fail / Block"** ➔ Flow remains `FLOW BLOCKED` with warning: *"Sensitive action blocked until identity verification is completed."*

---

## 11. AI Model Configuration

The model pipeline is encapsulated in [`backend/model.py`](file:///Users/tanyaporwal/Documents/EchoSentinel/backend/model.py):
- **Model Checkpoint:** `HyperMoon/wav2vec2-base-960h-finetuned-deepfake`
- **Model Architecture:** `Wav2Vec2ForSequenceClassification`
- **Dataset:** ASVspoof 2019 (Bonafide vs. Spoof)
- **Inference Mode:** Evaluated on CPU or MPS/CUDA via `torch.no_grad()`
- **Singleton Loader:** Model weights (~378 MB) are cached locally and loaded once at startup to prevent latency overhead on incoming chunks.

---

## 12. Important Honest Limitations

EchoSentinel is a hackathon prototype designed to demonstrate real-time acoustic spoof detection and automated step-up identity challenge guardrails.

**Honest Disclaimers:**
- **Probabilistic, Not Certain:** Detection results identify acoustic patterns associated with genuine vs. synthetic speech; they do *not* mathematically prove identity.
- **No Identity Proof:** The model does *not* verify that a voice belongs to a specific human individual (speaker verification vs. anti-spoofing).
- **No Telephony Interception:** EchoSentinel runs in modern browsers and client applications; it does *not* tap into cellular carrier infrastructure, SS7, or SIM cards.
- **No Government ID / Biometric Replacement:** The step-up challenge in this prototype is an illustrative prevention pattern and does not replace bank-grade fraud infrastructure or government ID validation.
- **Always Use:** *"Likely Authentic"* and *"Possible Voice Clone"* — never *"100% Authentic"* or *"100% Fake"*.