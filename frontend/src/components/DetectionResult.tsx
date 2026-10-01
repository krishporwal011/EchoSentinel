"use client";

import React from "react";
import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert, AlertTriangle, Sparkles, Radio, Activity } from "lucide-react";

interface DetectionResultProps {
  prediction?: "authentic" | "AI-generated" | "Possible spoof" | string | null;
  rawModelPrediction?: string | null;
  confidence?: number | null;
  modelSpoofScore?: number | null;
  riskScore?: number | null;
  riskLevel?: "Low" | "Suspicious" | "High" | "Critical" | null;
  audioQualityScore?: number | null;
  audioQualityRating?: string | null;
  detectionReliability?: "HIGH" | "MEDIUM" | "LOW" | null;
  qualityWarning?: string | null;
  qualityFlags?: string[] | null;
  isDemoSimulated?: boolean;
}

export const DetectionResult: React.FC<DetectionResultProps> = ({
  prediction,
  rawModelPrediction,
  confidence,
  modelSpoofScore,
  riskScore,
  riskLevel,
  audioQualityScore,
  audioQualityRating,
  detectionReliability,
  qualityWarning,
  qualityFlags,
  isDemoSimulated = false,
}) => {
  if (!prediction || riskScore === null || riskScore === undefined || !riskLevel) {
    return (
      <div className="bg-[#111520] border border-[rgba(255,255,255,0.12)] rounded-2xl p-5 sm:p-6 shadow-xl">
        <div className="flex items-center gap-2 mb-3">
          <Radio size={18} className="text-[#626978]" />
          <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase">
            ACOUSTIC CLASSIFICATION • STANDBY
          </span>
        </div>
        <h2 className="font-serif-cinematic text-xl sm:text-2xl text-[#9ba2b1] tracking-tight">
          No audio analyzed yet
        </h2>
        <div className="mt-4 pt-3 border-t border-[rgba(255,255,255,0.08)] flex items-center justify-between text-xs text-[#626978]">
          <span>Record live microphone stream or upload an audio file to begin analysis.</span>
          <span className="text-[11px] font-mono text-[#626978]">16 kHz Wav2Vec2 Engine Ready</span>
        </div>
      </div>
    );
  }

  const isPossibleSpoof = prediction.toLowerCase().includes("possible spoof");
  const isAuthentic = prediction === "authentic" && !isPossibleSpoof;
  const isClone = prediction === "AI-generated" && !isPossibleSpoof;
  const isLowReliability = detectionReliability === "LOW";
  const spoofScoreVal = riskScore;
  const qualityVal = audioQualityScore !== undefined && audioQualityScore !== null ? audioQualityScore : 100;

  let headline = "";
  if (isPossibleSpoof) {
    headline = `Possible Spoof (Low Reliability) — Model Spoof Score: ${spoofScoreVal}/100 — ${riskLevel.toUpperCase()} RISK ⚠️`;
  } else if (isAuthentic) {
    headline = `Likely Authentic — Model Spoof Score: ${spoofScoreVal}/100 — ${riskLevel.toUpperCase()} RISK 🟢`;
  } else {
    headline = `Possible Voice Clone — Model Spoof Score: ${spoofScoreVal}/100 — ${riskLevel.toUpperCase()} RISK ${
      riskLevel === "Critical" ? "🔴" : "🟠"
    }`;
  }

  return (
    <motion.div
      key={prediction + riskLevel + riskScore}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.76, 0, 0.24, 1] }}
      className="bg-[#111520] border border-[rgba(255,255,255,0.12)] rounded-2xl p-5 sm:p-6 shadow-xl space-y-4"
    >
      {/* Classification Header and Telemetry Badges */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[rgba(255,255,255,0.08)] pb-3">
        <div className="flex items-center gap-2">
          {isPossibleSpoof ? (
            <AlertTriangle size={18} className="text-[#f59e0b]" />
          ) : isAuthentic ? (
            <ShieldCheck size={18} className="text-[#70d6a0]" />
          ) : (
            <ShieldAlert size={18} className="text-[#e66d76]" />
          )}
          <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase">
            ACOUSTIC CLASSIFICATION
          </span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Quality Badge */}
          <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#161a26] border border-[rgba(255,255,255,0.15)] text-[10px] font-mono text-[#cbd5e1]">
            <Activity size={10} className="text-[#60a5fa]" />
            <span>Audio Quality: {qualityVal}/100</span>
          </div>

          {/* Reliability Badge */}
          <div
            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono border ${
              detectionReliability === "HIGH"
                ? "bg-[#102a1e] border-[#10b981]/40 text-[#6ee7b7]"
                : detectionReliability === "MEDIUM"
                ? "bg-[#2d2210] border-[#f59e0b]/40 text-[#fcd34d]"
                : "bg-[#2e1518] border-[#ef4444]/40 text-[#fca5a5]"
            }`}
          >
            <span>{detectionReliability || "HIGH"} RELIABILITY</span>
          </div>

          {isDemoSimulated && (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#181c27] border border-[#66b7ff]/30 text-[10px] font-mono text-[#8ddcff]">
              <Sparkles size={11} />
              <span>DEMO SIMULATION</span>
            </div>
          )}
        </div>
      </div>

      {/* Primary Climax Headline in Serif */}
      <h2 className="font-serif-cinematic text-xl sm:text-2xl md:text-3xl text-[#f4f5f7] tracking-tight leading-snug">
        {headline}
      </h2>

      {/* Quality-Aware Alert Banner (When Audio Degradation is Detected) */}
      {qualityWarning && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-[#241711] border border-[#f59e0b]/40 rounded-xl p-3.5 flex items-start gap-3 text-xs"
        >
          <AlertTriangle size={17} className="text-[#f59e0b] shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-[#fde68a]">
              Audio quality may reduce detection reliability
            </p>
            <p className="text-[#fef3c7]/85 leading-relaxed">
              {qualityWarning}
            </p>
          </div>
        </motion.div>
      )}

      {/* Metric Breakdown Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-center text-xs">
        <div className="bg-[#161a26] p-2 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[10px] font-mono text-[#9ba2b1] uppercase">Model Spoof Score</div>
          <div className="text-sm font-semibold text-[#f4f5f7] mt-0.5">{spoofScoreVal}/100</div>
        </div>
        <div className="bg-[#161a26] p-2 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[10px] font-mono text-[#9ba2b1] uppercase">Audio Quality</div>
          <div className="text-sm font-semibold text-[#f4f5f7] mt-0.5">{qualityVal}/100 ({audioQualityRating || "good"})</div>
        </div>
        <div className="bg-[#161a26] p-2 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[10px] font-mono text-[#9ba2b1] uppercase">Detection Reliability</div>
          <div className="text-sm font-semibold text-[#f4f5f7] mt-0.5">{detectionReliability || "HIGH"}</div>
        </div>
        <div className="bg-[#161a26] p-2 rounded-lg border border-[rgba(255,255,255,0.06)]">
          <div className="text-[10px] font-mono text-[#9ba2b1] uppercase">Assigned Risk</div>
          <div className="text-sm font-semibold text-[#f4f5f7] mt-0.5">{riskLevel}</div>
        </div>
      </div>

      {/* Honest Probabilistic Footnote */}
      <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.08)] flex flex-wrap items-center justify-between gap-2 text-xs text-[#9ba2b1]">
        <span>Detection is probabilistic, not certain. Raw score is an uncalibrated model likelihood.</span>
        <span className="text-[11px] font-mono text-[#626978]">
          {isPossibleSpoof
            ? "Acoustic Degradation Detected"
            : isAuthentic
            ? "Authentic Voice Dynamics"
            : "Synthetic Acoustic Artifacts"}
        </span>
      </div>
    </motion.div>
  );
};
