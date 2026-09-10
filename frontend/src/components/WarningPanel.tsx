"use client";

import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ShieldAlert } from "lucide-react";

interface WarningPanelProps {
  riskScore: number;
  riskLevel: "High" | "Critical";
  onOpenVerification: () => void;
}

export const WarningPanel: React.FC<WarningPanelProps> = ({
  riskScore,
  riskLevel,
  onOpenVerification,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.6, ease: [0.76, 0, 0.24, 1] }}
      className="w-full bg-gradient-to-r from-[#181c27] via-[#111520] to-[#181c27] border border-[#e66d76]/40 rounded-2xl p-5 sm:p-6 shadow-xl"
    >
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-5">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-[#e66d76]/15 border border-[#e66d76]/30 text-[#e66d76] rounded-xl shrink-0 mt-0.5">
            <AlertTriangle size={24} />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-widest text-[#e66d76] uppercase font-bold px-2 py-0.5 rounded bg-[#e66d76]/10 border border-[#e66d76]/20">
                RISK DETECTED • {riskScore}/100
              </span>
            </div>

            <h3 className="font-serif-cinematic text-xl sm:text-2xl text-[#f4f5f7] mt-1.5">
              Voice Authenticity Warning
            </h3>

            <p className="text-xs sm:text-sm text-[#9ba2b1] mt-1 leading-relaxed max-w-xl">
              This voice may contain signs of synthetic generation or impersonation.
              Sensitive actions have been temporarily placed on hold.
            </p>
          </div>
        </div>

        {/* Action Button */}
        <button
          type="button"
          onClick={onOpenVerification}
          className="px-5 py-3 rounded-xl bg-[#e66d76] hover:bg-[#e66d76]/90 text-white font-mono text-xs tracking-wider font-semibold transition-all shadow-lg flex items-center justify-center gap-2 self-start md:self-auto shrink-0"
        >
          <ShieldAlert size={16} />
          <span>IDENTITY VERIFICATION REQUIRED →</span>
        </button>
      </div>
    </motion.div>
  );
};
