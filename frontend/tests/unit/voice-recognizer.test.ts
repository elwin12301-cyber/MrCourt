import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ContinuousRecognizer, recognitionSupported, type RecognizerEvents } from '../../src/voice/recognizer';

class Fake {
  static all: Fake[] = [];
  lang = '';
  interimResults = false;
  continuous = false;
  onresult: ((e: unknown) => void) | null = null;
  onerror: ((e: { error?: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = false;
  aborted = false;
  constructor() {
    Fake.all.push(this);
  }
  start() {
    this.started = true;
  }
  stop() {
    this.onend?.();
  }
  abort() {
    this.aborted = true;
  }
  say(text: string, confidence = 0.9, isFinal = true) {
    const result = Object.assign([{ transcript: text, confidence }], { isFinal });
    this.onresult?.({ resultIndex: 0, results: [result] });
  }
  endTurn() {
    this.onend?.();
  }
}

const w = window as unknown as Record<string, unknown>;
const last = () => Fake.all[Fake.all.length - 1];

function setup() {
  const events = {
    onPhrase: vi.fn(),
    onInterim: vi.fn(),
    onState: vi.fn(),
    onError: vi.fn(),
  } satisfies RecognizerEvents;
  return { events, recognizer: new ContinuousRecognizer(events, 'en-IN') };
}

beforeEach(() => {
  vi.useFakeTimers();
  Fake.all = [];
  w.SpeechRecognition = Fake;
});
afterEach(() => {
  vi.useRealTimers();
  delete w.SpeechRecognition;
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});

describe('continuous recognition', () => {
  it('listens continuously in the chosen language and reports finished phrases with their confidence', () => {
    const { events, recognizer } = setup();
    expect(recognizer.start()).toBe(true);
    expect(last()).toMatchObject({ continuous: true, interimResults: true, lang: 'en-IN', started: true });
    last().say('go to dash', 0.5, false);
    expect(events.onInterim).toHaveBeenCalledWith('go to dash');
    expect(events.onPhrase).not.toHaveBeenCalled(); // an unfinished phrase is never acted on
    last().say('go to dashboard', 0.92);
    expect(events.onPhrase).toHaveBeenCalledWith('go to dashboard', 0.92);
    last().say('open cases', 0); // a recogniser that gives no confidence reports 0
    expect(events.onPhrase).toHaveBeenLastCalledWith('open cases', null);
  });

  it('starts again whenever the browser ends a turn, and keeps going until the person stops it', () => {
    const { events, recognizer } = setup();
    recognizer.start();
    for (let turn = 0; turn < 5; turn += 1) {
      vi.advanceTimersByTime(2000); // a normal turn is longer than a second
      const before = Fake.all.length;
      last().endTurn();
      vi.advanceTimersByTime(300);
      expect(Fake.all.length).toBe(before + 1);
      expect(last().started).toBe(true);
    }
    expect(recognizer.listening).toBe(true);
    recognizer.stop();
    expect(events.onState).toHaveBeenLastCalledWith('stopped');
    const count = Fake.all.length;
    vi.advanceTimersByTime(60_000);
    expect(Fake.all.length).toBe(count); // never restarts after a stop
    expect(recognizer.listening).toBe(false);
  });

  it('stops when asked even if the browser reports the end afterwards', () => {
    const { recognizer } = setup();
    recognizer.start();
    const rec = last();
    recognizer.stop();
    rec.endTurn();
    vi.advanceTimersByTime(5000);
    expect(Fake.all.length).toBe(1);
  });

  it('says plainly when the microphone is blocked, the language is not supported or there is no support', () => {
    for (const [code, expected] of [['not-allowed', 'denied'], ['service-not-allowed', 'denied'], ['language-not-supported', 'language'], ['network', 'network'], ['audio-capture', 'failed']] as const) {
      Fake.all = [];
      const { events, recognizer } = setup();
      recognizer.start();
      last().onerror?.({ error: code });
      expect(events.onError).toHaveBeenCalledWith(expected);
      expect(recognizer.listening).toBe(false);
      vi.advanceTimersByTime(5000);
      expect(Fake.all.length).toBe(1);
    }
    delete w.SpeechRecognition;
    const { events, recognizer } = setup();
    expect(recognitionSupported()).toBe(false);
    expect(recognizer.start()).toBe(false);
    expect(events.onError).toHaveBeenCalledWith('unsupported');
  });

  it('treats silence and abort as normal, and gives up on a recogniser that ends at once, again and again', () => {
    const { events, recognizer } = setup();
    recognizer.start();
    last().onerror?.({ error: 'no-speech' });
    expect(events.onError).not.toHaveBeenCalled();
    for (let i = 0; i < 12; i += 1) {
      last().endTurn(); // ends in no time at all
      vi.advanceTimersByTime(200);
    }
    expect(events.onError).toHaveBeenCalledWith('failed');
    expect(recognizer.listening).toBe(false);
  });

  it('can be paused and resumed, and takes the new language at the next turn', () => {
    const { events, recognizer } = setup();
    recognizer.start();
    recognizer.pause();
    expect(events.onState).toHaveBeenLastCalledWith('paused');
    expect(recognizer.listening).toBe(false);
    const count = Fake.all.length;
    vi.advanceTimersByTime(5000);
    expect(Fake.all.length).toBe(count);
    recognizer.resume();
    expect(last().started).toBe(true);
    expect(events.onState).toHaveBeenLastCalledWith('listening');
    recognizer.setLanguage('ta-IN');
    vi.advanceTimersByTime(2000);
    last().endTurn();
    vi.advanceTimersByTime(300);
    expect(last().lang).toBe('ta-IN');
  });

  it('pauses while the tab is hidden and carries on when it is shown', () => {
    const { events, recognizer } = setup();
    recognizer.start();
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
    expect(events.onState).toHaveBeenLastCalledWith('paused');
    expect(recognizer.listening).toBe(false);
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    document.dispatchEvent(new Event('visibilitychange'));
    expect(recognizer.listening).toBe(true);
    expect(last().started).toBe(true);
    recognizer.stop();
  });
});
