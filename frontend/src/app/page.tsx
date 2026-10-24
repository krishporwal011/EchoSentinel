"use client";

import React, { useState, useRef, useCallback, useEffect, useReducer } from "react";
import { motion } from "framer-motion";
import { Mic, MicOff, Flame, Sparkles } from "lucide-react";
import { Preloader } from "../components/Preloader";
import { AudioLandscape } from "../components/AudioLandscape";
import { AudioWaveform } from "../components/AudioWaveform";
import { AnalysisPipeline } from "../components/AnalysisPipeline";
import { DetectionResult } from "../components/DetectionResult";
import { WarningPanel } from "../components/WarningPanel";
import { RiskMeter } from "../components/RiskMeter";
import { ScamIntentAnalysis } from "../components/ScamIntentAnalysis";
import { DemoMode } from "../components/DemoMode";
import { UploadAudio } from "../components/UploadAudio";
import { PageTransition } from "../components/PageTransition";
import { AudioStreamRecorder } from "../lib/audioRecorder";
import { createDemoResult, type DetectionResponse } from "../lib/detection";
import { detectionReducer, initialDetectionState } from "../lib/detectionState";
import { WORKFLOW_STEPS, HONEST_LIMITATIONS } from "../lib/content";
import { triggerUpcomingFeatureModal } from "../components/UpcomingFeatureModal";

const riskOf = (result: DetectionResponse | null): "Low" | "Suspicious" | "High" | "Critical" => {
  if (!result) return "Low";
  if (result.prediction.label === "likely_ai_generated") {
    const aiProb = result.prediction.ai_probability ?? 0;
    return aiProb >= 0.85 ? "Critical" : "High";
  }
  const level = result.prediction.risk_level;
  return level === "high" ? "High" : level === "medium" || level === "inconclusive" ? "Suspicious" : "Low";
};

export default function Home() {
  // Intro & Boot Stages
  const [showPreloader, setShowPreloader] = useState(true);

  // Live Audio Detection State
  const [isRecording, setIsRecording] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [detectionState, dispatch] = useReducer(detectionReducer, initialDetectionState);
  const { result, errorMessage, isAnalyzing } = detectionState;
  const [audioLevel, setAudioLevel] = useState(0);
  const [waveformData, setWaveformData] = useState<Uint8Array | null>(null);
  const [chunkCounter, setChunkCounter] = useState(1);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  // Demo Simulation State
  const [isDemoMode, setIsDemoMode] = useState(false);

  // References
  const recorderRef = useRef<AudioStreamRecorder | null>(null);
  const startAttemptRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const requestSeqRef = useRef<number>(0);

  const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const API_URL = rawApiUrl.replace(/\/+$/, "");

  useEffect(() => () => {
    startAttemptRef.current += 1;
    recorderRef.current?.stop();
    recorderRef.current = null;
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  // Keep the model output intact; smoothing probabilities would misrepresent inference.
  const handleDetectionData = useCallback(
    (data: DetectionResponse, seqId?: number, isLiveChunk: boolean = false) => {
      if (seqId === undefined) return;
      void isLiveChunk;
      dispatch({ type: "request_succeeded", requestId: seqId, result: data });

    },
    []
  );

  const sessionIdRef = useRef<string>(`session_${Date.now()}`);

  // Send an audio chunk to backend /detect with concurrency tracking
  const sendChunk = useCallback(
    async (blob: Blob, seqId: number) => {
      const requestId = ++requestSeqRef.current;
      dispatch({ type: "request_started", requestId });
      setChunkCounter(seqId);

      try {
        const formData = new FormData();
        formData.append("file", blob, `stream_${seqId}.wav`);
        formData.append("session_id", sessionIdRef.current);
        formData.append("sequence_id", String(seqId));

        const resp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
        if (!resp.ok) {
          const errorBody = await resp.json().catch(() => null);
          const detail = errorBody?.error?.message || errorBody?.detail || `HTTP ${resp.status}`;
          throw new Error(detail);
        }

        const data: DetectionResponse = { ...(await resp.json()), mode: "real" };
        handleDetectionData(data, requestId, true);
      } catch (err: unknown) {
        const error = err instanceof Error ? err : new Error(String(err));
        console.warn("Stream analysis notice:", error);
        dispatch({ type: "request_failed", requestId, message: error.message || "Live audio analysis failed." });
      } finally {
        // Reducer request IDs prevent older chunk completions from changing current state.
      }
    },
    [API_URL, handleDetectionData]
  );

  // Start Live Detection via Web Audio API Chunker
  const handleStartDetection = async () => {
    if (isRecording || isStarting) return;
    setIsStarting(true);
    setRecordingSeconds(0);
    sessionIdRef.current = `session_${Date.now()}`;

    try {
      recorderRef.current = new AudioStreamRecorder({
        chunkIntervalMs: 2500,
        onChunk: (blob: Blob, seqId: number) => {
          sendChunk(blob, seqId);
        },
        onWaveformData: (data: Uint8Array) => {
          setWaveformData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i++) {
            sum += Math.abs(data[i] - 128);
          }
          setAudioLevel(Math.min(100, Math.round((sum / data.length) * 2)));
        },
        onError: (err: Error) => {
          console.error("Audio recording error:", err);
          handleStopDetection();
          dispatch({
            type: "request_failed",
            requestId: ++requestSeqRef.current,
            message: `Microphone error: ${err.message}`,
          });
        },
      });

      await recorderRef.current.start();
      setIsRecording(true);
      setIsStarting(false);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      setIsStarting(false);
      setIsRecording(false);
      const msg = err instanceof Error ? err.message : "Could not access microphone.";
      console.error("Microphone startup failed:", err);
      dispatch({
        type: "request_failed",
        requestId: ++requestSeqRef.current,
        message: `Microphone permission denied or unavailable: ${msg}`,
      });
    }
  };

  // Stop Live Detection
  const handleStopDetection = () => {
    startAttemptRef.current += 1;
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRecording(false);
    setIsStarting(false);
    dispatch({ type: "request_invalidated", requestId: ++requestSeqRef.current });
    setAudioLevel(0);
    setWaveformData(null);
  };

  // File Upload Ingestion
  const handleFileSelected = async (file: File) => {
    if (isRecording || isStarting) handleStopDetection();
    const requestId = ++requestSeqRef.current;
    dispatch({ type: "request_started", requestId, clearResult: true });

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      const resp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
      if (!resp.ok) {
        const errorBody = await resp.json().catch(() => null);
        const detail = errorBody?.error?.message || errorBody?.detail || `Upload processing failed (HTTP ${resp.status})`;
        throw new Error(detail);
      }

      const data: DetectionResponse = { ...(await resp.json()), mode: "real" };
      handleDetectionData(data, requestId, false);
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error("Upload failed:", err);
      dispatch({ type: "request_failed", requestId, clearResult: true, message: error.message || "Upload processing failed." });
    }
  };

  // Demo Simulation: Authentic Voice
  const handleSimulateGenuine = () => {
    const requestId = ++requestSeqRef.current;
    dispatch({ type: "request_started", requestId, clearResult: true });

    setTimeout(() => {
      const mock = createDemoResult(false);
      handleDetectionData(mock, requestId, false);
    }, 600);
  };

  // Demo Simulation: Cloned Voice
  const handleSimulateClone = () => {
    const requestId = ++requestSeqRef.current;
    dispatch({ type: "request_started", requestId, clearResult: true });

    setTimeout(() => {
      const mock = createDemoResult(true);
      handleDetectionData(mock, requestId, false);
    }, 700);
  };

  const handleTestSample = async (samplePath: string, sampleName: string) => {
    if (isRecording || isStarting) handleStopDetection();
    const requestId = ++requestSeqRef.current;
    dispatch({ type: "request_started", requestId, clearResult: true });

    try {
      const resp = await fetch(samplePath);
      if (!resp.ok) throw new Error(`Could not load audio sample ${sampleName}`);
      const blob = await resp.blob();
      const file = new File([blob], sampleName, { type: blob.type || "audio/wav" });
      
      const formData = new FormData();
      formData.append("file", file, file.name);
      const apiResp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
      if (!apiResp.ok) {
        const errorBody = await apiResp.json().catch(() => null);
        throw new Error(errorBody?.error?.message || errorBody?.detail || `HTTP ${apiResp.status}`);
      }
      const data: DetectionResponse = { ...(await apiResp.json()), mode: "real" };
      handleDetectionData(data, requestId, false);
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error("Test sample failed:", err);
      dispatch({ type: "request_failed", requestId, clearResult: true, message: error.message || "Failed to analyze sample." });
    }
  };

  const handleReset = () => {
    handleStopDetection();
    dispatch({ type: "reset", requestId: ++requestSeqRef.current });
  };

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, "0");
    const s = (secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const isThreatActive = result?.prediction.label === "likely_ai_generated";

  return (
    <>
      {/* 1. Fullscreen Boot Preloader */}
      {showPreloader && <Preloader onComplete={() => setShowPreloader(false)} />}

      {/* Main Cinematic Command Center */}
      <PageTransition>
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-6 space-y-16">
          {/* Hero Section */}
          <section className="relative flex flex-col lg:flex-row items-center justify-between gap-12 pt-4 sm:pt-8">
            <div className="max-w-xl z-10">
              {/* Overworld Tagline in High-Contrast Serif */}
              <motion.h1
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, ease: [0.76, 0, 0.24, 1] }}
                className="font-serif-cinematic text-5xl sm:text-7xl font-normal leading-[1.08] text-[#f4f5f7]"
              >
                Listen <br />
                before you <br />
                <span className="text-[#66b7ff] italic font-medium">trust.</span>
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.6 }}
                className="mt-6 text-sm sm:text-base text-[#9ba2b1] leading-relaxed max-w-lg"
              >
                Real-time AI detection for voice cloning and impersonation attacks.
                Listen to the acoustic signal before authorizing sensitive continuation.
              </motion.p>

              {/* Primary Call-to-Actions */}
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.35, duration: 0.6 }}
                className="flex flex-wrap items-center gap-4 mt-8"
              >
                {!isRecording && !isStarting ? (
                  <button
                    type="button"
                    onClick={handleStartDetection}
                    className="px-8 py-3.5 rounded-full bg-[#66b7ff] hover:bg-[#8ddcff] text-[#090b11] font-mono text-sm tracking-wider font-semibold transition-all shadow-lg flex items-center gap-2.5 group"
                  >
                    <Mic size={15} />
                    <span>START LIVE DETECTION</span>
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[#090b11]/25 text-[#090b11] font-bold">
                      UPCOMING ❤️
                    </span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleStopDetection}
                    className="px-8 py-3.5 rounded-full bg-[#e66d76] hover:bg-[#e66d76]/90 text-white font-mono text-sm tracking-wider font-semibold transition-all shadow-lg flex items-center gap-2.5 animate-pulse"
                  >
                    <MicOff size={15} />
                    <span>{isStarting ? "CANCEL START" : "STOP DETECTION"}</span>
                  </button>
                )}

                <UploadAudio onFileSelected={handleFileSelected} disabled={isRecording || isStarting} />

                {/* State Tag */}
                {isRecording && (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#111520] border border-[rgba(255,255,255,0.12)] text-sm font-mono text-[#70d6a0]">
                    <span className="w-2 h-2 rounded-full bg-[#70d6a0] animate-ping" />
                    <span>LIVE AUDIO {formatTimer(recordingSeconds)}</span>
                  </div>
                )}

                {/* Instant Sample Test Buttons */}
                <div className="w-full pt-3 flex flex-wrap items-center gap-2 sm:gap-3">
                  <span className="text-xs font-mono uppercase tracking-wider text-[#9ba2b1]">
                    Test Datasets:
                  </span>
                  <button
                    type="button"
                    onClick={() => handleTestSample("/samples/ai_voice_sample_1.wav", "ai_voice_sample_1.wav")}
                    disabled={isRecording || isStarting || isAnalyzing}
                    className="px-3 py-1.5 rounded-full border border-[#ef4444]/60 bg-[#ef4444]/15 hover:bg-[#ef4444]/30 text-[#fca5a5] hover:text-white font-mono text-xs tracking-wider transition-all flex items-center gap-1.5 shadow-sm disabled:opacity-50"
                  >
                    <Flame size={13} className="text-[#ef4444]" />
                    <span>TEST AI VOICE (DEEPFAKE)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleTestSample("/samples/human_voice_sample_1.mp3", "human_voice_sample_1.mp3")}
                    disabled={isRecording || isStarting || isAnalyzing}
                    className="px-3 py-1.5 rounded-full border border-[#10b981]/60 bg-[#10b981]/15 hover:bg-[#10b981]/30 text-[#a7f3d0] hover:text-white font-mono text-xs tracking-wider transition-all flex items-center gap-1.5 shadow-sm disabled:opacity-50"
                  >
                    <Sparkles size={13} className="text-[#10b981]" />
                    <span>TEST HUMAN VOICE (REAL)</span>
                  </button>
                </div>
              </motion.div>
            </div>

            {/* Central Audio Landscape Core */}
            <div className="w-full lg:w-1/2 flex items-center justify-center relative">
              <AudioLandscape
                isRecording={isRecording}
                audioLevel={audioLevel}
                riskLevel={riskOf(result)}
              />
            </div>
          </section>

          {/* User Error Banner */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-[#e66d76]/10 border border-[#e66d76]/40 text-[#e66d76] flex items-center justify-between text-sm font-mono">
              <div className="flex items-center gap-2">
                <span className="font-bold">NOTICE:</span>
                <span>{errorMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => dispatch({ type: "clear_error" })}
                className="text-[#e66d76] hover:text-white px-2 py-0.5 rounded text-sm transition-colors"
              >
                ✕
              </button>
            </div>
          )}

          {/* High / Critical Threat Warning Layer */}
          {isThreatActive && result && (
            <WarningPanel
              aiProbability={result.prediction.ai_probability ?? 0}
              humanProbability={result.prediction.human_probability ?? 0}
            />
          )}

          {/* Operational Detection Console */}
          <section className="space-y-6">
            {/* Fluid Waveform */}
            <AudioWaveform
              isRecording={isRecording}
              waveformData={waveformData}
              chunkNumber={chunkCounter}
              isAnalyzing={isAnalyzing}
              riskLevel={riskOf(result)}
            />

            {/* Sequential Neural Analysis Nodes */}
            <AnalysisPipeline
              isAnalyzing={isAnalyzing}
              processingTimeMs={result?.processing_time_ms}
            />

            {/* Primary Result Headline */}
            <DetectionResult result={result} isAnalyzing={isAnalyzing} />

            {/* Comprehensive Threat Risk Meter */}
            {result && (
              <RiskMeter
                score={result.prediction.fake_score ?? (result.prediction.ai_probability ? Math.round(result.prediction.ai_probability * 100) : 0)}
                level={riskOf(result)}
                prediction={result.prediction.label === "likely_ai_generated" ? "AI-generated" : "authentic"}
              />
            )}

            {/* Context-Aware Scam Intent Analysis (Speech-to-Text & Social Engineering Defense) */}
            <ScamIntentAnalysis result={result} isAnalyzing={isAnalyzing} />

          {/* Demo controls remain separate from uploaded audio inference. */}
          <div className="grid grid-cols-1 gap-6">
              <DemoMode
                isDemoMode={isDemoMode}
                onToggleDemoMode={setIsDemoMode}
                onSimulateGenuine={handleSimulateGenuine}
                onSimulateClone={handleSimulateClone}
                onReset={handleReset}
                isLoading={isAnalyzing}
              />
            </div>
          </section>

          {/* Section: Overview / How It Works */}
          <section className="pt-10 border-t border-[rgba(255,255,255,0.08)] space-y-10">
            <div className="max-w-2xl">
              <span className="text-[12px] font-mono tracking-widest text-[#66b7ff] uppercase block mb-2">
                DEFENSE ARCHITECTURE
              </span>
              <h2 className="font-serif-cinematic text-3xl sm:text-4xl text-[#f4f5f7]">
                Voice can be copied. <br />
                Trust shouldn&apos;t be.
              </h2>
              <p className="mt-3 text-sm sm:text-sm text-[#9ba2b1] leading-relaxed">
                EchoSentinel analyzes audio for patterns associated with synthetic speech and presents
                model scores, signal measurements, and the limits of each result.
              </p>
            </div>

            {/* Four Sequential Stage Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {WORKFLOW_STEPS.map((step) => (
                <div
                  key={step.step}
                  className="p-5 rounded-xl bg-[#111520] border border-[rgba(255,255,255,0.08)] space-y-3"
                >
                  <span className="text-sm font-mono text-[#66b7ff] font-semibold block">
                    {step.step}
                  </span>
                  <h3 className="text-sm font-mono tracking-wider font-bold text-[#f4f5f7] uppercase">
                    {step.title}
                  </h3>
                  <p className="text-sm text-[#9ba2b1] leading-relaxed">
                    {step.description}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Section: Under The Surface (Model Transparency) */}
          <section className="p-6 sm:p-8 rounded-2xl bg-[#111520] border border-[rgba(255,255,255,0.12)] space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <span className="text-[12px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                  TECHNICAL PIPELINE
                </span>
                <h3 className="font-serif-cinematic text-2xl text-[#f4f5f7] mt-0.5">
                  Under the Surface
                </h3>
              </div>
              <span className="text-[13px] font-mono text-[#70d6a0] px-3 py-1 rounded-full bg-[#70d6a0]/10 border border-[#70d6a0]/30 self-start sm:self-auto">
                PyTorch Wav2Vec2 Sequence Classification
              </span>
            </div>

            <p className="text-sm sm:text-sm text-[#9ba2b1] leading-relaxed max-w-3xl">
              Incoming 16 kHz audio chunks pass through our feature extraction pipeline and sequence
              classification layers. The model evaluates bonafide vs. spoof probabilities across
              temporal acoustic frames, outputting uncalibrated class scores to the client in real time.
            </p>

            <div className="p-4 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] flex items-center justify-between text-sm font-mono text-[#9ba2b1] overflow-x-auto">
              <span>AUDIO INGEST</span>
              <span className="text-[#8b93a3]">→</span>
              <span>16 KHZ RESAMPLING</span>
              <span className="text-[#8b93a3]">→</span>
              <span>WAV2VEC2 TRANSFORMER</span>
              <span className="text-[#8b93a3]">→</span>
              <span>RISK ENGINE (0-100)</span>
              <span className="text-[#8b93a3]">→</span>
              <span>IDENTITY GATE</span>
            </div>
          </section>

          {/* Section: Limitations & Honesty */}
          <section className="space-y-6">
            <div className="max-w-xl">
              <span className="text-[12px] font-mono tracking-widest text-[#e8c86b] uppercase block mb-1.5">
                HONEST GUARANTEES
              </span>
              <h3 className="font-serif-cinematic text-2xl text-[#f4f5f7]">
                What EchoSentinel Does Not Claim
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {HONEST_LIMITATIONS.map((item, idx) => (
                <div
                  key={idx}
                  className="p-5 rounded-xl bg-[#111520] border border-[rgba(255,255,255,0.08)] space-y-2"
                >
                  <h4 className="text-sm font-mono font-semibold text-[#f4f5f7]">
                    &quot;{item.title}&quot;
                  </h4>
                  <p className="text-sm text-[#9ba2b1] leading-relaxed">
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>

            <div className="p-4 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] text-sm text-[#9ba2b1] text-center italic">
              Detection is one layer of defense. Acoustic verification informs judgment; it does not replace multi-factor institutional protocols.
            </div>
          </section>

          {/* Footer */}
          <footer className="pt-8 border-t border-[rgba(255,255,255,0.08)] flex flex-col sm:flex-row items-center justify-between gap-4 text-sm font-mono text-[#8b93a3]">
            <span>ECHOSENTINEL • VOICE SAFETY PROTOTYPE</span>
            <span>WAV2VEC2 + FASTAPI + NEXT.JS</span>
          </footer>
        </div>
      </PageTransition>

    </>
  );
}
