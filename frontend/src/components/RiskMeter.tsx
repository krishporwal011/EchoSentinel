"use client";

import React from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, AlertCircle, Radio } from "lucide-react";

export interface RiskMeterProps {
  score?: number | null; // 0 - 100
  level?: "Low" | "Suspicious" | "High" | "Critical" | null;
  confidence?: number | null; // 0.0 - 1.0
  prediction?: "authentic" | "AI-generated" | null;
}

export const RiskMeter: React.FC<RiskMeterProps> = ({
  score,
  level,
  confidence,
  prediction,
}) => {
  const isIdle = score === null || score === undefined || !level || !prediction;
  const safeScore = isIdle ? 0 : Math.max(0, Math.min(100, Math.round(score)));

  // Clean, professional configuration
  const config = !isIdle && level
    ? {
        Low: {
          color: "#10b981",
          badgeClass: "bg-emerald-950/60 text-emerald-300 border-emerald-800/80",
          icon: ShieldCheck,
          emoji: "🟢",
          label: "LOW RISK",
        },
        Suspicious: {
          color: "#f59e0b",
          badgeClass: "bg-amber-950/60 text-amber-300 border-amber-800/80",
          icon: AlertTriangle,
          emoji: "🟡",
          label: "SUSPICIOUS",
        },
        High: {
          color: "#f97316",
          badgeClass: "bg-orange-950/60 text-orange-300 border-orange-800/80",
          icon: ShieldAlert,
          emoji: "🟠",
          label: "HIGH RISK",
        },
        Critical: {
          color: "#ef4444",
          badgeClass: "bg-red-950/60 text-red-300 border-red-800/80",
          icon: AlertCircle,
          emoji: "🔴",
          label: "CRITICAL",
        },
      }[level]
    : {
        color: "#64748b",
        badgeClass: "bg-slate-800/60 text-slate-400 border-slate-700",
        icon: Radio,
        emoji: "⚪",
        label: "STANDBY",
      };

  const Icon = config.icon;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      {/* Card Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-slate-800 text-slate-200 border border-slate-700">
            <Icon size={18} style={{ color: config.color }} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Threat Risk Engine</h3>
            <p className="text-xs text-slate-400">Wav2Vec2 Acoustic Classifier</p>
          </div>
        </div>

        <div
          className={`px-2.5 py-1 rounded-md text-xs font-semibold border flex items-center gap-1.5 ${config.badgeClass}`}
        >
          <span>{config.emoji}</span>
          <span>{config.label}</span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 gap-3 my-3">
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
          <div className="text-[11px] font-mono uppercase text-slate-400">Risk Score</div>
          <div className="flex items-baseline gap-1 mt-1">
            <span
              className="text-3xl font-bold font-mono tracking-tight"
              style={{ color: config.color }}
            >
              {isIdle ? "--" : safeScore}
            </span>
            <span className="text-xs text-slate-500 font-mono">/ 100</span>
          </div>
        </div>

        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
          <div className="text-[11px] font-mono uppercase text-slate-400">Model Spoof Score</div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-3xl font-bold font-mono tracking-tight text-slate-100">
              {isIdle ? "--" : `${safeScore}%`}
            </span>
            <span className="text-xs text-slate-500 font-mono">score</span>
          </div>
        </div>
      </div>

      {/* Risk Gauge Bar */}
      <div className="mt-4">
        <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1.5">
          <span>0 Low</span>
          <span>31 Suspicious</span>
          <span>61 High</span>
          <span>81-100 Critical</span>
        </div>

        {/* Clean Progress Track */}
        <div className="relative w-full h-2.5 rounded-md bg-slate-950 overflow-hidden border border-slate-800 flex">
          <div className="h-full bg-emerald-950 border-r border-slate-900" style={{ width: "30%" }} />
          <div className="h-full bg-amber-950 border-r border-slate-900" style={{ width: "30%" }} />
          <div className="h-full bg-orange-950 border-r border-slate-900" style={{ width: "20%" }} />
          <div className="h-full bg-red-950" style={{ width: "20%" }} />

          {/* Solid Active Fill Indicator */}
          <div
            className="absolute top-0 left-0 h-full transition-all duration-300 ease-out"
            style={{
              width: `${safeScore}%`,
              backgroundColor: config.color,
            }}
          />
        </div>
      </div>

      {/* Footer Assessment */}
      <div className="mt-4 pt-3 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs">
        <div className="text-slate-300">
          Status:{" "}
          <strong className="font-semibold text-slate-100">
            {isIdle
              ? "Awaiting Audio Analysis"
              : prediction === "AI-generated"
              ? "Possible Voice Clone"
              : "Likely Authentic"}
          </strong>
        </div>
        <div className="text-[11px] text-slate-400">
          Detection is probabilistic, not certain.
        </div>
      </div>
    </div>
  );
};
