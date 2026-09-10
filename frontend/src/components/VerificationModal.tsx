"use client";

import React, { useState, useEffect } from "react";
import { ShieldAlert, KeyRound, CheckCircle2, XCircle, AlertOctagon } from "lucide-react";

interface VerificationModalProps {
  isOpen: boolean;
  onPass: () => void;
  onFail: () => void;
  onClose: () => void;
  riskLevel: "High" | "Critical";
  riskScore: number;
}

const PHRASE_DICTIONARY = [
  "47 Blue Mango",
  "92 Silver Falcon",
  "18 Amber Horizon",
  "63 Crimson River",
  "85 Golden Willow",
  "34 Cobalt Summit",
  "51 Velvet Aurora",
  "76 Copper Lantern",
  "29 Emerald Compass",
];

export const VerificationModal: React.FC<VerificationModalProps> = ({
  isOpen,
  onPass,
  onFail,
  onClose,
  riskLevel,
  riskScore,
}) => {
  const [challengePhrase, setChallengePhrase] = useState<string>("");

  useEffect(() => {
    if (isOpen) {
      const randomItem = PHRASE_DICTIONARY[Math.floor(Math.random() * PHRASE_DICTIONARY.length)];
      setChallengePhrase(`My secure phrase is ${randomItem}.`);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm"
    >
      <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-xl shadow-xl overflow-hidden text-slate-100 flex flex-col">
        {/* Modal Header */}
        <div className="bg-slate-800/80 p-5 border-b border-slate-700 flex items-center gap-3.5">
          <div className="p-2 bg-red-950/80 border border-red-800 text-red-400 rounded-lg">
            <ShieldAlert size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono font-semibold uppercase px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-800">
                {riskLevel} Threat Triggered ({riskScore}/100)
              </span>
            </div>
            <h2 id="modal-title" className="text-base font-semibold text-white mt-1">
              Identity Verification Required
            </h2>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4">
          {/* Warning Message */}
          <div className="flex items-start gap-3 bg-red-950/40 border border-red-900/60 rounded-lg p-3.5 text-sm text-red-200 leading-relaxed">
            <AlertOctagon className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <strong>Warning:</strong> This voice shows characteristics associated with synthetic or cloned speech. Sensitive actions have been temporarily paused.
            </div>
          </div>

          {/* Random Challenge Phrase Box */}
          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-1.5">
              <KeyRound size={14} className="text-blue-400" />
              <span>DYNAMIC CHALLENGE PHRASE</span>
            </div>
            <p className="text-xs text-slate-400 mb-2">
              Prompt speaker to articulate the following verification phrase:
            </p>
            <div className="bg-slate-900 border border-slate-700 rounded-md p-3 text-center">
              <span className="text-sm sm:text-base font-mono font-semibold text-slate-100 select-all">
                "{challengePhrase}"
              </span>
            </div>
          </div>

          {/* Honest Prototype Notice */}
          <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800/80 text-[11px] text-slate-400 leading-normal">
            <strong className="text-slate-300">Prototype Demo Guardrail:</strong> This prototype evaluates acoustic cloning likelihood. Verification controls below illustrate the prevention workflow and do not mathematically verify identity.
          </div>
        </div>

        {/* Modal Actions */}
        <div className="p-4 bg-slate-950/80 border-t border-slate-800 flex flex-col-reverse sm:flex-row sm:justify-end gap-2.5">
          <button
            type="button"
            onClick={onFail}
            className="px-4 py-2 rounded-lg border border-red-800/80 bg-red-950/40 hover:bg-red-950 text-red-300 text-xs font-medium flex items-center justify-center gap-2 transition-colors"
          >
            <XCircle size={15} />
            <span>Fail / Block</span>
          </button>
          <button
            type="button"
            onClick={onPass}
            className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
          >
            <CheckCircle2 size={15} />
            <span>I passed the check (Continue)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
