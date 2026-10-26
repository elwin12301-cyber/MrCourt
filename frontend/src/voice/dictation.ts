/**
 * Dictation: spoken words go into a text field through the field's normal input events, so the app reacts exactly as
 * if they had been typed (the same privacy rules for questions and drafts apply). Password and one-time-code fields
 * are never dictated (FR-012).
 */

export type TextField = HTMLInputElement | HTMLTextAreaElement;

const TEXT_TYPES = new Set(['text', 'search', 'email', 'tel', 'url', 'number', '']);

export function isTextField(el: Element | null): el is TextField {
  if (!el) return false;
  if (el.tagName === 'TEXTAREA') return true;
  if (el.tagName !== 'INPUT') return false;
  return TEXT_TYPES.has(((el as HTMLInputElement).getAttribute('type') ?? 'text').toLowerCase());
}

/** Why a field must be typed by hand, or null when dictating into it is fine. */
export function refusalFor(el: Element): string | null {
  const type = (el.getAttribute('type') ?? '').toLowerCase();
  const auto = (el.getAttribute('autocomplete') ?? '').toLowerCase();
  if (
    type === 'password' ||
    auto.includes('password') ||
    auto.includes('one-time-code') ||
    el.closest('[data-voice-no-dictate]')
  ) {
    return 'Please type this one yourself.';
  }
  return null;
}

function setValue(field: TextField, value: string): void {
  // React watches the element's own value setter, so use the original one to make the change visible to it.
  const proto = field.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (setter) setter.call(field, value);
  else field.value = value;
  field.dispatchEvent(new Event('input', { bubbles: true }));
}

/** Adds spoken words after what is already in the field. */
export function typeInto(field: TextField, text: string): void {
  const current = field.value;
  const joiner = current && !/\s$/.test(current) ? ' ' : '';
  setValue(field, current + joiner + text);
}

export function clearField(field: TextField): void {
  setValue(field, '');
}
