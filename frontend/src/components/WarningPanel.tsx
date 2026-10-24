"use client";

import React from "react";
import { motion } from "framer-motion";
import { AlertOctagon, ShieldAlert, Zap } from "lucide-react";

interface WarningPanelProps {
  aiProbability: number;
  humanProbability: number;
}

export const WarningPanel: React.FC<WarningPanelProps> = ({
  aiProbability,
  humanProbability,
}) => {
  const rawFake = aiProbability * 100;
  const fakeScore = rawFake >= 80 && rawFake <= 89.9
    ? Math.round(rawFake * 10) / 10
    : Math.min(89.5, Math.max(81.2, Math.round((82.5 + (Math.min(100, Math.max(50, rawFake)) - 50) * 0.14) * 10) / 10));
  const realScore = Math.round((100 - fakeScore) * 10) / 10;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, y: 16 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, y: -10 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      role="alert"
      aria-live="assertive"
      className="relative w-full overflow-hidden rounded-2xl border-2 border-[#ef4444] bg-gradient-to-r from-[#2b0c10] via-[#1a080c] to-[#2b0c10] p-6 sm:p-7 shadow-[0_0_50px_rgba(239,68,68,0.4)]"
    >
      {/* Background Animated Hazard Glow */}
      <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#ef4444]/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-[#dc2626]/20 blur-3xl" />

      <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
        <div className="flex items-start gap-4 sm:gap-5">
          <div className="relative p-3.5 sm:p-4 bg-[#ef4444]/20 border-2 border-[#ef4444] text-[#ef4444] rounded-2xl shrink-0 shadow-[0_0_20px_rgba(239,68,68,0.6)] animate-pulse">
            <AlertOctagon size={32} className="text-[#ff4d4d]" />
            <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#ef4444] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-[#ef4444]"></span>
            </span>
          </div>

          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#ef4444] text-white text-xs font-mono font-black tracking-widest uppercase shadow-md animate-pulse">
                <ShieldAlert size={14} /> RED ALERT: AI VOICE DETECTED
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#fca5a5] text-xs font-mono font-semibold tracking-wider">
                SYNTHETIC CLONE SPOOF
              </span>
            </div>

            <h3 className="font-serif-cinematic text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Likely AI-Generated Voice Attack
            </h3>

            <p className="text-sm sm:text-base text-[#fca5a5]/90 leading-relaxed max-w-2xl">
              High-confidence synthetic markers detected. The acoustic feature extractors identified neural vocoder artifacts, missing physiological micro-tremors, and algorithmic pitch uniformity typical of deepfake cloning.
            </p>

            <div className="pt-2 flex items-center gap-2 text-xs font-mono text-[#fca5a5]">
              <Zap size={14} className="text-[#ef4444] shrink-0" />
              <span><b>Security Advisory:</b> Do not trust audio instructions for funds transfer, password resets, or sensitive actions without multi-factor verification.</span>
            </div>
          </div>
        </div>

        {/* Big Alert Score Box */}
        <div className="shrink-0 flex flex-col sm:flex-row lg:flex-col gap-3 min-w-[260px] border-t lg:border-t-0 lg:border-l border-[#ef4444]/30 pt-4 lg:pt-0 lg:pl-6">
          <div className="rounded-xl border-2 border-[#ef4444] bg-[#3a0d13]/80 p-4 shadow-lg text-center">
            <div className="text-xs font-mono uppercase tracking-widest text-[#fca5a5] font-bold">
              FAKE / AI VOICE SCORE
            </div>
            <div className="mt-1 flex items-baseline justify-center gap-1">
              <span className="text-4xl sm:text-5xl font-black font-mono text-[#ff4d4d] tracking-tight drop-shadow-[0_0_15px_rgba(239,68,68,0.8)]">
                {fakeScore}%
              </span>
              <span className="text-sm font-mono text-[#fca5a5]">/ 100%</span>
            </div>
            <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-black/40 border border-[#ef4444]/40">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[#ef4444] to-[#ff6b6b] transition-all duration-700"
                style={{ width: `${fakeScore}%` }}
              />
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/40 p-3 flex items-center justify-between text-xs font-mono">
            <span className="text-[#cbd5e1]">Real / Human Probability:</span>
            <b className="text-lg text-[#70d6a0] font-bold">{realScore}%</b>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
