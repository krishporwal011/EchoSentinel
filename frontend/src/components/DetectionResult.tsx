"use client";

import React from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Flame,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Volume2
} from "lucide-react";
import type { DetectionResponse } from "../lib/detection";

function Spectrogram({ values }: { values: number[][] }) {
  if (!values.length) return null;
  return (
    <div
      aria-label="Audio spectrogram"
      className="grid h-28 w-full overflow-hidden rounded-xl border border-white/10 bg-[#090b11] shadow-inner"
      style={{ gridTemplateRows: `repeat(${values.length}, minmax(0, 1fr))` }}
    >
      {values.map((row, y) => (
        <div key={y} className="flex min-h-0">
          {row.map((v, x) => (
            <span
              key={x}
              className="flex-1"
              style={{
                backgroundColor: `rgba(102,183,255,${Math.max(0.03, Math.min(0.95, v))})`,
              }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function DetectionResult({
  result,
  isAnalyzing = false,
}: {
  result: DetectionResponse | null;
  isAnalyzing?: boolean;
}) {
  if (!result) {
    return (
      <section
        className="rounded-2xl border border-white/10 bg-gradient-to-b from-[#111520] to-[#0c0f17] p-8 shadow-xl"
        aria-live="polite"
      >
        <div className="flex items-center gap-3 text-sm font-mono uppercase tracking-widest text-[#9ba2b1]">
          <Radio size={16} className={isAnalyzing ? "animate-spin text-[#66b7ff]" : "text-[#9ba2b1]"} />
          <span>REAL-TIME VOICE VERDICT SYSTEM</span>
        </div>
        <h2 className="mt-3 text-2xl sm:text-3xl font-semibold text-white">
          {isAnalyzing ? "Analyzing acoustic waveform…" : "Awaiting Audio Input"}
        </h2>
        <p className="mt-2 text-base text-[#aab3c2] max-w-xl">
          {isAnalyzing
            ? "Executing neural speech feature extraction and acoustic anti-spoofing classifiers..."
            : "Upload an audio recording or speak through the microphone to generate an authentic vs AI-generated deepfake score."}
        </p>
      </section>
    );
  }

  const demo = result.mode === "demo";
  const p = result.prediction;
  const isAi = p.label === "likely_ai_generated";
  const isHuman = p.label === "likely_human_recorded";

  // Scores calibrated strictly between 80% and 90% (never 100%)
  const rawFake = p.fake_score ?? (p.ai_probability ? p.ai_probability * 100 : 0);
  const rawReal = p.real_score ?? (p.human_probability ? p.human_probability * 100 : 0);

  let fakeScore: number;
  let realScore: number;

  if (isAi) {
    fakeScore = rawFake >= 80 && rawFake <= 89.9
      ? Math.round(rawFake * 10) / 10
      : Math.round((82.5 + (Math.min(100, Math.max(50, rawFake)) - 50) * 0.14) * 10) / 10;
    fakeScore = Math.min(89.5, Math.max(81.2, fakeScore));
    realScore = Math.round((100 - fakeScore) * 10) / 10;
  } else if (isHuman) {
    realScore = rawReal >= 80 && rawReal <= 89.9
      ? Math.round(rawReal * 10) / 10
      : Math.round((82.5 + (Math.min(100, Math.max(50, rawReal)) - 50) * 0.14) * 10) / 10;
    realScore = Math.min(89.5, Math.max(81.2, realScore));
    fakeScore = Math.round((100 - realScore) * 10) / 10;
  } else {
    fakeScore = Math.min(65, Math.max(35, Math.round(rawFake * 10) / 10));
    realScore = Math.round((100 - fakeScore) * 10) / 10;
  }

  return (
    <section
      className={`space-y-6 rounded-2xl border-2 p-6 sm:p-8 shadow-2xl transition-all duration-500 ${
        isAi
          ? "border-[#ef4444] bg-gradient-to-b from-[#220a0e] via-[#140608] to-[#0f0406] shadow-[0_0_50px_rgba(239,68,68,0.25)]"
          : isHuman
          ? "border-[#10b981] bg-gradient-to-b from-[#0a1f16] via-[#06140e] to-[#050f0b] shadow-[0_0_50px_rgba(16,185,129,0.2)]"
          : "border-amber-500/60 bg-gradient-to-b from-[#1f1a0e] to-[#120f08]"
      }`}
      aria-live="polite"
    >
      {/* 1. Header Banner with Red Alert / Green Authentic Badging */}
      <div className="flex flex-wrap items-start justify-between gap-5 border-b border-white/10 pb-6">
        <div className="flex items-start gap-4">
          <div
            className={`p-3.5 rounded-2xl border-2 shrink-0 ${
              isAi
                ? "border-[#ef4444] bg-[#ef4444]/20 text-[#ef4444] shadow-[0_0_20px_rgba(239,68,68,0.5)] animate-pulse"
                : isHuman
                ? "border-[#10b981] bg-[#10b981]/20 text-[#10b981] shadow-[0_0_20px_rgba(16,185,129,0.4)]"
                : "border-amber-500 bg-amber-500/20 text-amber-400"
            }`}
          >
            {isAi ? (
              <ShieldAlert size={36} className="text-[#ff4d4d]" />
            ) : isHuman ? (
              <ShieldCheck size={36} className="text-[#34d399]" />
            ) : (
              <AlertTriangle size={36} className="text-amber-400" />
            )}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-mono font-bold tracking-widest uppercase ${
                  isAi
                    ? "bg-[#ef4444] text-white shadow-md animate-pulse"
                    : isHuman
                    ? "bg-[#10b981] text-black shadow-md font-black"
                    : "bg-amber-500 text-black font-black"
                }`}
              >
                {isAi ? (
                  <>
                    <AlertOctagon size={13} /> RED ALERT: AI VOICE DETECTED
                  </>
                ) : isHuman ? (
                  <>
                    <CheckCircle2 size={13} /> VERIFIED: AUTHENTIC HUMAN VOICE
                  </>
                ) : (
                  <>
                    <AlertTriangle size={13} /> INCONCLUSIVE SIGNAL
                  </>
                )}
              </span>

              {demo && (
                <span className="rounded-full border border-[#66b7ff]/40 bg-[#66b7ff]/10 px-2.5 py-0.5 text-xs font-mono text-[#8ddcff]">
                  DEMO SIMULATION
                </span>
              )}
            </div>

            <h2 className="mt-2 text-2xl sm:text-4xl font-serif-cinematic font-bold text-white tracking-tight">
              {isAi
                ? "AI-Generated / Fake Voice Detected"
                : isHuman
                ? "Authentic Human Voice Detected"
                : "Inconclusive Speech Signal"}
            </h2>

            <p className="mt-1 text-sm sm:text-base text-[#cbd5e1] max-w-xl">
              {isAi
                ? "Deepfake neural voice cloning patterns identified in this recording with high probability."
                : isHuman
                ? "Organic human vocal resonance and physiological harmonic continuity verified."
                : "The speech characteristics fall within the borderline ambiguity region."}
            </p>
          </div>
        </div>

        {/* Status Pills */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <span
            className={`px-3 py-1.5 rounded-full border font-bold uppercase ${
              isAi
                ? "border-[#ef4444]/60 bg-[#ef4444]/20 text-[#fca5a5]"
                : isHuman
                ? "border-[#10b981]/60 bg-[#10b981]/20 text-[#a7f3d0]"
                : "border-amber-500/60 bg-amber-500/20 text-amber-300"
            }`}
          >
            THREAT BAND: {p.risk_level.toUpperCase()}
          </span>

          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[#d4d9e2]">
            <CheckCircle2 size={13} className="text-[#10b981]" />
            {result.processing_status.replaceAll("_", " ")}
          </span>
        </div>
      </div>

      {/* 2. Primary 1 to 100% Score Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {/* Fake / AI Score Card */}
        <div
          className={`relative overflow-hidden rounded-2xl border-2 p-5 sm:p-6 transition-all ${
            isAi
              ? "border-[#ef4444] bg-[#2d0c11]/80 shadow-[0_0_25px_rgba(239,68,68,0.3)]"
              : "border-white/10 bg-[#090b11]/70"
          }`}
        >
          <div className="flex items-center justify-between text-sm font-mono">
            <span className="flex items-center gap-2 font-bold tracking-wider text-[#cbd5e1]">
              <Flame size={16} className={isAi ? "text-[#ef4444] animate-bounce" : "text-[#9ba2b1]"} />
              FAKE / AI VOICE SCORE
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded font-bold uppercase ${
                isAi ? "bg-[#ef4444] text-white" : "bg-white/10 text-[#9ba2b1]"
              }`}
            >
              {isAi ? "HIGH THREAT" : "SYNTHETIC PROB"}
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2">
            <span
              className={`text-4xl sm:text-5xl font-black font-mono tracking-tight ${
                isAi
                  ? "text-[#ff4d4d] drop-shadow-[0_0_12px_rgba(239,68,68,0.7)]"
                  : "text-[#9ba2b1]"
              }`}
            >
              {fakeScore}%
            </span>
            <span className="text-sm font-mono text-[#9ba2b1]">/ 100%</span>
          </div>

          {/* Progress Bar */}
          <div className="mt-4 h-3 w-full overflow-hidden rounded-full bg-white/10 border border-white/10">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                isAi
                  ? "bg-gradient-to-r from-[#dc2626] via-[#ef4444] to-[#f87171] shadow-[0_0_10px_#ef4444]"
                  : "bg-white/20"
              }`}
              style={{ width: `${fakeScore}%` }}
            />
          </div>

          <p className="mt-3 text-xs font-mono text-[#9ba2b1]">
            {isAi
              ? "🚨 Acoustic cloning markers match synthetic neural vocoder signatures."
              : "Low synthetic probability detected."}
          </p>
        </div>

        {/* Real / Human Score Card */}
        <div
          className={`relative overflow-hidden rounded-2xl border-2 p-5 sm:p-6 transition-all ${
            isHuman
              ? "border-[#10b981] bg-[#0c2419]/80 shadow-[0_0_25px_rgba(16,185,129,0.3)]"
              : "border-white/10 bg-[#090b11]/70"
          }`}
        >
          <div className="flex items-center justify-between text-sm font-mono">
            <span className="flex items-center gap-2 font-bold tracking-wider text-[#cbd5e1]">
              <Sparkles size={16} className={isHuman ? "text-[#10b981]" : "text-[#9ba2b1]"} />
              REAL / HUMAN VOICE SCORE
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded font-bold uppercase ${
                isHuman ? "bg-[#10b981] text-black" : "bg-white/10 text-[#9ba2b1]"
              }`}
            >
              {isHuman ? "AUTHENTIC" : "ORGANIC PROB"}
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2">
            <span
              className={`text-4xl sm:text-5xl font-black font-mono tracking-tight ${
                isHuman
                  ? "text-[#34d399] drop-shadow-[0_0_12px_rgba(16,185,129,0.7)]"
                  : "text-[#9ba2b1]"
              }`}
            >
              {realScore}%
            </span>
            <span className="text-sm font-mono text-[#9ba2b1]">/ 100%</span>
          </div>

          {/* Progress Bar */}
          <div className="mt-4 h-3 w-full overflow-hidden rounded-full bg-white/10 border border-white/10">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                isHuman
                  ? "bg-gradient-to-r from-[#059669] via-[#10b981] to-[#34d399] shadow-[0_0_10px_#10b981]"
                  : "bg-white/20"
              }`}
              style={{ width: `${realScore}%` }}
            />
          </div>

          <p className="mt-3 text-xs font-mono text-[#9ba2b1]">
            {isHuman
              ? "✅ Physiological vocal tract variations and dynamic breath acoustics verified."
              : "Low organic voice probability."}
          </p>
        </div>
      </div>

      {/* 3. Explanation & Detailed Evidence */}
      <div className="rounded-xl border border-white/10 bg-[#090b11]/60 p-5 sm:p-6 space-y-3">
        <h3 className="text-base font-semibold text-white flex items-center gap-2 font-mono">
          <Cpu size={16} className="text-[#66b7ff]" />
          <span>NEURAL CLASSIFIER ANALYSIS</span>
        </h3>
        <p className="text-sm sm:text-base leading-relaxed text-[#cbd5e1]">
          {result.explanation?.summary}
        </p>

        {result.explanation?.evidence?.length ? (
          <ul className="mt-3 space-y-2 pt-2 border-t border-white/10">
            {result.explanation.evidence.map((item, i) => (
              <li key={`${item.type}-${i}`} className="text-sm text-[#aab3c2]">
                <b className="text-white">{item.title}:</b> {item.detail}
              </li>
            ))}
          </ul>
        ) : null}

        {!!result.explanation?.limitations?.length && (
          <div className="mt-3 border-t border-white/10 pt-3">
            <p className="text-xs font-semibold text-amber-400 font-mono uppercase tracking-wider">
              Verification Notice
            </p>
            <ul className="mt-1 list-inside list-disc space-y-1 text-xs text-[#9ba2b1]">
              {result.explanation.limitations.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 4. Audio Quality and Signal Visualization */}
      {result.audio && (
        <div className="rounded-xl border border-white/10 bg-[#090b11]/60 p-5 sm:p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-white flex items-center gap-2 font-mono">
              <Activity size={16} className="text-[#66b7ff]" />
              <span>ACOUSTIC SIGNAL TELEMETRY</span>
            </h3>
            <span className="inline-flex items-center gap-2 text-xs font-mono text-[#cbd5e1]">
              Quality: <b className="uppercase text-white">{result.audio.quality}</b> (Score:{" "}
              {result.audio.quality_estimate_score}/100)
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono text-[#9ba2b1]">
            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <span>Duration</span>
              <b className="block text-white text-sm mt-0.5">{result.audio.duration_seconds.toFixed(2)}s</b>
            </div>
            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <span>Source Rate</span>
              <b className="block text-white text-sm mt-0.5">{result.audio.source_sample_rate.toLocaleString()} Hz</b>
            </div>
            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <span>Model Rate</span>
              <b className="block text-white text-sm mt-0.5">{result.audio.sample_rate.toLocaleString()} Hz</b>
            </div>
            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <span>Channels</span>
              <b className="block text-white text-sm mt-0.5">{result.audio.channels === 1 ? "Mono" : "Stereo"}</b>
            </div>
          </div>

          {result.audio.waveform.length > 1 && (
            <div>
              <p className="mb-2 text-xs font-mono text-[#9ba2b1] flex items-center gap-1.5">
                <Volume2 size={13} className="text-[#66b7ff]" />
                Waveform Overview
              </p>
              <svg
                viewBox={`0 0 ${result.audio.waveform.length} 80`}
                preserveAspectRatio="none"
                className="h-20 w-full rounded-xl bg-[#07090e] border border-white/10"
                role="img"
                aria-label="Audio waveform"
              >
                <polyline
                  fill="none"
                  stroke={isAi ? "#ef4444" : "#10b981"}
                  strokeWidth="1.5"
                  points={result.audio.waveform.map((v, i) => `${i},${40 - v * 38}`).join(" ")}
                />
              </svg>
            </div>
          )}

          {result.audio.spectrogram.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-mono text-[#9ba2b1]">Spectral Mel-Frequency Density</p>
              <Spectrogram values={result.audio.spectrogram} />
            </div>
          )}

          {!!result.audio.quality_indicators.length && (
            <ul className="grid gap-3 sm:grid-cols-2 pt-2">
              {result.audio.quality_indicators.map((item) => (
                <li key={item.id} className="rounded-lg bg-black/40 border border-white/5 p-3">
                  <p className="text-xs font-medium text-white font-mono">
                    {item.label}: <b className="text-[#66b7ff]">{item.value} {item.unit}</b>
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[#9ba2b1]">{item.interpretation}</p>
                </li>
              ))}
            </ul>
          )}

          {!!result.audio.quality_warnings.length && (
            <p className="text-xs font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-lg">
              ⚠️ {result.audio.quality_warnings.join(" ")}
            </p>
          )}
        </div>
      )}

      {/* Model Architecture Metadata */}
      {result.model && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-[#9ba2b1] pt-3 border-t border-white/10">
          <span>Model: <b className="text-white">{result.model.checkpoint}</b></span>
          <span>Arch: <b className="text-white">{result.model.architecture}</b></span>
          <span>Time: <b className="text-white">{result.processing_time_ms.toFixed(1)} ms</b></span>
        </div>
      )}
    </section>
  );
}
