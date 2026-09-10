"use client";

import React, { useState, useRef, useCallback } from "react";
import { Mic, MicOff, AlertTriangle } from "lucide-react";
import { PageTransition } from "../../components/PageTransition";
import { AudioWaveform } from "../../components/AudioWaveform";
import { AnalysisPipeline } from "../../components/AnalysisPipeline";
import { DetectionResult } from "../../components/DetectionResult";
import { RiskIndicator } from "../../components/RiskIndicator";
import { WarningPanel } from "../../components/WarningPanel";
import { IdentityVerification } from "../../components/IdentityVerification";
import { UploadAudio } from "../../components/UploadAudio";
import { AudioStreamRecorder } from "../../lib/audioRecorder";

interface DetectionResponse {
  prediction: "authentic" | "AI-generated";
  confidence: number;
  risk_score: number;
  risk_level: "Low" | "Suspicious" | "High" | "Critical";
  processing_time_ms?: number;
}

export default function DetectionPage() {
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [waveformData, setWaveformData] = useState<Uint8Array | null>(null);
  const [chunkCounter, setChunkCounter] = useState(1);

  const [result, setResult] = useState<DetectionResponse>({
    prediction: "authentic",
    confidence: 0.93,
    risk_score: 12,
    risk_level: "Low",
    processing_time_ms: 22.0,
  });

  const [isVerificationOpen, setIsVerificationOpen] = useState(false);
  const [isBlocked, setIsBlocked] = useState(false);

  const recorderRef = useRef<AudioStreamRecorder | null>(null);
  const latestSeqRef = useRef<number>(0);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleDetectionData = useCallback((data: DetectionResponse, seqId?: number) => {
    if (seqId && seqId < latestSeqRef.current) return;
    if (seqId) latestSeqRef.current = seqId;

    setResult(data);
    if (data.risk_level === "High" || data.risk_level === "Critical") {
      setIsBlocked(true);
      setIsVerificationOpen(true);
    }
  }, []);

  const sendChunk = useCallback(
    async (blob: Blob, seqId: number) => {
      setIsAnalyzing(true);
      setChunkCounter(seqId);

      try {
        const formData = new FormData();
        formData.append("file", blob, `detection_chunk_${seqId}.wav`);

        const resp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
        if (!resp.ok) throw new Error("API error");

        const data: DetectionResponse = await resp.json();
        handleDetectionData(data, seqId);
      } catch (err) {
        console.warn("Detection error:", err);
      } finally {
        setIsAnalyzing(false);
      }
    },
    [API_URL, handleDetectionData]
  );

  const handleStart = async () => {
    try {
      const recorder = new AudioStreamRecorder({
        chunkIntervalMs: 2800,
        onChunk: sendChunk,
        onWaveformData: setWaveformData,
        onError: () => handleStop(),
      });
      recorderRef.current = recorder;
      await recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error(err);
      setIsRecording(false);
    }
  };

  const handleStop = () => {
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    setIsRecording(false);
    setIsAnalyzing(false);
    setWaveformData(null);
  };

  const handleUpload = async (file: File) => {
    if (isRecording) handleStop();
    setIsAnalyzing(true);

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);

      const resp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
      if (!resp.ok) throw new Error("Upload error");

      const data: DetectionResponse = await resp.json();
      handleDetectionData(data, ++latestSeqRef.current);
    } catch (err) {
      console.error(err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const isThreat = result.risk_level === "High" || result.risk_level === "Critical";

  return (
    <PageTransition>
      <div className="max-w-5xl mx-auto px-5 sm:px-8 py-6 space-y-10">
        {/* Header */}
        <div className="space-y-3">
          <span className="text-[10px] font-mono tracking-widest text-[#66b7ff] uppercase block">
            DETECTION CONSOLE
          </span>
          <h1 className="font-serif-cinematic text-4xl sm:text-5xl text-[#f4f5f7]">
            Give us a voice to listen to.
          </h1>
          <p className="text-sm text-[#9ba2b1] max-w-xl">
            Stream live vocal audio directly via your browser microphone or upload pre-recorded audio
            files to evaluate synthetic cloning likelihood.
          </p>
        </div>

        {/* Primary Controls */}
        <div className="flex flex-wrap items-center gap-4">
          {!isRecording ? (
            <button
              type="button"
              onClick={handleStart}
              className="px-8 py-3.5 rounded-full bg-[#66b7ff] hover:bg-[#8ddcff] text-[#090b11] font-mono text-xs tracking-wider font-semibold transition-all shadow-lg flex items-center gap-2.5"
            >
              <Mic size={15} />
              <span>LIVE MICROPHONE</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleStop}
              className="px-8 py-3.5 rounded-full bg-[#e66d76] hover:bg-[#e66d76]/90 text-white font-mono text-xs tracking-wider font-semibold transition-all shadow-lg flex items-center gap-2.5 animate-pulse"
            >
              <MicOff size={15} />
              <span>STOP RECORDING</span>
            </button>
          )}

          <UploadAudio onFileSelected={handleUpload} disabled={isRecording} />
        </div>

        {/* Warning If High / Critical */}
        {isThreat && (
          <WarningPanel
            riskScore={result.risk_score}
            riskLevel={result.risk_level === "Critical" ? "Critical" : "High"}
            onOpenVerification={() => setIsVerificationOpen(true)}
          />
        )}

        {/* Waveform Visualization */}
        <AudioWaveform
          isRecording={isRecording}
          waveformData={waveformData}
          chunkNumber={chunkCounter}
          isAnalyzing={isAnalyzing}
          riskLevel={result.risk_level}
        />

        {/* Pipeline Nodes */}
        <AnalysisPipeline
          isAnalyzing={isAnalyzing}
          processingTimeMs={result.processing_time_ms}
        />

        {/* Result & Gauge */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <DetectionResult
            prediction={result.prediction}
            confidence={result.confidence}
            riskScore={result.risk_score}
            riskLevel={result.risk_level}
          />

          <RiskIndicator
            score={result.risk_score}
            level={result.risk_level}
            confidence={result.confidence}
          />
        </div>

        {/* Identity Verification Modal */}
        <IdentityVerification
          isOpen={isVerificationOpen}
          onPass={() => {
            setIsVerificationOpen(false);
            setIsBlocked(false);
          }}
          onFail={() => {
            setIsVerificationOpen(false);
            setIsBlocked(true);
          }}
          onClose={() => setIsVerificationOpen(false)}
        />
      </div>
    </PageTransition>
  );
}
