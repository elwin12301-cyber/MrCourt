import { act, renderHook } from '@testing-library/react';
import {
  VOICE_DENIED,
  VOICE_LISTENING,
  VOICE_NO_SPEECH,
  VOICE_UNSUPPORTED,
  useSpeechInput,
} from '../../src/hooks/useSpeechInput';

class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = '';
  interimResults = false;
  continuous = false;
  onresult: ((e: { results: { transcript: string }[][] }) => void) | null = null;
  onerror: ((e: { error?: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = false;
  constructor() {
    FakeRecognition.last = this;
  }
  start() {
    this.started = true;
  }
  stop() {
    this.onend?.();
  }
  say(...parts: string[]) {
    this.onresult?.({ results: parts.map((transcript) => [{ transcript }]) });
  }
}

const w = window as unknown as Record<string, unknown>;

beforeEach(() => {
  FakeRecognition.last = null;
  w.SpeechRecognition = FakeRecognition;
  window.localStorage.clear();
});
afterEach(() => {
  delete w.SpeechRecognition;
  delete w.webkitSpeechRecognition;
});

describe('useSpeechInput', () => {
  it('listens, fills the box with interim words, and remembers that voice was used', () => {
    const seen: string[] = [];
    const { result } = renderHook(() => useSpeechInput((t) => seen.push(t)));
    expect(result.current.state).toBe('idle');

    act(() => result.current.toggle());
    expect(result.current.state).toBe('listening');
    expect(result.current.listening).toBe(true);
    expect(result.current.notice).toBe(VOICE_LISTENING);
    expect(FakeRecognition.last?.started).toBe(true);
    expect(FakeRecognition.last?.interimResults).toBe(true);

    act(() => FakeRecognition.last?.say('what is'));
    act(() => FakeRecognition.last?.say('what is', 'section 138'));
    expect(seen).toEqual(['what is', 'what is section 138']);
    expect(result.current.usedVoice).toBe(true);

    act(() => result.current.toggle()); // second press stops
    expect(result.current.state).toBe('idle');
    expect(result.current.notice).toContain('Stopped listening');

    act(() => result.current.clearUsedVoice());
    expect(result.current.usedVoice).toBe(false);
  });

  it('says so when the browser has no speech recognition', () => {
    delete w.SpeechRecognition;
    const { result } = renderHook(() => useSpeechInput(() => undefined));
    act(() => result.current.toggle());
    expect(result.current.state).toBe('unsupported');
    expect(result.current.notice).toBe(VOICE_UNSUPPORTED);
    expect(result.current.usedVoice).toBe(false);
  });

  it('explains a blocked microphone', () => {
    const { result } = renderHook(() => useSpeechInput(() => undefined));
    act(() => result.current.toggle());
    act(() => FakeRecognition.last?.onerror?.({ error: 'not-allowed' }));
    act(() => FakeRecognition.last?.onend?.());
    expect(result.current.state).toBe('denied');
    expect(result.current.notice).toBe(VOICE_DENIED);
  });

  it('explains when nothing was heard, and can be tried again', () => {
    const { result } = renderHook(() => useSpeechInput(() => undefined));
    act(() => result.current.toggle());
    act(() => FakeRecognition.last?.onerror?.({ error: 'no-speech' }));
    act(() => FakeRecognition.last?.onend?.());
    expect(result.current.state).toBe('error');
    expect(result.current.notice).toBe(VOICE_NO_SPEECH);
    act(() => result.current.toggle());
    expect(result.current.state).toBe('listening');
  });

  it('uses and remembers the chosen language', () => {
    const { result } = renderHook(() => useSpeechInput(() => undefined));
    expect(result.current.language).toBe('en-IN');
    act(() => result.current.setLanguage('ta-IN'));
    act(() => result.current.toggle());
    expect(FakeRecognition.last?.lang).toBe('ta-IN');
    const again = renderHook(() => useSpeechInput(() => undefined));
    expect(again.result.current.language).toBe('ta-IN');
  });

  it('stays marked as voice after the person edits the text', () => {
    const { result } = renderHook(() => useSpeechInput(() => undefined));
    act(() => result.current.toggle());
    act(() => FakeRecognition.last?.say('hello'));
    act(() => result.current.toggle());
    expect(result.current.usedVoice).toBe(true);
  });
});
