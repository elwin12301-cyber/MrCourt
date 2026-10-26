import { PACKS } from './lang';
import { distance, normalise, tokens } from './text';
import type { LanguagePack, VoiceControl } from './types';

/**
 * Matches what a person said (a target such as "history" or "save") to the controls on screen.
 * It never guesses: a single clear winner is returned; equals, or nothing close enough, are not.
 */

export type MatchResult =
  | { kind: 'one'; control: VoiceControl; score: number }
  | { kind: 'several'; controls: VoiceControl[] }
  | { kind: 'none'; closest: VoiceControl[] };

const MINIMUM = 0.6;
const TIE = 0.05;

function dropWords(words: string[], packs: LanguagePack[]): string[] {
  const skip = new Set(packs.flatMap((p) => [...p.generic, ...p.fillers].flatMap((w) => tokens(w))));
  return words.filter((w) => !skip.has(w));
}

/** The other spoken forms of a control name, from every pack (for example "டாஷ்போர்டு" for Dashboard). */
export function aliasesFor(name: string, packs: LanguagePack[] = PACKS): string[] {
  const key = normalise(name);
  const found: string[] = [];
  for (const pack of packs) {
    const list = pack.names[key];
    if (list) found.push(...list);
  }
  return found;
}

/** How well a spoken target fits one candidate name, from 0 (not at all) to 1 (exactly). */
export function score(target: string[], candidate: string[]): number {
  if (!target.length || !candidate.length) return 0;
  if (target.length === candidate.length && target.every((w, i) => w === candidate[i])) return 1;
  const candidateSet = new Set(candidate);
  const targetSet = new Set(target);
  if (target.every((w) => candidateSet.has(w))) return Math.max(MINIMUM, 0.85 - 0.03 * (candidate.length - target.length));
  // Words the person said that the name does not have: one stray word is forgiven, two or more is noise ("ok google ...").
  if (candidate.every((w) => targetSet.has(w)) && target.length - candidate.length <= 1) return 0.75;
  const near = (w: string) =>
    candidateSet.has(w) || (w.length >= 5 && candidate.some((c) => c.length >= 5 && distance(w, c, 1) <= 1));
  if (target.every(near)) {
    const exact = target.filter((w) => candidateSet.has(w)).length;
    return 0.6 + 0.1 * (exact / target.length);
  }
  return 0;
}

function bestScore(target: string[], control: VoiceControl, packs: LanguagePack[]): number {
  const names = [control.name, ...aliasesFor(control.name, packs)];
  let best = 0;
  for (const name of names) {
    const candidate = dropWords(tokens(name), packs);
    const wanted = dropWords(target, packs);
    best = Math.max(best, score(wanted.length ? wanted : target, candidate.length ? candidate : tokens(name)));
  }
  return best;
}

export interface MatchOptions {
  packs?: LanguagePack[];
  /** For "go to" and "open": a menu or tab beats a button of the same name when both match. */
  preferNav?: boolean;
  /** The kind of control the person named ("tab", "button", "link", "menu"): it wins a tie. */
  hint?: 'tab' | 'button' | 'link' | 'nav';
}

export function matchTarget(target: string, controls: VoiceControl[], options: MatchOptions = {}): MatchResult {
  const packs = options.packs ?? PACKS;
  const wanted = tokens(target);
  if (!wanted.length) return { kind: 'none', closest: [] };

  const boost = (control: VoiceControl) =>
    options.hint && (options.hint === 'nav' ? control.isNav : control.kind === options.hint) ? 0.1 : 0;
  const rank = (list: VoiceControl[]) =>
    list
      .map((control) => ({ control, score: bestScore(wanted, control, packs) }))
      .map((m) => (m.score > 0 ? { ...m, score: Math.min(1.1, m.score + boost(m.control)) } : m))
      .filter((m) => m.score > 0)
      .sort((a, b) => b.score - a.score);

  // Controls that can act come first; a disabled one is only reported when nothing enabled fits.
  const enabled = rank(controls.filter((c) => c.enabled));
  const ranked = enabled.length && enabled[0].score >= MINIMUM ? enabled : rank(controls);
  if (!ranked.length || ranked[0].score < MINIMUM) {
    return { kind: 'none', closest: rank(controls).slice(0, 3).map((m) => m.control) };
  }
  const top = ranked[0].score;
  let contenders = ranked.filter((m) => top - m.score <= TIE).map((m) => m.control);
  if (contenders.length > 1 && options.preferNav) {
    const nav = contenders.filter((c) => c.isNav);
    if (nav.length === 1) contenders = nav;
  }
  if (contenders.length === 1) return { kind: 'one', control: contenders[0], score: top };
  return { kind: 'several', controls: contenders };
}
