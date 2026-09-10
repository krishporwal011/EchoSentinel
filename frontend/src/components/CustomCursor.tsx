"use client";

import React, { useEffect, useState } from "react";
import { motion, useSpring } from "framer-motion";

export const CustomCursor: React.FC = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const cursorX = useSpring(0, { stiffness: 400, damping: 28 });
  const cursorY = useSpring(0, { stiffness: 400, damping: 28 });

  useEffect(() => {
    // Only enable on desktop with fine pointer
    const isTouch = window.matchMedia("(pointer: coarse)").matches;
    if (isTouch) return;

    const handleMouseMove = (e: MouseEvent) => {
      cursorX.set(e.clientX);
      cursorY.set(e.clientY);
      if (!isVisible) setIsVisible(true);

      const target = e.target as HTMLElement | null;
      if (target) {
        const interactive =
          target.closest("button") ||
          target.closest("a") ||
          target.closest("input") ||
          target.closest("[role='button']") ||
          target.dataset.interactive;
        setIsHovered(!!interactive);
      }
    };

    const handleMouseLeave = () => setIsVisible(false);
    const handleMouseEnter = () => setIsVisible(true);

    window.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseleave", handleMouseLeave);
    document.addEventListener("mouseenter", handleMouseEnter);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseleave", handleMouseLeave);
      document.removeEventListener("mouseenter", handleMouseEnter);
    };
  }, [cursorX, cursorY, isVisible]);

  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden hidden md:block">
      {/* Small Core Dot */}
      <motion.div
        className="fixed top-0 left-0 w-2 h-2 rounded-full bg-[#8ddcff] -translate-x-1/2 -translate-y-1/2 shadow-[0_0_8px_#66b7ff]"
        style={{ x: cursorX, y: cursorY }}
      />
      {/* Outer Spring Ring */}
      <motion.div
        className="fixed top-0 left-0 rounded-full border border-[#66b7ff]/50 -translate-x-1/2 -translate-y-1/2"
        style={{ x: cursorX, y: cursorY }}
        animate={{
          width: isHovered ? 40 : 24,
          height: isHovered ? 40 : 24,
          backgroundColor: isHovered ? "rgba(102, 183, 255, 0.08)" : "transparent",
          borderColor: isHovered ? "rgba(141, 220, 255, 0.7)" : "rgba(102, 183, 255, 0.35)",
        }}
        transition={{ type: "spring", stiffness: 350, damping: 25 }}
      />
    </div>
  );
};
