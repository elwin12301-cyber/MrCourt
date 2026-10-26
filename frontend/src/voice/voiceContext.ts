import { createContext, useContext } from 'react';
import type { ActionResult, VoiceControl, VoiceStatus } from './types';

export interface VoiceApi {
  /** Voice control is switched on (it may be paused or confirming). */
  on: boolean;
  status: VoiceStatus;
  supported: boolean;
  /** The agreement to the microphone notice, from the person's settings (or the browser before sign-in). */
  consent: boolean;
  language: string;
  /** Who recognises the speech: the browser, or (only by the person's choice) the cloud speech service. */
  engine: 'browser' | 'cloud';
  /** The app says what it did ("Opened Dashboard") in a spoken reply. */
  replies: boolean;
  setReplies(on: boolean): void;
  /** The last phrase heard, for display only; cleared when voice control is turned off, never stored. */
  lastHeard: string;
  result: ActionResult | null;
  /** Controls that carry number labels right now. */
  numbers: VoiceControl[] | null;
  confirmPrompt: string | null;
  helpOpen: boolean;
  noticeOpen: boolean;
  /** A plain message when voice control could not start or had to stop. */
  error: string | null;
  start(): void;
  stop(): void;
  toggle(): void;
  setLanguage(code: string): boolean;
  openHelp(): void;
  closeHelp(): void;
  /** The notice's "Agree and turn on". */
  agree(): Promise<void>;
  /** The notice's "Not now". */
  decline(): void;
  /** Withdraws the agreement (Settings): stops listening too. */
  withdraw(): Promise<void>;
  /** Buttons on the confirmation, for mouse and keyboard. */
  answerPrompt(confirm: boolean): void;
  /** Types text as if heard, used by tests and the numbers toggle button. */
  showNumbers(show: boolean): void;
}

export const VoiceContext = createContext<VoiceApi | null>(null);

export function useVoice(): VoiceApi {
  const api = useContext(VoiceContext);
  if (!api) throw new Error('useVoice must be used inside the VoiceProvider');
  return api;
}

/** The keyboard shortcut that starts and stops voice control. */
export const VOICE_SHORTCUT = { key: 'v', label: 'Alt+Shift+V' } as const;

export const UNSUPPORTED_TEXT =
  "Voice control isn't available in this browser. It works best in Chrome or Edge. The mouse and keyboard still work.";
export const DENIED_TEXT =
  'The microphone is blocked. Allow it for this site in your browser settings, then turn voice control on again.';
export const NETWORK_TEXT =
  "The browser's speech service could not be reached. Check your connection, then turn voice control on again.";
export const FAILED_TEXT = "Voice control stopped because the microphone didn't work. Turn it on again to retry.";
export const LANGUAGE_TEXT =
  "Your browser can't listen in that language. Choose another language, or use the mouse and keyboard.";
