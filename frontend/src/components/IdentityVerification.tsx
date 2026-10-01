"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CHALLENGE_PHRASES } from "../lib/content";
import { ShieldCheck, ShieldAlert, KeyRound, Mic, CheckCircle2, XCircle, RotateCcw } from "lucide-react";

interface IdentityVerificationProps {
  isOpen: boolean;
  onPass: () => void;
  onFail: () => void;
  onClose: () => void;
}

export const IdentityVerification: React.FC<IdentityVerificationProps> = ({
  isOpen,
  onPass,
  onFail,
  onClose,
}) => {
  const [phrase, setPhrase] = useState<string>("");
  const [challengeState, setChallengeState] = useState<"idle" | "listening" | "verifying" | "passed" | "blocked">("idle");

  useEffect(() => {
    if (isOpen) {
      const randomItem = CHALLENGE_PHRASES[Math.floor(Math.random() * CHALLENGE_PHRASES.length)];
      setPhrase(randomItem);
      setChallengeState("idle");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleStartChallenge = () => {
    setChallengeState("listening");
    // Simulate active listening state
    setTimeout(() => {
      setChallengeState("verifying");
      setTimeout(() => {
        // Ready for verification decisions
      }, 700);
    }, 1500);
  };

  const handlePass = () => {
    setChallengeState("passed");
    setTimeout(() => {
      onPass();
    }, 700);
  };

  const handleFail = () => {
    setChallengeState("blocked");
    setTimeout(() => {
      onFail();
    }, 700);
  };

  const handleTryAgain = () => {
    const randomItem = CHALLENGE_PHRASES[Math.floor(Math.random() * CHALLENGE_PHRASES.length)];
    setPhrase(randomItem);
    setChallengeState("idle");
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#090b11]/90 backdrop-blur-md"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.4, ease: [0.76, 0, 0.24, 1] }}
        className="w-full max-w-xl bg-[#111520] border border-[rgba(255,255,255,0.14)] rounded-2xl overflow-hidden shadow-2xl text-[#f4f5f7] flex flex-col"
      >
        {/* Verification Header */}
        <div className="p-6 border-b border-[rgba(255,255,255,0.08)] bg-[#181c27]/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[#66b7ff]/10 border border-[#66b7ff]/30 text-[#66b7ff]">
              <KeyRound size={20} />
            </div>
            <div>
              <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                STEP-UP CHALLENGE • SIMULATION
              </span>
              <h2 className="font-serif-cinematic text-xl sm:text-2xl text-[#f4f5f7]">
                Prototype Verification Gate
              </h2>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="text-[#626978] hover:text-[#f4f5f7] text-sm p-1"
          >
            ✕
          </button>
        </div>

        {/* Verification Body */}
        <div className="p-6 sm:p-8 space-y-6">
          <div className="text-center max-w-md mx-auto">
            <p className="text-xs text-[#9ba2b1] italic">
              Prototype Demonstration: Acoustic detection triggered a risk intervention gate.
              Automated voice biometrics are not implemented; use the simulation controls below.
            </p>
          </div>

          {/* Dynamic Challenge Phrase Box */}
          <div className="p-5 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.08)] text-center">
            <span className="text-[10px] font-mono tracking-widest text-[#66b7ff] uppercase block mb-2">
              DYNAMIC ACOUSTIC CHALLENGE (SAMPLE PHRASE)
            </span>
            <div className="text-lg sm:text-xl font-serif-cinematic text-[#f4f5f7] py-2">
              "Say: {phrase}"
            </div>
          </div>

          {/* Verification Status Animation */}
          {challengeState === "listening" && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="p-4 rounded-xl bg-[#181c27] border border-[#66b7ff]/30 flex flex-col items-center gap-2 text-center"
            >
              <div className="w-8 h-8 rounded-full border-2 border-[#66b7ff] border-t-transparent animate-spin" />
              <span className="text-xs font-mono text-[#8ddcff]">SIMULATING RESPONSE CAPTURE...</span>
            </motion.div>
          )}

          {challengeState === "verifying" && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="p-4 rounded-xl bg-[#181c27] border border-[#8ddcff]/30 flex flex-col items-center gap-2 text-center"
            >
              <span className="text-xs font-mono text-[#8ddcff] animate-pulse">EVALUATING CHALLENGE RESPONSE...</span>
            </motion.div>
          )}

          {challengeState === "passed" && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 rounded-xl bg-[#70d6a0]/10 border border-[#70d6a0]/40 flex items-center justify-center gap-2 text-[#70d6a0]"
            >
              <CheckCircle2 size={18} />
              <span className="text-xs font-mono font-semibold">SIMULATED PASS • UNBLOCKED</span>
            </motion.div>
          )}

          {challengeState === "blocked" && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 rounded-xl bg-[#e66d76]/10 border border-[#e66d76]/40 flex flex-col items-center justify-center gap-2 text-[#e66d76]"
            >
              <div className="flex items-center gap-2">
                <XCircle size={18} />
                <span className="text-xs font-mono font-semibold">SIMULATED BLOCK • FLOW HALTED</span>
              </div>
              <p className="text-[11px] text-[#9ba2b1]">
                Step-up challenge simulation rejected. Sensitive action remains locked.
              </p>
            </motion.div>
          )}

          {/* Prototype Honest Guardrail Note */}
          <div className="p-3 bg-[#090b11]/60 rounded-lg border border-[rgba(255,255,255,0.06)] text-[11px] text-[#626978] leading-normal text-center">
            <strong>Prototype Security Gate:</strong> Manual controls demonstrate the prevention workflow
            and do not cryptographically or biometrically verify the speaker's vocal identity.
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-5 bg-[#090b11] border-t border-[rgba(255,255,255,0.08)] flex flex-col sm:flex-row sm:justify-end gap-3">
          {challengeState === "blocked" ? (
            <button
              type="button"
              onClick={handleTryAgain}
              className="px-5 py-2.5 rounded-xl border border-[rgba(255,255,255,0.14)] bg-[#181c27] hover:bg-[#111520] text-xs font-mono text-[#f4f5f7] flex items-center justify-center gap-2 transition-colors"
            >
              <RotateCcw size={14} />
              <span>TRY AGAIN</span>
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={handleFail}
                className="px-4 py-2.5 rounded-xl border border-[#e66d76]/30 bg-[#e66d76]/10 hover:bg-[#e66d76]/20 text-[#e66d76] text-xs font-mono transition-colors flex items-center justify-center gap-1.5"
              >
                <span>Simulate Block</span>
              </button>
              <button
                type="button"
                onClick={handlePass}
                className="px-6 py-2.5 rounded-xl bg-[#70d6a0] hover:bg-[#70d6a0]/90 text-[#090b11] text-xs font-mono font-semibold transition-colors flex items-center justify-center gap-1.5"
              >
                <CheckCircle2 size={15} />
                <span>Simulate Pass & Continue</span>
              </button>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
};
