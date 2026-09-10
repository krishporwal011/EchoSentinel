"use client";

import React, { useState } from "react";
import { KeyRound, ShieldAlert, CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { PageTransition } from "../../components/PageTransition";
import { CHALLENGE_PHRASES } from "../../lib/content";

export default function VerificationPage() {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [status, setStatus] = useState<"ready" | "verifying" | "passed" | "blocked">("ready");

  const currentPhrase = CHALLENGE_PHRASES[phraseIndex % CHALLENGE_PHRASES.length];

  const handleNextPhrase = () => {
    setPhraseIndex((prev) => prev + 1);
    setStatus("ready");
  };

  const handleVerify = (pass: boolean) => {
    setStatus("verifying");
    setTimeout(() => {
      setStatus(pass ? "passed" : "blocked");
    }, 600);
  };

  return (
    <PageTransition>
      <div className="max-w-4xl mx-auto px-5 sm:px-8 py-6 space-y-10">
        {/* Page Header */}
        <div className="space-y-3">
          <span className="text-[10px] font-mono tracking-widest text-[#66b7ff] uppercase block">
            PREVENTION LAYER
          </span>
          <h1 className="font-serif-cinematic text-4xl sm:text-5xl text-[#f4f5f7]">
            Identity Verification Gate
          </h1>
          <p className="text-sm text-[#9ba2b1] max-w-xl">
            When high or critical acoustic clone risk is identified, EchoSentinel halts sensitive
            operations until dynamic challenge verification is satisfied.
          </p>
        </div>

        {/* Interactive Challenge Testing Card */}
        <div className="bg-[#111520] border border-[rgba(255,255,255,0.12)] rounded-2xl p-6 sm:p-8 space-y-6 shadow-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-[#66b7ff]/10 text-[#66b7ff] border border-[#66b7ff]/20">
                <KeyRound size={20} />
              </div>
              <h2 className="text-base font-mono font-semibold text-[#f4f5f7]">
                DYNAMIC CHALLENGE PROTOCOL
              </h2>
            </div>
            <button
              type="button"
              onClick={handleNextPhrase}
              className="text-xs font-mono text-[#9ba2b1] hover:text-[#f4f5f7] flex items-center gap-1.5"
            >
              <RotateCcw size={12} />
              <span>NEW PHRASE</span>
            </button>
          </div>

          <div className="p-6 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] text-center">
            <span className="text-[10px] font-mono text-[#626978] uppercase tracking-widest block mb-2">
              PROMPT TO ARTICULATE
            </span>
            <div className="font-serif-cinematic text-2xl sm:text-3xl text-[#f4f5f7]">
              "Say: {currentPhrase}"
            </div>
          </div>

          {/* Verification Status */}
          {status === "verifying" && (
            <div className="p-4 rounded-xl bg-[#181c27] text-center font-mono text-xs text-[#8ddcff] animate-pulse">
              ANALYZING AUDIO RESPONSE...
            </div>
          )}

          {status === "passed" && (
            <div className="p-4 rounded-xl bg-[#70d6a0]/10 border border-[#70d6a0]/30 text-[#70d6a0] flex items-center justify-center gap-2 font-mono text-xs font-semibold">
              <CheckCircle2 size={16} />
              <span>CHALLENGE VERIFIED • SENSITIVE FLOW UNLOCKED</span>
            </div>
          )}

          {status === "blocked" && (
            <div className="p-4 rounded-xl bg-[#e66d76]/10 border border-[#e66d76]/30 text-[#e66d76] flex items-center justify-center gap-2 font-mono text-xs font-semibold">
              <XCircle size={16} />
              <span>CHALLENGE FAILED • SENSITIVE FLOW BLOCKED</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => handleVerify(false)}
              className="px-5 py-2.5 rounded-xl border border-[#e66d76]/30 bg-[#e66d76]/10 hover:bg-[#e66d76]/20 text-[#e66d76] font-mono text-xs transition-colors"
            >
              Simulate Failure (Block)
            </button>
            <button
              type="button"
              onClick={() => handleVerify(true)}
              className="px-6 py-2.5 rounded-xl bg-[#70d6a0] hover:bg-[#70d6a0]/90 text-[#090b11] font-mono text-xs font-semibold transition-colors flex items-center gap-1.5"
            >
              <CheckCircle2 size={15} />
              <span>Simulate Pass (Continue)</span>
            </button>
          </div>
        </div>

        {/* Explainers */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs text-[#9ba2b1]">
          <div className="p-5 rounded-xl bg-[#111520] border border-[rgba(255,255,255,0.08)] space-y-2">
            <h3 className="font-mono text-[#f4f5f7] font-semibold text-xs">Dynamic Entropy</h3>
            <p className="leading-relaxed">
              Randomized challenge phrases prevent replay attacks where malicious agents play back
              pre-recorded legitimate voicemails or samples.
            </p>
          </div>
          <div className="p-5 rounded-xl bg-[#111520] border border-[rgba(255,255,255,0.08)] space-y-2">
            <h3 className="font-mono text-[#f4f5f7] font-semibold text-xs">Human Oversight Gate</h3>
            <p className="leading-relaxed">
              Verification acts as a decisive step-up gate. If the challenge fails, high-value transfers,
              credential resets, or sensitive actions remain locked.
            </p>
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
