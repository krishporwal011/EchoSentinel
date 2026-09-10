"use client";

import React from "react";
import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert, Sparkles } from "lucide-react";

interface DetectionResultProps {
  prediction: "authentic" | "AI-generated";
  confidence: number;
  riskScore: number;
  riskLevel: "Low" | "Suspicious" | "High" | "Critical";
  isDemoSimulated?: boolean;
}

export const DetectionResult: React.FC<DetectionResultProps> = ({
  prediction,
  confidence,
  riskLevel,
  isDemoSimulated = false,
}) => {
  const isAuthentic = prediction === "authentic";
  const confidencePct = Math.round(confidence * 100);

  const headline = isAuthentic
    ? `Likely Authentic — ${confidencePct}% — ${riskLevel.toUpperCase()} RISK 🟢`
    : `Possible Voice Clone — ${confidencePct}% — ${riskLevel.toUpperCase()} RISK ${
        riskLevel === "Critical" ? "🔴" : "🟠"
      }`;

  return (
    <motion.div
      key={prediction + riskLevel}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.76, 0, 0.24, 1] }}
      className="bg-[#111520] border border-[rgba(255,255,255,0.12)] rounded-2xl p-5 sm:p-6 shadow-xl"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          {isAuthentic ? (
            <ShieldCheck size={18} className="text-[#70d6a0]" />
          ) : (
            <ShieldAlert size={18} className="text-[#e66d76]" />
          )}
          <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase">
            ACOUSTIC CLASSIFICATION
          </span>
        </div>

        {isDemoSimulated && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#181c27] border border-[#66b7ff]/30 text-[10px] font-mono text-[#8ddcff]">
            <Sparkles size={11} />
            <span>DEMO SIMULATION</span>
          </div>
        )}
      </div>

      {/* Primary Climax Headline in Serif */}
      <h2 className="font-serif-cinematic text-xl sm:text-2xl md:text-3xl text-[#f4f5f7] tracking-tight leading-snug">
        {headline}
      </h2>

      {/* Honest Probabilistic Footnote */}
      <div className="mt-4 pt-3 border-t border-[rgba(255,255,255,0.08)] flex items-center justify-between text-xs text-[#9ba2b1]">
        <span>Detection is probabilistic, not certain.</span>
        <span className="text-[11px] font-mono text-[#626978]">
          {isAuthentic ? "Authentic Voice Dynamics" : "Synthetic Acoustic Artifacts"}
        </span>
      </div>
    </motion.div>
  );
};
