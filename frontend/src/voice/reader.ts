/**
 * Reading aloud with the browser's own speech output (research D7). The text read is the text on the screen as it
 * is, so an answer's source marks, sources and disclaimer are read with it. Nothing leaves the device.
 */

export type ReadResult = { ok: true } | { ok: false; reason: 'unsupported' | 'no-voice' | 'empty' };

function synth(): SpeechSynthesis | null {
  return typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;
}

export function speaking(): boolean {
  return !!synth()?.speaking;
}

export function stopSpeaking(): void {
  synth()?.cancel();
}

/** Starts reading. `language` is a recognition code such as `ta-IN`; a missing voice is reported, not faked. */
export function speak(text: string, language: string, onEnd?: () => void): ReadResult {
  const engine = synth();
  if (!engine || typeof SpeechSynthesisUtterance === 'undefined') return { ok: false, reason: 'unsupported' };
  const clean = text.replace(/\s+/g, ' ').trim();
  if (!clean) return { ok: false, reason: 'empty' };
  const voices = engine.getVoices();
  const prefix = language.split('-')[0].toLowerCase();
  const match = voices.find((v) => v.lang.toLowerCase().startsWith(prefix));
  if (voices.length > 0 && !match) return { ok: false, reason: 'no-voice' };
  engine.cancel();
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.lang = language;
  if (match) utterance.voice = match;
  utterance.onend = () => onEnd?.();
  utterance.onerror = () => onEnd?.();
  engine.speak(utterance);
  return { ok: true };
}

/** The text of the latest marked answer on screen, including its sources and disclaimer. */
export function answerText(root: ParentNode = document): string {
  const marked = Array.from(root.querySelectorAll<HTMLElement>('[data-voice-read]'));
  const last = marked[marked.length - 1];
  return last ? visibleText(last) : '';
}

/** The text of the main part of the screen. */
export function screenText(root: ParentNode = document): string {
  const main = root.querySelector<HTMLElement>('main') ?? (root as HTMLElement);
  return visibleText(main);
}

function visibleText(el: HTMLElement): string {
  const parts: string[] = [];
  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      parts.push(node.textContent ?? '');
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const e = node as Element;
    if (e.getAttribute('aria-hidden') === 'true' || e.hasAttribute('hidden') || e.hasAttribute('data-voice-ui')) return;
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'svg'].includes(e.tagName)) return;
    const style = getComputedStyle(e);
    if (style.display === 'none' || style.visibility === 'hidden') return;
    e.childNodes.forEach(walk);
    parts.push(' ');
  };
  walk(el);
  return parts.join('').replace(/\s+/g, ' ').trim();
}
