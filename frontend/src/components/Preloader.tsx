"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { EchoLogo } from "./EchoLogo";

interface PreloaderProps {
  onComplete: () => void;
}

export const Preloader: React.FC<PreloaderProps> = ({ onComplete }) => {
  const [progress, setProgress] = useState(0);
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    // Smooth progress counter over ~1300ms
    const startTime = performance.now();
    const duration = 1350;

    const update = (now: number) => {
      const elapsed = now - startTime;
      const pct = Math.min(100, Math.floor((elapsed / duration) * 100));
      setProgress(pct);

      if (elapsed < duration) {
        requestAnimationFrame(update);
      } else {
        setProgress(100);
        setTimeout(() => {
          setIsDone(true);
          setTimeout(onComplete, 400);
        }, 150);
      }
    };

    const frame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frame);
  }, [onComplete]);

  return (
    <AnimatePresence>
      {!isDone && (
        <motion.div
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-[#090b11] text-slate-100"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6, ease: [0.76, 0, 0.24, 1] }}
        >
          <div className="flex flex-col items-center text-center max-w-xs w-full px-6">
            {/* Logo Emblem */}
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="mb-5"
            >
              <EchoLogo size={48} withGlow withRings />
            </motion.div>

            {/* Wordmark */}
            <motion.h1
              className="text-sm sm:text-base font-mono font-semibold tracking-[0.25em] text-[#f4f5f7]"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1, duration: 0.4 }}
            >
              ECHOSENTINEL
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              className="text-[10px] font-mono tracking-[0.2em] text-[#9ba2b1] mt-1.5 uppercase"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.4 }}
            >
              Voice Authenticity System
            </motion.p>

            {/* Loading Line & Percentage */}
            <div className="w-full mt-8">
              <div className="h-[2px] w-full bg-[#181c27] rounded-full overflow-hidden relative">
                <motion.div
                  className="h-full bg-gradient-to-r from-[#66b7ff] to-[#8ddcff]"
                  style={{ width: `${progress}%` }}
                />
              </div>

              <div className="mt-2.5 flex justify-between items-center text-[10px] font-mono text-[#626978]">
                <span>INITIALIZING SENSORS</span>
                <span className="text-[#9ba2b1] font-semibold">{progress}%</span>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
