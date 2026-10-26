import type { Intent, VoiceControl } from './types';

/**
 * Safety rules for voice control (FR-016 to FR-019):
 *  - a risky control never runs on the phrase that named it; the app says what it is about to do and waits;
 *  - only "confirm", heard in a LATER phrase, runs it; cancel, silence (15 s), Escape or any other command drops it;
 *  - the same phrase that started a confirmation can never answer it.
 */

export const CONFIRM_TIMEOUT_MS = 15_000;

const IRREVERSIBLE = /delete|remove|deactivate|private-doc|erase|discard|hatao|mitao|azhi|neekku|nishkriya/;

export interface Pending {
  prompt: string;
  riskKind: string;
  run: () => void;
  phraseId: number;
  expiresAt: number;
}

export type Answer = 'none' | 'confirmed' | 'cancelled' | 'expired' | 'same-phrase';

/** What the app says before a risky control runs. */
export function describeRisk(control: VoiceControl): string {
  const detail = control.element.closest('[data-voice-detail]')?.getAttribute('data-voice-detail');
  const irreversible = IRREVERSIBLE.test(control.riskKind);
  return (
    `About to press “${control.name}”.` +
    (detail ? ` ${detail}.` : '') +
    (irreversible ? ' This cannot be undone.' : '') +
    ' Say confirm or cancel.'
  );
}

/** Holds at most one pending confirmation. */
export class Confirmation {
  pending: Pending | null = null;

  constructor(
    private readonly now: () => number = () => Date.now(),
    readonly timeoutMs: number = CONFIRM_TIMEOUT_MS,
  ) {}

  begin(prompt: string, riskKind: string, run: () => void, phraseId: number): Pending {
    this.pending = { prompt, riskKind, run, phraseId, expiresAt: this.now() + this.timeoutMs };
    return this.pending;
  }

  /** Drops the pending confirmation without running it (Escape, silence, leaving the screen). */
  clear(): void {
    this.pending = null;
  }

  /** True when a confirmation is waiting and its time has not run out. */
  active(): boolean {
    return !!this.pending && this.now() <= this.pending.expiresAt;
  }

  /** Called when its time may have run out; clears it and says whether it had. */
  expireIfDue(): boolean {
    if (this.pending && this.now() > this.pending.expiresAt) {
      this.pending = null;
      return true;
    }
    return false;
  }

  /**
   * A later phrase has been understood as `intent`. Only "confirm" runs the action; anything else cancels it.
   * The phrase that started the confirmation cannot answer it.
   */
  answer(intent: Intent, phraseId: number): Answer {
    const pending = this.pending;
    if (!pending) return 'none';
    if (this.now() > pending.expiresAt) {
      this.pending = null;
      return 'expired';
    }
    if (phraseId === pending.phraseId) return 'same-phrase';
    this.pending = null;
    if (intent === 'confirm') {
      pending.run();
      return 'confirmed';
    }
    return 'cancelled';
  }
}
