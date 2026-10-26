import { describe, expect, it, vi } from 'vitest';
import { CONFIRM_TIMEOUT_MS, Confirmation, describeRisk } from '../../src/voice/safety';
import type { VoiceControl } from '../../src/voice/types';

function clock() {
  let t = 1_000;
  return { now: () => t, advance: (ms: number) => (t += ms) };
}

describe('confirmation', () => {
  it('runs only when "confirm" is heard in a LATER phrase', () => {
    const c = clock();
    const confirmation = new Confirmation(c.now);
    const run = vi.fn();
    confirmation.begin('About to delete', 'delete', run, 5);
    expect(confirmation.answer('confirm', 5)).toBe('same-phrase'); // the phrase that started it cannot answer it
    expect(run).not.toHaveBeenCalled();
    expect(confirmation.active()).toBe(true);
    expect(confirmation.answer('confirm', 6)).toBe('confirmed');
    expect(run).toHaveBeenCalledOnce();
    expect(confirmation.pending).toBeNull();
  });

  it('is cancelled by "cancel" and by any other command', () => {
    for (const intent of ['cancel', 'open', 'none', 'numbers', 'stop'] as const) {
      const confirmation = new Confirmation(clock().now);
      const run = vi.fn();
      confirmation.begin('About to send', 'send', run, 1);
      expect(confirmation.answer(intent, 2)).toBe('cancelled');
      expect(run).not.toHaveBeenCalled();
      expect(confirmation.pending).toBeNull();
    }
  });

  it('is dropped after 15 seconds of silence, and "confirm" then runs nothing', () => {
    const c = clock();
    const confirmation = new Confirmation(c.now);
    const run = vi.fn();
    confirmation.begin('About to log out', 'logout', run, 1);
    c.advance(CONFIRM_TIMEOUT_MS - 1);
    expect(confirmation.active()).toBe(true);
    c.advance(2);
    expect(confirmation.active()).toBe(false);
    expect(confirmation.answer('confirm', 2)).toBe('expired');
    expect(run).not.toHaveBeenCalled();
    expect(confirmation.expireIfDue()).toBe(false);
  });

  it('says nothing is pending when nothing is', () => {
    expect(new Confirmation(clock().now).answer('confirm', 1)).toBe('none');
  });

  it('holds one confirmation at a time and can be cleared (Escape)', () => {
    const confirmation = new Confirmation(clock().now);
    const first = vi.fn();
    const second = vi.fn();
    confirmation.begin('one', 'delete', first, 1);
    confirmation.begin('two', 'delete', second, 2);
    confirmation.clear();
    expect(confirmation.answer('confirm', 3)).toBe('none');
    expect(first).not.toHaveBeenCalled();
    expect(second).not.toHaveBeenCalled();
  });
});

describe('what is said before a risky action', () => {
  const control = (name: string, riskKind: string, detail?: string): VoiceControl => {
    const wrap = document.createElement('div');
    if (detail) wrap.setAttribute('data-voice-detail', detail);
    const el = document.createElement('button');
    wrap.appendChild(el);
    return { element: el, name, kind: 'button', visible: true, enabled: true, risky: true, riskKind, isNav: false };
  };

  it('says what will happen, and that a removal cannot be undone', () => {
    expect(describeRisk(control('Remove document', 'private-doc', 'It belongs to Rohan Sharma'))).toBe(
      'About to press “Remove document”. It belongs to Rohan Sharma. This cannot be undone. Say confirm or cancel.',
    );
    expect(describeRisk(control('Sign out', 'logout'))).toBe('About to press “Sign out”. Say confirm or cancel.');
    expect(describeRisk(control('Deactivate account', 'deactivate'))).toContain('cannot be undone');
  });
});
