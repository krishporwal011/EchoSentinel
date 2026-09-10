"use client";

import React, { useEffect, useRef } from "react";

interface AudioWaveformProps {
  isRecording: boolean;
  waveformData: Uint8Array | null;
  chunkNumber?: number;
  isAnalyzing?: boolean;
  riskLevel?: "Low" | "Suspicious" | "High" | "Critical";
}

export const AudioWaveform: React.FC<AudioWaveformProps> = ({
  isRecording,
  waveformData,
  chunkNumber = 1,
  isAnalyzing = false,
  riskLevel = "Low",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const getWaveColor = () => {
    if (!isRecording) return "#626978"; // text-muted
    switch (riskLevel) {
      case "Critical":
        return "#e66d76";
      case "High":
        return "#e79a65";
      case "Suspicious":
        return "#e8c86b";
      case "Low":
      default:
        return "#70d6a0";
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let dpr = window.devicePixelRatio || 1;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 600) * dpr;
    let height = (canvas.height = (canvas.parentElement?.clientHeight || 120)) * dpr;
    ctx.scale(dpr, dpr);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth * dpr;
      height = canvas.height = canvas.parentElement.clientHeight * dpr;
      ctx.scale(dpr, dpr);
    };
    window.addEventListener("resize", handleResize);

    let phase = 0;

    const render = () => {
      const renderW = width / dpr;
      const renderH = height / dpr;
      phase += isRecording ? 0.04 : 0.015;

      ctx.clearRect(0, 0, renderW, renderH);

      // Subtle Center Axis Line
      ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, renderH / 2);
      ctx.lineTo(renderW, renderH / 2);
      ctx.stroke();

      const waveColor = getWaveColor();

      // Draw Thin Fluid Waveform
      ctx.strokeStyle = waveColor;
      ctx.lineWidth = 1.8;
      ctx.beginPath();

      if (isRecording && waveformData && waveformData.length > 0) {
        const sliceWidth = renderW / (waveformData.length - 1);
        let x = 0;

        for (let i = 0; i < waveformData.length; i++) {
          const v = waveformData[i] / 128.0;
          const y = (v * renderH) / 2;

          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);

          x += sliceWidth;
        }
      } else {
        // Idle fluid sine wave
        const amplitude = isRecording ? renderH * 0.22 : renderH * 0.08;
        for (let x = 0; x < renderW; x += 3) {
          const y = renderH / 2 + Math.sin(x * 0.02 + phase) * amplitude * Math.sin(x * 0.004);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      // Flowing particles along the line
      ctx.fillStyle = waveColor;
      const particleOffset = (phase * 60) % renderW;
      for (let p = 0; p < 3; p++) {
        const px = (particleOffset + p * (renderW / 3)) % renderW;
        const py = renderH / 2 + Math.sin(px * 0.02 + phase) * (renderH * 0.1);
        ctx.beginPath();
        ctx.arc(px, py, 2, 0, Math.PI * 2);
        ctx.fill();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
    };
  }, [isRecording, waveformData, riskLevel]);

  const formattedChunk = String(chunkNumber).padStart(2, "0");

  return (
    <div className="relative w-full h-24 sm:h-28 rounded-xl bg-[#111520] border border-[rgba(255,255,255,0.12)] overflow-hidden shadow-inner">
      <canvas ref={canvasRef} className="w-full h-full block" />

      {/* Top Left: Real-time Audio Stream Status */}
      <div className="absolute top-2.5 left-3.5 flex items-center gap-2 pointer-events-none">
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            isRecording ? "bg-[#70d6a0] animate-pulse" : "bg-[#626978]"
          }`}
        />
        <span className="text-[10px] font-mono tracking-widest text-[#9ba2b1] uppercase">
          {isRecording ? "LIVE 16 KHZ PCM" : "SENSOR INACTIVE"}
        </span>
      </div>

      {/* Top Right: Discrete Chunk Processing Indicator */}
      {isRecording && (
        <div className="absolute top-2.5 right-3.5 flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#181c27] border border-[rgba(255,255,255,0.12)] text-[10px] font-mono">
          <span className="text-[#9ba2b1]">CHUNK {formattedChunk}</span>
          <span className="text-[#626978]">•</span>
          <span className={isAnalyzing ? "text-[#8ddcff] animate-pulse" : "text-[#70d6a0]"}>
            {isAnalyzing ? "ANALYZING..." : "ANALYZED"}
          </span>
        </div>
      )}

      {/* Bottom Right: FFT Spec */}
      <div className="absolute bottom-2 right-3.5 text-[9px] font-mono text-[#626978] pointer-events-none">
        512 FFT • MONO WAV STREAM
      </div>
    </div>
  );
};
