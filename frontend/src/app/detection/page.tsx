"use client";

import React, { useState, useRef, useCallback, useEffect, useReducer } from "react";
import { Mic, MicOff, Flame, Sparkles } from "lucide-react";
import { PageTransition } from "../../components/PageTransition";
import { AudioWaveform } from "../../components/AudioWaveform";
import { AnalysisPipeline } from "../../components/AnalysisPipeline";
import { DetectionResult } from "../../components/DetectionResult";
import { WarningPanel } from "../../components/WarningPanel";
import { RiskMeter } from "../../components/RiskMeter";
import { ScamIntentAnalysis } from "../../components/ScamIntentAnalysis";
import { UploadAudio } from "../../components/UploadAudio";
import { AudioStreamRecorder } from "../../lib/audioRecorder";
import { parseDetectionResponse, type DetectionResponse } from "../../lib/detection";
import { detectionReducer, initialDetectionState } from "../../lib/detectionState";
import { triggerUpcomingFeatureModal } from "../../components/UpcomingFeatureModal";

const riskOf = (result: DetectionResponse | null): "Low" | "Suspicious" | "High" | "Critical" => {
  if (!result) return "Low";
  if (result.prediction.label === "likely_ai_generated") {
    const aiProb = result.prediction.ai_probability ?? 0;
    return aiProb >= 0.85 ? "Critical" : "High";
  }
  return result.prediction.risk_level === "high" ? "High" : result.prediction.risk_level === "medium" || result.prediction.risk_level === "inconclusive" ? "Suspicious" : "Low";
};

export default function DetectionPage() {
  const [isRecording, setIsRecording] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [detectionState, dispatch] = useReducer(detectionReducer, initialDetectionState);
  const { result, errorMessage, isAnalyzing } = detectionState;
  const [waveformData, setWaveformData] = useState<Uint8Array | null>(null);
  const [chunkCounter, setChunkCounter] = useState(1);
  const recorderRef = useRef<AudioStreamRecorder | null>(null);
  const startAttemptRef = useRef(0);
  const requestSeqRef = useRef<number>(0);

  const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const API_URL = rawApiUrl.replace(/\/+$/, "");

  useEffect(() => () => {
    startAttemptRef.current += 1;
    recorderRef.current?.stop();
    recorderRef.current = null;
  }, []);

  const handleDetectionData = useCallback((data: DetectionResponse, seqId?: number) => {
    if (seqId === undefined) return;
    dispatch({ type: "request_succeeded", requestId: seqId, result: data });
  }, []);

  const sessionIdRef = useRef<string>(`session_${Date.now()}`);

  const sendChunk = useCallback(
    async (blob: Blob, seqId: number) => {
      const requestId = ++requestSeqRef.current;
      dispatch({ type: "request_started", requestId });
      setChunkCounter(seqId);

      try {
        const formData = new FormData();
        formData.append("file", blob, `detection_chunk_${seqId}.wav`);
        formData.append("session_id", sessionIdRef.current);
        formData.append("sequence_id", String(seqId));

        const resp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
        if (!resp.ok) {
          const errorBody = await resp.json().catch(() => null);
          const detail = errorBody?.error?.message || errorBody?.detail || `HTTP ${resp.status}`;
          throw new Error(detail);
        }

        const payload: unknown = await resp.json().catch(() => {
          throw new Error("The analysis service returned invalid JSON. Please retry.");
        });
        const data: DetectionResponse = { ...parseDetectionResponse(payload), mode: "real" };
        handleDetectionData(data, requestId);
      } catch (err: unknown) {
        const error = err instanceof Error ? err : new Error(String(err));
        console.warn("Detection error:", error);
        dispatch({ type: "request_failed", requestId, message: error.message || "Live audio analysis failed." });
      } finally {
        // The reducer only changes state for the current request, so stale completions are ignored.
      }
    },
    [API_URL, handleDetectionData]
  );

  const handleStart = async () => {
    if (isRecording || isStarting) return;
    setIsStarting(true);
    sessionIdRef.current = `session_${Date.now()}`;

    try {
      recorderRef.current = new AudioStreamRecorder({
        chunkIntervalMs: 2500,
        onChunk: (blob: Blob, seqId: number) => {
          sendChunk(blob, seqId);
        },
        onWaveformData: (data: Uint8Array) => {
          setWaveformData(data);
        },
        onError: (err: Error) => {
          console.error("Audio recording error:", err);
          handleStop();
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

  const handleStop = () => {
    startAttemptRef.current += 1;
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    setIsRecording(false);
    setIsStarting(false);
    dispatch({ type: "request_invalidated", requestId: ++requestSeqRef.current });
    setWaveformData(null);
  };

  const handleUpload = async (file: File) => {
    if (isRecording || isStarting) handleStop();
    const requestId = ++requestSeqRef.current;
    dispatch({ type: "request_started", requestId, clearResult: true });

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      const resp = await fetch(`${API_URL}/detect`, { method: "POST", body: formData });
      if (!resp.ok) {
        const errorBody = await resp.json().catch(() => null);
        const detail = errorBody?.error?.message || errorBody?.detail || `Upload failed (HTTP ${resp.status})`;
        throw new Error(detail);
      }

      const payload: unknown = await resp.json().catch(() => {
        throw new Error("The analysis service returned invalid JSON. Please retry.");
      });
      const data: DetectionResponse = { ...parseDetectionResponse(payload), mode: "real" };
      handleDetectionData(data, requestId);
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error(err);
      dispatch({ type: "request_failed", requestId, clearResult: true, message: error.message || "Audio processing failed." });
    }
  };

  const handleTestSample = async (samplePath: string, sampleName: string) => {
    if (isRecording || isStarting) handleStop();
    const requestId = ++requestSeqRef.current;
    dispatch({ type: "request_started", requestId, clearResult: true });

    try {
      const resp = await fetch(samplePath);
      if (!resp.ok) throw new Error(`Could not load audio sample ${sampleName}`);
      const blob = await resp.blob();
      const file = new File([blob], sampleName, { type: blob.type || "audio/wav" });
      await handleUpload(file);
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error("Test sample failed:", err);
      dispatch({ type: "request_failed", requestId, clearResult: true, message: error.message || "Failed to analyze sample." });
    }
  };

  const isThreat = result?.prediction.label === "likely_ai_generated";

  return (
    <PageTransition>
      <div className="max-w-5xl mx-auto px-5 sm:px-8 py-6 space-y-10">
        {/* Header */}
        <div className="space-y-3">
          <span className="text-[12px] font-mono tracking-widest text-[#66b7ff] uppercase block">
            DETECTION CONSOLE
          </span>
          <h1 className="font-serif-cinematic text-4xl sm:text-5xl text-[#f4f5f7]">
            Give us a voice to listen to.
          </h1>
          <p className="text-sm text-[#9ba2b1] max-w-xl">
            Stream live vocal audio directly via your browser microphone{" "}
            <button
              type="button"
              onClick={() => triggerUpcomingFeatureModal()}
              className="text-[#66b7ff] underline cursor-pointer inline-flex items-center gap-0.5 font-medium hover:text-[#8ddcff]"
            >
              (Upcoming Feature ❤️)
            </button>
            , upload audio files, or test authentic vs synthetic voice datasets.
          </p>
        </div>

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

        {/* Primary Controls */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            {!isRecording && !isStarting ? (
              <button
                type="button"
                onClick={handleStart}
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
                onClick={handleStop}
                className="px-8 py-3.5 rounded-full bg-[#e66d76] hover:bg-[#e66d76]/90 text-white font-mono text-sm tracking-wider font-semibold transition-all shadow-lg flex items-center gap-2.5 animate-pulse"
              >
                <MicOff size={15} />
                <span>{isStarting ? "CANCEL START" : "STOP RECORDING"}</span>
              </button>
            )}

            <UploadAudio onFileSelected={handleUpload} disabled={isRecording || isStarting} />
          </div>

          {/* Instant Sample Test Buttons */}
          <div className="flex flex-wrap items-center gap-2.5 pt-2">
            <span className="text-xs font-mono uppercase tracking-wider text-[#9ba2b1]">
              Instant Samples:
            </span>
            <button
              type="button"
              onClick={() => handleTestSample("/samples/ai_voice_sample_1.wav", "ai_voice_sample_1.wav")}
              disabled={isRecording || isStarting || isAnalyzing}
              className="px-3.5 py-1.5 rounded-full border border-[#ef4444]/60 bg-[#ef4444]/15 hover:bg-[#ef4444]/30 text-[#fca5a5] hover:text-white font-mono text-xs tracking-wider transition-all flex items-center gap-1.5 shadow-sm disabled:opacity-50"
            >
              <Flame size={13} className="text-[#ef4444]" />
              <span>TEST AI VOICE (DEEPFAKE)</span>
            </button>

            <button
              type="button"
              onClick={() => handleTestSample("/samples/human_voice_sample_1.mp3", "human_voice_sample_1.mp3")}
              disabled={isRecording || isStarting || isAnalyzing}
              className="px-3.5 py-1.5 rounded-full border border-[#10b981]/60 bg-[#10b981]/15 hover:bg-[#10b981]/30 text-[#a7f3d0] hover:text-white font-mono text-xs tracking-wider transition-all flex items-center gap-1.5 shadow-sm disabled:opacity-50"
            >
              <Sparkles size={13} className="text-[#10b981]" />
              <span>TEST HUMAN VOICE (REAL)</span>
            </button>
          </div>
        </div>

        {/* Warning If High / Critical Threat */}
        {isThreat && result && (
          <WarningPanel
            aiProbability={result.prediction.ai_probability ?? 0}
            humanProbability={result.prediction.human_probability ?? 0}
          />
        )}

        {/* Waveform Visualization */}
        <AudioWaveform
          isRecording={isRecording}
          waveformData={waveformData}
          chunkNumber={chunkCounter}
          isAnalyzing={isAnalyzing}
          riskLevel={riskOf(result)}
        />

        {/* Pipeline Nodes */}
        <AnalysisPipeline
          isAnalyzing={isAnalyzing}
          processingTimeMs={result?.processing_time_ms}
        />

        {/* Result & Gauge */}
        <div className="space-y-6">
          <DetectionResult result={result} isAnalyzing={isAnalyzing} />

          {result && (
            <RiskMeter
              score={result.prediction.fake_score ?? (result.prediction.ai_probability ? Math.round(result.prediction.ai_probability * 100) : 0)}
              level={riskOf(result)}
              prediction={result.prediction.label === "likely_ai_generated" ? "AI-generated" : "authentic"}
            />
          )}

          {/* Context-Aware Scam Intent Analysis (Speech-to-Text & Social Engineering Defense) */}
          <ScamIntentAnalysis result={result} isAnalyzing={isAnalyzing} />
        </div>

      </div>
    </PageTransition>
  );
}
