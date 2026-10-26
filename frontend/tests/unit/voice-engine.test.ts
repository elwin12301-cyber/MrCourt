import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VoiceEngine, type EngineUi } from '../../src/voice/engine';
import type { VoiceControl } from '../../src/voice/types';

function setup(now: () => number = () => Date.now()) {
  let numbers: VoiceControl[] | null = null;
  const ui = {
    setNumbers: vi.fn((list: VoiceControl[] | null) => {
      numbers = list;
    }),
    openHelp: vi.fn(),
    stopListening: vi.fn(),
    setLanguage: vi.fn((code: string) => ['en-IN', 'hi-IN', 'ta-IN'].includes(code)),
    confirmPrompt: vi.fn(),
    dictating: vi.fn(),
    language: () => 'en-IN',
  } satisfies EngineUi;
  const engine = new VoiceEngine(ui, now);
  return { engine, ui, numbers: () => numbers };
}

const clicks: string[] = [];
function page(html: string) {
  document.body.innerHTML = html;
  clicks.length = 0;
  document.body.addEventListener('click', onClick);
}
function onClick(e: Event) {
  const t = (e.target as HTMLElement).closest('a,button,input,[role]') as HTMLElement | null;
  if (!t) return;
  if (t.tagName === 'A') e.preventDefault();
  clicks.push(t.getAttribute('aria-label') ?? t.textContent?.trim() ?? t.tagName);
}

const MENU = `<nav aria-label="Main"><a href="/dashboard">Dashboard</a><a href="/cases">Cases</a><a href="/ask">Ask MrCourt</a><a href="/settings">Settings</a></nav>`;

beforeEach(() => {
  window.scrollBy = vi.fn();
  window.scrollTo = vi.fn();
});
afterEach(() => {
  document.body.removeEventListener('click', onClick);
  document.body.innerHTML = '';
  vi.useRealTimers();
});

describe('going to a screen by name (US1)', () => {
  it('opens a menu item in English, in a mixed phrase and in the other languages', () => {
    page(MENU);
    const { engine } = setup();
    for (const phrase of ['go to dashboard', 'open cases', 'dashboard ku po', 'chella to dashboard', 'settings kholo', 'dashboard par jao', 'டாஷ்போர்டு போ', 'सेटिंग खोलो']) {
      clicks.length = 0;
      const result = engine.handle(phrase);
      expect(result.kind, phrase).toBe('done');
      expect(clicks, phrase).toHaveLength(1);
    }
  });

  it('says a screen is not available to a person who has no such menu item', () => {
    page(MENU);
    const result = setup().engine.handle('open audit log');
    expect(result.kind).toBe('refused');
    expect(result.message).toContain('not available to you');
    expect(clicks).toEqual([]);
  });

  it('says it could not find an unknown name and offers nothing to click', () => {
    page(MENU);
    const result = setup().engine.handle('open the unicorn page');
    expect(result.kind).toBe('unknown');
    expect(clicks).toEqual([]);
  });

  it('goes back, forward, refreshes and goes home', () => {
    page(MENU);
    const back = vi.spyOn(window.history, 'back').mockImplementation(() => undefined);
    const forward = vi.spyOn(window.history, 'forward').mockImplementation(() => undefined);
    const { engine } = setup();
    expect(engine.handle('go back').kind).toBe('done');
    expect(engine.handle('go forward').kind).toBe('done');
    expect(back).toHaveBeenCalledOnce();
    expect(forward).toHaveBeenCalledOnce();
    clicks.length = 0;
    expect(engine.handle('go home').kind).toBe('done');
    expect(clicks).toEqual(['Dashboard']);
  });
});

describe('clicking by name, number and position (US2)', () => {
  it('presses a named button, asks which when two share a name, and refuses a disabled one', () => {
    page(`${MENU}<main><button>Save</button><button disabled>Send update</button></main>`);
    const { engine, ui } = setup();
    expect(engine.handle('click save').kind).toBe('done');
    expect(clicks).toEqual(['Save']);
    const disabled = engine.handle('click send update');
    expect(disabled.kind).toBe('refused');
    expect(disabled.message).toContain('not available now');

    page('<main><button>Save</button><button>Save</button></main>');
    const which = engine.handle('click save');
    expect(which.kind).toBe('ask');
    expect(which.message).toContain('Which one?');
    expect(clicks).toEqual([]);
    expect(ui.setNumbers).toHaveBeenLastCalledWith(expect.arrayContaining([expect.objectContaining({ number: 1 }), expect.objectContaining({ number: 2 })]));
    expect(engine.handle('2').kind).toBe('done'); // a bare number answers the question
    expect(clicks).toHaveLength(1);
  });

  it('shows numbers, clicks by number, and hides them', () => {
    page(`${MENU}<main><button>Save</button></main>`);
    const { engine, ui, numbers } = setup();
    expect(engine.handle('click 2').kind).toBe('refused'); // numbers are not shown yet
    expect(engine.handle('show numbers').kind).toBe('done');
    expect(numbers()?.map((c) => [c.number, c.name])).toEqual([[1, 'Dashboard'], [2, 'Cases'], [3, 'Ask MrCourt'], [4, 'Settings'], [5, 'Save']]);
    expect(engine.handle('click 5').kind).toBe('done');
    expect(clicks).toEqual(['Save']);
    expect(engine.handle('click 9').message).toContain('no number 9');
    expect(engine.handle('hide numbers').kind).toBe('done');
    expect(ui.setNumbers).toHaveBeenLastCalledWith(null);
    expect(engine.handle('click 1').kind).toBe('refused');
  });

  it('refuses a number whose control has left the page', () => {
    page(`${MENU}<main><button id="gone">Gone</button></main>`);
    const { engine } = setup();
    engine.handle('show numbers');
    document.getElementById('gone')?.remove();
    expect(engine.handle('click 5').message).toContain('no longer on screen');
  });

  it('opens the first, the third and the last item of a list', () => {
    page(`${MENU}<main><ul><li><a href="/1">Alpha</a></li><li><a href="/2">Beta</a></li><li><a href="/3">Gamma</a></li></ul></main>`);
    const { engine } = setup();
    engine.handle('open the first case');
    engine.handle('open the third one');
    engine.handle('open the last one');
    expect(clicks).toEqual(['Alpha', 'Gamma', 'Gamma']);
    expect(engine.handle('open the fifth case').message).toContain('only 3');
  });

  it('sets a switch, and says so when it is already in that state', () => {
    page('<main><button role="switch" aria-checked="false" aria-label="Text message reminders"></button></main>');
    const { engine } = setup();
    expect(engine.handle('turn off text message reminders').message).toContain('already off');
    expect(clicks).toEqual([]);
    expect(engine.handle('turn on text message reminders').kind).toBe('done');
    expect(clicks).toEqual(['Text message reminders']);
  });

  it('chooses an option in a drop-down', () => {
    page('<main><select aria-label="Court"><option value="m">Madras High Court</option><option value="d">Delhi High Court</option></select></main>');
    const { engine } = setup();
    const changed = vi.fn();
    document.querySelector('select')?.addEventListener('change', changed);
    expect(engine.handle('select Delhi High Court').kind).toBe('done');
    expect(document.querySelector('select')?.value).toBe('d');
    expect(changed).toHaveBeenCalledOnce();
  });
});

describe('staying safe (US4)', () => {
  const RISKY = `${MENU}<main><button data-voice-risk="logout">Sign out</button><button>Delete document</button></main>`;

  it('asks before a risky control runs, and runs it only after "confirm" in a later phrase', () => {
    page(RISKY);
    const { engine, ui } = setup();
    const asked = engine.handle('log out');
    expect(asked.kind).toBe('ask');
    expect(asked.message).toContain('Say confirm or cancel');
    expect(clicks).toEqual([]);
    expect(ui.confirmPrompt).toHaveBeenLastCalledWith(asked.message);
    expect(engine.handle('confirm').kind).toBe('done');
    expect(clicks).toEqual(['Sign out']);
    expect(ui.confirmPrompt).toHaveBeenLastCalledWith(null);
  });

  it('cancels on "cancel", on any other command, on Escape and when time runs out', () => {
    page(RISKY);
    let t = 1000;
    const { engine } = setup(() => t);
    engine.handle('click delete document');
    expect(engine.handle('cancel').message).toContain('Cancelled');
    engine.handle('click delete document');
    expect(engine.handle('go to dashboard').message).toContain('Cancelled');
    expect(clicks).toEqual([]);
    engine.handle('click delete document');
    expect(engine.cancelPending()).toBe(true);
    expect(engine.handle('confirm').message).toContain('nothing to confirm');
    engine.handle('click delete document');
    t += 16_000;
    expect(engine.handle('confirm').message).toContain('timed out');
    expect(clicks).toEqual([]);
  });

  it('does not confirm on a phrase it did not catch clearly, and keeps waiting', () => {
    page(RISKY);
    const { engine } = setup();
    engine.handle('click delete document');
    expect(engine.handle('confirm', 0.2).kind).toBe('ask');
    expect(clicks).toEqual([]);
    expect(engine.handle('confirm', 0.9).kind).toBe('done');
    expect(clicks).toEqual(['Delete document']);
  });

  it('a control marked safe on purpose is not asked about, even with a risky word in its name', () => {
    page('<main><button data-voice-risk="none">Send question</button><button>Send update</button></main>');
    const { engine } = setup();
    expect(engine.handle('click send question').kind).toBe('done');
    expect(engine.handle('click send update').kind).toBe('ask');
  });

  it('can be answered by hand with the buttons', () => {
    page(RISKY);
    const { engine } = setup();
    engine.handle('log out');
    expect(engine.resolveByHand(false)?.message).toContain('Cancelled');
    engine.handle('log out');
    expect(engine.resolveByHand(true)?.kind).toBe('done');
    expect(clicks).toEqual(['Sign out']);
    expect(engine.resolveByHand(true)).toBeNull();
  });

  it('runs only the first command of a phrase, never a risky second one', () => {
    page(RISKY);
    const result = setup().engine.handle('open cases and delete document');
    expect(clicks).toEqual(['Cases']);
    expect(result.message).toContain('I ignored “and delete document”');
  });

  it('never acts on a phrase it did not catch clearly, or did not understand', () => {
    page(RISKY);
    const { engine } = setup();
    expect(engine.handle('open cases', 0.2).kind).toBe('refused');
    expect(engine.handle('mumble mumble').kind).toBe('unknown');
    expect(engine.handle('delete document').kind).toBe('unknown'); // a bare name that is not a menu item does nothing
    expect(clicks).toEqual([]);
  });

  it('a risky control is reached only through the confirmation, also by number and by position', () => {
    page(`${MENU}<main><ul><li><button>Delete document</button></li><li><button>Delete notes</button></li></ul></main>`);
    const { engine } = setup();
    engine.handle('show numbers');
    expect(engine.handle('click 5').kind).toBe('ask');
    engine.handle('cancel');
    expect(engine.handle('open the first one').kind).toBe('ask');
    expect(clicks).toEqual([]);
  });
});

describe('dictation, reading, scrolling and the rest (US3, US5)', () => {
  it('dictates into a field, types commands as words, and stops on request', () => {
    page('<main><label for="q">Ask a legal question</label><textarea id="q"></textarea><button data-voice-risk="none">Send</button></main>');
    const { engine, ui } = setup();
    const field = document.getElementById('q') as HTMLTextAreaElement;
    expect(engine.handle('dictate').kind).toBe('refused'); // nothing is selected
    expect(engine.handle('click ask a legal question').kind).toBe('done');
    expect(engine.handle('dictate').kind).toBe('done');
    expect(ui.dictating).toHaveBeenLastCalledWith(true);
    engine.handle('what is the punishment under section 138');
    engine.handle('go to dashboard');
    expect(field.value).toBe('what is the punishment under section 138 go to dashboard');
    expect(clicks).toEqual([]);
    expect(engine.handle('stop dictating').kind).toBe('done');
    expect(ui.dictating).toHaveBeenLastCalledWith(false);
    expect(engine.handle('click send').kind).toBe('done');
    expect(clicks).toEqual(['Send']);
  });

  it('clears the field by voice', () => {
    page('<main><input aria-label="Search" value="old"></main>');
    const { engine } = setup();
    (document.querySelector('input') as HTMLInputElement).focus();
    expect(engine.handle('clear field').kind).toBe('done');
    expect((document.querySelector('input') as HTMLInputElement).value).toBe('');
  });

  it('refuses to dictate into password, one-time-code and marked fields', () => {
    page(`<main>
      <input aria-label="Phone code" autocomplete="one-time-code">
      <input aria-label="Secret note" data-voice-no-dictate>
      <input aria-label="Your name"></main>`);
    const { engine } = setup();
    for (const name of ['phone code', 'secret note']) {
      const result = engine.handle(`dictate in ${name}`);
      expect(result.kind, name).toBe('refused');
      expect(result.message).toContain('type this one yourself');
    }
    expect(engine.dictating).toBe(false);
    expect(engine.handle('dictate in your name').kind).toBe('done');
    expect(engine.dictating).toBe(true);
  });

  it('reads the answer with its sources and the disclaimer, and stops on request', () => {
    page(`<main><div data-voice-read><p>Section 138 deals with cheque dishonour.</p><p class="src">Source: NI Act s. 138</p><p>Informational only, not legal advice.</p></div></main>`);
    const spoken: string[] = [];
    const cancel = vi.fn();
    vi.stubGlobal('speechSynthesis', { getVoices: () => [], cancel, speak: (u: { text: string }) => spoken.push(u.text), speaking: false });
    vi.stubGlobal('SpeechSynthesisUtterance', class { text: string; lang = ''; voice: unknown = null; onend: (() => void) | null = null; onerror: (() => void) | null = null; constructor(t: string) { this.text = t; } });
    const { engine } = setup();
    expect(engine.handle('read the answer').kind).toBe('done');
    expect(spoken).toEqual(['Section 138 deals with cheque dishonour. Source: NI Act s. 138 Informational only, not legal advice.']);
    cancel.mockClear();
    expect(engine.handle('stop reading').kind).toBe('done');
    expect(cancel).toHaveBeenCalled();
    page('<main><p>No answer here</p></main>');
    expect(engine.handle('read the answer').message).toContain('no answer on screen');
    vi.unstubAllGlobals();
  });

  it('says plainly when there is no voice for the language or no reading at all', () => {
    page('<main><div data-voice-read>Answer</div></main>');
    vi.stubGlobal('speechSynthesis', { getVoices: () => [{ lang: 'fr-FR' }], cancel: vi.fn(), speak: vi.fn(), speaking: false });
    vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(public text: string) {} });
    expect(setup().engine.handle('read the answer').message).toContain('no voice for that language');
    vi.unstubAllGlobals();
  });

  it('scrolls, goes to the top and the bottom', () => {
    page('<main><p>Long page</p></main>');
    const { engine } = setup();
    expect(engine.handle('scroll down').kind).toBe('done');
    expect(window.scrollBy).toHaveBeenCalledWith(expect.objectContaining({ top: expect.any(Number) }));
    expect(engine.handle('scroll up').kind).toBe('done');
    expect(engine.handle('go to top').kind).toBe('done');
    expect(window.scrollTo).toHaveBeenCalled();
    expect(engine.handle('bottom').kind).toBe('done');
  });

  it('closes an open dialog without changing anything', () => {
    page('<button>Behind</button><dialog open aria-label="Help"><button>Save</button><button>Close</button></dialog>');
    const { engine } = setup();
    expect(engine.handle('close dialog').kind).toBe('done');
    expect(clicks).toEqual(['Close']);
    page('<main><button>Only</button></main>');
    expect(engine.handle('close dialog').message).toContain('No dialog is open');
    expect(engine.handle('cancel').message).toContain('nothing to cancel');
  });

  it('answers help, language and stop through the interface', () => {
    page(MENU);
    const { engine, ui } = setup();
    expect(engine.handle('what can I say').kind).toBe('done');
    expect(ui.openHelp).toHaveBeenCalledOnce();
    expect(engine.handle('speak Tamil').message).toContain('Tamil');
    expect(ui.setLanguage).toHaveBeenLastCalledWith('ta-IN');
    expect(engine.handle('speak Klingon').kind).toBe('refused');
    expect(engine.handle('stop listening').kind).toBe('done');
    expect(ui.stopListening).toHaveBeenCalledOnce();
  });

  it('forgets everything when voice control is turned off', () => {
    page(`${MENU}<main><button data-voice-risk="delete">Remove</button></main>`);
    const { engine, ui } = setup();
    engine.handle('show numbers');
    engine.handle('click remove');
    engine.reset();
    expect(engine.confirmation.pending).toBeNull();
    expect(engine.isShowingNumbers).toBe(false);
    expect(ui.setNumbers).toHaveBeenLastCalledWith(null);
    expect(engine.handle('confirm').kind).toBe('info');
    expect(clicks).toEqual([]);
  });
});

describe('a menu name said on its own', () => {
  it('opens a main-menu item by its exact name, including its other spoken forms', () => {
    page(`<nav aria-label="Main"><a href="/dashboard">Overview</a><a href="/admin/cases">Cases</a></nav><main><button>Save</button></main>`);
    const { engine } = setup();
    expect(engine.handle('overview').kind).toBe('done');
    expect(engine.handle('cases').kind).toBe('done');
    expect(engine.handle('dashboard').kind).toBe('done'); // another name for Overview
    expect(clicks).toEqual(['Overview', 'Cases', 'Overview']);
  });

  it('does nothing for a name that is not in the menu, or only nearly one', () => {
    page(`<nav aria-label="Main"><a href="/dashboard">Overview</a></nav><main><button>Save</button></main>`);
    const { engine } = setup();
    expect(engine.handle('save').kind).toBe('unknown');
    expect(engine.handle('overvue').kind).toBe('unknown');
    expect(engine.handle('over view please now').kind).toBe('unknown');
    expect(clicks).toEqual([]);
  });
});

describe('helping when a name is wrong', () => {
  it('"go to overview" opens the dashboard for an advocate, and "go to dashboard" opens Overview for an administrator', () => {
    page(`<nav aria-label="Main"><a href="/dashboard">Dashboard</a><a href="/cases">Cases</a></nav>`);
    expect(setup().engine.handle('go to overview').kind).toBe('done');
    expect(clicks).toEqual(['Dashboard']);
    page(`<nav aria-label="Main"><a href="/dashboard">Overview</a><a href="/admin/cases">Cases</a></nav>`);
    expect(setup().engine.handle('go to dashboard').kind).toBe('done');
    expect(clicks).toEqual(['Overview']);
  });

  it('a wrong name gets the closest names, said the way the voice language says "go to"', () => {
    page(MENU);
    const english = setup().engine.handle('go to the cases list xyz');
    expect(english.kind).toBe('unknown');
    expect(english.message).toContain('Try saying “go to');
    const none = setup().engine.handle('open the unicorn page');
    expect(none.message).toContain('Try saying “go to Dashboard” or “go to Cases”');
    expect(none.message).toContain('show numbers');
  });

  it('suggests in the chosen language', () => {
    page(MENU);
    const ui = { ...setup().ui, language: () => 'ta-IN' } satisfies EngineUi;
    expect(new VoiceEngine(ui).handle('open the unicorn page').message).toContain('“Dashboard ku po”');
    const hindi = { ...setup().ui, language: () => 'hi-IN' } satisfies EngineUi;
    expect(new VoiceEngine(hindi).handle('open the unicorn page').message).toContain('“Dashboard par jao”');
  });
});
