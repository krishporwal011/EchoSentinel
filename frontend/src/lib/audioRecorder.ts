/**
 * EchoSentinel Audio Capture & Real-Time Chunker
 * Captures microphone stream via Web Audio API, provides 60fps waveform data,
 * and extracts continuous 2.5–3.0 second 16kHz mono WAV chunks.
 */

export interface AudioRecorderOptions {
  onChunk: (chunk: Blob, sequenceId: number) => void;
  onWaveformData?: (data: Uint8Array) => void;
  onError?: (error: Error) => void;
  chunkIntervalMs?: number; // default 2500ms
}

export class AudioStreamRecorder {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private analyserNode: AnalyserNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private isRecording = false;
  private sequenceCounter = 0;
  private sampleRate = 16000;
  private pcmChunks: Float32Array[] = [];
  private totalSamples = 0;
  private chunkTimer: NodeJS.Timeout | null = null;
  private options: AudioRecorderOptions;
  private animationFrameId: number | null = null;

  constructor(options: AudioRecorderOptions) {
    this.options = {
      chunkIntervalMs: 2500,
      ...options,
    };
  }

  public async start(): Promise<void> {
    if (this.isRecording) return;

    try {
      // 1. Request microphone access
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      // 2. Initialize AudioContext at 16kHz for model compatibility
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioContext = new AudioCtx({ sampleRate: this.sampleRate });
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }

      this.sampleRate = this.audioContext.sampleRate;
      this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

      // 3. Create AnalyserNode for live visual waveform
      this.analyserNode = this.audioContext.createAnalyser();
      this.analyserNode.fftSize = 512;
      this.analyserNode.smoothingTimeConstant = 0.8;
      this.sourceNode.connect(this.analyserNode);

      // 4. Create buffer processor node (4096 buffer size)
      this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);
      this.processorNode.onaudioprocess = (e) => {
        if (!this.isRecording) return;
        const inputData = e.inputBuffer.getChannelData(0);
        // Clone samples
        const copy = new Float32Array(inputData.length);
        copy.set(inputData);
        this.pcmChunks.push(copy);
        this.totalSamples += copy.length;
      };

      this.sourceNode.connect(this.processorNode);
      // Connect to destination through zero-gain to avoid speaker feedback
      const silentGain = this.audioContext.createGain();
      silentGain.gain.value = 0.0;
      this.processorNode.connect(silentGain);
      silentGain.connect(this.audioContext.destination);

      this.isRecording = true;
      this.sequenceCounter = 0;
      this.pcmChunks = [];
      this.totalSamples = 0;

      // 5. Start waveform animation loop
      this.startWaveformLoop();

      // 6. Schedule periodic chunk extraction
      const intervalMs = this.options.chunkIntervalMs || 2500;
      this.chunkTimer = setInterval(() => {
        this.flushChunk();
      }, intervalMs);

    } catch (err) {
      this.stop();
      const error = err instanceof Error ? err : new Error(String(err));
      if (this.options.onError) {
        this.options.onError(error);
      }
      throw error;
    }
  }

  private startWaveformLoop() {
    if (!this.analyserNode) return;
    const bufferLength = this.analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const tick = () => {
      if (!this.isRecording || !this.analyserNode) return;
      this.analyserNode.getByteTimeDomainData(dataArray);
      if (this.options.onWaveformData) {
        this.options.onWaveformData(dataArray);
      }
      this.animationFrameId = requestAnimationFrame(tick);
    };

    this.animationFrameId = requestAnimationFrame(tick);
  }

  public flushChunk() {
    if (!this.isRecording || this.totalSamples === 0) return;

    // Combine accumulated Float32 chunks
    const merged = new Float32Array(this.totalSamples);
    let offset = 0;
    for (const chunk of this.pcmChunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    // Reset accumulator
    this.pcmChunks = [];
    this.totalSamples = 0;

    // Don't send empty or near-empty chunks (< 0.5s)
    if (merged.length < this.sampleRate * 0.5) return;

    // Convert Float32 array to standard 16-bit PCM WAV Blob
    const wavBlob = encodeWavBlob(merged, this.sampleRate);
    this.sequenceCounter += 1;
    this.options.onChunk(wavBlob, this.sequenceCounter);
  }

  public stop(): void {
    this.isRecording = false;

    if (this.chunkTimer) {
      clearInterval(this.chunkTimer);
      this.chunkTimer = null;
    }

    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode = null;
    }

    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }

    if (this.analyserNode) {
      this.analyserNode.disconnect();
      this.analyserNode = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }

    this.pcmChunks = [];
    this.totalSamples = 0;
  }

  public getActiveState(): boolean {
    return this.isRecording;
  }
}

/**
 * Encodes Float32 mono samples into a RIFF 16-bit PCM WAV Blob
 */
export function encodeWavBlob(samples: Float32Array, sampleRate: number = 16000): Blob {
  const numChannels = 1;
  const bitsPerSample = 16;
  const bytesPerSample = bitsPerSample / 8;
  const byteRate = sampleRate * numChannels * bytesPerSample;
  const blockAlign = numChannels * bytesPerSample;
  const dataSize = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  // RIFF identifier 'RIFF'
  writeString(view, 0, "RIFF");
  // RIFF chunk length
  view.setUint32(4, 36 + dataSize, true);
  // RIFF type 'WAVE'
  writeString(view, 8, "WAVE");
  // format chunk identifier 'fmt '
  writeString(view, 12, "fmt ");
  // format chunk length
  view.setUint32(16, 16, true);
  // sample format (1 = PCM)
  view.setUint16(20, 1, true);
  // channel count
  view.setUint16(22, numChannels, true);
  // sample rate
  view.setUint32(24, sampleRate, true);
  // byte rate
  view.setUint32(28, byteRate, true);
  // block align
  view.setUint16(32, blockAlign, true);
  // bits per sample
  view.setUint16(34, bitsPerSample, true);
  // data chunk identifier 'data'
  writeString(view, 36, "data");
  // data chunk length
  view.setUint32(40, dataSize, true);

  // Write 16-bit PCM samples
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    // Scale to signed 16-bit integer
    const intSample = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(offset, intSample, true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}
