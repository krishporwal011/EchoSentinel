"use client";

import React from "react";
import { PlayCircle, UserCheck, Bot, RefreshCw } from "lucide-react";

interface DemoControlsProps {
  isDemoMode: boolean;
  onToggleDemoMode: (enabled: boolean) => void;
  onSimulateGenuine: () => void;
  onSimulateClone: () => void;
  onReset: () => void;
  isLoading: boolean;
}

export const DemoControls: React.FC<DemoControlsProps> = ({
  isDemoMode,
  onToggleDemoMode,
  onSimulateGenuine,
  onSimulateClone,
  onReset,
  isLoading,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-slate-800 text-slate-200 border border-slate-700">
            <PlayCircle size={18} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Scenario Demo Showcase</h3>
            <p className="text-xs text-slate-400">Deterministic testing for evaluation & presentation</p>
          </div>
        </div>

        {/* Demo Mode Toggle */}
        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <span className="text-xs font-mono text-slate-400">
            {isDemoMode ? "Demo Mode" : "Live Pipeline"}
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={isDemoMode}
            onClick={() => onToggleDemoMode(!isDemoMode)}
            className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/40 ${
              isDemoMode ? "bg-blue-600" : "bg-slate-700"
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
        <div className="space-y-3 pt-1">
          {/* Clearly Labelled Simulation Banner */}
          <div className="flex items-center justify-between bg-blue-950/40 border border-blue-800/60 px-3.5 py-2 rounded-lg text-xs text-blue-200">
            <div className="flex items-center gap-2 font-mono">
              <span className="w-2 h-2 rounded-full bg-blue-400" />
              <strong>DEMO SIMULATION ACTIVE</strong>
            </div>
            <span className="text-[11px] text-blue-300/80">
              Results are illustrative simulations
            </span>
          </div>

          <p className="text-xs text-slate-400">
            Select a calibrated scenario to test the detection-to-prevention workflow:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {/* Genuine Voice Button */}
            <button
              type="button"
              disabled={isLoading}
              onClick={onSimulateGenuine}
              className="flex items-center justify-between p-3 rounded-lg border border-slate-700 bg-slate-950 hover:bg-slate-800/80 text-left transition-colors group disabled:opacity-50"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded-md bg-emerald-950/60 border border-emerald-800 text-emerald-400">
                  <UserCheck size={16} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-white">
                    1. Genuine Voice Sample
                  </div>
                  <div className="text-[11px] text-emerald-400 font-mono">
                    Likely Authentic • 93% • Low
                  </div>
                </div>
              </div>
              <span className="text-base">🟢</span>
            </button>

            {/* AI Cloned Voice Button */}
            <button
              type="button"
              disabled={isLoading}
              onClick={onSimulateClone}
              className="flex items-center justify-between p-3 rounded-lg border border-slate-700 bg-slate-950 hover:bg-slate-800/80 text-left transition-colors group disabled:opacity-50"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded-md bg-red-950/60 border border-red-800 text-red-400">
                  <Bot size={16} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-white">
                    2. AI Cloned Voice Sample
                  </div>
                  <div className="text-[11px] text-red-400 font-mono">
                    Possible Voice Clone • 88% • Critical
                  </div>
                </div>
              </div>
              <span className="text-base">🔴</span>
            </button>
          </div>

          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={onReset}
              className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1.5 px-2.5 py-1.5 rounded-md hover:bg-slate-800 transition-colors"
            >
              <RefreshCw size={12} />
              <span>Reset State</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="text-xs text-slate-400 bg-slate-950 rounded-lg p-3 border border-slate-800 flex items-center justify-between">
          <span>
            Connected to <strong>Real Wav2Vec2 Inference Pipeline</strong>. Click "Start Detection" to process live audio chunks.
          </span>
          <button
            type="button"
            onClick={() => onToggleDemoMode(true)}
            className="text-xs font-medium text-blue-400 hover:text-blue-300 whitespace-nowrap ml-3"
          >
            Switch to Demo Mode →
          </button>
        </div>
      )}
    </div>
  );
};
