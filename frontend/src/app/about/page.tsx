"use client";

import React from "react";
import { PageTransition } from "../../components/PageTransition";
import { HONEST_LIMITATIONS } from "../../lib/content";
import { triggerUpcomingFeatureModal } from "../../components/UpcomingFeatureModal";

export default function AboutPage() {
  const pillars = [
    {
      title: "AI VOICE DETECTION",
      desc: "Pretrained Wav2Vec2 transformer architectures identify temporal acoustic discrepancies, neural codec artifacts, and synthetic phase anomalies.",
    },
    {
      title: "REAL-TIME LIVE DETECTION (UPCOMING ❤️)",
      desc: "Continuous 2.5–3.0 second chunk processing is an upcoming feature of EchoSentinel Team India ❤️ to provide low-latency risk telemetry directly during live conversations.",
      isUpcoming: true,
    },
    {
      title: "RISK ASSESSMENT",
      desc: "Uncalibrated model scores are mapped to operational bands for display. These bands do not represent measured accuracy or calibrated real-world risk.",
    },
    {
      title: "TRANSPARENT RESULTS",
      desc: "See the model’s class scores, signal measurements, and limitations. Results are estimates and do not verify speaker identity.",
    },
  ];

  return (
    <PageTransition>
      <div className="max-w-4xl mx-auto px-5 sm:px-8 py-6 space-y-12">
        {/* Hero */}
        <div className="space-y-4">
          <span className="text-[12px] font-mono tracking-widest text-[#66b7ff] uppercase block">
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
              onClick={p.isUpcoming ? () => triggerUpcomingFeatureModal() : undefined}
              className={`p-6 rounded-2xl bg-[#111520] border border-[rgba(255,255,255,0.1)] space-y-2.5 transition-all ${
                p.isUpcoming ? "cursor-pointer hover:border-[#66b7ff]/50 hover:bg-[#151a28] group" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-mono text-[#66b7ff] tracking-widest block font-semibold">
                  0{i + 1}
                </span>
                {p.isUpcoming && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#66b7ff]/20 text-[#8ddcff] border border-[#66b7ff]/30">
                    CLICK TO VIEW ROADMAP ❤️
                  </span>
                )}
              </div>
              <h2 className="text-sm font-mono tracking-wider font-bold text-[#f4f5f7]">
                {p.title}
              </h2>
              <p className="text-sm text-[#9ba2b1] leading-relaxed">
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
          <p className="text-sm sm:text-sm text-[#9ba2b1] leading-relaxed">
            EchoSentinel is an acoustic signal detection system. It does not replace governmental
            identification, mathematical cryptographic keys, or biometric proof of life.
            Detection is probabilistic and intended to inform human judgment; it does not block actions in other systems.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-3">
            {HONEST_LIMITATIONS.map((l, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-[#090b11] border border-[rgba(255,255,255,0.06)] text-sm space-y-1.5"
              >
                <span className="font-mono text-[#f4f5f7] font-semibold block">{l.title}</span>
                <span className="text-[#9ba2b1] block text-[13px] leading-normal">{l.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
