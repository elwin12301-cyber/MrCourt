import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useUpdateSettings } from '../services/account';
import { useMe } from '../services/auth';
import { parseCommand } from './commands';
import { accessibleName, isRendered, scanControls } from './controls';
import { VoiceBar } from '../components/VoiceBar';
import { VoiceConfirm } from '../components/VoiceConfirm';
import { VoiceHelp } from '../components/VoiceHelp';
import { VoiceNotice } from '../components/VoiceNotice';
import { VoiceNumbers } from '../components/VoiceNumbers';
import { VoiceEngine } from './engine';
import { VOICE_CONTROL_LANGUAGES } from './lang';
import { CloudPhraseListener, type CloudError } from './cloudPhrases';
import { ContinuousRecognizer, recognitionSupported, type RecognizerError } from './recognizer';
import { speak, speaking, stopSpeaking } from './reader';
import { MIC_EVENT } from './coordination';
import { CONFIRM_TIMEOUT_MS } from './safety';
import type { ActionResult, VoiceControl, VoiceStatus } from './types';
import {
  DENIED_TEXT,
  FAILED_TEXT,
  LANGUAGE_TEXT,
  NETWORK_TEXT,
  UNSUPPORTED_TEXT,
  VOICE_SHORTCUT,
  VoiceContext,
  type VoiceApi,
} from './voiceContext';

const CONSENT_KEY = 'mrcourt.voice.consent';
const LANGUAGE_KEY = 'mrcourt.voice.language'; // shared with the question-bar microphone
const REPLIES_KEY = 'mrcourt.voice.replies'; // "0" turns the spoken replies off

function readLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* only a convenience before sign-in */
  }
}

function offered(code: string | null | undefined): string | null {
  return VOICE_CONTROL_LANGUAGES.some((l) => l.code === code) ? (code as string) : null;
}

const ERROR_TEXT: Record<RecognizerError, string> = {
  denied: DENIED_TEXT,
  unsupported: UNSUPPORTED_TEXT,
  language: LANGUAGE_TEXT,
  network: NETWORK_TEXT,
  failed: FAILED_TEXT,
};

/** What the provider needs from a listener: the browser's recognition or the opt-in cloud phrases. */
interface Listener {
  stop(): void;
  pause(): void;
  resume(): void;
  setLanguage(code: string): void;
}

const CLOUD_TEXT: Record<CloudError, string> = {
  denied: DENIED_TEXT,
  failed: FAILED_TEXT,
  busy: 'The speech service is busy, so voice control is paused for a minute.',
  unavailable: 'The speech service is not available right now. Voice control stopped.',
};

/** Words that may interrupt reading aloud (the rest is ignored while the app speaks, so it never hears itself). */
const ALLOWED_WHILE_SPEAKING = new Set(['stop_reading', 'stop_listening']);

/**
 * For the coverage tests only (development builds): what the control finder sees on the current screen, and any
 * element that looks clickable (pointer cursor) but is not reachable by voice.
 */
if (import.meta.env.DEV && typeof window !== 'undefined') {
  (window as unknown as Record<string, unknown>).__voiceCoverage = () => {
    const controls = scanControls({ ignoreDialog: true });
    const reached = controls.map((c) => c.element);
    const mouseOnly: string[] = [];
    document.querySelectorAll<HTMLElement>('body *').forEach((el) => {
      if (el.closest('[data-voice-ui]') || !isRendered(el)) return;
      if (getComputedStyle(el).cursor !== 'pointer') return;
      if (reached.some((r) => r === el || r.contains(el) || el.contains(r))) return;
      if (el.closest('label') || el.tagName === 'LABEL') return;
      mouseOnly.push(`${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''} “${(el.textContent ?? '').trim().slice(0, 40)}”`);
    });
    const unnamed: string[] = [];
    document.querySelectorAll<HTMLElement>('a[href],button,[role="button"],[role="tab"],[role="switch"],input:not([type="hidden"]),select,textarea,[tabindex="0"]').forEach((el) => {
      if (el.closest('[data-voice-ui]') || !isRendered(el)) return;
      if (el.tagName === 'INPUT' && el.getAttribute('type') === 'password') return;
      if (!accessibleName(el)) unnamed.push(`${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''}`);
    });
    return {
      controls: controls.map((c) => ({
        name: c.name,
        kind: c.kind,
        risky: c.risky,
        riskKind: c.riskKind,
        tagged: !!c.element.closest('[data-voice-risk]'),
        enabled: c.enabled,
        group: ((s) => (s ? accessibleName(s) : ''))(c.element.closest('select')),
        // Rows and list items repeat the same data (two questions with the same words): voice tells them apart by place.
        inRepeat: c.listIndex !== undefined || !!c.element.closest('li,tr,[role="listitem"],[role="row"]'),
      })),
      mouseOnly,
      unnamed,
    };
  };
}

/**
 * Voice control for the whole app (feature 011): holds the microphone session, the engine that understands phrases
 * and the pieces of interface that show what is happening. Off by default. Nothing is kept of what is said.
 */
export function VoiceProvider({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  const update = useUpdateSettings();
  const supported = recognitionSupported();

  const [on, setOn] = useState(false);
  const [recState, setRecState] = useState<'listening' | 'paused' | 'stopped'>('stopped');
  const [lastHeard, setLastHeard] = useState('');
  const [result, setResult] = useState<ActionResult | null>(null);
  const [numbers, setNumbers] = useState<VoiceControl[] | null>(null);
  const [confirmPrompt, setConfirmPrompt] = useState<string | null>(null);
  const [dictating, setDictating] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localConsent, setLocalConsent] = useState(() => readLocal(CONSENT_KEY) === '1');
  const [replies, setRepliesState] = useState(() => readLocal(REPLIES_KEY) !== '0');
  const repliesRef = useRef(replies);
  repliesRef.current = replies;
  const [localLanguage, setLocalLanguage] = useState(() => offered(readLocal(LANGUAGE_KEY)));

  const consent = me ? me.settings.voice_consent : localConsent;
  const language = offered(me?.settings.voice_language) ?? localLanguage ?? 'en-IN';

  const recognizer = useRef<Listener | null>(null);
  const [engineKind, setEngineKind] = useState<'browser' | 'cloud'>('browser');
  const cloudOptIn = useRef(false);
  cloudOptIn.current = !!me?.settings.voice_cloud_opt_in && !!me?.settings.voice_consent;
  const engine = useRef<VoiceEngine | null>(null);
  const languageRef = useRef(language);
  languageRef.current = language;
  const confirmTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopRef = useRef<() => void>(() => undefined);
  const setLanguageRef = useRef<(code: string) => boolean>(() => false);

  // ----- the engine's view of the interface -----------------------------------------------------------

  const getEngine = useCallback((): VoiceEngine => {
    if (!engine.current) {
      engine.current = new VoiceEngine({
        setNumbers: (list) => setNumbers(list ? [...list] : null),
        openHelp: () => setHelpOpen(true),
        stopListening: () => {
          // Stop after the phrase has been answered, so the result line is still shown.
          setTimeout(() => stopRef.current(), 0);
        },
        setLanguage: (code) => setLanguageRef.current(code),
        confirmPrompt: (prompt) => setConfirmPrompt(prompt),
        dictating: (value) => setDictating(value),
        language: () => languageRef.current,
      });
    }
    return engine.current;
  }, []);

  // ----- turning on and off ---------------------------------------------------------------------------

  const speakPrompt = useCallback((text: string) => {
    // The recogniser is set aside while the prompt is spoken, so the words "confirm" and "cancel" in it can
    // never be heard as an answer.
    const rec = recognizer.current;
    rec?.pause();
    const resume = () => setTimeout(() => recognizer.current?.resume(), 400);
    // The replies and prompts are written in English, so they are read with an English voice.
    const spoken = speak(text, 'en-IN', resume);
    if (!spoken.ok) rec?.resume();
  }, []);

  const handlePhrase = useCallback(
    (text: string, confidence: number | null) => {
      if (speaking() && !ALLOWED_WHILE_SPEAKING.has(parseCommand(text).action ?? '')) return;
      const eng = getEngine();
      setLastHeard(text);
      const outcome = eng.handle(text, confidence);
      setResult(outcome);
      if (outcome.kind === 'ask' && eng.confirmation.active()) speakPrompt(outcome.message);
      else if (repliesRef.current && !outcome.quiet && outcome.kind !== 'info') speakPrompt(outcome.message);
    },
    [getEngine, speakPrompt],
  );

  const startCloud = useCallback(() => {
    const listener = new CloudPhraseListener(
      {
        onPhrase: (text) => handlePhrase(text, null),
        onState: (s) => setRecState(s),
        onError: (code) => {
          setError(CLOUD_TEXT[code]);
          if (code !== 'busy') {
            setOn(false);
            getEngine().reset();
          }
        },
      },
      languageRef.current,
    );
    recognizer.current = listener;
    setEngineKind('cloud');
    void listener.start().then((ok) => {
      if (!ok) setOn(false);
    });
  }, [getEngine, handlePhrase]);

  const begin = useCallback(() => {
    const events = {
      onPhrase: handlePhrase,
      onState: (s: 'listening' | 'paused' | 'stopped') => setRecState(s),
      onError: (code: RecognizerError) => {
        if (code === 'language' && cloudOptIn.current) {
          // The browser cannot recognise this language and the person chose the cloud option: short phrases only.
          startCloud();
          return;
        }
        setError(ERROR_TEXT[code]);
        setOn(false);
        getEngine().reset();
      },
    };
    const rec = new ContinuousRecognizer(events, languageRef.current);
    recognizer.current = rec;
    setEngineKind('browser');
    setError(null);
    setOn(true);
    if (!rec.start()) setOn(false);
  }, [getEngine, handlePhrase, startCloud]);

  const stop = useCallback(() => {
    recognizer.current?.stop();
    recognizer.current = null;
    engine.current?.reset();
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    setOn(false);
    setRecState('stopped');
    setLastHeard('');
    setResult(null);
    setNumbers(null);
    setConfirmPrompt(null);
    setDictating(false);
  }, []);
  stopRef.current = stop;

  const start = useCallback(() => {
    if (on) return;
    if (!supported) {
      setError(UNSUPPORTED_TEXT);
      return;
    }
    if (!consent) {
      setNoticeOpen(true);
      return;
    }
    begin();
  }, [begin, consent, on, supported]);

  const toggle = useCallback(() => (on ? stop() : start()), [on, start, stop]);

  const saveConsent = useCallback(
    async (agreed: boolean) => {
      if (me) {
        await update.mutateAsync({ voice_consent: agreed });
      } else {
        writeLocal(CONSENT_KEY, agreed ? '1' : null);
        setLocalConsent(agreed);
      }
    },
    [me, update],
  );

  const agree = useCallback(async () => {
    try {
      await saveConsent(true);
    } catch {
      setError('Could not save your agreement. Please try again.');
      return;
    }
    setNoticeOpen(false);
    begin();
  }, [begin, saveConsent]);

  const decline = useCallback(() => setNoticeOpen(false), []);

  const withdraw = useCallback(async () => {
    stop();
    await saveConsent(false);
  }, [saveConsent, stop]);

  const setLanguage = useCallback(
    (code: string): boolean => {
      const next = offered(code);
      if (!next) return false;
      writeLocal(LANGUAGE_KEY, next);
      setLocalLanguage(next);
      languageRef.current = next;
      recognizer.current?.setLanguage(next);
      if (me) update.mutate({ voice_language: next });
      return true;
    },
    [me, update],
  );
  setLanguageRef.current = setLanguage;

  const answerPrompt = useCallback(
    (confirm: boolean) => {
      stopSpeaking(); // the prompt is answered, so stop reading it (listening then carries on)
      const outcome = engine.current?.resolveByHand(confirm);
      if (outcome) setResult(outcome);
      setConfirmPrompt(null);
    },
    [],
  );

  const setReplies = useCallback((on: boolean) => {
    writeLocal(REPLIES_KEY, on ? '1' : '0');
    setRepliesState(on);
    if (!on) stopSpeaking();
  }, []);

  const showNumbers = useCallback(
    (show: boolean) => {
      const outcome = getEngine().handle(show ? 'show numbers' : 'hide numbers');
      setResult(outcome);
    },
    [getEngine],
  );

  // ----- side effects ---------------------------------------------------------------------------------

  // A choice made before signing in is kept with the person's settings once they sign in.
  const migrated = useRef(false);
  useEffect(() => {
    if (!me || migrated.current) return;
    migrated.current = true;
    if (localConsent && !me.settings.voice_consent) {
      update.mutate({ voice_consent: true });
    }
    writeLocal(CONSENT_KEY, null);
  }, [me, localConsent, update]);

  // Leaving the signed-in session ends voice control.
  const wasSignedIn = useRef(false);
  useEffect(() => {
    if (me) wasSignedIn.current = true;
    else if (wasSignedIn.current) {
      wasSignedIn.current = false;
      migrated.current = false;
      stop();
    }
  }, [me, stop]);

  // A confirmation that is not answered is dropped after 15 seconds.
  useEffect(() => {
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    if (!confirmPrompt) return undefined;
    confirmTimer.current = setTimeout(() => {
      if (engine.current?.cancelPending()) setResult({ kind: 'info', message: 'No answer, so nothing was done.' });
    }, CONFIRM_TIMEOUT_MS);
    return () => {
      if (confirmTimer.current) clearTimeout(confirmTimer.current);
    };
  }, [confirmPrompt]);

  // Keys: Escape drops a confirmation; any key stops reading aloud; the shortcut starts and stops voice control.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey && event.shiftKey && event.key.toLowerCase() === VOICE_SHORTCUT.key) {
        event.preventDefault();
        toggle();
        return;
      }
      if (['Shift', 'Control', 'Alt', 'Meta'].includes(event.key)) return;
      if (speaking()) stopSpeaking();
      if (event.key === 'Escape' && engine.current?.cancelPending()) {
        setResult({ kind: 'info', message: 'Cancelled. Nothing was done.' });
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [toggle]);

  // Number labels follow the page while it changes or scrolls.
  useEffect(() => {
    if (!numbers) return undefined;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const refresh = () => {
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        engine.current?.refreshNumbers();
      }, 200);
    };
    const observer = new MutationObserver(refresh);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'disabled', 'aria-hidden'] });
    return () => {
      observer.disconnect();
      if (timer) clearTimeout(timer);
    };
  }, [numbers]);

  // The question-bar microphone has the microphone while it is in use; voice control waits and then carries on.
  useEffect(() => {
    const onMic = (event: Event) => {
      const state = (event as CustomEvent<string>).detail;
      if (state === 'start') recognizer.current?.pause();
      else recognizer.current?.resume();
    };
    window.addEventListener(MIC_EVENT, onMic);
    return () => window.removeEventListener(MIC_EVENT, onMic);
  }, []);

  useEffect(() => {
    document.body.classList.toggle('vc-on', on);
    return () => document.body.classList.remove('vc-on');
  }, [on]);

  useEffect(
    () => () => {
      recognizer.current?.stop();
      stopSpeaking();
    },
    [],
  );

  // ----- value ----------------------------------------------------------------------------------------

  const status: VoiceStatus = !on
    ? 'off'
    : confirmPrompt
      ? 'confirming'
      : recState === 'paused'
        ? 'paused'
        : dictating
          ? 'dictating'
          : recState === 'listening'
            ? 'listening'
            : 'starting';

  const value = useMemo<VoiceApi>(
    () => ({
      on,
      status,
      supported,
      consent,
      language,
      engine: engineKind,
      replies,
      setReplies,
      lastHeard,
      result,
      numbers,
      confirmPrompt,
      helpOpen,
      noticeOpen,
      error,
      start,
      stop,
      toggle,
      setLanguage,
      openHelp: () => setHelpOpen(true),
      closeHelp: () => setHelpOpen(false),
      agree,
      decline,
      withdraw,
      answerPrompt,
      showNumbers,
    }),
    [on, status, supported, consent, language, engineKind, replies, setReplies, lastHeard, result, numbers, confirmPrompt, helpOpen, noticeOpen, error,
      start, stop, toggle, setLanguage, agree, decline, withdraw, answerPrompt, showNumbers],
  );

  return (
    <VoiceContext.Provider value={value}>
      {children}
      <VoiceBar />
      <VoiceNumbers />
      <VoiceConfirm />
      <VoiceHelp />
      <VoiceNotice />
    </VoiceContext.Provider>
  );
}
