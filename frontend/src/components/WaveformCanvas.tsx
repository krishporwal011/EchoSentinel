"use client";

import React, { useEffect, useRef } from "react";

interface WaveformCanvasProps {
  isRecording: boolean;
  waveformData: Uint8Array | null;
  riskLevel?: "Low" | "Suspicious" | "High" | "Critical";
  isAnalyzing?: boolean;
}

export const WaveformCanvas: React.FC<WaveformCanvasProps> = ({
  isRecording,
  waveformData,
  riskLevel = "Low",
  isAnalyzing = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const idlePhaseRef = useRef<number>(0);

  // Clean, professional stroke color
  const getStrokeColor = () => {
    if (!isRecording) return "#64748b"; // slate-500
    switch (riskLevel) {
      case "Critical":
        return "#ef4444"; // red-500
      case "High":
        return "#f97316"; // orange-500
      case "Suspicious":
        return "#f59e0b"; // amber-500
      case "Low":
      default:
        return "#10b981"; // emerald-500
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let dpr = window.devicePixelRatio || 1;
    const resizeCanvas = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    const render = () => {
      const rect = canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;

      ctx.clearRect(0, 0, width, height);

      // Clean background grid line (center reference)
      ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();

      const strokeColor = getStrokeColor();

      // No neon shadow blur — clean, crisp technical line
      ctx.shadowBlur = 0;

      if (isRecording && waveformData && waveformData.length > 0) {
        ctx.beginPath();
        ctx.lineWidth = 2;
        ctx.strokeStyle = strokeColor;

        const sliceWidth = width / (waveformData.length - 1);
        let x = 0;

        for (let i = 0; i < waveformData.length; i++) {
          const v = waveformData[i] / 128.0;
          const y = (v * height) / 2;

          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
          x += sliceWidth;
        }

        ctx.stroke();
      } else {
        // Ambient subtle waveform
        idlePhaseRef.current += isRecording ? 0.05 : 0.015;
        const phase = idlePhaseRef.current;

        ctx.beginPath();
        ctx.lineWidth = isRecording ? 2 : 1.5;
        ctx.strokeStyle = isRecording ? strokeColor : "rgba(148, 163, 184, 0.35)";

        const amplitude = isRecording ? height * 0.18 : height * 0.06;
        const wavelength = 0.018;

        for (let x = 0; x < width; x += 2) {
          const y = height / 2 + Math.sin(x * wavelength + phase) * amplitude;
          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }

        ctx.stroke();
      }

      animationRef.current = requestAnimationFrame(render);
    };

    animationRef.current = requestAnimationFrame(render);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      window.removeEventListener("resize", resizeCanvas);
    };
  }, [isRecording, waveformData, riskLevel]);

  return (
    <div className="relative w-full h-28 sm:h-36 rounded-lg overflow-hidden bg-slate-950 border border-slate-800">
      <canvas
        ref={canvasRef}
        className="w-full h-full block"
        style={{ width: "100%", height: "100%" }}
      />
      {/* Telemetry Labels */}
      <div className="absolute top-2.5 left-3 flex items-center gap-2 pointer-events-none">
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            isRecording ? "bg-red-500 animate-pulse" : "bg-slate-600"
          }`}
        />
        <span className="text-xs font-mono text-slate-400">
          {isRecording ? "Live Audio Stream • 16 kHz Mono" : "Sensor Inactive"}
        </span>
      </div>

      {isAnalyzing && (
        <div className="absolute top-2.5 right-3 flex items-center gap-1.5 bg-slate-900 px-2 py-0.5 rounded border border-slate-700 text-slate-300 text-xs font-mono">
          <span>Processing chunk...</span>
        </div>
      )}

      <div className="absolute bottom-2 right-3 pointer-events-none">
        <span className="text-[11px] font-mono text-slate-500">
          PCM Float32 • 512 FFT
        </span>
      </div>
    </div>
  );
};
