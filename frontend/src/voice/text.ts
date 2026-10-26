/** Small text helpers shared by the matcher and the command parser. */

/** Zero-width characters some recognisers put into words. */
const INVISIBLE = new RegExp('[\u200B-\u200D\uFEFF]', 'g');

/**
 * Lower case, Unicode composed, punctuation removed. Letters, combining marks and digits are kept: Hindi and Tamil
 * words lose their vowel signs if marks are dropped.
 */
export function normalise(value: string): string {
  return value
    .normalize('NFC')
    .toLowerCase()
    .replace(INVISIBLE, '')
    .replace(/[^\p{L}\p{M}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function tokens(value: string): string[] {
  const text = normalise(value);
  return text ? text.split(' ') : [];
}

/** Edit distance, with an early stop above `limit`. */
export function distance(a: string, b: string, limit = 2): number {
  if (a === b) return 0;
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  const row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    let previous = row[0];
    row[0] = i;
    let best = row[0];
    for (let j = 1; j <= b.length; j += 1) {
      const current = row[j];
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, previous + (a[i - 1] === b[j - 1] ? 0 : 1));
      previous = current;
      best = Math.min(best, row[j]);
    }
    if (best > limit) return limit + 1;
  }
  return row[b.length];
}

/** Where `needle` occurs as a run of whole tokens inside `hay`, or -1. */
export function findRun(hay: string[], needle: string[]): number {
  if (!needle.length || needle.length > hay.length) return -1;
  for (let i = 0; i + needle.length <= hay.length; i += 1) {
    let all = true;
    for (let j = 0; j < needle.length; j += 1) {
      if (hay[i + j] !== needle[j]) {
        all = false;
        break;
      }
    }
    if (all) return i;
  }
  return -1;
}
