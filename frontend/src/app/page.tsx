"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Mic, MicOff, Lock, Unlock, CheckCircle2, ChevronDown, ArrowRight } from "lucide-react";
import { Preloader } from "../components/Preloader";
import { SoundGate } from "../components/SoundGate";
import { AudioLandscape } from "../components/AudioLandscape";
import { AudioWaveform } from "../components/AudioWaveform";
import { AnalysisPipeline } from "../components/AnalysisPipeline";
import { DetectionResult } from "../components/DetectionResult";
import { RiskIndicator } from "../components/RiskIndicator";
import { WarningPanel } from "../components/WarningPanel";
import { IdentityVerification } from "../components/IdentityVerification";
import { DemoMode } from "../components/DemoMode";
import { UploadAudio } from "../components/UploadAudio";
import { PageTransition } from "../components/PageTransition";
import { AudioStreamRecorder } from "../lib/audioRecorder";
import { WORKFLOW_STEPS, HONEST_LIMITATIONS } from "../lib/content";

interface DetectionResponse {
  prediction: "authentic" | "AI-generated" | "Possible spoof" | string;
  raw_model_prediction?: string;
  confidence: number;
  model_spoof_score?: number;
  risk_score: number;
  risk_level: "Low" | "Suspicious" | "High" | "Critical";
  audio_quality_score?: number;
  audio_quality_rating?: string;
  detection_reliability?: "HIGH" | "MEDIUM" | "LOW";
  reliability_label?: string;
  quality_flags?: string[];
  quality_warning?: string;
  processing_time_ms?: number;
  model_source?: string;
  status?: string;
}

export default function Home() {
  // Intro & Boot Stages
  const [showPreloader, setShowPreloader] = useState(true);
  const [showSoundGate, setShowSoundGate] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Live Audio Detection State
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [waveformData, setWaveformData] = useState<Uint8Array | null>(null);
  const [chunkCounter, setChunkCounter] = useState(1);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Results State - starts as null until actual inference completes
  const [result, setResult] = useState<DetectionResponse | null>(null);

  // Verification & Threat Mitigation State
  const [isVerificationOpen, setIsVerificationOpen] = useState(false);
  const [isBlocked, setIsBlocked] = useState(false);
  const [isVerified, setIsVerified] = useState(false);

  // Demo Simulation State
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [isDemoSimulated, setIsDemoSimulated] = useState(false);

  // References
  const recorderRef = useRef<AudioStreamRecorder | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const latestSeqRef = useRef<number>(0);
  const activeRequestsRef = useRef<number>(0);
  const recentScoresRef = useRef<number[]>([]);

  const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const API_URL = rawApiUrl.replace(/\/+$/, "");

  // Handle incoming detection result with sequence-number protection and temporal smoothing
  const handleDetectionData = useCallback(
    (data: DetectionResponse, seqId?: number, isLiveChunk: boolean = false) => {
      // Sequence protection: discard older out-of-order responses
      if (seqId && seqId < latestSeqRef.current) {
        return;
      }
      if (seqId) latestSeqRef.current = seqId;

      let finalData = data;

      // Temporal smoothing over recent live chunks (sliding window of up to 3 chunks)
      if (isLiveChunk) {
        recentScoresRef.current.push(data.risk_score);
        if (recentScoresRef.current.length > 3) {
          recentScoresRef.current.shift();
        }

        // Apply smoothing to prevent jumping, but do NOT suppress genuine Critical spikes (>=81)
        if (data.risk_score < 80 && recentScoresRef.current.length >= 2) {
          const weights =
            recentScoresRef.current.length === 2 ? [0.4, 0.6] : [0.2, 0.3, 0.5];
          const smoothedScore = Math.round(
            recentScoresRef.current.reduce((acc, score, idx) => acc + score * weights[idx], 0)
          );
          const smoothedLevel: "Low" | "Suspicious" | "High" | "Critical" =
            smoothedScore <= 30
              ? "Low"
              : smoothedScore <= 60
              ? "Suspicious"
              : smoothedScore <= 80
              ? "High"
              : "Critical";

          finalData = {
            ...data,
            risk_score: smoothedScore,
            risk_level: smoothedLevel,
          };
        }
      } else {
        recentScoresRef.current = [data.risk_score];
      }

      setResult(finalData);
      setErrorMessage(null);

      if (finalData.risk_level === "High" || finalData.risk_level === "Critical") {
        setIsBlocked(true);
        setIsVerified(false);
        setIsVerificationOpen(true);
      }
    },
    []
  );

  // Send an audio chunk to backend /detect with concurrency tracking
  const sendChunk = useCallback(
    async (blob: Blob, seqId: number, simulateType?: "genuine" | "clone") => {
      activeRequestsRef.current += 1;
      setIsAnalyzing(true);
      setChunkCounter(seqId);

      try {
        const formData = new FormData();
        formData.append("file", blob, `stream_${seqId}.wav`);

        let url = `${API_URL}/detect`;
        if (simulateType) url += `?simulate=${simulateType}`;

        const resp = await fetch(url, { method: "POST", body: formData });
        if (!resp.ok) {
          const errorBody = await resp.json().catch(() => null);
          const detail = errorBody?.detail || `HTTP ${resp.status}`;
          throw new Error(detail);
        }

        const data: DetectionResponse = await resp.json();
        handleDetectionData(data, seqId, true);
      } catch (err: any) {
        console.warn("Stream analysis notice:", err);
      } finally {
        activeRequestsRef.current = Math.max(0, activeRequestsRef.current - 1);
        if (activeRequestsRef.current === 0) {
          setIsAnalyzing(false);
        }
      }
    },
    [API_URL, handleDetectionData]
  );

  // Start Live Detection
  const handleStartDetection = async () => {
    setIsDemoSimulated(false);
    setRecordingSeconds(0);
    setErrorMessage(null);
    recentScoresRef.current = [];

    try {
      const recorder = new AudioStreamRecorder({
        chunkIntervalMs: 2800,
        onChunk: (chunkBlob, seqId) => {
          sendChunk(chunkBlob, seqId);
        },
        onWaveformData: (data) => {
          setWaveformData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i++) {
            sum += Math.abs(data[i] - 128);
          }
          const avg = sum / data.length;
          setAudioLevel(Math.min(1, avg / 45));
        },
        onError: (err) => {
          console.error("Mic error:", err);
          setErrorMessage(
            err.message?.includes("Permission") || err.message?.includes("NotAllowedError")
              ? "Microphone access was denied. Please allow microphone permission in your browser."
              : `Microphone error: ${err.message || "Device unavailable."}`
          );
          handleStopDetection();
        },
      });

      recorderRef.current = recorder;
      await recorder.start();
      setIsRecording(true);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.error("Failed to start detection:", err);
      setErrorMessage(
        err.message?.includes("Permission") || err.name === "NotAllowedError"
          ? "Microphone access was denied. Please allow microphone permission in your browser settings."
          : `Failed to initialize microphone: ${err.message || "Device unavailable"}`
      );
      setIsRecording(false);
    }
  };

  // Stop Live Detection
  const handleStopDetection = () => {
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRecording(false);
    setIsAnalyzing(false);
    activeRequestsRef.current = 0;
    setAudioLevel(0);
    setWaveformData(null);
    recentScoresRef.current = [];
  };

  // File Upload Ingestion
  const handleFileSelected = async (file: File) => {
    if (isRecording) handleStopDetection();
    setIsDemoSimulated(false);
    activeRequestsRef.current += 1;
    setIsAnalyzing(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);

      const resp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
      if (!resp.ok) {
        const errorBody = await resp.json().catch(() => null);
        const detail = errorBody?.detail || `Upload processing failed (HTTP ${resp.status})`;
        throw new Error(detail);
      }

      const data: DetectionResponse = await resp.json();
      handleDetectionData(data, ++latestSeqRef.current, false);
    } catch (err: any) {
      console.error("Upload failed:", err);
      setErrorMessage(err.message || "Upload processing failed.");
    } finally {
      activeRequestsRef.current = Math.max(0, activeRequestsRef.current - 1);
      if (activeRequestsRef.current === 0) {
        setIsAnalyzing(false);
      }
    }
  };

  // Demo Simulation: Authentic Voice
  const handleSimulateGenuine = () => {
    setIsDemoSimulated(true);
    setIsAnalyzing(true);
    setErrorMessage(null);

    setTimeout(() => {
      const mock: DetectionResponse = {
        prediction: "authentic",
        confidence: 0.93,
        model_spoof_score: 0.07,
        risk_score: 7,
        risk_level: "Low",
        processing_time_ms: 18.2,
        model_source: "demo_simulation",
      };
      handleDetectionData(mock, ++latestSeqRef.current, false);
      setIsBlocked(false);
      setIsVerified(false);
      setIsAnalyzing(false);
    }, 600);
  };

  // Demo Simulation: Cloned Voice
  const handleSimulateClone = () => {
    setIsDemoSimulated(true);
    setIsAnalyzing(true);
    setErrorMessage(null);

    setTimeout(() => {
      const mock: DetectionResponse = {
        prediction: "AI-generated",
        confidence: 0.88,
        model_spoof_score: 0.88,
        risk_score: 88,
        risk_level: "Critical",
        processing_time_ms: 22.4,
        model_source: "demo_simulation",
      };
      handleDetectionData(mock, ++latestSeqRef.current, false);
      setIsAnalyzing(false);
    }, 700);
  };

  const handleReset = () => {
    handleStopDetection();
    setResult(null);
    setIsBlocked(false);
    setIsVerified(false);
    setIsVerificationOpen(false);
    setIsDemoSimulated(false);
    setErrorMessage(null);
    recentScoresRef.current = [];
  };

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, "0");
    const s = (secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const isThreatActive = result ? result.risk_level === "High" || result.risk_level === "Critical" : false;

  return (
    <>
      {/* 1. Fullscreen Boot Preloader */}
      {showPreloader && <Preloader onComplete={() => setShowPreloader(false)} />}

      {/* 2. Fullscreen Sound Gate Entrance */}
      {!showPreloader && showSoundGate && (
        <SoundGate
          onEnter={(sound) => {
            setSoundEnabled(sound);
            setShowSoundGate(false);
          }}
        />
      )}

      {/* 3. Main Cinematic Command Center */}
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
                {!isRecording ? (
                  <button
                    type="button"
                    onClick={handleStartDetection}
                    className="px-8 py-3.5 rounded-full bg-[#66b7ff] hover:bg-[#8ddcff] text-[#090b11] font-mono text-xs tracking-wider font-semibold transition-all shadow-lg flex items-center gap-2.5"
                  >
                    <Mic size={15} />
                    <span>START DETECTION</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleStopDetection}
                    className="px-8 py-3.5 rounded-full bg-[#e66d76] hover:bg-[#e66d76]/90 text-white font-mono text-xs tracking-wider font-semibold transition-all shadow-lg flex items-center gap-2.5 animate-pulse"
                  >
                    <MicOff size={15} />
                    <span>STOP DETECTION</span>
                  </button>
                )}

                <UploadAudio onFileSelected={handleFileSelected} disabled={isRecording} />

                {/* State Tag */}
                {isRecording && (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#111520] border border-[rgba(255,255,255,0.12)] text-xs font-mono text-[#70d6a0]">
                    <span className="w-2 h-2 rounded-full bg-[#70d6a0] animate-ping" />
                    <span>LIVE AUDIO {formatTimer(recordingSeconds)}</span>
                  </div>
                )}
              </motion.div>
            </div>

            {/* Central Audio Landscape Core */}
            <div className="w-full lg:w-1/2 flex items-center justify-center relative">
              <AudioLandscape
                isRecording={isRecording}
                audioLevel={audioLevel}
                riskLevel={result ? result.risk_level : "Low"}
              />
            </div>
          </section>

          {/* User Error Banner */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-[#e66d76]/10 border border-[#e66d76]/40 text-[#e66d76] flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="font-bold">NOTICE:</span>
                <span>{errorMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setErrorMessage(null)}
                className="text-[#e66d76] hover:text-white px-2 py-0.5 rounded text-sm transition-colors"
              >
                ✕
              </button>
            </div>
          )}

          {/* High / Critical Threat Warning Layer */}
          {isThreatActive && result && (
            <WarningPanel
              riskScore={result.risk_score}
              riskLevel={result.risk_level === "Critical" ? "Critical" : "High"}
              onOpenVerification={() => setIsVerificationOpen(true)}
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
              riskLevel={result ? result.risk_level : "Low"}
            />

            {/* Sequential Neural Analysis Nodes */}
            <AnalysisPipeline
              isAnalyzing={isAnalyzing}
              processingTimeMs={result?.processing_time_ms}
            />

            {/* Primary Result Headline */}
            <DetectionResult
              prediction={result?.prediction}
              rawModelPrediction={result?.raw_model_prediction}
              confidence={result?.confidence}
              modelSpoofScore={result?.model_spoof_score}
              riskScore={result?.risk_score}
              riskLevel={result?.risk_level}
              audioQualityScore={result?.audio_quality_score}
              audioQualityRating={result?.audio_quality_rating}
              detectionReliability={result?.detection_reliability}
              qualityWarning={result?.quality_warning}
              qualityFlags={result?.quality_flags}
              isDemoSimulated={isDemoSimulated}
            />

            {/* Twin Threat Gauge & Demo Controls */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <RiskIndicator
                score={result?.risk_score ?? null}
                level={result?.risk_level ?? null}
                confidence={result?.confidence ?? null}
              />

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
              <span className="text-[10px] font-mono tracking-widest text-[#66b7ff] uppercase block mb-2">
                DEFENSE ARCHITECTURE
              </span>
              <h2 className="font-serif-cinematic text-3xl sm:text-4xl text-[#f4f5f7]">
                Voice can be copied. <br />
                Trust shouldn't be.
              </h2>
              <p className="mt-3 text-xs sm:text-sm text-[#9ba2b1] leading-relaxed">
                EchoSentinel analyzes acoustic micro-signatures associated with AI speech synthesis
                and introduces an active identity challenge before sensitive continuation is unlocked.
              </p>
            </div>

            {/* Four Sequential Stage Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {WORKFLOW_STEPS.map((step) => (
                <div
                  key={step.step}
                  className="p-5 rounded-xl bg-[#111520] border border-[rgba(255,255,255,0.08)] space-y-3"
                >
                  <span className="text-xs font-mono text-[#66b7ff] font-semibold block">
                    {step.step}
                  </span>
                  <h3 className="text-sm font-mono tracking-wider font-bold text-[#f4f5f7] uppercase">
                    {step.title}
                  </h3>
                  <p className="text-xs text-[#9ba2b1] leading-relaxed">
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
                <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                  TECHNICAL PIPELINE
                </span>
                <h3 className="font-serif-cinematic text-2xl text-[#f4f5f7] mt-0.5">
                  Under the Surface
                </h3>
              </div>
              <span className="text-[11px] font-mono text-[#70d6a0] px-3 py-1 rounded-full bg-[#70d6a0]/10 border border-[#70d6a0]/30 self-start sm:self-auto">
                PyTorch Wav2Vec2 Sequence Classification
              </span>
            </div>

            <p className="text-xs sm:text-sm text-[#9ba2b1] leading-relaxed max-w-3xl">
              Incoming 16 kHz audio chunks pass through our feature extraction pipeline and sequence
              classification layers. The model evaluates bonafide vs. spoof probabilities across
              temporal acoustic frames, outputting calibrated threat scores to the client in real time.
            </p>

            <div className="p-4 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] flex items-center justify-between text-xs font-mono text-[#9ba2b1] overflow-x-auto">
              <span>AUDIO INGEST</span>
              <span className="text-[#626978]">→</span>
              <span>16 KHZ RESAMPLING</span>
              <span className="text-[#626978]">→</span>
              <span>WAV2VEC2 TRANSFORMER</span>
              <span className="text-[#626978]">→</span>
              <span>RISK ENGINE (0-100)</span>
              <span className="text-[#626978]">→</span>
              <span>IDENTITY GATE</span>
            </div>
          </section>

          {/* Section: Limitations & Honesty */}
          <section className="space-y-6">
            <div className="max-w-xl">
              <span className="text-[10px] font-mono tracking-widest text-[#e8c86b] uppercase block mb-1.5">
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
                  <h4 className="text-xs font-mono font-semibold text-[#f4f5f7]">
                    "{item.title}"
                  </h4>
                  <p className="text-xs text-[#9ba2b1] leading-relaxed">
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>

            <div className="p-4 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] text-xs text-[#9ba2b1] text-center italic">
              Detection is one layer of defense. Acoustic verification informs judgment; it does not replace multi-factor institutional protocols.
            </div>
          </section>

          {/* Footer */}
          <footer className="pt-8 border-t border-[rgba(255,255,255,0.08)] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-[#626978]">
            <span>ECHOSENTINEL • VOICE SAFETY PROTOTYPE</span>
            <span>WAV2VEC2 + FASTAPI + NEXT.JS</span>
          </footer>
        </div>
      </PageTransition>

      {/* Identity Verification Step-Up Modal */}
      <IdentityVerification
        isOpen={isVerificationOpen}
        onPass={() => {
          setIsVerificationOpen(false);
          setIsBlocked(false);
          setIsVerified(true);
        }}
        onFail={() => {
          setIsVerificationOpen(false);
          setIsBlocked(true);
          setIsVerified(false);
        }}
        onClose={() => setIsVerificationOpen(false)}
      />
    </>
  );
}
