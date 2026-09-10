"use client";

import React from "react";
import { motion } from "framer-motion";

interface RiskIndicatorProps {
  score: number; // 0 - 100
  level: "Low" | "Suspicious" | "High" | "Critical";
  confidence: number;
}

export const RiskIndicator: React.FC<RiskIndicatorProps> = ({
  score,
  level,
  confidence,
}) => {
  const safeScore = Math.max(0, Math.min(100, Math.round(score)));

  // Risk styling tokens
  const config = {
    Low: {
      color: "#70d6a0",
      emoji: "🟢",
      label: "LOW RISK",
      badgeClass: "bg-[#70d6a0]/10 text-[#70d6a0] border-[#70d6a0]/30",
    },
    Suspicious: {
      color: "#e8c86b",
      emoji: "🟡",
      label: "SUSPICIOUS",
      badgeClass: "bg-[#e8c86b]/10 text-[#e8c86b] border-[#e8c86b]/30",
    },
    High: {
      color: "#e79a65",
      emoji: "🟠",
      label: "HIGH RISK",
      badgeClass: "bg-[#e79a65]/10 text-[#e79a65] border-[#e79a65]/30",
    },
    Critical: {
      color: "#e66d76",
      emoji: "🔴",
      label: "CRITICAL",
      badgeClass: "bg-[#e66d76]/10 text-[#e66d76] border-[#e66d76]/30",
    },
  }[level];

  // Circle dimensions for circular arc
  const radius = 64;
  const strokeWidth = 5;
  const circumference = 2 * Math.PI * radius;
  // Sweep arc across 270 degrees (3/4 of a circle)
  const arcLength = circumference * 0.75;
  const strokeDashoffset = arcLength - (safeScore / 100) * arcLength;

  return (
    <div className="bg-[#111520] border border-[rgba(255,255,255,0.12)] rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
            THREAT RISK ENGINE
          </span>
          <h3 className="text-sm font-semibold text-[#f4f5f7] mt-0.5">
            Acoustic Clone Likelihood
          </h3>
        </div>

        <div
          className={`px-3 py-1 rounded-full text-xs font-mono font-semibold border flex items-center gap-1.5 ${config.badgeClass}`}
        >
          <span>{config.emoji}</span>
          <span>{config.label}</span>
        </div>
      </div>

      {/* Cinematic Circular Gauge */}
      <div className="relative flex items-center justify-center py-4 my-auto">
        <svg width="170" height="170" viewBox="0 0 170 170" className="rotate-[135deg]">
          {/* Background Track Arc */}
          <circle
            cx="85"
            cy="85"
            r={radius}
            fill="none"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
          />

          {/* Animated Active Score Arc */}
          <motion.circle
            cx="85"
            cy="85"
            r={radius}
            fill="none"
            stroke={config.color}
            strokeWidth={strokeWidth + 1}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
            initial={{ strokeDashoffset: arcLength }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1.1, ease: [0.76, 0, 0.24, 1] }}
          />
        </svg>

        {/* Center Score Metric */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center select-none pointer-events-none">
          <motion.span
            key={safeScore}
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="text-4xl font-mono font-bold tracking-tighter"
            style={{ color: config.color }}
          >
            {safeScore}
          </motion.span>
          <span className="text-[10px] font-mono text-[#626978] tracking-widest uppercase">
            / 100 SCORE
          </span>
        </div>
      </div>

      {/* Footer Metrics & Calibrated Risk Bands */}
      <div className="pt-4 border-t border-[rgba(255,255,255,0.08)]">
        <div className="flex justify-between items-center text-xs font-mono mb-2">
          <span className="text-[#9ba2b1]">Model Confidence:</span>
          <span className="text-[#f4f5f7] font-semibold">
            {Math.round(confidence * 100)}% prob
          </span>
        </div>

        <div className="grid grid-cols-4 gap-1 text-[9px] font-mono text-center pt-1 text-[#626978]">
          <div className="bg-[#090b11] py-1 rounded border border-[rgba(255,255,255,0.04)]">
            0–30 LOW
          </div>
          <div className="bg-[#090b11] py-1 rounded border border-[rgba(255,255,255,0.04)]">
            31–60 SUSP
          </div>
          <div className="bg-[#090b11] py-1 rounded border border-[rgba(255,255,255,0.04)]">
            61–80 HIGH
          </div>
          <div className="bg-[#090b11] py-1 rounded border border-[rgba(255,255,255,0.04)]">
            81–100 CRIT
          </div>
        </div>
      </div>
    </div>
  );
};
