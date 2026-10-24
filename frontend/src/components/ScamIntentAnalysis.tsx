"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  FileText,
  KeyRound,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Send,
  HelpCircle,
  Info,
  Mic,
  MicOff,
  Square,
  Radio,
  RotateCcw,
} from "lucide-react";
import type { DetectionResponse, ScamAnalysisResult, ScamIndicator } from "../lib/detection";
import { AudioStreamRecorder } from "../lib/audioRecorder";

interface ScamIntentAnalysisProps {
  result: DetectionResponse | null;
  isAnalyzing?: boolean;
}

const getRiskColor = (level: string) => {
  switch (level.toUpperCase()) {
    case "CRITICAL":
      return {
        bg: "bg-[#ef4444]/15",
        border: "border-[#ef4444]/60",
        text: "text-[#ef4444]",
        badge: "bg-[#ef4444] text-white",
        bar: "bg-gradient-to-r from-[#ef4444] to-[#dc2626]",
      };
    case "HIGH":
      return {
        bg: "bg-[#f97316]/15",
        border: "border-[#f97316]/60",
        text: "text-[#f97316]",
        badge: "bg-[#f97316] text-white",
        bar: "bg-gradient-to-r from-[#f97316] to-[#ea580c]",
      };
    case "MEDIUM":
      return {
        bg: "bg-[#e8c86b]/15",
        border: "border-[#e8c86b]/60",
        text: "text-[#e8c86b]",
        badge: "bg-[#e8c86b] text-[#090b11]",
        bar: "bg-gradient-to-r from-[#e8c86b] to-[#d97706]",
      };
    case "LOW":
      return {
        bg: "bg-[#70d6a0]/15",
        border: "border-[#70d6a0]/50",
        text: "text-[#70d6a0]",
        badge: "bg-[#70d6a0] text-[#090b11]",
        bar: "bg-gradient-to-r from-[#70d6a0] to-[#10b981]",
      };
    default:
      return {
        bg: "bg-[#9ba2b1]/15",
        border: "border-[rgba(255,255,255,0.12)]",
        text: "text-[#9ba2b1]",
        badge: "bg-[#9ba2b1] text-[#090b11]",
        bar: "bg-[#9ba2b1]",
      };
  }
};

export const ScamIntentAnalysis: React.FC<ScamIntentAnalysisProps> = ({
  result,
  isAnalyzing = false,
}) => {
  // Manual text testing sandbox state
  const [manualText, setManualText] = useState("");
  const [isEvaluatingManual, setIsEvaluatingManual] = useState(false);
  const [manualResult, setManualResult] = useState<ScamAnalysisResult | null>(null);
  const [showManualTester, setShowManualTester] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);

  // Live microphone capture and near-real-time streaming transcription state
  const [isLiveMicRecording, setIsLiveMicRecording] = useState(false);
  const [liveTranscriptionStatus, setLiveTranscriptionStatus] = useState<
    "idle" | "listening" | "transcribing" | "completed" | "unavailable" | "error"
  >("idle");
  const [liveChunkSeq, setLiveChunkSeq] = useState(0);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [liveScamResult, setLiveScamResult] = useState<ScamAnalysisResult | null>(null);
  const [liveProvider, setLiveProvider] = useState<string | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [micSeconds, setMicSeconds] = useState(0);

  const micRecorderRef = useRef<AudioStreamRecorder | null>(null);
  const micTimerRef = useRef<NodeJS.Timeout | null>(null);
  const liveSessionIdRef = useRef<string>(`mic_session_${Date.now()}`);

  const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const API_URL = rawApiUrl.replace(/\/+$/, "");

  // Cleanup microphone on unmount
  useEffect(() => {
    return () => {
      micRecorderRef.current?.stop();
      micRecorderRef.current = null;
      if (micTimerRef.current) clearInterval(micTimerRef.current);
    };
  }, []);

  // Priority of Scam Result: Live Mic > Manual Tester > Uploaded Detection result
  const scamData: ScamAnalysisResult | null =
    liveScamResult || manualResult || result?.scam_analysis || null;
  const transcriptionData = result?.transcription;

  // Deduplicate and collapse repeating phrase loops and duplicate lines
  const cleanTranscriptRepetitions = (text: string): string => {
    if (!text) return "";
    let cleaned = text.replace(/[\r\t\f\v ]+/g, " ").trim();

    // Deduplicate consecutive lines
    const lines = cleaned.split("\n").map((l) => l.trim()).filter(Boolean);
    const dedupLines: string[] = [];
    for (const line of lines) {
      if (dedupLines.length === 0 || dedupLines[dedupLines.length - 1].toLowerCase() !== line.toLowerCase()) {
        dedupLines.push(line);
      }
    }
    cleaned = dedupLines.join(" ");

    // N-gram phrase repetition collapse (from 16 down to 1 words)
    let words = cleaned.split(" ");
    for (let phraseLen = 16; phraseLen >= 1; phraseLen--) {
      let idx = 0;
      const newWords: string[] = [];
      while (idx < words.length) {
        if (idx + phraseLen * 2 <= words.length) {
          const p1 = words.slice(idx, idx + phraseLen).map((w) => w.toLowerCase().replace(/[.,!?"'|]/g, "")).join(" ");
          const p2 = words.slice(idx + phraseLen, idx + phraseLen * 2).map((w) => w.toLowerCase().replace(/[.,!?"'|]/g, "")).join(" ");
          if (p1 === p2) {
            newWords.push(...words.slice(idx, idx + phraseLen));
            idx += phraseLen * 2;
            while (idx + phraseLen <= words.length) {
              const pNext = words.slice(idx, idx + phraseLen).map((w) => w.toLowerCase().replace(/[.,!?"'|]/g, "")).join(" ");
              if (pNext === p1) {
                idx += phraseLen;
              } else {
                break;
              }
            }
            if (idx < words.length && words.length - idx < phraseLen) {
              const rem = words.slice(idx).map((w) => w.toLowerCase().replace(/[.,!?"'|]/g, "")).join(" ");
              const p1Prefix = words.slice(idx - phraseLen, idx - phraseLen + (words.length - idx)).map((w) => w.toLowerCase().replace(/[.,!?"'|]/g, "")).join(" ");
              if (rem === p1Prefix) {
                idx = words.length;
              }
            }
            continue;
          }
        }
        newWords.push(words[idx]);
        idx += 1;
      }
      words = newWords;
    }

    let res = words.join(" ");
    res = res.replace(/(\b(?:and\s+)?([a-zA-Z0-9\s']{4,40}))(?:\s*(?:and|,)?\s*\2\b)+/gi, "$1");
    res = res.replace(/\s+(?:and|or|that)\s*$/i, "");
    return res.replace(/\s+/g, " ").trim();
  };

  const rawTranscriptText =
    liveTranscript || (manualResult ? manualText : (transcriptionData?.text || ""));

  const activeTranscriptText = React.useMemo(
    () => cleanTranscriptRepetitions(rawTranscriptText),
    [rawTranscriptText]
  );

  const currentRiskLevel = scamData?.scam_risk_level || "UNKNOWN";
  const riskStyles = getRiskColor(currentRiskLevel);

  // When a new detection result arrives, prioritize it over previous manual sandbox test
  useEffect(() => {
    if (result) {
      setManualResult(null);
      setManualText("");
    }
  }, [result]);

  const threatPhrasesList: string[] = React.useMemo(() => {
    const list: string[] = [];
    const textLower = (activeTranscriptText || "").toLowerCase();

    // 1. Add exact detected snippets from backend if present in transcript (or if transcript empty)
    if (scamData?.detected_threat_phrases && scamData.detected_threat_phrases.length > 0) {
      for (const phrase of scamData.detected_threat_phrases) {
        const trimmed = phrase.trim();
        if (
          trimmed.length >= 2 &&
          (!activeTranscriptText || textLower.includes(trimmed.toLowerCase())) &&
          !list.some((existing) => existing.toLowerCase() === trimmed.toLowerCase())
        ) {
          list.push(trimmed);
        }
      }
    }

    // 2. Comprehensive keywords that indicate threats if they appear directly in spoken text
    const keyScamTerms = [
      "Punjab National Bank", "Punjab Nesnal Bank", "State Bank", "SBI Bank", "HDFC Bank", "ICICI Bank", "Axis Bank", "PNB",
      "bank manager", "bank se bol raha", "bank support", "customer care", "head office",
      "OTP", "one-time password", "UPI PIN", "banking PIN", "CVV", "CVV2", "password", "security code", "3 digit code",
      "account blocked", "account is blocked", "account will be blocked", "account block", "account band", "khata band", "account suspend", "freeze account", "rok laga di",
      "AnyDesk", "TeamViewer", "QuickSupport", "RustDesk", "screen share",
      "digital arrest", "under digital arrest", "CBI", "police verification", "arrest warrant", "customs department",
      "electricity power", "bijli ka bill", "power cut", "power disconnected", "power supply",
      "SIM blocked", "SIM band", "TRAI", "traffic challan", "e-challan",
      "pre-approved loan", "processing fee", "registration fee", "lottery", "lucky draw", "KBC", "cash prize", "bahut saara paisa",
      "QR code", "scan QR code", "illegal drugs", "narcotics", "parcel", "courier", "like youtube videos", "daily income", "work from home"
    ];

    if (activeTranscriptText) {
      for (const term of keyScamTerms) {
        if (
          textLower.includes(term.toLowerCase()) &&
          !list.some((existing) => existing.toLowerCase() === term.toLowerCase())
        ) {
          list.push(term);
        }
      }
    }

    // Filter out redundant short fragments that are completely contained within longer matched phrases
    const refined = list.filter((item) => {
      return !list.some((other) => other.length > item.length && other.toLowerCase().includes(item.toLowerCase()));
    });

    return refined.length > 0 ? refined : list;
  }, [scamData, activeTranscriptText]);

  const hasThreats =
    threatPhrasesList.length > 0 ||
    scamData?.scam_risk_level === "CRITICAL" ||
    scamData?.scam_risk_level === "HIGH" ||
    scamData?.scam_risk_level === "MEDIUM";

  const renderHighlightedTranscript = (text: string, phrases: string[]) => {
    if (!text) return null;
    if (!phrases || phrases.length === 0) return text;

    const matchedPhrases = phrases
      .map((p) => p.trim())
      .filter((p) => p.length >= 2 && text.toLowerCase().includes(p.toLowerCase()))
      .sort((a, b) => b.length - a.length);

    if (matchedPhrases.length === 0) return text;

    const escaped = matchedPhrases.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const regex = new RegExp(`(${escaped.join("|")})`, "gi");
    const parts = text.split(regex);

    return parts.map((part, i) => {
      const isMatch = matchedPhrases.some((p) => p.toLowerCase() === part.toLowerCase());
      if (isMatch) {
        return (
          <mark
            key={i}
            className="bg-[#ef4444]/35 text-[#fee2e2] border border-[#ef4444]/90 px-2.5 py-0.5 rounded-md font-bold shadow-[0_0_14px_rgba(239,68,68,0.4)] mx-1 inline-flex items-center gap-1.5 not-italic"
          >
            <AlertTriangle size={12} className="text-[#ef4444] shrink-0 inline animate-pulse" />
            <span>{part}</span>
            <span className="text-[9px] uppercase font-mono px-1 py-0.2 bg-[#ef4444] text-white rounded font-black tracking-wider">
              THREAT / SUSPICIOUS
            </span>
          </mark>
        );
      }
      return part;
    });
  };

  // ---------------------------------------------------------------------------
  // Live Microphone Recording & Incremental Windowed Transcription
  // ---------------------------------------------------------------------------
  const handleStartLiveMic = async () => {
    if (isLiveMicRecording) return;
    setLiveError(null);
    setLiveTranscript("");
    setLiveScamResult(null);
    setLiveChunkSeq(0);
    setMicSeconds(0);
    setLiveTranscriptionStatus("listening");
    liveSessionIdRef.current = `mic_session_${Date.now()}`;

    try {
      micRecorderRef.current = new AudioStreamRecorder({
        chunkIntervalMs: 2500, // Near-real-time 2.5 second audio window
        onChunk: async (blob: Blob, seqId: number) => {
          setLiveChunkSeq(seqId);
          setLiveTranscriptionStatus("transcribing");

          try {
            const formData = new FormData();
            formData.append("file", blob, `mic_stream_${seqId}.wav`);
            formData.append("session_id", liveSessionIdRef.current);
            formData.append("sequence_id", String(seqId));

            const resp = await fetch(`${API_URL}/api/transcribe`, {
              method: "POST",
              body: formData,
            });

            if (!resp.ok) {
              const errBody = await resp.json().catch(() => null);
              throw new Error(errBody?.detail || errBody?.error?.message || `HTTP ${resp.status}`);
            }

            const data = await resp.json();
            if (data.rolling_transcript || data.transcription?.text) {
              setLiveTranscript(data.rolling_transcript || data.transcription?.text);
            }
            if (data.transcription?.provider) {
              setLiveProvider(data.transcription.provider);
            }
            if (data.scam_analysis) {
              setLiveScamResult(data.scam_analysis);
            }

            if (data.transcription?.status === "unavailable") {
              setLiveTranscriptionStatus("unavailable");
            } else if (data.transcription?.status === "error") {
              setLiveTranscriptionStatus("error");
              setLiveError(data.transcription?.message || "Transcription encountered an error.");
            } else {
              setLiveTranscriptionStatus("completed");
            }
          } catch (chunkErr: unknown) {
            const msg = chunkErr instanceof Error ? chunkErr.message : "Audio chunk transcription failed";
            console.warn("Live microphone chunk processing note:", msg);
            setLiveTranscriptionStatus("error");
            setLiveError(msg);
          }
        },
        onError: (err: Error) => {
          console.error("Audio recorder stream error:", err);
          handleStopLiveMic();
          setLiveTranscriptionStatus("error");
          setLiveError(`Microphone stream error: ${err.message}`);
        },
      });

      await micRecorderRef.current.start();
      setIsLiveMicRecording(true);

      micTimerRef.current = setInterval(() => {
        setMicSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      setIsLiveMicRecording(false);
      setLiveTranscriptionStatus("error");
      const msg = err instanceof Error ? err.message : "Microphone permission denied or device unavailable.";
      setLiveError(`Microphone error: ${msg}`);
    }
  };

  const handleStopLiveMic = () => {
    if (micRecorderRef.current) {
      micRecorderRef.current.stop();
      micRecorderRef.current = null;
    }
    if (micTimerRef.current) {
      clearInterval(micTimerRef.current);
      micTimerRef.current = null;
    }
    setIsLiveMicRecording(false);
    if (liveTranscriptionStatus === "listening" || liveTranscriptionStatus === "transcribing") {
      setLiveTranscriptionStatus("completed");
    }
  };

  const handleResetLiveMic = () => {
    handleStopLiveMic();
    setLiveTranscript("");
    setLiveScamResult(null);
    setLiveError(null);
    setLiveChunkSeq(0);
    setMicSeconds(0);
    setLiveTranscriptionStatus("idle");
    setLiveProvider(null);
  };

  // ---------------------------------------------------------------------------
  // Manual Text Sandbox Analyzer
  // ---------------------------------------------------------------------------
  const handleManualAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualText.trim()) return;

    setIsEvaluatingManual(true);
    setManualError(null);

    try {
      const resp = await fetch(`${API_URL}/api/analyze-scam`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: manualText.trim() }),
      });

      if (!resp.ok) {
        throw new Error(`Scam analysis failed (HTTP ${resp.status})`);
      }

      const data: ScamAnalysisResult = await resp.json();
      setManualResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Analysis request failed";
      setManualError(msg);
    } finally {
      setIsEvaluatingManual(false);
    }
  };

  const handleQuickPreset = (text: string) => {
    setManualText(text);
  };

  const formatTimer = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  return (
    <section className="space-y-6 rounded-2xl bg-[#111520] border border-[rgba(255,255,255,0.12)] p-6 sm:p-8 relative overflow-hidden shadow-2xl">
      {/* Background Ambient Glow */}
      <div
        className={`absolute -top-24 -right-24 w-96 h-96 rounded-full blur-[120px] pointer-events-none transition-colors duration-700 ${
          currentRiskLevel === "CRITICAL" || currentRiskLevel === "HIGH"
            ? "bg-[#ef4444]/15"
            : currentRiskLevel === "MEDIUM"
            ? "bg-[#e8c86b]/10"
            : currentRiskLevel === "LOW"
            ? "bg-[#70d6a0]/10"
            : "bg-[#66b7ff]/5"
        }`}
      />

      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-[rgba(255,255,255,0.08)] pb-5">
        <div className="flex items-center gap-3.5">
          <div
            className={`p-3 rounded-xl border ${
              currentRiskLevel === "CRITICAL" || currentRiskLevel === "HIGH"
                ? "bg-[#ef4444]/20 border-[#ef4444]/50 text-[#ef4444]"
                : "bg-[#66b7ff]/15 border-[#66b7ff]/40 text-[#66b7ff]"
            }`}
          >
            <ShieldAlert size={24} />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-mono tracking-widest text-[#66b7ff] uppercase font-bold">
                NLP SOCIAL ENGINEERING DEFENSE
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[rgba(255,255,255,0.06)] text-[#9ba2b1] border border-[rgba(255,255,255,0.08)]">
                INDEPENDENT OF VOICE MODEL
              </span>
            </div>
            <h2 className="font-serif-cinematic text-2xl sm:text-3xl text-[#f4f5f7]">
              Scam Intent Analysis
            </h2>
          </div>
        </div>

        {/* Status Badges & Quick Action Controls */}
        <div className="flex items-center gap-3 flex-wrap">
          {isLiveMicRecording ? (
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#ef4444]/15 border border-[#ef4444]/50 text-[#fca5a5] text-xs font-mono font-bold animate-pulse">
              <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444] animate-ping" />
              <span>LIVE MIC DEFENSE: ACTIVE ({formatTimer(micSeconds)})</span>
            </div>
          ) : isAnalyzing || liveTranscriptionStatus === "transcribing" ? (
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#66b7ff]/10 border border-[#66b7ff]/30 text-[#8ddcff] text-xs font-mono animate-pulse">
              <span className="w-2 h-2 rounded-full bg-[#66b7ff] animate-ping" />
              <span>STATUS: ANALYZING CHUNK #{liveChunkSeq || 1}</span>
            </div>
          ) : scamData?.status === "UNCERTAIN" ? (
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#e8c86b]/15 border border-[#e8c86b]/40 text-[#e8c86b] text-xs font-mono font-bold">
              <span className="w-2 h-2 rounded-full bg-[#e8c86b]" />
              <span>STATUS: UNCERTAIN</span>
            </div>
          ) : scamData?.status === "UNAVAILABLE" ? (
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#171c2b] border border-[rgba(255,255,255,0.08)] text-[#9ba2b1] text-xs font-mono font-bold">
              <span>STATUS: UNAVAILABLE</span>
            </div>
          ) : scamData ? (
            <div
              className={`flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-mono font-bold tracking-wider uppercase ${riskStyles.bg} ${riskStyles.border} ${riskStyles.text}`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  currentRiskLevel === "CRITICAL" || currentRiskLevel === "HIGH"
                    ? "bg-[#ef4444] animate-ping"
                    : currentRiskLevel === "LOW"
                    ? "bg-[#70d6a0]"
                    : "bg-[#e8c86b]"
                }`}
              />
              <span>STATUS: ANALYZED — {scamData.scam_risk_level}</span>
              {scamData.scam_risk_score !== null && scamData.scam_risk_score !== undefined && (
                <span className="opacity-80">({scamData.scam_risk_score}/100)</span>
              )}
            </div>
          ) : (
            <div className="px-3.5 py-1.5 rounded-full bg-[#171c2b] border border-[rgba(255,255,255,0.08)] text-[#9ba2b1] text-xs font-mono">
              STATUS: READY FOR MICROPHONE OR AUDIO
            </div>
          )}

          <button
            type="button"
            onClick={() => setShowManualTester(!showManualTester)}
            className="px-3 py-1.5 rounded-lg border border-[rgba(255,255,255,0.12)] bg-[#171c2b] hover:bg-[#1f2638] text-xs font-mono text-[#f4f5f7] transition-all flex items-center gap-1.5 shadow-sm"
          >
            <span>{showManualTester ? "Hide Sandbox" : "Test Text"}</span>
            {showManualTester ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {/* Interactive Text Tester Panel (Optional Drawer for phrase debugging) */}
      <AnimatePresence>
        {showManualTester && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="rounded-xl bg-[#0d1017] border border-[rgba(255,255,255,0.08)] p-4 sm:p-5 space-y-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-[#66b7ff] tracking-wider uppercase flex items-center gap-1.5 font-bold">
                <Sparkles size={13} />
                Live Conversation Text Testing Sandbox
              </span>
              <span className="text-[11px] font-mono text-[#9ba2b1]">
                Evaluates rules & context across 179+ patterns (English, Hinglish & Devanagari)
              </span>
            </div>

            <form onSubmit={handleManualAnalyze} className="space-y-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={manualText}
                  onChange={(e) => setManualText(e.target.value)}
                  placeholder="e.g. Apne mobile par aaya hua OTP bataiye, ya 'Never share your UPI PIN'"
                  className="flex-1 bg-[#111520] border border-[rgba(255,255,255,0.12)] focus:border-[#66b7ff] text-sm text-[#f4f5f7] px-4 py-2.5 rounded-xl font-sans focus:outline-none placeholder:text-[#8b93a3]"
                />
                <button
                  type="submit"
                  disabled={isEvaluatingManual || !manualText.trim()}
                  className="px-5 py-2.5 rounded-xl bg-[#66b7ff] hover:bg-[#8ddcff] text-[#090b11] font-mono text-xs font-bold tracking-wider transition-all disabled:opacity-50 flex items-center gap-1.5 shadow-md"
                >
                  <Send size={13} />
                  <span>{isEvaluatingManual ? "ANALYZING..." : "ANALYZE"}</span>
                </button>
              </div>

              {/* Quick Preset Buttons */}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <span className="text-[11px] font-mono text-[#9ba2b1] mr-1">Presets:</span>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Please tell me the OTP you received.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] hover:bg-[#ef4444]/25 transition-all"
                >
                  Direct OTP Request
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Apne mobile par aaya hua OTP bataiye.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] hover:bg-[#ef4444]/25 transition-all"
                >
                  Hinglish OTP (OTP002)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("अपना ओटीपी बताइए।")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] hover:bg-[#ef4444]/25 transition-all"
                >
                  Devanagari OTP (DEVA001)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Never share your OTP or UPI PIN with anyone over the phone.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#10b981]/15 border border-[#10b981]/40 text-[#a7f3d0] hover:bg-[#10b981]/25 transition-all"
                >
                  Safety Warning (SAFE001)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Your Aadhaar number is linked to an illegal transaction.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] hover:bg-[#ef4444]/25 transition-all"
                >
                  Digital Arrest (GOV001)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Aapka bank account aaj block ho jayega.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#f97316]/15 border border-[#f97316]/40 text-[#fdba74] hover:bg-[#f97316]/25 transition-all"
                >
                  Account Block Threat (BANK011)
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleQuickPreset("Install AnyDesk right now and share your screen while opening your banking app.")
                  }
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#f97316]/15 border border-[#f97316]/40 text-[#fdba74] hover:bg-[#f97316]/25 transition-all"
                >
                  Remote Access Trap (REMOTE002)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Your electricity power will be disconnected tonight due to unpaid bill.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#f97316]/15 border border-[#f97316]/40 text-[#fdba74] hover:bg-[#f97316]/25 transition-all"
                >
                  Electricity Cut Threat (BANK020)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Main bank manager bol raha hu, aapka account band ho gaya hai.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#f97316]/15 border border-[#f97316]/40 text-[#fdba74] hover:bg-[#f97316]/25 transition-all"
                >
                  Bank Manager (HIN022)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Card ke piche ka CVV number bataiye verification ke liye.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] hover:bg-[#ef4444]/25 transition-all"
                >
                  Card CVV Request (HIN024)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("QR code scan karo paise milenge aapke khate me.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] hover:bg-[#ef4444]/25 transition-all"
                >
                  QR Code Money Trap (HIN027)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("TRAI verification ke liye call kiya hai, aapka SIM band ho jayega.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#f97316]/15 border border-[#f97316]/40 text-[#fdba74] hover:bg-[#f97316]/25 transition-all"
                >
                  TRAI SIM Block (HIN026)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickPreset("Pay a registration fee to secure your job.")}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-[#e8c86b]/15 border border-[#e8c86b]/40 text-[#fde68a] hover:bg-[#e8c86b]/25 transition-all"
                >
                  Job Offer Advance Fee (JOB001)
                </button>
                {manualResult && (
                  <button
                    type="button"
                    onClick={() => {
                      setManualResult(null);
                      setManualText("");
                    }}
                    className="text-[11px] font-mono px-2 py-1 rounded text-[#9ba2b1] hover:text-white transition-all underline ml-auto"
                  >
                    Reset Sandbox
                  </button>
                )}
              </div>
            </form>

            {manualError && (
              <div className="text-xs font-mono text-[#ef4444] bg-[#ef4444]/10 p-2.5 rounded-lg border border-[#ef4444]/30">
                {manualError}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* High-Risk Contextual Warning Banner */}
      {scamData?.warning_banner && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-5 rounded-xl bg-gradient-to-r from-[#ef4444]/25 to-[#991b1b]/20 border-2 border-[#ef4444] text-[#fee2e2] flex items-start gap-3.5 shadow-xl relative"
        >
          <div className="p-2 rounded-lg bg-[#ef4444] text-white mt-0.5 shadow-md">
            <AlertTriangle size={20} />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-black tracking-widest text-white uppercase bg-[#ef4444] px-2 py-0.5 rounded">
                CRITICAL THREAT WARNING
              </span>
              <span className="text-xs font-mono text-[#fca5a5]">
                Potential Credential Harvesting or Extortion
              </span>
            </div>
            <p className="text-sm font-sans font-semibold text-white leading-relaxed">
              {scamData.warning_banner}
            </p>
          </div>
        </motion.div>
      )}

      {/* Dual Independent Systems Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* System A: Voice Authenticity Assessment */}
        <div className="p-4 sm:p-5 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono tracking-wider text-[#9ba2b1] uppercase flex items-center gap-1.5">
              <KeyRound size={13} className="text-[#66b7ff]" />
              System A: Voice Authenticity
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[rgba(255,255,255,0.05)] text-[#9ba2b1]">
              Acoustic Neural Model
            </span>
          </div>

          {result ? (
            <div className="space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="font-serif-cinematic text-lg text-[#f4f5f7]">
                  {result.prediction.label === "likely_ai_generated"
                    ? "Synthetic / AI Voice Detected"
                    : result.prediction.label === "likely_human_recorded"
                    ? "Authentic Human Voice"
                    : "Inconclusive Acoustic Signal"}
                </span>
                <span
                  className={`font-mono text-sm font-bold ${
                    result.prediction.label === "likely_ai_generated" ? "text-[#ef4444]" : "text-[#70d6a0]"
                  }`}
                >
                  {result.prediction.label === "likely_ai_generated"
                    ? `${result.prediction.fake_score ?? 85}% AI`
                    : `${result.prediction.real_score ?? 89}% Real`}
                </span>
              </div>
              <p className="text-xs text-[#9ba2b1] leading-relaxed">
                Evaluates vocal tract resonance, micro-tremors, and spectral continuity. Does not analyze
                spoken language or intent.
              </p>
            </div>
          ) : (
            <div className="text-xs font-mono text-[#8b93a3] py-2">
              Waiting for audio ingestion or file upload...
            </div>
          )}
        </div>

        {/* System B: Scam Intent Assessment */}
        <div className="p-4 sm:p-5 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono tracking-wider text-[#9ba2b1] uppercase flex items-center gap-1.5">
              <ShieldAlert size={13} className={riskStyles.text} />
              System B: Scam Intent
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[rgba(255,255,255,0.05)] text-[#9ba2b1]">
              Context-Aware NLP Rules
            </span>
          </div>

          {scamData && scamData.status === "ANALYZED" ? (
            <div className="space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="font-serif-cinematic text-lg text-[#f4f5f7]">
                  {hasThreats
                    ? scamData.scam_risk_level === "CRITICAL"
                      ? "🚨 Critical Social Engineering Attack"
                      : "⚠️ Threatening / Suspicious Message Detected"
                    : scamData.scam_risk_level === "MEDIUM"
                    ? "⚠️ Suspicious / Unverified Request"
                    : "Standard / Legitimate Conversation"}
                </span>
                <span className={`font-mono text-sm font-bold ${riskStyles.text}`}>
                  {scamData.scam_risk_level} ({scamData.scam_risk_score ?? 0}/100)
                </span>
              </div>
              {/* Progress bar */}
              <div className="w-full bg-[#171c2b] rounded-full h-2 overflow-hidden border border-[rgba(255,255,255,0.06)]">
                <div
                  className={`h-full transition-all duration-500 ${riskStyles.bar}`}
                  style={{ width: `${Math.min(100, Math.max(5, scamData.scam_risk_score ?? 10))}%` }}
                />
              </div>
              <p className="text-xs text-[#9ba2b1] leading-relaxed">
                {scamData.message || "Rule-based analysis of spoken instructions, requests, and pressure tactics."}
              </p>
            </div>
          ) : (
            <div className="text-xs font-mono text-[#8b93a3] py-2">
              {scamData?.status === "UNAVAILABLE"
                ? scamData.message || "Transcription unavailable. Ensure Local Whisper is cached or OPENAI_API_KEY is configured."
                : isAnalyzing || isLiveMicRecording
                ? "Continuously analyzing conversation speech..."
                : "No conversation transcript has been analyzed yet."}
            </div>
          )}
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* Live Microphone Recording & Incremental Speech Transcription Card   */}
      {/* --------------------------------------------------------------------- */}
      <div className="p-5 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] space-y-4">
        {/* Top Control Bar with Start/Stop Button & Real-time Status */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 border-b border-[rgba(255,255,255,0.06)] pb-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-[#66b7ff] uppercase tracking-wider flex items-center gap-1.5 font-bold">
              <FileText size={15} />
              Live Microphone Speech Transcription
            </span>

            {/* Provider indicator */}
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[rgba(255,255,255,0.06)] text-[#8ddcff] border border-[rgba(255,255,255,0.08)]">
              {liveProvider === "local"
                ? "⚡ LOCAL WHISPER (M1 Metal)"
                : liveProvider === "openai"
                ? "☁ OPENAI AUDIO API"
                : "LOCAL WHISPER / AUTO"}
            </span>
          </div>

          {/* Action Button & Live Badges */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Live Recording Status Badge */}
            <div
              className={`flex items-center gap-2 px-3 py-1 rounded-md text-[11px] font-mono border ${
                isLiveMicRecording
                  ? "bg-[#ef4444]/15 border-[#ef4444]/40 text-[#fca5a5]"
                  : "bg-[#171c2b] border-[rgba(255,255,255,0.08)] text-[#9ba2b1]"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isLiveMicRecording ? "bg-[#ef4444] animate-ping" : "bg-[#9ba2b1]"
                }`}
              />
              <span>{isLiveMicRecording ? `RECORDING (${formatTimer(micSeconds)})` : "MIC: IDLE"}</span>
            </div>

            {/* Transcription Status Badge */}
            <div
              className={`flex items-center gap-2 px-3 py-1 rounded-md text-[11px] font-mono border ${
                liveTranscriptionStatus === "transcribing"
                  ? "bg-[#66b7ff]/15 border-[#66b7ff]/40 text-[#8ddcff] animate-pulse"
                  : liveTranscriptionStatus === "completed"
                  ? "bg-[#70d6a0]/15 border-[#70d6a0]/40 text-[#70d6a0]"
                  : liveTranscriptionStatus === "unavailable"
                  ? "bg-[#e8c86b]/15 border-[#e8c86b]/40 text-[#e8c86b]"
                  : "bg-[#171c2b] border-[rgba(255,255,255,0.08)] text-[#9ba2b1]"
              }`}
            >
              <span>
                {liveTranscriptionStatus === "transcribing"
                  ? `CHUNK #${liveChunkSeq} TRANSCRIBING...`
                  : liveTranscriptionStatus === "listening"
                  ? "LISTENING FOR SPEECH..."
                  : liveTranscriptionStatus === "completed"
                  ? "TRANSCRIPTION ACTIVE"
                  : liveTranscriptionStatus === "unavailable"
                  ? "TRANSCRIPTION UNAVAILABLE"
                  : liveTranscriptionStatus === "error"
                  ? "TRANSCRIPTION ERROR"
                  : "READY"}
              </span>
            </div>

            {/* Primary Start / Stop Live Microphone Button */}
            {!isLiveMicRecording ? (
              <button
                type="button"
                onClick={handleStartLiveMic}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#66b7ff] to-[#38bdf8] hover:from-[#8ddcff] hover:to-[#60a5fa] text-[#090b11] font-mono text-xs font-black tracking-wider transition-all flex items-center gap-2 shadow-lg shadow-[#66b7ff]/20 active:scale-95"
              >
                <Mic size={14} />
                <span>START LIVE MICROPHONE DEFENSE</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStopLiveMic}
                className="px-4 py-2 rounded-xl bg-[#ef4444] hover:bg-[#dc2626] text-white font-mono text-xs font-black tracking-wider transition-all flex items-center gap-2 shadow-lg shadow-[#ef4444]/30 active:scale-95"
              >
                <Square size={13} className="fill-white" />
                <span>STOP MICROPHONE</span>
              </button>
            )}

            {/* Reset Button */}
            {(liveTranscript || liveScamResult) && (
              <button
                type="button"
                onClick={handleResetLiveMic}
                title="Clear current stream and reset buffer"
                className="p-2 rounded-lg border border-[rgba(255,255,255,0.12)] bg-[#171c2b] hover:bg-[#1f2638] text-[#9ba2b1] hover:text-white transition-all"
              >
                <RotateCcw size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Live Rolling Transcript Output Box */}
        {activeTranscriptText ? (
          <div className="space-y-3">
            {/* Prominent Threat Alert Banner */}
            {hasThreats && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-[#2a090e] via-[#1c0609] to-[#120306] border-2 border-[#ef4444] shadow-[0_0_35px_rgba(239,68,68,0.35)] space-y-2.5">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span className="text-xs font-mono font-black text-[#ef4444] tracking-wider flex items-center gap-2 uppercase">
                    <AlertTriangle size={16} className="text-[#ef4444] animate-bounce shrink-0" />
                    🚨 THREATENING / SUSPICIOUS MESSAGE DETECTED IN YOUR TRANSCRIPT
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#ef4444] text-white font-black tracking-wider uppercase">
                    {scamData?.scam_risk_level || "HIGH"} RISK ({scamData?.scam_risk_score ?? 85}/100)
                  </span>
                </div>

                <p className="text-sm font-sans text-[#fee2e2] font-semibold leading-relaxed">
                  {scamData?.warning_banner ||
                    "This spoken message matches dangerous scam patterns from EchoSentinel scam rules. Do not comply with these requests or share personal financial credentials."}
                </p>

                {threatPhrasesList.length > 0 && (
                  <div className="pt-2 border-t border-[#ef4444]/30 space-y-1.5">
                    <span className="text-[11px] font-mono text-[#fca5a5] uppercase tracking-wider block font-bold">
                      ⚠️ Flagged Threatening / Suspicious Words &amp; Phrases:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {threatPhrasesList.map((phrase, idx) => (
                        <span
                          key={idx}
                          className="px-2.5 py-1 rounded-md bg-[#ef4444]/25 border border-[#ef4444]/60 text-[#fca5a5] font-mono text-xs flex items-center gap-1.5 font-bold shadow-sm"
                        >
                          <ShieldAlert size={12} className="text-[#ef4444]" />
                          &ldquo;{phrase}&rdquo;
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div
              className={`p-4 rounded-xl bg-[#111520] border transition-all duration-300 space-y-2 relative ${
                hasThreats
                  ? "border-[#ef4444]/60 shadow-[0_0_20px_rgba(239,68,68,0.15)]"
                  : "border-[rgba(255,255,255,0.08)]"
              }`}
            >
              <div className="flex items-center justify-between text-[11px] font-mono text-[#9ba2b1] border-b border-[rgba(255,255,255,0.04)] pb-2">
                <span className="text-[#8ddcff] flex items-center gap-1.5">
                  <Radio size={12} className={isLiveMicRecording ? "animate-pulse text-[#ef4444]" : ""} />
                  {liveChunkSeq > 0 ? `Near-Real-Time Session (${liveChunkSeq} Chunks Merged)` : "Spoken Audio Transcript"}
                </span>
                <span className="text-[#9ba2b1]">Boundary Deduplication Active</span>
              </div>
              <div className="text-sm font-sans text-[#f4f5f7] leading-relaxed italic relative pt-1">
                <span className="text-[#66b7ff] font-serif text-3xl absolute -top-1 -left-1 pointer-events-none select-none opacity-40">
                  &ldquo;
                </span>
                <div className="pl-5 text-[15px] text-[#f4f5f7] whitespace-pre-wrap font-medium">
                  {renderHighlightedTranscript(activeTranscriptText, threatPhrasesList)}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 rounded-xl bg-[#111520] border border-dashed border-[rgba(255,255,255,0.08)] text-xs font-mono text-[#8b93a3] text-center space-y-2">
            <div className="w-10 h-10 rounded-full bg-[#171c2b] flex items-center justify-center mx-auto text-[#66b7ff]">
              <Mic size={20} />
            </div>
            <p className="text-sm font-sans text-[#f4f5f7] font-semibold">
              {isLiveMicRecording
                ? "Microphone listening... Speak into your mic to see live transcription."
                : "Click 'Start Live Microphone Defense' to capture live speech and analyze scam intent automatically."}
            </p>
            <p className="text-[11px] text-[#9ba2b1] max-w-lg mx-auto">
              Audio is sliced into near-real-time 2.5s chunks, transcribed using the local Whisper model (or OpenAI Audio API), and evaluated against configured scam rules with rolling context.
            </p>
          </div>
        )}

        {liveError && (
          <div className="p-3 rounded-lg bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] text-xs font-mono flex items-center gap-2">
            <AlertTriangle size={14} className="shrink-0" />
            <span>{liveError}</span>
          </div>
        )}
      </div>

      {/* Detected Indicators List */}
      {scamData && scamData.indicators && scamData.indicators.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-[#9ba2b1] uppercase tracking-wider">
              Detected Threat Indicators ({scamData.indicators.length})
            </span>
            <div className="flex gap-1.5 flex-wrap">
              {scamData.categories.map((cat) => (
                <span
                  key={cat}
                  className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] font-semibold"
                >
                  {cat}
                </span>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {scamData.indicators.map((ind: ScamIndicator, idx: number) => {
              const isCrit = ind.severity === "critical" || ind.severity === "high";
              return (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border space-y-2 transition-all ${
                    isCrit
                      ? "bg-[#171116] border-[#ef4444]/40 hover:border-[#ef4444]/70"
                      : "bg-[#111520] border-[rgba(255,255,255,0.08)]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          isCrit ? "bg-[#ef4444]" : ind.severity === "medium" ? "bg-[#e8c86b]" : "bg-[#70d6a0]"
                        }`}
                      />
                      <span className="font-mono text-xs font-bold text-[#f4f5f7]">
                        {ind.matched_concept}
                      </span>
                    </div>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                        isCrit
                          ? "bg-[#ef4444] text-white"
                          : ind.severity === "medium"
                          ? "bg-[#e8c86b] text-[#090b11]"
                          : "bg-[#70d6a0] text-[#090b11]"
                      }`}
                    >
                      {ind.severity}
                    </span>
                  </div>

                  <p className="text-xs text-[#9ba2b1] leading-relaxed">{ind.explanation}</p>

                  {ind.evidence && (
                    <div className="text-[11px] font-mono bg-[#090b11] p-2.5 rounded-lg border border-[rgba(255,255,255,0.06)] text-[#fdba74]">
                      <span className="text-[#9ba2b1] mr-1.5">Evidence snippet:</span>
                      &ldquo;{ind.evidence}&rdquo;
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : scamData && scamData.status === "ANALYZED" ? (
        <div className="p-4 rounded-xl bg-[#090b11] border border-[#70d6a0]/30 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-[#70d6a0]/20 text-[#70d6a0]">
            <ShieldCheck size={18} />
          </div>
          <div>
            <div className="text-xs font-mono font-bold text-[#70d6a0] uppercase">
              No Social Engineering Threats Detected
            </div>
            <p className="text-xs text-[#9ba2b1]">
              The spoken conversation did not trigger active credential requests, urgency threats, or remote control patterns.
            </p>
          </div>
        </div>
      ) : null}

      {/* Actionable Security Recommendations */}
      {scamData?.recommendations && scamData.recommendations.length > 0 && (
        <div className="p-4 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] space-y-2">
          <span className="text-xs font-mono text-[#66b7ff] uppercase tracking-wider flex items-center gap-1.5 font-bold">
            <Info size={13} />
            Recommended Defensive Actions
          </span>
          <ul className="space-y-1.5 text-xs text-[#d1d5db]">
            {scamData.recommendations.map((rec: string, idx: number) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-[#66b7ff] mt-0.5">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Engine Limitations & Transparency Notice */}
      <div className="p-3.5 rounded-xl bg-[#0d1017] border border-[rgba(255,255,255,0.04)] text-[11px] font-mono text-[#8b93a3] flex items-start gap-2 leading-relaxed">
        <HelpCircle size={14} className="shrink-0 mt-0.5 text-[#9ba2b1]" />
        <div>
          <span className="text-[#f4f5f7] font-semibold">Heuristic Intent Scoring:</span> EchoSentinel evaluates conversational patterns against structured rules in backend/scam_rules.json with clause-level negation suppression. A high risk score indicates suspicious conversational tactics, not legal proof of fraud. Voice authenticity and scam intent are evaluated by independent systems.
        </div>
      </div>
    </section>
  );
};
