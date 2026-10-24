export type ClassificationLabel = "likely_ai_generated" | "likely_human_recorded" | "inconclusive";
export type RiskLevel = "low" | "medium" | "high" | "inconclusive";

export interface TranscriptionResult {
  status: "completed" | "unavailable" | "error" | "skipped";
  text?: string | null;
  language?: string | null;
  duration_seconds?: number | null;
  message?: string | null;
  provider?: string | null;
}

export interface ScamIndicator {
  category: string;
  matched_concept: string;
  evidence: string;
  explanation: string;
  severity: "low" | "medium" | "high" | "critical";
}

export interface ScamAnalysisResult {
  status: "ANALYZED" | "UNAVAILABLE" | "ERROR" | "UNCERTAIN";
  scam_risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN";
  scam_risk_score?: number | null;
  categories: string[];
  indicators: ScamIndicator[];
  detected_threat_phrases?: string[];
  threat_alert_text?: string | null;
  recommendations: string[];
  limitations: string[];
  warning_banner?: string | null;
  message?: string | null;
}

export interface DetectionResponse {
  success: boolean;
  prediction: {
    label: ClassificationLabel;
    ai_probability: number | null;
    human_probability: number | null;
    risk_level: RiskLevel;
    confidence: number | null;
    confidence_note: string;
    probability_type: string;
    fake_score?: number;
    real_score?: number;
  };
  audio?: {
    duration_seconds: number;
    source_sample_rate: number;
    sample_rate: number;
    channels: number;
    quality: "good" | "fair" | "poor";
    quality_estimate_score: number;
    quality_method: string;
    quality_indicators: Array<{ id: string; label: string; value: number; unit: string; interpretation: string }>;
    quality_warnings: string[];
    waveform: number[];
    spectrogram: number[][];
    spectrogram_sample_rate: number;
    spectrogram_hop_length: number;
  };
  explanation?: {
    summary: string;
    evidence: Array<{ type: string; title: string; detail: string }>;
    limitations: string[];
  };
  model?: {
    name: string;
    checkpoint: string;
    revision: string | null;
    architecture: string;
    inference_completed: boolean;
    labels: Record<string, number>;
    probabilities_calibrated: boolean;
  };
  transcription?: TranscriptionResult;
  scam_analysis?: ScamAnalysisResult;
  processing_status: string;
  processing_time_ms: number;
  notice?: string;
  mode?: "real" | "demo";
}

type JsonObject = Record<string, unknown>;

const isObject = (value: unknown): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);
const isOptionalProbability = (value: unknown): value is number | null =>
  value === null || (isFiniteNumber(value) && value >= 0 && value <= 1);

/** Validate the live API payload before it reaches UI components. */
export function parseDetectionResponse(payload: unknown): DetectionResponse {
  const invalid = (field: string): never => {
    throw new Error(`The analysis service returned an invalid response (${field}). Please retry.`);
  };
  if (!isObject(payload) || payload.success !== true) return invalid("success");

  const prediction = payload.prediction;
  if (!isObject(prediction)) return invalid("prediction");
  if (!(["likely_ai_generated", "likely_human_recorded", "inconclusive"] as unknown[]).includes(prediction.label)) return invalid("prediction.label");
  if (!(["low", "medium", "high", "inconclusive"] as unknown[]).includes(prediction.risk_level)) return invalid("prediction.risk_level");
  if (!isOptionalProbability(prediction.ai_probability) || !isOptionalProbability(prediction.human_probability)) return invalid("prediction.probabilities");
  if (prediction.ai_probability !== null && prediction.human_probability !== null && Math.abs(prediction.ai_probability + prediction.human_probability - 1) > 1e-4) return invalid("prediction.probabilities");
  if (prediction.confidence !== null && !isOptionalProbability(prediction.confidence)) return invalid("prediction.confidence");
  if (typeof prediction.confidence_note !== "string" || typeof prediction.probability_type !== "string") return invalid("prediction.metadata");

  const audio = payload.audio;
  if (!isObject(audio)
    || !isFiniteNumber(audio.duration_seconds) || audio.duration_seconds <= 0
    || !Number.isInteger(audio.source_sample_rate) || (audio.source_sample_rate as number) <= 0
    || !Number.isInteger(audio.sample_rate) || (audio.sample_rate as number) <= 0
    || !Number.isInteger(audio.channels) || (audio.channels as number) <= 0
    || !["good", "fair", "poor"].includes(String(audio.quality))
    || !isFiniteNumber(audio.quality_estimate_score)
    || typeof audio.quality_method !== "string"
    || !Array.isArray(audio.quality_indicators)
    || !Array.isArray(audio.quality_warnings) || !audio.quality_warnings.every((item) => typeof item === "string")
    || !Array.isArray(audio.waveform) || !audio.waveform.every(isFiniteNumber)
    || !Array.isArray(audio.spectrogram) || !audio.spectrogram.every((row) => Array.isArray(row) && row.every(isFiniteNumber))
    || !Number.isInteger(audio.spectrogram_sample_rate) || !Number.isInteger(audio.spectrogram_hop_length)) return invalid("audio");
  if (!audio.quality_indicators.every((item) => isObject(item)
    && typeof item.id === "string" && typeof item.label === "string"
    && isFiniteNumber(item.value) && typeof item.unit === "string" && typeof item.interpretation === "string")) return invalid("audio.quality_indicators");

  const explanation = payload.explanation;
  if (!isObject(explanation)
    || typeof explanation.summary !== "string"
    || !Array.isArray(explanation.evidence)
    || !explanation.evidence.every((item) => isObject(item) && typeof item.type === "string" && typeof item.title === "string" && typeof item.detail === "string")
    || !Array.isArray(explanation.limitations) || !explanation.limitations.every((item) => typeof item === "string")) return invalid("explanation");

  const model = payload.model;
  if (!isObject(model)
    || typeof model.name !== "string" || typeof model.checkpoint !== "string"
    || (model.revision !== null && typeof model.revision !== "string")
    || typeof model.architecture !== "string" || model.inference_completed !== true
    || !isObject(model.labels)
    || !Number.isInteger(model.labels.bonafide) || !Number.isInteger(model.labels.spoof)
    || model.labels.bonafide === model.labels.spoof
    || typeof model.probabilities_calibrated !== "boolean") return invalid("model");
  if (payload.processing_status !== "completed" || !isFiniteNumber(payload.processing_time_ms) || payload.processing_time_ms < 0) return invalid("processing status");

  return payload as unknown as DetectionResponse;
}

let lastDemoScore = 0;

export function createDemoResult(isSynthetic: boolean): DetectionResponse {
  let score = 86.8;
  for (let i = 0; i < 20; i++) {
    const cand = Math.round((81.5 + Math.random() * 7.6) * 10) / 10;
    if (Math.abs(cand - lastDemoScore) >= 0.5) {
      score = cand;
      break;
    }
  }
  lastDemoScore = score;

  const fakeScore = isSynthetic ? score : Math.round((100 - score) * 10) / 10;
  const realScore = isSynthetic ? Math.round((100 - score) * 10) / 10 : score;
  const aiProbability = fakeScore / 100;
  const humanProbability = realScore / 100;
  return {
    success: true,
    mode: "demo",
    prediction: {
      label: isSynthetic ? "likely_ai_generated" : "likely_human_recorded",
      ai_probability: aiProbability,
      human_probability: humanProbability,
      risk_level: isSynthetic ? "high" : "low",
      confidence: Math.round(Math.max(aiProbability, humanProbability) * 1000) / 1000,
      confidence_note: "Simulated demonstration example (calibrated 80–90% range).",
      probability_type: "demo_simulation",
      fake_score: fakeScore,
      real_score: realScore,
    },
    transcription: isSynthetic
      ? {
          status: "completed",
          text: "Attention! Your bank account will be blocked today due to pending verification. Please tell me your 6-digit OTP code right now to complete your KYC immediately.",
          language: "english",
          duration_seconds: 4.8,
          message: "Demonstration transcription simulated.",
        }
      : {
          status: "completed",
          text: "Hello, this is a routine advisory from customer support. Please remember to never share your secret OTP or UPI PIN with anyone over the phone.",
          language: "english",
          duration_seconds: 5.1,
          message: "Demonstration transcription simulated.",
        },
    scam_analysis: isSynthetic
      ? {
          status: "ANALYZED",
          scam_risk_level: "CRITICAL",
          scam_risk_score: 92,
          categories: ["SENSITIVE_INFORMATION_REQUEST", "URGENCY_AND_THREATS"],
          indicators: [
            {
              category: "SENSITIVE_INFORMATION_REQUEST",
              matched_concept: "OTP / verification code request",
              evidence: "Please tell me your 6-digit OTP code right now to complete your KYC immediately.",
              explanation: "The speaker is requesting secret one-time verification credentials.",
              severity: "critical",
            },
            {
              category: "URGENCY_AND_THREATS",
              matched_concept: "Account suspension threat",
              evidence: "Attention! Your bank account will be blocked today due to pending verification.",
              explanation: "The speaker manufactures artificial urgency regarding account suspension.",
              severity: "high",
            },
          ],
          recommendations: [
            "Immediately terminate the conversation. Do NOT disclose OTPs, PINs, or passwords.",
            "Do not install remote applications or approve unsolicited payment requests.",
            "Contact your financial institution through their verified customer support number immediately.",
          ],
          limitations: [
            "Demo simulation showing high-confidence social engineering attack detection.",
            "Voice authenticity and scam intent are evaluated by independent systems.",
          ],
          warning_banner:
            "CRITICAL ALERT: High-confidence social-engineering attack detected. The conversation combines sensitive credential solicitation with urgency threats. Never share your OTP or banking passwords.",
          message: "Detected 2 potential scam intent indicator(s) across 2 categories.",
        }
      : {
          status: "ANALYZED",
          scam_risk_level: "LOW",
          scam_risk_score: 12,
          categories: [],
          indicators: [
            {
              category: "SECURITY_AWARENESS",
              matched_concept: "Security warning regarding credentials",
              evidence: "Please remember to never share your secret OTP or UPI PIN with anyone over the phone.",
              explanation: "The speaker is advising the listener NOT to reveal sensitive credentials.",
              severity: "low",
            },
          ],
          recommendations: ["Continue standard vigilance when sharing personal information."],
          limitations: [
            "Demo simulation demonstrating context-aware negation handling (security advice is not flagged as a scam).",
          ],
          warning_banner: null,
          message: "No active social-engineering or credential harvesting requests detected.",
        },
    processing_status: "demo_simulation",
    processing_time_ms: Math.round((18.0 + Math.random() * 8.0) * 10) / 10,
  };
}
