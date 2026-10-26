/** Shared shapes for voice control (feature 011). See specs/011-voice-control/data-model.md. */

export type VoiceStatus = 'off' | 'starting' | 'listening' | 'paused' | 'confirming' | 'dictating';

export type ControlKind = 'link' | 'button' | 'tab' | 'switch' | 'checkbox' | 'radio' | 'option' | 'input' | 'other';

export interface VoiceControl {
  element: HTMLElement;
  /** What the person sees and a screen reader says. */
  name: string;
  kind: ControlKind;
  visible: boolean;
  enabled: boolean;
  /** Needs a spoken "confirm" before it runs. */
  risky: boolean;
  /** Why it is risky, for the prompt ("delete", "logout", ...); empty when not risky. */
  riskKind: string;
  /** In reading order, set for the controls that are on screen. */
  number?: number;
  /** Place among the repeated items of the main list (0 based), and the list's length. */
  listIndex?: number;
  listSize?: number;
  /** Inside the main navigation (menu, side bar). */
  isNav: boolean;
}

export type ActionKey =
  | 'go'
  | 'click'
  | 'set_on'
  | 'set_off'
  | 'choose'
  | 'scroll_up'
  | 'scroll_down'
  | 'top'
  | 'bottom'
  | 'next_page'
  | 'back'
  | 'forward'
  | 'refresh'
  | 'home'
  | 'close'
  | 'cancel'
  | 'confirm'
  | 'show_numbers'
  | 'hide_numbers'
  | 'dictate'
  | 'stop_dictating'
  | 'clear_field'
  | 'read_answer'
  | 'read_screen'
  | 'stop_reading'
  | 'help'
  | 'stop_listening'
  | 'speak';

export const ACTION_KEYS: ActionKey[] = [
  'go', 'click', 'set_on', 'set_off', 'choose', 'scroll_up', 'scroll_down', 'top', 'bottom', 'next_page', 'back',
  'forward', 'refresh', 'home', 'close', 'cancel', 'confirm', 'show_numbers', 'hide_numbers', 'dictate',
  'stop_dictating', 'clear_field', 'read_answer', 'read_screen', 'stop_reading', 'help', 'stop_listening', 'speak',
];

export type Intent =
  | 'open' // go to a screen, or click a named control
  | 'number'
  | 'position'
  | 'set'
  | 'choose'
  | 'scroll'
  | 'history'
  | 'close'
  | 'numbers'
  | 'dictate'
  | 'read'
  | 'help'
  | 'language'
  | 'stop'
  | 'confirm'
  | 'cancel'
  | 'none';

export interface Command {
  intent: Intent;
  /** Which action phrase was heard (for example "go", "set_on", "scroll_down"). */
  action: ActionKey | null;
  /** What to act on, with the action words and fillers taken out. */
  target: string;
  /** For `number` and `position` (-1 means the last one). */
  index?: number;
  /** For `set`: the state asked for. */
  state?: boolean;
  /** A word such as "tab" or "button" in the phrase: when two controls fit equally, the one of that kind wins. */
  hint?: 'tab' | 'button' | 'link' | 'nav';
  /** The phrase as heard, normalised. Never stored. */
  phrase: string;
  /** Just a menu name, said with no action word ("overview"): acted on only if it is exactly a main-menu item. */
  bare?: boolean;
  /** Words dropped because only one action runs per phrase. */
  ignored: string;
}

export interface LanguagePack {
  code: 'en' | 'hi' | 'ta';
  /** The recognition language, for example `ta-IN`. */
  recognition: string;
  label: string;
  /** Spoken forms for each action: native script and romanised, tokens separated by spaces. */
  actions: Record<ActionKey, string[]>;
  /** Words dropped around a target. */
  fillers: string[];
  /** Generic nouns dropped on both sides of a comparison ("tab", "button", ...). */
  generic: string[];
  /** Words that join two commands in one phrase. */
  connectors: string[];
  /** Ordinal words to a place in a list (-1 means the last one). */
  positions: Record<string, number>;
  /** Number words to digits. */
  numbers: Record<string, number>;
  /** Spoken language names to recognition codes, for "speak Tamil". */
  languages: Record<string, string>;
  /** Whole phrases that are a command by themselves, mapped to the control name they open ("log out" -> "sign out"). */
  shortcuts: Record<string, string>;
  /** A control's English name (normalised) to its other spoken forms. */
  names: Record<string, string[]>;
  /** Words that make a control risky. */
  riskWords: string[];
  /** Lines for the "what can I say" list. */
  help: { go: string; click: string; numbers: string; set: string; scroll: string; dictate: string; read: string; stop: string };
  /** How to say "go to <name>" in this language, for suggestions: {x} stands for the name. */
  goTemplate: string;
  /** A phrase to suggest in the voice panel. */
  suggestion: string;
  /** Wording not yet checked by a native speaker (see specs/011-voice-control/results.md). */
  needsReview: boolean;
}

export interface ActionResult {
  kind: 'done' | 'ask' | 'refused' | 'unknown' | 'info';
  message: string;
  /** Not read aloud (it would only repeat what the person has just heard). */
  quiet?: boolean;
}
