"use client";

import React, { useEffect, useRef } from "react";

interface AudioLandscapeProps {
  isRecording?: boolean;
  audioLevel?: number; // 0.0 - 1.0 from microphone
  riskLevel?: "Low" | "Suspicious" | "High" | "Critical";
}

export const AudioLandscape: React.FC<AudioLandscapeProps> = ({
  isRecording = false,
  audioLevel = 0,
  riskLevel = "Low",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const getRiskColor = (alpha = 1) => {
    switch (riskLevel) {
      case "Critical":
        return `rgba(230, 109, 118, ${alpha})`;
      case "High":
        return `rgba(231, 154, 101, ${alpha})`;
      case "Suspicious":
        return `rgba(232, 200, 107, ${alpha})`;
      case "Low":
      default:
        return `rgba(102, 183, 255, ${alpha})`;
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 600);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 400);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    let time = 0;
    const numNodes = 64;

    const render = () => {
      time += isRecording ? 0.03 + audioLevel * 0.04 : 0.015;
      ctx.clearRect(0, 0, width, height);

      const centerX = width / 2;
      const centerY = height / 2;
      const baseRadius = Math.min(width, height) * 0.22;
      const dynamicRadius = baseRadius + (isRecording ? audioLevel * 35 : Math.sin(time * 1.5) * 6);

      // 1. Soft Central Volumetric Core Glow
      const glowGrad = ctx.createRadialGradient(
        centerX,
        centerY,
        baseRadius * 0.2,
        centerX,
        centerY,
        dynamicRadius * 1.8
      );
      glowGrad.addColorStop(0, getRiskColor(isRecording ? 0.2 + audioLevel * 0.15 : 0.08));
      glowGrad.addColorStop(1, "rgba(9, 11, 17, 0)");
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(centerX, centerY, dynamicRadius * 1.8, 0, Math.PI * 2);
      ctx.fill();

      // 2. Concentric Resonating Wave Rings
      const ringCount = 3;
      for (let r = 1; r <= ringCount; r++) {
        const ringRadius = dynamicRadius * (0.6 + r * 0.35);
        const ringAlpha = (0.35 / r) * (isRecording ? 1 + audioLevel * 0.5 : 0.8);

        ctx.strokeStyle = getRiskColor(ringAlpha);
        ctx.lineWidth = 1;
        ctx.beginPath();

        // Wave displacement around circle
        for (let i = 0; i <= 100; i++) {
          const angle = (i / 100) * Math.PI * 2;
          const wave = Math.sin(angle * 6 + time * 2) * (isRecording ? 4 + audioLevel * 12 : 2);
          const rad = ringRadius + wave;
          const x = centerX + Math.cos(angle) * rad;
          const y = centerY + Math.sin(angle) * rad;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }

      // 3. Central Soundwave Nodes / Sphere Points
      ctx.fillStyle = getRiskColor(0.85);
      for (let i = 0; i < numNodes; i++) {
        const theta = (i / numNodes) * Math.PI * 2;
        const phi = Math.sin(time + i * 0.4) * 0.4; // 3D tilt
        const rOffset = Math.sin(time * 2 + i) * (isRecording ? 8 + audioLevel * 20 : 4);
        const currentR = dynamicRadius + rOffset;

        const x = centerX + Math.cos(theta) * currentR;
        const y = centerY + Math.sin(theta) * currentR * (0.8 + phi);
        const nodeSize = isRecording ? 1.5 + audioLevel * 2 : 1.2;

        ctx.beginPath();
        ctx.arc(x, y, nodeSize, 0, Math.PI * 2);
        ctx.fill();
      }

      // 4. Central Audio Sentinel Core
      ctx.fillStyle = getRiskColor(0.9);
      ctx.beginPath();
      ctx.arc(centerX, centerY, 3.5 + (isRecording ? audioLevel * 4 : 0), 0, Math.PI * 2);
      ctx.fill();

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
    };
  }, [isRecording, audioLevel, riskLevel]);

  return (
    <div className="relative w-full h-[280px] sm:h-[340px] md:h-[400px] flex items-center justify-center select-none pointer-events-none">
      <canvas ref={canvasRef} className="w-full h-full block" />
    </div>
  );
};
