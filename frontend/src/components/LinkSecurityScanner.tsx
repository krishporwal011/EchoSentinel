"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  Clock,
  XCircle,
  ExternalLink,
  Search,
  RefreshCw,
  Info,
  Lock,
} from "lucide-react";

export interface UrlStats {
  malicious?: number | null;
  suspicious?: number | null;
  harmless?: number | null;
  undetected?: number | null;
}

export type ScanStatus = "completed" | "pending" | "error";

export type ThreatClassification =
  | "malicious"
  | "suspicious"
  | "no_threats_detected"
  | "unknown"
  | "analysis_pending"
  | "scan_error";

export interface ScanUrlResponse {
  status: ScanStatus;
  classification: ThreatClassification;
  url: string;
  stats?: UrlStats | null;
  provider: string;
  analysis_id?: string | null;
  report_url?: string | null;
  message: string;
}

export const LinkSecurityScanner: React.FC = () => {
  const [urlInput, setUrlInput] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanUrlResponse | null>(null);
  const [lastScannedUrl, setLastScannedUrl] = useState<string | null>(null);

  const validateInput = (value: string): string | null => {
    const trimmed = value.trim();
    if (!trimmed) {
      return "Please enter a website URL to scan.";
    }
    if (trimmed.length > 2048) {
      return "URL exceeds the maximum length of 2048 characters.";
    }
    if (/\s/.test(trimmed)) {
      return "URL cannot contain spaces.";
    }
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return "Only HTTP and HTTPS URLs are supported.";
      }
      if (!parsed.hostname || !parsed.hostname.includes(".")) {
        return "Please enter a valid domain or hostname (e.g., https://example.com).";
      }
    } catch {
      return "Invalid URL format. Please include https:// or http:// prefix.";
    }
    return null;
  };

  const handleScan = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    const error = validateInput(urlInput);
    if (error) {
      setValidationError(error);
      return;
    }
    setValidationError(null);

    // Duplicate submit prevention
    if (isScanning) return;

    const targetUrl = urlInput.trim();
    setIsScanning(true);
    setLastScannedUrl(targetUrl);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiBase}/api/scan-url`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ url: targetUrl }),
      });

      if (!response.ok) {
        let errorMsg = `Server error (HTTP ${response.status})`;
        try {
          const errData = await response.json();
          errorMsg = errData.message || errData.detail || errorMsg;
        } catch {
          // ignore json parse error
        }
        setScanResult({
          status: "error",
          classification: "scan_error",
          url: targetUrl,
          stats: null,
          provider: "VirusTotal",
          analysis_id: null,
          report_url: null,
          message: errorMsg,
        });
        return;
      }

      const data: ScanUrlResponse = await response.json();
      setScanResult(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to connect to the backend scanner.";
      setScanResult({
        status: "error",
        classification: "scan_error",
        url: targetUrl,
        stats: null,
        provider: "VirusTotal",
        analysis_id: null,
        report_url: null,
        message: message.includes("Failed to fetch")
          ? "Unable to reach EchoSentinel backend API. Please verify the backend server is running on port 8000."
          : message,
      });
    } finally {
      setIsScanning(false);
    }
  };

  const handleRetry = () => {
    if (lastScannedUrl) {
      setUrlInput(lastScannedUrl);
      void handleScan();
    }
  };

  const getClassificationBadge = (classification: ThreatClassification) => {
    switch (classification) {
      case "malicious":
        return {
          label: "MALICIOUS",
          textColor: "text-[#ef4444]",
          bgColor: "bg-[#ef4444]/15",
          borderColor: "border-[#ef4444]/40",
          icon: <ShieldAlert size={18} className="text-[#ef4444]" />,
          barColor: "bg-[#ef4444]",
        };
      case "suspicious":
        return {
          label: "SUSPICIOUS",
          textColor: "text-[#f59e0b]",
          bgColor: "bg-[#f59e0b]/15",
          borderColor: "border-[#f59e0b]/40",
          icon: <AlertTriangle size={18} className="text-[#f59e0b]" />,
          barColor: "bg-[#f59e0b]",
        };
      case "no_threats_detected":
        return {
          label: "NO THREATS DETECTED",
          textColor: "text-[#10b981]",
          bgColor: "bg-[#10b981]/15",
          borderColor: "border-[#10b981]/40",
          icon: <ShieldCheck size={18} className="text-[#10b981]" />,
          barColor: "bg-[#10b981]",
        };
      case "analysis_pending":
        return {
          label: "ANALYSIS PENDING",
          textColor: "text-[#9ba2b1]",
          bgColor: "bg-white/5",
          borderColor: "border-white/10",
          icon: <Clock size={18} className="text-[#9ba2b1] animate-spin" />,
          barColor: "bg-[#9ba2b1]",
        };
      case "scan_error":
        return {
          label: "SCAN ERROR",
          textColor: "text-[#f87171]",
          bgColor: "bg-[#f87171]/15",
          borderColor: "border-[#f87171]/40",
          icon: <XCircle size={18} className="text-[#f87171]" />,
          barColor: "bg-[#f87171]",
        };
      case "unknown":
      default:
        return {
          label: "UNKNOWN",
          textColor: "text-[#9ba2b1]",
          bgColor: "bg-white/5",
          borderColor: "border-white/10",
          icon: <HelpCircle size={18} className="text-[#9ba2b1]" />,
          barColor: "bg-[#9ba2b1]",
        };
    }
  };

  const badge = scanResult ? getClassificationBadge(scanResult.classification) : null;

  return (
    <div className="space-y-8">
      {/* Scanner Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-mono tracking-widest text-[#66b7ff] uppercase font-semibold">
            LINK SECURITY SCANNER
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#66b7ff]/10 text-[#8ddcff] border border-[#66b7ff]/20">
            VIRUSTOTAL API V3
          </span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-serif-cinematic font-bold text-[#f4f5f7]">
          Link Security Scanner
        </h2>
        <p className="text-sm text-[#9ba2b1] max-w-2xl">
          Check suspicious URLs against VirusTotal threat intelligence.
        </p>
      </div>

      {/* URL Input Form Card */}
      <div className="p-6 sm:p-8 rounded-3xl bg-[#111520] border border-[rgba(255,255,255,0.1)] shadow-xl relative overflow-hidden">
        {/* Subtle accent blur */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-[#66b7ff]/5 rounded-full blur-3xl pointer-events-none" />

        <form onSubmit={handleScan} className="space-y-4 relative z-10">
          <div className="space-y-1.5">
            <label
              htmlFor="url-scanner-input"
              className="text-xs font-mono uppercase tracking-wider text-[#cbd5e1] block"
            >
              Target Website URL
            </label>
            <div className="flex flex-col sm:flex-row items-stretch gap-3">
              <div className="relative flex-1">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#626978]">
                  <Search size={16} />
                </div>
                <input
                  id="url-scanner-input"
                  type="text"
                  value={urlInput}
                  onChange={(e) => {
                    setUrlInput(e.target.value);
                    if (validationError) setValidationError(null);
                  }}
                  disabled={isScanning}
                  placeholder="Paste a website URL to scan…"
                  className="w-full pl-10 pr-4 py-3.5 rounded-2xl bg-[#090b11] border border-[rgba(255,255,255,0.12)] text-[#f4f5f7] placeholder-[#626978] text-sm font-mono focus:outline-none focus:border-[#66b7ff] transition-all disabled:opacity-60"
                />
              </div>

              <button
                type="submit"
                disabled={isScanning || !urlInput.trim()}
                className="px-8 py-3.5 rounded-2xl bg-gradient-to-r from-[#66b7ff] to-[#4da3ff] hover:from-[#8ddcff] hover:to-[#66b7ff] text-[#090b11] font-mono text-sm tracking-wider font-bold transition-all shadow-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap cursor-pointer"
              >
                {isScanning ? (
                  <>
                    <RefreshCw size={15} className="animate-spin" />
                    <span>SCANNING…</span>
                  </>
                ) : (
                  <>
                    <Search size={15} />
                    <span>SCAN LINK</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Validation Feedback */}
          {validationError && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-xs font-mono text-[#fca5a5] flex items-center gap-1.5 pt-1"
            >
              <AlertTriangle size={13} />
              <span>{validationError}</span>
            </motion.div>
          )}

          {/* Privacy & Security Notice */}
          <div className="p-3.5 rounded-xl bg-[#090b11]/60 border border-white/5 text-xs text-[#9ba2b1] flex items-start gap-2.5">
            <Lock size={14} className="text-[#66b7ff] shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              <strong className="text-[#cbd5e1]">Security Notice:</strong> URLs submitted are checked against VirusTotal threat intelligence and public security vendor databases. Do not submit internal links, credentials, or private confidential tokens.
            </p>
          </div>
        </form>
      </div>

      {/* Loading Radar Animation State */}
      {isScanning && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="p-8 rounded-3xl bg-[#111520] border border-[#66b7ff]/30 text-center space-y-4"
        >
          <div className="flex justify-center">
            <div className="relative w-16 h-16 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border border-[#66b7ff]/40 animate-ping" />
              <div className="w-10 h-10 rounded-full bg-[#66b7ff]/20 border border-[#66b7ff] flex items-center justify-center">
                <RefreshCw size={18} className="text-[#66b7ff] animate-spin" />
              </div>
            </div>
          </div>
          <div>
            <h3 className="text-base font-mono font-semibold text-[#f4f5f7]">
              Querying VirusTotal Threat Intelligence Engine…
            </h3>
            <p className="text-xs font-mono text-[#9ba2b1] mt-1">
              Analyzing URL signatures across 70+ antivirus and web reputation vendors.
            </p>
          </div>
        </motion.div>
      )}

      {/* Scan Results Display */}
      <AnimatePresence>
        {scanResult && !isScanning && badge && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className={`p-6 sm:p-8 rounded-3xl bg-[#111520] border ${badge.borderColor} shadow-2xl space-y-6 relative overflow-hidden`}
          >
            {/* Top Indicator Strip */}
            <div className={`absolute top-0 left-0 right-0 h-1 ${badge.barColor}`} />

            {/* Header: Classification + Provider */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
              <div className="space-y-1">
                <span className="text-[11px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                  THREAT CLASSIFICATION
                </span>
                <div className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full ${badge.bgColor} border ${badge.borderColor} text-xs font-mono font-bold tracking-wider ${badge.textColor}`}>
                  {badge.icon}
                  <span>{badge.label}</span>
                </div>
              </div>

              <div className="text-right space-y-1">
                <span className="text-[11px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                  SCAN PROVIDER
                </span>
                <span className="text-sm font-mono font-semibold text-[#f4f5f7]">
                  {scanResult.provider}
                </span>
              </div>
            </div>

            {/* Submitted URL */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                SUBMITTED URL
              </span>
              <div className="p-3.5 rounded-xl bg-[#090b11] border border-white/10 font-mono text-xs text-[#8ddcff] break-all select-all flex items-center justify-between gap-2">
                <span>{scanResult.url}</span>
              </div>
            </div>

            {/* Detailed Explanation / Warning */}
            <div className="p-4 rounded-2xl bg-[#090b11]/80 border border-white/10 space-y-2">
              <div className="flex items-center gap-2 text-xs font-mono font-semibold text-[#cbd5e1]">
                <Info size={14} className="text-[#66b7ff]" />
                <span>SCAN SUMMARY</span>
              </div>
              <p className="text-sm text-[#cbd5e1] leading-relaxed">
                {scanResult.message}
              </p>
            </div>

            {/* 4 Detection Counts */}
            <div className="space-y-2">
              <span className="text-[11px] font-mono tracking-widest text-[#9ba2b1] uppercase block">
                SECURITY VENDOR DETECTION METRICS
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {/* Malicious */}
                <div className="p-4 rounded-2xl bg-[#090b11] border border-white/10 space-y-1">
                  <span className="text-[11px] font-mono uppercase text-[#ef4444] tracking-wider block">
                    Malicious
                  </span>
                  <span className="text-2xl font-mono font-bold text-white">
                    {scanResult.stats?.malicious !== undefined && scanResult.stats?.malicious !== null
                      ? scanResult.stats.malicious
                      : "—"}
                  </span>
                  <span className="text-[10px] font-mono text-[#9ba2b1] block">Vendors flagged</span>
                </div>

                {/* Suspicious */}
                <div className="p-4 rounded-2xl bg-[#090b11] border border-white/10 space-y-1">
                  <span className="text-[11px] font-mono uppercase text-[#f59e0b] tracking-wider block">
                    Suspicious
                  </span>
                  <span className="text-2xl font-mono font-bold text-white">
                    {scanResult.stats?.suspicious !== undefined && scanResult.stats?.suspicious !== null
                      ? scanResult.stats.suspicious
                      : "—"}
                  </span>
                  <span className="text-[10px] font-mono text-[#9ba2b1] block">Flagged suspicious</span>
                </div>

                {/* Harmless */}
                <div className="p-4 rounded-2xl bg-[#090b11] border border-white/10 space-y-1">
                  <span className="text-[11px] font-mono uppercase text-[#10b981] tracking-wider block">
                    Harmless
                  </span>
                  <span className="text-2xl font-mono font-bold text-white">
                    {scanResult.stats?.harmless !== undefined && scanResult.stats?.harmless !== null
                      ? scanResult.stats.harmless
                      : "—"}
                  </span>
                  <span className="text-[10px] font-mono text-[#9ba2b1] block">Clean rating</span>
                </div>

                {/* Undetected */}
                <div className="p-4 rounded-2xl bg-[#090b11] border border-white/10 space-y-1">
                  <span className="text-[11px] font-mono uppercase text-[#9ba2b1] tracking-wider block">
                    Undetected
                  </span>
                  <span className="text-2xl font-mono font-bold text-white">
                    {scanResult.stats?.undetected !== undefined && scanResult.stats?.undetected !== null
                      ? scanResult.stats.undetected
                      : "—"}
                  </span>
                  <span className="text-[10px] font-mono text-[#9ba2b1] block">No signatures</span>
                </div>
              </div>
            </div>

            {/* Analysis Metadata & Actions */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-white/10">
              <div className="flex items-center gap-3 text-xs font-mono text-[#9ba2b1]">
                <span>Status: <strong className="text-white capitalize">{scanResult.status}</strong></span>
                {scanResult.analysis_id && (
                  <>
                    <span>•</span>
                    <span>ID: <code className="text-[#8ddcff]">{scanResult.analysis_id.slice(0, 16)}…</code></span>
                  </>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {scanResult.report_url && (
                  <a
                    href={scanResult.report_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-5 py-2.5 rounded-full bg-[#66b7ff]/15 hover:bg-[#66b7ff]/25 text-[#8ddcff] hover:text-white font-mono text-xs tracking-wider font-semibold transition-all border border-[#66b7ff]/30 flex items-center gap-2"
                  >
                    <span>VIEW FULL VIRUSTOTAL REPORT</span>
                    <ExternalLink size={13} />
                  </a>
                )}

                {(scanResult.status === "error" || scanResult.status === "pending") && (
                  <button
                    type="button"
                    onClick={handleRetry}
                    className="px-5 py-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white font-mono text-xs tracking-wider transition-all flex items-center gap-1.5"
                  >
                    <RefreshCw size={12} />
                    <span>Retry</span>
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
