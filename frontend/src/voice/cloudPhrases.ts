import { ApiError } from '../services/api';
import { transcribe } from '../services/text';
import { concat, downsample, encodeWav } from '../services/wav';
import type { RecognizerState } from './recognizer';

/**
 * The opt-in fallback for a language the browser cannot recognise (research D4, FR-032). It listens to the
 * microphone on this device, notices when someone starts and stops speaking, and sends ONLY that short phrase to
 * MrCourt's speech service, then throws the audio away. Never a continuous stream; nothing is kept; used only after
 * the person has agreed to voice control and chosen the cloud option.
 */

export type CloudError = 'denied' | 'failed' | 'busy' | 'unavailable';

export interface CloudEvents {
  onPhrase(text: string): void;
  onState(state: RecognizerState): void;
  onError(error: CloudError): void;
}

/** How loud counts as speech, how long a silence ends a phrase, and the longest phrase sent. */
export const SPEECH_LEVEL = 0.015;
export const SILENCE_MS = 700;
export const MAX_PHRASE_SECONDS = 8;
const MIN_PHRASE_SECONDS = 0.35;
const PRE_ROLL_CHUNKS = 2;
const BUSY_PAUSE_MS = 60_000;

function rms(samples: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
  return Math.sqrt(sum / Math.max(1, samples.length));
}

export class CloudPhraseListener {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private wanted = false;
  private paused = false;
  private blockedUntil = 0;
  private recording: Float32Array[] | null = null;
  private recent: Float32Array[] = [];
  private lastLoud = 0;
  private startedAt = 0;
  private queue: Promise<void> = Promise.resolve();

  constructor(
    private readonly events: CloudEvents,
    private language: string,
  ) {}

  get listening(): boolean {
    return this.wanted && !this.paused && Date.now() >= this.blockedUntil;
  }

  setLanguage(code: string): void {
    this.language = code;
  }

  async start(): Promise<boolean> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      const name = (error as { name?: string }).name;
      this.events.onError(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : 'failed');
      return false;
    }
    const AudioCtor =
      window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.context = new AudioCtor();
    this.source = this.context.createMediaStreamSource(this.stream);
    this.processor = this.context.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (event) => this.hear(new Float32Array(event.inputBuffer.getChannelData(0)));
    this.source.connect(this.processor);
    this.processor.connect(this.context.destination);
    this.wanted = true;
    this.events.onState('listening');
    return true;
  }

  stop(): void {
    this.wanted = false;
    this.paused = false;
    this.recording = null;
    this.recent = [];
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.context?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.context = null;
    this.events.onState('stopped');
  }

  pause(): void {
    if (!this.wanted || this.paused) return;
    this.paused = true;
    this.recording = null;
    this.events.onState('paused');
  }

  resume(): void {
    if (!this.wanted || !this.paused) return;
    this.paused = false;
    this.events.onState('listening');
  }

  /** One block of audio from the microphone. Kept only while a phrase is being captured. */
  private hear(chunk: Float32Array): void {
    if (!this.wanted || this.paused || Date.now() < this.blockedUntil) return;
    const loud = rms(chunk) >= SPEECH_LEVEL;
    const now = Date.now();
    if (!this.recording) {
      this.recent.push(chunk);
      if (this.recent.length > PRE_ROLL_CHUNKS) this.recent.shift();
      if (loud) {
        this.recording = [...this.recent];
        this.recent = [];
        this.startedAt = now;
        this.lastLoud = now;
      }
      return;
    }
    this.recording.push(chunk);
    if (loud) this.lastLoud = now;
    if (now - this.lastLoud >= SILENCE_MS || now - this.startedAt >= MAX_PHRASE_SECONDS * 1000) this.finish();
  }

  private finish(): void {
    const chunks = this.recording;
    this.recording = null;
    const rate = this.context?.sampleRate ?? 48_000;
    if (!chunks) return;
    const samples = concat(chunks);
    if (samples.length / rate < MIN_PHRASE_SECONDS) return;
    const wav = encodeWav(downsample(samples, rate));
    // One phrase at a time, in order; the audio is dropped as soon as the answer (or the failure) is back.
    this.queue = this.queue.then(() => this.send(wav));
  }

  private async send(wav: Blob): Promise<void> {
    if (!this.wanted) return;
    try {
      const text = (await transcribe(wav, this.language)).trim();
      if (text && this.wanted && !this.paused) this.events.onPhrase(text);
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        this.blockedUntil = Date.now() + BUSY_PAUSE_MS;
        this.events.onError('busy');
        setTimeout(() => {
          if (this.wanted && !this.paused) this.events.onState('listening');
        }, BUSY_PAUSE_MS);
      } else if (error instanceof ApiError && error.status === 503) {
        this.events.onError('unavailable');
        this.stop();
      } else {
        this.events.onError('failed');
      }
    }
  }
}
