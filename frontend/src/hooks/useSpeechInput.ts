import { useCallback, useEffect, useRef, useState } from 'react';

interface RecognitionResultEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}

interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort?(): void;
}

type RecognitionCtor = new () => Recognition;

function getCtor(): RecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const VOICE_UNSUPPORTED = "Voice input isn't available in this browser. Please type your question.";
export const VOICE_FAILED = "Couldn't hear that. Check microphone permission, or type your question.";
export const VOICE_DENIED =
  'The microphone is blocked. Allow it for this site in your browser settings, or type your question.';
export const VOICE_NO_SPEECH = "I didn't hear anything. Try again, or type your question.";
export const VOICE_LANGUAGE = "Your browser can't listen in that language. Choose another, or type your question.";
export const VOICE_LISTENING = 'Listening… speak now. Press the microphone again to stop.';
export const VOICE_STOPPED = 'Stopped listening. Check the text, then send.';

export type VoiceState = 'idle' | 'listening' | 'unsupported' | 'denied' | 'error';

/** Languages offered. Which ones work depends on the browser; the screen says so. */
export const VOICE_LANGUAGES = [
  { code: 'en-IN', label: 'English (India)' },
  { code: 'hi-IN', label: 'Hindi' },
  { code: 'ta-IN', label: 'Tamil' },
  { code: 'te-IN', label: 'Telugu' },
  { code: 'kn-IN', label: 'Kannada' },
  { code: 'ml-IN', label: 'Malayalam' },
  { code: 'mr-IN', label: 'Marathi' },
  { code: 'bn-IN', label: 'Bengali' },
  { code: 'gu-IN', label: 'Gujarati' },
] as const;

const LANGUAGE_KEY = 'mrcourt.voice.language';

function savedLanguage(): string {
  try {
    const value = window.localStorage.getItem(LANGUAGE_KEY);
    return VOICE_LANGUAGES.some((l) => l.code === value) && value ? value : 'en-IN';
  } catch {
    return 'en-IN';
  }
}

/**
 * Browser speech-to-text. Audio never reaches MrCourt servers. The spoken words fill the question
 * box as they arrive so the person can correct them before sending. `usedVoice` stays true once
 * dictation put text in the box, until `clearUsedVoice` (called when the question is sent).
 */
export function useSpeechInput(onText: (text: string) => void) {
  const [state, setState] = useState<VoiceState>('idle');
  const [notice, setNotice] = useState<string | null>(null);
  const [language, setLanguageState] = useState(savedLanguage);
  const [usedVoice, setUsedVoice] = useState(false);
  const active = useRef<Recognition | null>(null);
  const heard = useRef(false);
  const failed = useRef(false);

  useEffect(
    () => () => {
      active.current?.abort?.();
      active.current = null;
    },
    [],
  );

  const setLanguage = useCallback((code: string) => {
    setLanguageState(code);
    try {
      window.localStorage.setItem(LANGUAGE_KEY, code);
    } catch {
      /* storing the choice is only a convenience */
    }
  }, []);

  const toggle = useCallback(() => {
    if (active.current) {
      active.current.stop();
      return;
    }
    const Ctor = getCtor();
    if (!Ctor) {
      setState('unsupported');
      setNotice(VOICE_UNSUPPORTED);
      return;
    }
    heard.current = false;
    failed.current = false;
    const recognition = new Ctor();
    recognition.lang = language;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((r) => r[0]?.transcript ?? '')
        .join(' ')
        .trim();
      if (transcript) {
        heard.current = true;
        setUsedVoice(true);
        onText(transcript);
      }
    };
    recognition.onerror = (event) => {
      failed.current = true;
      const code = event.error ?? '';
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        setState('denied');
        setNotice(VOICE_DENIED);
      } else if (code === 'no-speech') {
        setState('error');
        setNotice(VOICE_NO_SPEECH);
      } else if (code === 'language-not-supported') {
        setState('error');
        setNotice(VOICE_LANGUAGE);
      } else {
        setState('error');
        setNotice(VOICE_FAILED);
      }
    };
    recognition.onend = () => {
      active.current = null;
      if (!failed.current) {
        setState('idle');
        setNotice(heard.current ? VOICE_STOPPED : null);
      } else {
        setState((s) => (s === 'listening' ? 'idle' : s));
      }
    };
    active.current = recognition;
    setState('listening');
    setNotice(VOICE_LISTENING);
    try {
      recognition.start();
    } catch {
      active.current = null;
      setState('error');
      setNotice(VOICE_FAILED);
    }
  }, [onText, language]);

  const clearUsedVoice = useCallback(() => setUsedVoice(false), []);

  return {
    toggle,
    state,
    listening: state === 'listening',
    notice,
    language,
    setLanguage,
    usedVoice,
    clearUsedVoice,
  };
}

export type SpeechInput = ReturnType<typeof useSpeechInput>;
