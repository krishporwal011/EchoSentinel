"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { EchoLogo } from "./EchoLogo";
import { Volume2, VolumeX } from "lucide-react";

interface SoundGateProps {
  onEnter: (soundEnabled: boolean) => void;
}

export const SoundGate: React.FC<SoundGateProps> = ({ onEnter }) => {
  const [isTransitioning, setIsTransitioning] = useState(false);

  const handleEnter = (soundEnabled: boolean) => {
    setIsTransitioning(true);
    // Signature intro sequence: 850ms duration with cubic-bezier
    setTimeout(() => {
      onEnter(soundEnabled);
    }, 850);
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#090b11] text-[#f4f5f7] px-6 select-none overflow-hidden">
      {/* Background Volumetric Glow */}
      <div className="absolute w-[500px] h-[500px] rounded-full bg-[#66b7ff]/5 blur-[120px] pointer-events-none" />

      {/* Main Sound Gate Container */}
      <div className="relative z-10 flex flex-col items-center text-center max-w-lg">
        {/* Animated Breathing Logo with Rotating Radar Rings */}
        <motion.div
          className="relative mb-8"
          animate={
            isTransitioning
              ? {
                  scale: [1, 1.15, 6],
                  opacity: [1, 1, 0],
                  filter: ["blur(0px)", "blur(2px)", "blur(12px)"],
                }
              : {
                  scale: [0.96, 1.02, 0.98, 0.96],
                }
          }
          transition={
            isTransitioning
              ? { duration: 0.85, ease: [0.76, 0, 0.24, 1] }
              : { duration: 3.6, repeat: Infinity, ease: "easeInOut" }
          }
        >
          {/* Subtle Radar Ring 1 */}
          <motion.div
            className="absolute -inset-6 rounded-full border border-[#66b7ff]/20 pointer-events-none"
            animate={
              isTransitioning
                ? { scale: 3.5, opacity: 0 }
                : { rotate: 360 }
            }
            transition={
              isTransitioning
                ? { duration: 0.8, ease: [0.76, 0, 0.24, 1] }
                : { duration: 20, repeat: Infinity, ease: "linear" }
            }
          />

          {/* Subtle Radar Ring 2 */}
          <motion.div
            className="absolute -inset-12 rounded-full border border-dashed border-[#8ddcff]/15 pointer-events-none"
            animate={
              isTransitioning
                ? { scale: 4.5, opacity: 0 }
                : { rotate: -360 }
            }
            transition={
              isTransitioning
                ? { duration: 0.8, ease: [0.76, 0, 0.24, 1] }
                : { duration: 28, repeat: Infinity, ease: "linear" }
            }
          />

          {/* Logo Emblem */}
          <EchoLogo size={80} withGlow withRings />
        </motion.div>

        {/* Narrative Headline in High-Contrast Serif */}
        <motion.h1
          className="font-serif-cinematic text-3xl sm:text-5xl md:text-6xl font-normal tracking-tight text-[#f4f5f7] leading-tight"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.7, ease: [0.76, 0, 0.24, 1] }}
        >
          Listen before you trust.
        </motion.h1>

        {/* Technical Sub-Tag */}
        <motion.p
          className="text-xs sm:text-sm font-mono tracking-[0.25em] text-[#9ba2b1] mt-3 uppercase"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.6 }}
        >
          AI-Powered Voice Authenticity
        </motion.p>

        {/* Entrance CTA Buttons */}
        <motion.div
          className="flex flex-col sm:flex-row items-center gap-4 mt-10 w-full sm:w-auto"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.6 }}
        >
          {/* Primary: ENTER ECHOSENTINEL */}
          <button
            type="button"
            disabled={isTransitioning}
            onClick={() => handleEnter(true)}
            className="w-full sm:w-auto px-8 py-3.5 rounded-full border border-[rgba(255,255,255,0.24)] bg-[#111520] hover:bg-[#181c27] hover:border-[#66b7ff]/60 text-[#f4f5f7] hover:text-white font-mono text-xs tracking-wider transition-all duration-300 flex items-center justify-center gap-2.5 shadow-lg group"
          >
            <Volume2 size={15} className="text-[#66b7ff] group-hover:scale-110 transition-transform" />
            <span className="group-hover:translate-x-0.5 transition-transform">
              ENTER ECHOSENTINEL
            </span>
          </button>

          {/* Secondary: CONTINUE WITHOUT SOUND */}
          <button
            type="button"
            disabled={isTransitioning}
            onClick={() => handleEnter(false)}
            className="w-full sm:w-auto px-5 py-3 rounded-full text-[#9ba2b1] hover:text-[#f4f5f7] font-mono text-xs tracking-wider transition-colors flex items-center justify-center gap-2"
          >
            <VolumeX size={14} />
            <span>CONTINUE WITHOUT SOUND</span>
          </button>
        </motion.div>
      </div>

      {/* Signature Expanding Audio Signal Transition Layer */}
      <AnimatePresence>
        {isTransitioning && (
          <motion.div
            className="fixed inset-0 pointer-events-none z-50 flex items-center justify-center bg-[#090b11]"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 0.9, 0] }}
            transition={{ duration: 0.85, ease: [0.76, 0, 0.24, 1] }}
          >
            {/* Expanding Circular Waveforms */}
            <motion.div
              className="w-24 h-24 rounded-full border-2 border-[#66b7ff] shadow-[0_0_80px_#8ddcff]"
              initial={{ scale: 0.5, opacity: 1 }}
              animate={{ scale: 30, opacity: 0 }}
              transition={{ duration: 0.85, ease: [0.76, 0, 0.24, 1] }}
            />
            <motion.div
              className="w-32 h-32 rounded-full border border-[#8ddcff] absolute"
              initial={{ scale: 0.3, opacity: 0.8 }}
              animate={{ scale: 22, opacity: 0 }}
              transition={{ duration: 0.75, delay: 0.08, ease: [0.76, 0, 0.24, 1] }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
