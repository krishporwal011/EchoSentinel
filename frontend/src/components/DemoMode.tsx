"use client";

import React from "react";
import { Sparkles, UserCheck, Bot, RefreshCw } from "lucide-react";

interface DemoModeProps {
  isDemoMode: boolean;
  onToggleDemoMode: (enabled: boolean) => void;
  onSimulateGenuine: () => void;
  onSimulateClone: () => void;
  onReset: () => void;
  isLoading: boolean;
}

export const DemoMode: React.FC<DemoModeProps> = ({
  isDemoMode,
  onToggleDemoMode,
  onSimulateGenuine,
  onSimulateClone,
  onReset,
  isLoading,
}) => {
  return (
    <div className="bg-[#111520] border border-[rgba(255,255,255,0.12)] rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-[#181c27] text-[#66b7ff] border border-[rgba(255,255,255,0.08)]">
            <Sparkles size={18} />
          </div>
          <div>
            <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
              SCENARIO SHOWCASE
            </span>
            <h3 className="text-sm font-semibold text-[#f4f5f7] mt-0.5">
              Deterministic Demo Mode
            </h3>
          </div>
        </div>

        {/* Demo Switch */}
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-mono text-[#9ba2b1]">
            {isDemoMode ? "DEMO ACTIVE" : "LIVE SENSOR"}
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={isDemoMode}
            onClick={() => onToggleDemoMode(!isDemoMode)}
            className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none focus:ring-1 focus:ring-[#66b7ff] ${
              isDemoMode ? "bg-[#66b7ff]" : "bg-[#181c27] border border-[rgba(255,255,255,0.12)]"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                isDemoMode ? "translate-x-5" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </div>

      {isDemoMode ? (
        <div className="space-y-3.5 my-auto">
          {/* Active Simulation Notice */}
          <div className="flex items-center justify-between bg-[#181c27] border border-[#66b7ff]/30 px-3.5 py-2 rounded-xl text-xs">
            <div className="flex items-center gap-2 font-mono text-[#8ddcff]">
              <span className="w-2 h-2 rounded-full bg-[#66b7ff] animate-pulse" />
              <strong>DEMO SIMULATION ACTIVE</strong>
            </div>
            <span className="text-[10px] font-mono text-[#9ba2b1]">
              Simulated demonstration
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Genuine Voice Button */}
            <button
              type="button"
              disabled={isLoading}
              onClick={onSimulateGenuine}
              className="flex items-center justify-between p-3.5 rounded-xl border border-[rgba(255,255,255,0.12)] bg-[#090b11] hover:bg-[#181c27] text-left transition-colors group disabled:opacity-50"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-[#70d6a0]/15 text-[#70d6a0]">
                  <UserCheck size={16} />
                </div>
                <div>
                  <div className="text-xs font-mono font-semibold text-[#f4f5f7] group-hover:text-white">
                    AUTHENTIC VOICE
                  </div>
                  <div className="text-[10px] text-[#70d6a0] font-mono mt-0.5">
                    Likely Authentic • 93%
                  </div>
                </div>
              </div>
              <span className="text-sm">🟢</span>
            </button>

            {/* AI-Generated Voice Button */}
            <button
              type="button"
              disabled={isLoading}
              onClick={onSimulateClone}
              className="flex items-center justify-between p-3.5 rounded-xl border border-[rgba(255,255,255,0.12)] bg-[#090b11] hover:bg-[#181c27] text-left transition-colors group disabled:opacity-50"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-[#e66d76]/15 text-[#e66d76]">
                  <Bot size={16} />
                </div>
                <div>
                  <div className="text-xs font-mono font-semibold text-[#f4f5f7] group-hover:text-white">
                    AI-GENERATED VOICE
                  </div>
                  <div className="text-[10px] text-[#e66d76] font-mono mt-0.5">
                    Possible Voice Clone • 88%
                  </div>
                </div>
              </div>
              <span className="text-sm">🔴</span>
            </button>
          </div>

          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={onReset}
              className="text-xs text-[#9ba2b1] hover:text-[#f4f5f7] font-mono flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-[#181c27] transition-colors"
            >
              <RefreshCw size={12} />
              <span>RESET DEMO</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-[#090b11] rounded-xl border border-[rgba(255,255,255,0.06)] text-xs text-[#9ba2b1] flex items-center justify-between">
          <span>Connected to live PyTorch Wav2Vec2 inference pipeline.</span>
          <button
            type="button"
            onClick={() => onToggleDemoMode(true)}
            className="text-xs font-mono text-[#66b7ff] hover:text-[#8ddcff] ml-3"
          >
            ENABLE DEMO →
          </button>
        </div>
      )}
    </div>
  );
};
