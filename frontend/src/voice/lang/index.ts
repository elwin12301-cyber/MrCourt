import { ACTION_KEYS, type LanguagePack } from '../types';
import { en } from './en';
import { hi } from './hi';
import { ta } from './ta';

/**
 * Every language that has a command pack. A language is added by writing its pack and listing it here
 * (FR-003b); nothing else in the app changes. All packs are active together so that mixed phrases work
 * whichever voice language is chosen.
 */
export const PACKS: LanguagePack[] = [en, hi, ta];

/** The recognition codes that have a pack: the only ones offered for voice control. */
export const VOICE_CONTROL_LANGUAGES = PACKS.map((p) => ({ code: p.recognition, label: p.label }));

export function packFor(recognition: string | null | undefined): LanguagePack {
  return PACKS.find((p) => p.recognition === recognition) ?? en;
}

/** Problems with a pack (a missing action, an empty list); an empty list means it is complete. */
export function packProblems(pack: LanguagePack): string[] {
  const problems: string[] = [];
  for (const key of ACTION_KEYS) {
    if (!pack.actions[key]?.length) problems.push(`${pack.code}: no phrases for "${key}"`);
  }
  if (!pack.help.go) problems.push(`${pack.code}: no help text`);
  if (!pack.suggestion) problems.push(`${pack.code}: no suggestion`);
  if (!pack.goTemplate.includes('{x}')) problems.push(`${pack.code}: goTemplate needs {x}`);
  return problems;
}
