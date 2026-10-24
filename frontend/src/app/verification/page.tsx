"use client";

import React, { useState } from "react";
import { PageTransition } from "../../components/PageTransition";
import { LinkSecurityScanner } from "../../components/LinkSecurityScanner";
import { ShieldCheck, Link as LinkIcon, UserCheck, AlertCircle } from "lucide-react";

export default function VerificationPage() {
  const [activeTab, setActiveTab] = useState<"link_scanner" | "voice_identity">("link_scanner");

  return (
    <PageTransition>
      <main className="mx-auto max-w-4xl space-y-10 px-5 py-6 sm:px-8">
        {/* Verification Hub Navigation Tabs */}
        <div className="flex flex-wrap items-center gap-3 p-1.5 rounded-2xl bg-[#111520] border border-[rgba(255,255,255,0.1)] w-fit">
          <button
            type="button"
            onClick={() => setActiveTab("link_scanner")}
            className={`px-5 py-2.5 rounded-xl font-mono text-xs tracking-wider font-semibold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "link_scanner"
                ? "bg-[#66b7ff] text-[#090b11] shadow-md"
                : "text-[#9ba2b1] hover:text-white"
            }`}
          >
            <LinkIcon size={14} />
            <span>LINK SECURITY SCANNER</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("voice_identity")}
            className={`px-5 py-2.5 rounded-xl font-mono text-xs tracking-wider font-semibold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "voice_identity"
                ? "bg-[#66b7ff] text-[#090b11] shadow-md"
                : "text-[#9ba2b1] hover:text-white"
            }`}
          >
            <UserCheck size={14} />
            <span>IDENTITY VERIFICATION</span>
          </button>
        </div>

        {/* Tab 1: LINK SECURITY SCANNER (VirusTotal Threat Intelligence) */}
        {activeTab === "link_scanner" && (
          <section aria-label="Link Security Scanner">
            <LinkSecurityScanner />
          </section>
        )}

        {/* Tab 2: VOICE IDENTITY VERIFICATION (Preserved Voice Safety Notice) */}
        {activeTab === "voice_identity" && (
          <section className="space-y-8" aria-label="Voice Identity Verification">
            <header className="space-y-3">
              <span className="block text-xs font-mono uppercase tracking-widest text-[#66b7ff] font-semibold">
                VOICE IDENTITY VERIFICATION
              </span>
              <h1 className="text-3xl sm:text-5xl font-serif-cinematic font-semibold text-[#f4f5f7]">
                Identity checks are not enabled
              </h1>
              <p className="max-w-2xl text-sm sm:text-base leading-relaxed text-[#9ba2b1]">
                EchoSentinel analyzes audio for patterns associated with synthetic speech. It does not verify a speaker’s biological identity or ask you to pass or block a challenge.
              </p>
            </header>

            <div className="rounded-2xl border border-white/10 bg-[#111520] p-6 sm:p-8 text-sm sm:text-base leading-relaxed text-[#cbd5e1] space-y-4 shadow-xl">
              <div className="flex items-center gap-2.5 text-[#66b7ff] font-mono text-xs tracking-wider uppercase font-semibold">
                <AlertCircle size={16} />
                <span>Operational Guidance</span>
              </div>
              <p>
                Treat acoustic detection results as estimates. For an urgent or sensitive financial, authorization, or personal voice request, always contact the person through a trusted, independent out-of-band communication channel.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-5 rounded-2xl bg-[#090b11] border border-white/10 space-y-2">
                <span className="text-xs font-mono text-[#70d6a0] uppercase tracking-wider block font-medium">
                  What EchoSentinel Detects
                </span>
                <p className="text-xs text-[#9ba2b1] leading-relaxed">
                  Deep neural voice cloning artifacts, phase cancellation anomalies, vocoder spectral glints, and synthetic speech synthesis.
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-[#090b11] border border-white/10 space-y-2">
                <span className="text-xs font-mono text-[#e66d76] uppercase tracking-wider block font-medium">
                  What It Does Not Do
                </span>
                <p className="text-xs text-[#9ba2b1] leading-relaxed">
                  Does not prove legal identity, biometric speaker ownership, passport validation, or banking credential checks.
                </p>
              </div>
            </div>
          </section>
        )}
      </main>
    </PageTransition>
  );
}
