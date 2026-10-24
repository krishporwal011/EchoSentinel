"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Heart, Sparkles, X, Upload, Radio } from "lucide-react";

export interface UpcomingFeatureOptions {
  title?: string;
  message?: string;
}

const UPCOMING_EVENT = "echosentinel:upcoming-feature";

/** Helper to trigger the upcoming feature popup from anywhere in the app */
export function triggerUpcomingFeatureModal(options?: UpcomingFeatureOptions) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(UPCOMING_EVENT, { detail: options }));
  }
}

export const UpcomingFeatureModal: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [content, setContent] = useState<UpcomingFeatureOptions>({});

  const handleOpen = useCallback((event: Event) => {
    const customEvent = event as CustomEvent<UpcomingFeatureOptions>;
    setContent(customEvent.detail || {});
    setIsOpen(true);
  }, []);

  const handleClose = useCallback(() => {
    setIsOpen(false);
  }, []);

  useEffect(() => {
    window.addEventListener(UPCOMING_EVENT, handleOpen);
    return () => window.removeEventListener(UPCOMING_EVENT, handleOpen);
  }, [handleOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleClose]);

  const handleUploadClick = () => {
    handleClose();
    // Trigger any visible file input on the page
    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    if (fileInput) {
      setTimeout(() => fileInput.click(), 100);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="upcoming-feature-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto"
        >
          {/* Backdrop blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={handleClose}
            className="fixed inset-0 bg-[#090b11]/80 backdrop-blur-md"
          />

          {/* Modal Container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 12 }}
            transition={{ type: "spring", damping: 25, stiffness: 320 }}
            className="relative w-full max-w-lg rounded-3xl bg-gradient-to-b from-[#151926] to-[#0c0e15] border border-[rgba(255,255,255,0.15)] shadow-2xl p-6 sm:p-8 overflow-hidden z-10"
          >
            {/* Ambient Background Glow */}
            <div className="absolute -top-24 -right-24 w-60 h-60 bg-[#66b7ff]/15 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -left-24 w-60 h-60 bg-[#e66d76]/15 rounded-full blur-3xl pointer-events-none" />

            {/* Close Button */}
            <button
              type="button"
              onClick={handleClose}
              aria-label="Close modal"
              className="absolute top-5 right-5 p-2 rounded-full text-[#9ba2b1] hover:text-white hover:bg-white/10 transition-colors"
            >
              <X size={18} />
            </button>

            {/* Header / Badges */}
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono font-semibold tracking-wider bg-[#ff9933]/15 text-[#ffb066] border border-[#ff9933]/30">
                <span>🇮🇳</span>
                <span>TEAM INDIA</span>
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono font-semibold tracking-wider bg-[#66b7ff]/15 text-[#8ddcff] border border-[#66b7ff]/30">
                <Radio size={12} className="animate-pulse text-[#66b7ff]" />
                <span>UPCOMING FEATURE</span>
              </span>
            </div>

            {/* Heart Icon Feature Hero */}
            <div className="flex items-center gap-3.5 mb-4">
              <div className="relative flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#e66d76]/25 to-[#ff7b90]/15 border border-[#e66d76]/40 shadow-inner">
                <Heart size={26} className="text-[#ff5c72] fill-[#ff5c72] animate-bounce" />
                <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[#10b981] ring-2 ring-[#0c0e15]" />
              </div>
              <div>
                <span className="text-[11px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                  EchoSentinel Roadmap
                </span>
                <span className="text-sm font-mono text-[#a5b4fc] flex items-center gap-1">
                  <span>Continuous Audio Ingest</span>
                  <Sparkles size={13} className="text-[#66b7ff]" />
                </span>
              </div>
            </div>

            {/* Core Message Required by User */}
            <div className="space-y-3 mb-6">
              <h2
                id="upcoming-feature-title"
                className="text-xl sm:text-2xl font-serif-cinematic font-bold text-white tracking-tight leading-snug"
              >
                {content.title || "It is an upcoming feature of EchoSentinel Team India ❤️"}
              </h2>

              <p className="text-sm text-[#cbd5e1] leading-relaxed">
                {content.message || (
                  <>
                    Live Detection &amp; continuous real-time microphone stream analysis is currently being developed by <strong className="text-white">EchoSentinel Team India ❤️</strong>.
                    Our deep neural streaming pipeline is being engineered for zero-latency detection.
                  </>
                )}
              </p>

              <div className="p-3.5 rounded-xl bg-[#090b11]/70 border border-white/10 text-xs text-[#9ba2b1] space-y-1.5">
                <div className="flex items-center gap-2 text-[#70d6a0] font-mono font-medium">
                  <span className="w-2 h-2 rounded-full bg-[#70d6a0]" />
                  <span>WHAT YOU CAN DO RIGHT NOW:</span>
                </div>
                <p>
                  You can upload any voice recording (<code className="text-[#8ddcff]">.mp3, .wav, .m4a</code>) or use the instant <strong>Test AI Voice (Deepfake)</strong> and <strong>Test Human Voice (Real)</strong> sample buttons on the dashboard!
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col-reverse sm:flex-row items-center gap-3 pt-2">
              <button
                type="button"
                onClick={handleClose}
                className="w-full sm:w-auto px-6 py-2.5 rounded-full bg-[#1e2433] hover:bg-[#283042] text-[#e2e8f0] font-mono text-xs tracking-wider font-semibold transition-all border border-white/10"
              >
                Got It ❤️
              </button>

              <button
                type="button"
                onClick={handleUploadClick}
                className="w-full sm:flex-1 px-6 py-2.5 rounded-full bg-gradient-to-r from-[#66b7ff] to-[#4da3ff] hover:from-[#8ddcff] hover:to-[#66b7ff] text-[#090b11] font-mono text-xs tracking-wider font-bold transition-all shadow-lg flex items-center justify-center gap-2"
              >
                <Upload size={14} />
                <span>Upload Audio File Instead</span>
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
