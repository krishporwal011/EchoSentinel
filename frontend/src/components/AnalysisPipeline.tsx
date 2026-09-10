"use client";

import React from "react";
import { motion } from "framer-motion";
import { Mic, Layers, Cpu, ShieldCheck } from "lucide-react";

interface AnalysisPipelineProps {
  isAnalyzing: boolean;
  processingTimeMs?: number;
}

export const AnalysisPipeline: React.FC<AnalysisPipelineProps> = ({
  isAnalyzing,
  processingTimeMs,
}) => {
  const nodes = [
    { id: "audio", label: "AUDIO", icon: Mic },
    { id: "preproc", label: "PREPROCESSING", icon: Layers },
    { id: "inference", label: "AI INFERENCE", icon: Cpu },
    { id: "risk", label: "RISK ENGINE", icon: ShieldCheck },
  ];

  return (
    <div className="w-full bg-[#111520] border border-[rgba(255,255,255,0.12)] rounded-xl p-4 sm:p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase">
            NEURAL ANALYSIS PIPELINE
          </span>
          {isAnalyzing && (
            <span className="w-1.5 h-1.5 rounded-full bg-[#66b7ff] animate-ping" />
          )}
        </div>
        {processingTimeMs && processingTimeMs > 0 && (
          <span className="text-[10px] font-mono text-[#9ba2b1]">
            LATENCY: <strong className="text-[#f4f5f7]">{processingTimeMs.toFixed(0)} ms</strong>
          </span>
        )}
      </div>

      {/* Connected Nodes */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 relative">
        {nodes.map((node, index) => {
          const Icon = node.icon;
          // Staggered active state during analysis
          const isActive = isAnalyzing;

          return (
            <div
              key={node.id}
              className={`p-3 rounded-lg border transition-all duration-300 flex flex-col items-center text-center relative ${
                isActive
                  ? "bg-[#181c27] border-[#66b7ff]/40 text-[#f4f5f7]"
                  : "bg-[#090b11] border-[rgba(255,255,255,0.08)] text-[#626978]"
              }`}
            >
              <motion.div
                animate={
                  isActive
                    ? {
                        scale: [1, 1.08, 1],
                        color: ["#9ba2b1", "#8ddcff", "#66b7ff"],
                      }
                    : {}
                }
                transition={{
                  duration: 0.6,
                  delay: index * 0.12,
                  repeat: isActive ? Infinity : 0,
                  repeatDelay: 0.2,
                }}
                className="mb-1.5"
              >
                <Icon size={16} />
              </motion.div>
              <span className="text-[10px] font-mono tracking-wider font-semibold">
                {node.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
