"use client";

import React from "react";
import { PageTransition } from "../../components/PageTransition";
import { HONEST_LIMITATIONS } from "../../lib/content";

export default function AboutPage() {
  const pillars = [
    {
      title: "AI VOICE DETECTION",
      desc: "Pretrained Wav2Vec2 transformer architectures identify temporal acoustic discrepancies, neural codec artifacts, and synthetic phase anomalies.",
    },
    {
      title: "REAL-TIME ANALYSIS",
      desc: "Continuous 2.5–3.0 second chunk processing provides low-latency risk telemetry directly during live conversations without cellular interception.",
    },
    {
      title: "RISK ASSESSMENT",
      desc: "Probabilistic scoring mapped across four calibrated threat bands: Low (0-30), Suspicious (31-60), High (61-80), and Critical (81-100).",
    },
    {
      title: "IDENTITY VERIFICATION",
      desc: "Dynamic challenge phrases create an active prevention gate, ensuring high-risk cloned voices cannot authorize sensitive flows.",
    },
  ];

  return (
    <PageTransition>
      <div className="max-w-4xl mx-auto px-5 sm:px-8 py-6 space-y-12">
        {/* Hero */}
        <div className="space-y-4">
          <span className="text-[10px] font-mono tracking-widest text-[#66b7ff] uppercase block">
            ABOUT ECHOSENTINEL
          </span>
          <h1 className="font-serif-cinematic text-4xl sm:text-6xl text-[#f4f5f7] leading-tight">
            Security begins <br />
            with listening.
          </h1>
          <p className="text-sm sm:text-base text-[#9ba2b1] max-w-xl leading-relaxed">
            Generative voice cloning has made impersonation trivial. EchoSentinel provides the acoustic
            defense layer necessary to detect synthetic voices and prevent automated social engineering.
          </p>
        </div>

        {/* Four Pillars */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-4">
          {pillars.map((p, i) => (
            <div
              key={i}
              className="p-6 rounded-2xl bg-[#111520] border border-[rgba(255,255,255,0.1)] space-y-2.5"
            >
              <span className="text-[10px] font-mono text-[#66b7ff] tracking-widest block font-semibold">
                0{i + 1}
              </span>
              <h2 className="text-sm font-mono tracking-wider font-bold text-[#f4f5f7]">
                {p.title}
              </h2>
              <p className="text-xs text-[#9ba2b1] leading-relaxed">
                {p.desc}
              </p>
            </div>
          ))}
        </div>

        {/* Honest Disclaimers */}
        <div className="p-6 sm:p-8 rounded-2xl bg-[#181c27] border border-[rgba(255,255,255,0.12)] space-y-4">
          <h3 className="font-serif-cinematic text-2xl text-[#f4f5f7]">
            Core Philosophy & Honest Guardrails
          </h3>
          <p className="text-xs sm:text-sm text-[#9ba2b1] leading-relaxed">
            EchoSentinel is an acoustic signal detection system. It does not replace governmental
            identification, mathematical cryptographic keys, or biometric proof of life.
            Detection is probabilistic, designed to empower human judgment and block unverified actions.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-3">
            {HONEST_LIMITATIONS.map((l, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.06)] text-xs space-y-1.5"
              >
                <span className="font-mono text-[#f4f5f7] font-semibold block">{l.title}</span>
                <span className="text-[#9ba2b1] block text-[11px] leading-normal">{l.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
