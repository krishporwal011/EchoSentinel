/**
 * EchoSentinel Editorial & Verification Content
 */

export const CHALLENGE_PHRASES = [
  "Blue mountains remember the morning.",
  "Silver rivers run quiet through stone.",
  "Forty-seven shadows follow the wind.",
  "Golden lanterns flicker before dawn.",
  "Cobalt waves whisper against the shore.",
  "Amber horizon holds the quiet bell.",
  "Velvet echoes carry through the valley.",
  "Ancient cedar stands beneath the stars.",
];

export const PIPELINE_STAGES = [
  { id: "audio", label: "AUDIO INGEST", desc: "16 kHz continuous capture & windowing" },
  { id: "preproc", label: "PREPROCESSING", desc: "Mono downmix & amplitude normalization" },
  { id: "model", label: "AI INFERENCE", desc: "Wav2Vec2 sequence classification" },
  { id: "risk", label: "RISK ENGINE", desc: "Acoustic spoof probability scoring" },
];

export const WORKFLOW_STEPS = [
  {
    step: "01",
    title: "LISTEN",
    description: "Capture live microphone input or ingest uploaded audio clips directly in your browser without cellular interception.",
  },
  {
    step: "02",
    title: "CHUNK",
    description: "Break continuous speech into precise 2.5–3.0 second analysis windows encoded as 16 kHz mono PCM signals.",
  },
  {
    step: "03",
    title: "INFER",
    description: "Execute a pretrained Wav2Vec2 transformer fine-tuned on the ASVspoof dataset to detect synthetic artifacts.",
  },
  {
    step: "04",
    title: "PROTECT",
    description: "Compute threat scores across 4 calibrated risk bands and trigger a dynamic identity challenge before sensitive continuation.",
  },
];

export const HONEST_LIMITATIONS = [
  {
    title: "Does not prove a person's identity",
    detail: "The detection model identifies patterns associated with synthetic speech. It does not verify biological speaker identity.",
  },
  {
    title: "Does not guarantee perfect detection",
    detail: "Detection is probabilistic. Zero-day generative models, clean audio, and noisy environments may produce false positives or negatives.",
  },
  {
    title: "Does not replace bank-grade fraud infrastructure",
    detail: "EchoSentinel provides an intelligent defense layer for communications, not a replacement for government ID or banking HSMs.",
  },
];
