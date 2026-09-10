"use client";

import React, { useRef } from "react";
import { Upload, FileAudio } from "lucide-react";

interface UploadAudioProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export const UploadAudio: React.FC<UploadAudioProps> = ({
  onFileSelected,
  disabled = false,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelected(file);
      e.target.value = "";
    }
  };

  return (
    <div className="relative inline-block">
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac"
        disabled={disabled}
        onChange={handleChange}
        className="hidden"
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="px-6 py-3.5 rounded-full border border-[rgba(255,255,255,0.18)] bg-[#111520] hover:bg-[#181c27] hover:border-[#66b7ff]/50 text-[#f4f5f7] font-mono text-xs tracking-wider transition-all flex items-center gap-2.5 shadow-md disabled:opacity-50"
      >
        <Upload size={14} className="text-[#66b7ff]" />
        <span>UPLOAD AUDIO</span>
      </button>
    </div>
  );
};
