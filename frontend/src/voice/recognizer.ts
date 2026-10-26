import { getCtor, type Recognition } from '../hooks/useSpeechInput';

/**
 * Continuous listening with the browser's own speech recognition (research D4). The browser ends a turn after a
 * silence or about a minute, so the app starts it again for as long as the person still wants to listen. It never
 * restarts after the person stops it, pauses while the tab is hidden, and says plainly when the microphone is
 * blocked or the language is not supported. MrCourt never receives the audio.
 */

export type RecognizerError = 'denied' | 'unsupported' | 'language' | 'network' | 'failed';
export type RecognizerState = 'listening' | 'paused' | 'stopped';

export interface RecognizerEvents {
  /** A finished phrase, with the recogniser's confidence when it gives one (null when it does not). */
  onPhrase(text: string, confidence: number | null): void;
  onInterim?(text: string): void;
  onState(state: RecognizerState): void;
  onError(error: RecognizerError): void;
}

interface ResultItem {
  transcript: string;
  confidence?: number;
}
interface ResultEvent {
  resultIndex?: number;
  results: ArrayLike<ArrayLike<ResultItem> & { isFinal?: boolean }>;
}

const RESTART_AFTER_MS = 150;
const QUICK_END_MS = 1000;
const MAX_QUICK_ENDS = 8;

export function recognitionSupported(): boolean {
  return getCtor() !== null;
}

export class ContinuousRecognizer {
  private active: Recognition | null = null;
  private wanted = false;
  private pausedByTab = false;
  private pausedByCaller = false;
  private restartTimer: ReturnType<typeof setTimeout> | null = null;
  private startedAt = 0;
  private quickEnds = 0;
  private onVisibility = () => {
    if (document.hidden) {
      if (this.wanted && !this.pausedByTab) {
        this.pausedByTab = true;
        this.halt();
        this.events.onState('paused');
      }
    } else if (this.pausedByTab) {
      this.pausedByTab = false;
      if (this.wanted && !this.pausedByCaller) this.begin();
    }
  };

  constructor(
    private readonly events: RecognizerEvents,
    private language: string,
  ) {}

  get listening(): boolean {
    return this.wanted && !this.pausedByTab && !this.pausedByCaller;
  }

  setLanguage(code: string): void {
    this.language = code;
    if (this.active) {
      // The language is read when a turn starts: end this one and the restart picks the new one up.
      this.active.stop();
    }
  }

  /** Starts listening. False when the browser has no speech recognition. */
  start(): boolean {
    if (!getCtor()) {
      this.events.onError('unsupported');
      return false;
    }
    this.wanted = true;
    this.pausedByCaller = false;
    this.pausedByTab = document.hidden;
    this.quickEnds = 0;
    document.addEventListener('visibilitychange', this.onVisibility);
    if (this.pausedByTab) this.events.onState('paused');
    else this.begin();
    return true;
  }

  /** The person's stop: nothing restarts afterwards. */
  stop(): void {
    this.wanted = false;
    this.pausedByTab = false;
    this.pausedByCaller = false;
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.halt();
    this.events.onState('stopped');
  }

  /** Listening is set aside (for example while the question-bar microphone is in use). */
  pause(): void {
    if (!this.wanted || this.pausedByCaller) return;
    this.pausedByCaller = true;
    this.halt();
    this.events.onState('paused');
  }

  resume(): void {
    if (!this.wanted || !this.pausedByCaller) return;
    this.pausedByCaller = false;
    if (!this.pausedByTab) this.begin();
  }

  private halt(): void {
    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }
    const current = this.active;
    this.active = null;
    if (current) {
      current.onend = null;
      current.onresult = null;
      current.onerror = null;
      try {
        (current.abort ?? current.stop).call(current);
      } catch {
        /* already ended */
      }
    }
  }

  private begin(): void {
    const Ctor = getCtor();
    if (!Ctor || !this.wanted) return;
    this.halt();
    const recognition = new Ctor();
    recognition.lang = this.language;
    recognition.interimResults = true;
    recognition.continuous = true;
    this.startedAt = Date.now();
    recognition.onresult = (raw) => {
      const event = raw as unknown as ResultEvent;
      for (let i = event.resultIndex ?? 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        const best = result[0];
        if (!best) continue;
        const text = (best.transcript ?? '').trim();
        if (!text) continue;
        if (result.isFinal === false) {
          this.events.onInterim?.(text);
        } else {
          this.quickEnds = 0;
          const confidence = typeof best.confidence === 'number' && best.confidence > 0 ? best.confidence : null;
          this.events.onPhrase(text, confidence);
        }
      }
    };
    recognition.onerror = (event) => {
      const code = event.error ?? '';
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        this.fail('denied');
      } else if (code === 'language-not-supported') {
        this.fail('language');
      } else if (code === 'network') {
        this.fail('network');
      } else if (code === 'audio-capture') {
        this.fail('failed');
      }
      // "no-speech" and "aborted" are normal while waiting: the end handler starts it again.
    };
    recognition.onend = () => {
      if (this.active !== recognition) return;
      this.active = null;
      if (!this.wanted || this.pausedByTab || this.pausedByCaller) return;
      if (Date.now() - this.startedAt < QUICK_END_MS) {
        this.quickEnds += 1;
        if (this.quickEnds >= MAX_QUICK_ENDS) {
          this.fail('failed');
          return;
        }
      }
      this.restartTimer = setTimeout(() => {
        this.restartTimer = null;
        this.begin();
      }, RESTART_AFTER_MS);
    };
    this.active = recognition;
    try {
      recognition.start();
      this.events.onState('listening');
    } catch {
      this.fail('failed');
    }
  }

  private fail(error: RecognizerError): void {
    this.wanted = false;
    this.pausedByTab = false;
    this.pausedByCaller = false;
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.halt();
    this.events.onError(error);
    this.events.onState('stopped');
  }
}
