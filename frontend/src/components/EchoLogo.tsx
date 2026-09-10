"use client";

import React from "react";
import { motion } from "framer-motion";

interface EchoLogoProps {
  size?: number;
  className?: string;
  withGlow?: boolean;
  withRings?: boolean;
}

export const EchoLogo: React.FC<EchoLogoProps> = ({
  size = 40,
  className = "",
  withGlow = false,
  withRings = false,
}) => {
  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Optional Orbiting Radar Rings */}
      {withRings && (
        <>
          <motion.div
            className="absolute rounded-full pointer-events-none border border-[#66b7ff]/20"
            style={{ width: size * 1.8, height: size * 1.8 }}
            animate={{ rotate: 360 }}
            transition={{ duration: 24, repeat: Infinity, ease: "linear" }}
          />
          <motion.div
            className="absolute rounded-full pointer-events-none border border-dashed border-[#8ddcff]/15"
            style={{ width: size * 2.4, height: size * 2.4 }}
            animate={{ rotate: -360 }}
            transition={{ duration: 32, repeat: Infinity, ease: "linear" }}
          />
        </>
      )}

      {/* SVG Emblem: Shield + Soundwaves + Triangular Core */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="relative z-10 transition-transform duration-500"
      >
        <defs>
          <linearGradient id="shieldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#66b7ff" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#8ddcff" stopOpacity="0.4" />
          </linearGradient>
          <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Outer Shield Outline */}
        <path
          d="M50 8 L85 24 V52 C85 74 50 92 50 92 C50 92 15 74 15 52 V24 L50 8Z"
          stroke="url(#shieldGrad)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="rgba(17, 21, 32, 0.6)"
          filter={withGlow ? "url(#softGlow)" : undefined}
        />

        {/* Acoustic Resonance Waves */}
        {/* Wave Left Outer */}
        <path
          d="M32 38 C28 44 28 56 32 62"
          stroke="#66b7ff"
          strokeWidth="2.5"
          strokeLinecap="round"
          opacity="0.5"
        />
        {/* Wave Left Inner */}
        <path
          d="M40 42 C38 46 38 54 40 58"
          stroke="#8ddcff"
          strokeWidth="2.5"
          strokeLinecap="round"
          opacity="0.8"
        />

        {/* Wave Right Outer */}
        <path
          d="M68 38 C72 44 72 56 68 62"
          stroke="#66b7ff"
          strokeWidth="2.5"
          strokeLinecap="round"
          opacity="0.5"
        />
        {/* Wave Right Inner */}
        <path
          d="M60 42 C62 46 62 54 60 58"
          stroke="#8ddcff"
          strokeWidth="2.5"
          strokeLinecap="round"
          opacity="0.8"
        />

        {/* Central Audio Core / Triangle */}
        <polygon
          points="50,38 56,60 44,60"
          fill="#66b7ff"
          opacity="0.9"
        />
        <circle cx="50" cy="52" r="3" fill="#ffffff" />
      </svg>
    </div>
  );
};
