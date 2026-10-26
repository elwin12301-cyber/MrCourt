import { PACKS } from './lang';
import { findRun, normalise, tokens } from './text';
import type { ActionKey, Command, Intent, LanguagePack } from './types';

/**
 * Turns one spoken phrase into at most one command (FR-019). All language packs are active together, so a phrase
 * such as "dashboard ku po" (Tamil action word, English screen name) or "settings kholo" works whichever voice
 * language is chosen. Nothing here guesses: a phrase with no action word is no command, except a bare number while
 * numbers are shown.
 */

interface Entry {
  key: ActionKey;
  tokens: string[];
}

const INTENT_OF: Record<ActionKey, Intent> = {
  go: 'open',
  click: 'open',
  set_on: 'set',
  set_off: 'set',
  choose: 'choose',
  scroll_up: 'scroll',
  scroll_down: 'scroll',
  top: 'scroll',
  bottom: 'scroll',
  next_page: 'scroll',
  back: 'history',
  forward: 'history',
  refresh: 'history',
  home: 'history',
  close: 'close',
  cancel: 'cancel',
  confirm: 'confirm',
  show_numbers: 'numbers',
  hide_numbers: 'numbers',
  dictate: 'dictate',
  stop_dictating: 'dictate',
  clear_field: 'dictate',
  read_answer: 'read',
  read_screen: 'read',
  stop_reading: 'read',
  help: 'help',
  stop_listening: 'stop',
  speak: 'language',
};

function entries(packs: LanguagePack[]): Entry[] {
  const list: Entry[] = [];
  for (const pack of packs) {
    for (const [key, phrases] of Object.entries(pack.actions) as [ActionKey, string[]][]) {
      for (const phrase of phrases) {
        const t = tokens(phrase);
        if (t.length) list.push({ key, tokens: t });
      }
    }
  }
  return list;
}

function union(packs: LanguagePack[], pick: (p: LanguagePack) => string[]): Set<string> {
  return new Set(packs.flatMap((p) => pick(p).flatMap((w) => tokens(w))));
}

function numberOf(words: string[], packs: LanguagePack[]): number | null {
  if (!words.length) return null;
  const table = new Map<string, number>();
  for (const pack of packs) for (const [w, n] of Object.entries(pack.numbers)) table.set(normalise(w), n);
  let total = 0;
  for (const word of words) {
    if (/^\d{1,3}$/.test(word)) total += Number(word);
    else if (table.has(word)) total += table.get(word) as number;
    else return null;
  }
  return total;
}

function positionOf(words: string[], packs: LanguagePack[]): { index: number; rest: string[] } | null {
  const table = new Map<string, number>();
  for (const pack of packs) for (const [w, n] of Object.entries(pack.positions)) table.set(normalise(w), n);
  const at = words.findIndex((w) => table.has(w));
  if (at < 0) return null;
  return { index: table.get(words[at]) as number, rest: words.filter((_, i) => i !== at) };
}

/** Where a second command starts, if the phrase has one: after a joining word that is followed by an action or a risk word. */
function splitAt(words: string[], list: Entry[], packs: LanguagePack[]): number {
  const joiners = packs.flatMap((p) => p.connectors.map((c) => tokens(c))).filter((t) => t.length);
  const risk = packs.flatMap((p) => p.riskWords.map((w) => tokens(w))).filter((t) => t.length);
  for (let i = 1; i < words.length; i += 1) {
    for (const joiner of joiners) {
      if (findRun(words.slice(i, i + joiner.length), joiner) !== 0) continue;
      const after = words.slice(i + joiner.length);
      if (!after.length) continue;
      const startsWithAction = list.some((e) => findRun(after.slice(0, e.tokens.length), e.tokens) === 0);
      const startsWithRisk = risk.some((r) => findRun(after.slice(0, r.length), r) === 0);
      if (startsWithAction || startsWithRisk) return i;
    }
  }
  return -1;
}

const HINTS: [Command['hint'], string[]][] = [
  ['tab', ['tab', 'टैब', 'டேப்']],
  ['button', ['button', 'बटन', 'பட்டன்']],
  ['link', ['link', 'लिंक', 'லிங்க்']],
  ['nav', ['menu', 'मेन्यू', 'மெனு']],
];

/** "the history TAB", "the save BUTTON": the kind of control the person named, if they named one. */
function hintOf(words: string[]): Command['hint'] {
  for (const [kind, list] of HINTS) if (words.some((w) => list.includes(w))) return kind;
  return undefined;
}

const NONE = (phrase: string, ignored = ''): Command => ({ intent: 'none', action: null, target: '', phrase, ignored });

export interface ParseOptions {
  packs?: LanguagePack[];
  /** Number labels are on screen, so a bare number is a command. */
  numbersShown?: boolean;
}

export function parseCommand(raw: string, options: ParseOptions = {}): Command {
  const packs = options.packs ?? PACKS;
  const phrase = normalise(raw);
  const all = tokens(phrase);
  if (!all.length) return NONE(phrase);
  const list = entries(packs);

  // Whole phrases that are a command by themselves ("log out"); a leading "please" is ignored.
  const bare = all[0] === 'please' ? all.slice(1).join(' ') : phrase;
  for (const pack of packs) {
    for (const [said, target] of Object.entries(pack.shortcuts)) {
      if (normalise(said) === bare) return { intent: 'open', action: 'click', target, phrase, ignored: '' };
    }
  }

  const cut = splitAt(all, list, packs);
  const words = cut > 0 ? all.slice(0, cut) : all;
  const ignored = cut > 0 ? all.slice(cut).join(' ') : '';

  // The earliest action phrase wins, and at the same place the longer one ("go back" over "go").
  let best: { key: ActionKey; at: number; length: number } | null = null;
  for (const entry of list) {
    const at = findRun(words, entry.tokens);
    if (at < 0) continue;
    if (!best || at < best.at || (at === best.at && entry.tokens.length > best.length)) {
      best = { key: entry.key, at, length: entry.tokens.length };
    }
  }

  const fillers = union(packs, (p) => p.fillers);
  const generic = union(packs, (p) => p.generic);

  if (!best) {
    if (options.numbersShown) {
      const bare = words.filter((w) => !fillers.has(w));
      const n = numberOf(bare, packs);
      if (n !== null) return { intent: 'number', action: null, target: String(n), index: n, phrase, ignored };
    }
    // A bare menu name ("overview"): only counts if it turns out to be exactly a main-menu item (see the engine).
    const name = words.filter((w) => !fillers.has(w) && !generic.has(w));
    if (name.length >= 1 && name.length <= 3 && cut < 0) {
      return { intent: 'open', action: 'go', target: name.join(' '), phrase, ignored, bare: true };
    }
    return NONE(phrase, ignored);
  }

  const rest = words.filter((_, i) => i < best.at || i >= best.at + best.length);
  const hint = hintOf(rest);
  const target = rest.filter((w) => !fillers.has(w) && !generic.has(w));
  let intent = INTENT_OF[best.key];
  const command: Command = { intent, action: best.key, target: target.join(' '), phrase, ignored, ...(hint ? { hint } : {}) };

  if (intent === 'open') {
    const n = numberOf(target, packs);
    if (n !== null) return { ...command, intent: 'number', index: n, target: String(n) };
    const place = positionOf(target, packs);
    if (place) return { ...command, intent: 'position', index: place.index, target: place.rest.join(' ') };
    return command;
  }
  if (intent === 'set') return { ...command, state: best.key === 'set_on' };
  if ((intent === 'close' || intent === 'cancel' || intent === 'confirm') && target.length) {
    // "close" or "cancel" followed by a name is a click on a control with that name; "confirm" with more words is not a confirmation.
    intent = intent === 'confirm' ? 'none' : 'open';
    return { ...command, intent };
  }
  return command;
}
