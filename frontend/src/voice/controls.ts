import { PACKS } from './lang';
import { findRun, normalise, tokens } from './text';
import type { ControlKind, VoiceControl } from './types';

/**
 * Finds what a person could click, by looking at the page itself: links, buttons, tabs, switches, check boxes,
 * radios, drop-down options, text fields and menu items, each with the name a screen reader gives it. New screens
 * and controls are therefore covered automatically, as long as they have an accessible name (FR-022). A person never
 * "sees" a control they cannot reach with a mouse: hidden, disabled and not-rendered controls are left out.
 *
 * Markup the rest of the app can add (all optional, see specs/011-voice-control/contracts/ui-contract.md):
 *   data-voice-risk="delete|logout|send|..."  the control needs a spoken confirmation
 *   data-voice-click                          an element that acts on click but is not a button or link
 *   data-voice-ui                             part of the voice interface itself: never listed
 */

const CLICKABLE = [
  'a[href]',
  'button',
  'summary',
  'input:not([type="hidden"])',
  'select',
  'option',
  'textarea',
  '[role="button"]',
  '[role="link"]',
  '[role="tab"]',
  '[role="menuitem"]',
  '[role="menuitemcheckbox"]',
  '[role="menuitemradio"]',
  '[role="switch"]',
  '[role="checkbox"]',
  '[role="radio"]',
  '[role="option"]',
  '[data-voice-click]',
  // A custom element that can be focused and acts on click or Enter, such as a table row that opens a case.
  '[tabindex="0"]',
].join(',');

function layoutAvailable(): boolean {
  return typeof navigator !== 'undefined' && !/jsdom/i.test(navigator.userAgent);
}

/** Visible to a person: not hidden, not aria-hidden, not inert, no ancestor with display none. */
export function isRendered(el: Element): boolean {
  if (el.closest('[hidden],[aria-hidden="true"],[inert]')) return false;
  const style = getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse') return false;
  for (let p = el.parentElement; p; p = p.parentElement) {
    if (getComputedStyle(p).display === 'none') return false;
  }
  if (layoutAvailable()) {
    const rects = el.getClientRects();
    if (rects.length === 0) return false;
    const r = rects[0];
    if (r.width === 0 && r.height === 0) return false;
  }
  return true;
}

function isEnabled(el: Element): boolean {
  if ((el as HTMLButtonElement).disabled) return false;
  if (el.getAttribute('aria-disabled') === 'true') return false;
  return !el.closest('fieldset[disabled]');
}

function collapse(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

/** The text a person reads inside an element: skips hidden parts and the number labels, uses an image's alt text. */
function textOf(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? '';
  if (node.nodeType !== Node.ELEMENT_NODE) return '';
  const el = node as Element;
  if (el.getAttribute('aria-hidden') === 'true' || el.hasAttribute('hidden') || el.hasAttribute('data-voice-ui')) return '';
  if (el.tagName === 'IMG') return el.getAttribute('alt') ?? '';
  if (el.tagName === 'SVG' || el.tagName === 'svg') {
    return el.getAttribute('aria-label') ?? el.querySelector('title')?.textContent ?? '';
  }
  return Array.from(el.childNodes).map(textOf).join(' ');
}

function labelText(el: HTMLElement): string {
  const labels = (el as HTMLInputElement).labels;
  if (labels && labels.length) {
    return Array.from(labels)
      .map((l) => collapse(textOf(l)))
      .join(' ');
  }
  const wrapping = el.closest('label');
  return wrapping ? collapse(textOf(wrapping)) : '';
}

/** The accessible name: aria-labelledby, aria-label, a label, the text, then the title or placeholder. */
export function accessibleName(el: HTMLElement): string {
  const by = el.getAttribute('aria-labelledby');
  if (by) {
    const text = by
      .split(/\s+/)
      .map((id) => document.getElementById(id))
      .filter((n): n is HTMLElement => !!n)
      .map((n) => collapse(textOf(n)))
      .join(' ');
    if (text) return text;
  }
  const aria = el.getAttribute('aria-label');
  if (aria && aria.trim()) return collapse(aria);
  const tag = el.tagName;
  if (tag === 'OPTION') return collapse(el.textContent ?? '');
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') {
    const type = (el.getAttribute('type') ?? 'text').toLowerCase();
    if (tag === 'INPUT' && ['button', 'submit', 'reset'].includes(type)) {
      const value = (el as HTMLInputElement).value;
      if (value) return collapse(value);
    }
    const label = labelText(el);
    if (label) return label;
    return collapse(el.getAttribute('placeholder') ?? el.getAttribute('title') ?? '');
  }
  const text = collapse(textOf(el));
  if (text) return text;
  return collapse(el.getAttribute('title') ?? '');
}

function kindOf(el: HTMLElement): ControlKind {
  const role = el.getAttribute('role');
  if (role === 'tab') return 'tab';
  if (role === 'switch') return 'switch';
  if (role === 'checkbox' || role === 'menuitemcheckbox') return 'checkbox';
  if (role === 'radio' || role === 'menuitemradio') return 'radio';
  if (role === 'option') return 'option';
  if (role === 'link') return 'link';
  if (role === 'button' || role === 'menuitem') return 'button';
  switch (el.tagName) {
    case 'A':
      return 'link';
    case 'OPTION':
      return 'option';
    case 'SELECT':
    case 'TEXTAREA':
      return 'input';
    case 'INPUT': {
      const type = (el.getAttribute('type') ?? 'text').toLowerCase();
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (['button', 'submit', 'reset', 'image'].includes(type)) return 'button';
      return 'input';
    }
    case 'BUTTON':
    case 'SUMMARY':
      return 'button';
    default:
      return 'other';
  }
}

/** Does this control need a spoken confirmation? By its tag, or (as a safety net) by risky words in its name. */
export function riskOf(el: HTMLElement, name: string): string {
  const tagged = el.closest('[data-voice-risk]')?.getAttribute('data-voice-risk');
  if (tagged === 'none') return ''; // marked safe on purpose, for example a question sent to the assistant
  if (tagged) return tagged;
  const words = tokens(name);
  for (const pack of PACKS) {
    for (const risky of pack.riskWords) {
      const t = tokens(risky);
      if (t.length && findRun(words, t) >= 0) return normalise(risky);
    }
  }
  return '';
}

/** The open dialog, if there is one: while it is open only its controls count. */
export function openDialog(root: Document | HTMLElement = document): HTMLElement | null {
  const dialogs = Array.from(root.querySelectorAll<HTMLElement>('[role="dialog"],[role="alertdialog"],dialog[open]')).filter(
    (d) => !d.closest('[data-voice-ui]') && isRendered(d),
  );
  return dialogs.length ? dialogs[dialogs.length - 1] : null;
}

export interface ScanOptions {
  root?: Document | HTMLElement;
  /** Also list controls that are rendered but outside the dialog (normally left out). */
  ignoreDialog?: boolean;
}

/** Everything a person could click right now, in page order. */
export function scanControls(options: ScanOptions = {}): VoiceControl[] {
  const root = options.root ?? document;
  const scope = options.ignoreDialog ? null : openDialog(root);
  const base: ParentNode = scope ?? root;
  const found: VoiceControl[] = [];
  const seen = new Set<Element>();
  for (const el of Array.from(base.querySelectorAll<HTMLElement>(CLICKABLE))) {
    if (seen.has(el) || el.closest('[data-voice-ui]')) continue;
    seen.add(el);
    if (el.tagName === 'INPUT' && (el.getAttribute('type') ?? '').toLowerCase() === 'password') continue;
    const kind = kindOf(el);
    if (kind === 'other' && !el.hasAttribute('data-voice-click') && el.getAttribute('tabindex') !== '0') continue;
    const visibilityTarget = el.tagName === 'OPTION' ? (el.closest('select') ?? el) : el;
    if (!isRendered(visibilityTarget)) continue;
    const name = accessibleName(el);
    if (!name) continue;
    found.push({
      element: el,
      name,
      kind: kind === 'other' ? 'button' : kind,
      visible: true,
      enabled: isEnabled(el),
      risky: false,
      riskKind: '',
      isNav: !!el.closest('nav,[role="tablist"],[role="menu"],[role="menubar"]'),
    });
  }
  for (const control of found) {
    control.riskKind = riskOf(control.element, control.name);
    control.risky = control.riskKind !== '';
  }
  assignListPositions(found, root);
  return found;
}

/** The repeated items of the main list on screen (cases, documents, people): its first control gets the place. */
function assignListPositions(controls: VoiceControl[], root: Document | HTMLElement): void {
  const main = (root instanceof Document ? root.querySelector('main') : root.closest('main')) ?? root;
  const items = Array.from((main as ParentNode).querySelectorAll<HTMLElement>('li,[role="listitem"],tr,[role="row"]')).filter(
    (item) => !item.closest('nav,[role="tablist"],[role="menu"],[data-voice-ui]'),
  );
  const groups = new Map<Element, HTMLElement[]>();
  for (const item of items) {
    const parent = item.parentElement;
    if (!parent) continue;
    const list = groups.get(parent) ?? [];
    list.push(item);
    groups.set(parent, list);
  }
  let best: HTMLElement[] = [];
  for (const group of groups.values()) {
    const withControls = group.filter((item) => controls.some((c) => item.contains(c.element) && c.kind !== 'input'));
    if (withControls.length >= 2 && withControls.length > best.length) best = withControls;
  }
  // Cards that are themselves links or buttons: siblings with the same tag and class inside one parent.
  const siblings = new Map<Element, Map<string, HTMLElement[]>>();
  for (const c of controls) {
    const parent = c.element.parentElement;
    if (!parent || c.isNav || c.kind === 'input' || c.element.closest('[role="tablist"],[role="menu"],[data-voice-ui]')) continue;
    if (!['link', 'button', 'other'].includes(c.kind) || !c.element.className) continue;
    const byShape = siblings.get(parent) ?? new Map<string, HTMLElement[]>();
    const key = `${c.element.tagName}|${c.element.className}`;
    byShape.set(key, [...(byShape.get(key) ?? []), c.element]);
    siblings.set(parent, byShape);
  }
  for (const byShape of siblings.values()) {
    for (const group of byShape.values()) {
      if (group.length >= 2 && group.length > best.length) best = group;
    }
  }
  best.forEach((item, index) => {
    const first = controls.find((c) => item.contains(c.element) && c.kind !== 'input');
    if (first) {
      first.listIndex = index;
      first.listSize = best.length;
    }
  });
}

function inViewport(el: HTMLElement): boolean {
  if (!layoutAvailable()) return true;
  const r = el.getBoundingClientRect();
  return r.bottom > 0 && r.right > 0 && r.top < window.innerHeight && r.left < window.innerWidth;
}

/** Numbers for the controls on screen, in reading order. Returns the numbered controls. */
export function numberControls(controls: VoiceControl[]): VoiceControl[] {
  const onScreen = controls.filter((c) => inViewport(c.element));
  if (layoutAvailable()) {
    onScreen.sort((a, b) => {
      const ra = a.element.getBoundingClientRect();
      const rb = b.element.getBoundingClientRect();
      const rowA = Math.round(ra.top / 12);
      const rowB = Math.round(rb.top / 12);
      return rowA - rowB || ra.left - rb.left;
    });
  }
  onScreen.forEach((c, i) => {
    c.number = i + 1;
  });
  return onScreen;
}
