import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VoiceEngine, type EngineUi } from '../../src/voice/engine';

/**
 * Phrase tables (SC-001, SC-003): at least 50 navigation phrases per language, at least 15 of them mixed with
 * English screen names, and at least 20 unclear phrases that must never act. The Hindi and Tamil wording is not yet
 * checked by native speakers (task T056); this table is what shows which phrases the packs miss.
 */

const MENU = `<nav aria-label="Main">
  <a href="/dashboard">Dashboard</a><a href="/cases">Cases</a><a href="/updates">Updates</a>
  <a href="/ask">Ask MrCourt</a><a href="/drafts">Drafts</a><a href="/settings">Settings</a>
</nav><main><div role="tablist"><button role="tab">History</button><button role="tab">Knowledge</button></div></main>`;

const clicked: string[] = [];
const onClick = (e: Event) => {
  const t = (e.target as HTMLElement).closest('a,button') as HTMLElement | null;
  if (!t) return;
  if (t.tagName === 'A') e.preventDefault();
  clicked.push(t.textContent?.trim() ?? '');
};

function engine() {
  const ui: EngineUi = {
    setNumbers: () => undefined,
    openHelp: () => undefined,
    stopListening: () => undefined,
    setLanguage: () => true,
    confirmPrompt: () => undefined,
    dictating: () => undefined,
    language: () => 'en-IN',
  };
  return new VoiceEngine(ui);
}

beforeEach(() => {
  document.body.innerHTML = MENU;
  document.body.addEventListener('click', onClick);
  clicked.length = 0;
  window.scrollBy = vi.fn();
});
afterEach(() => {
  document.body.removeEventListener('click', onClick);
  document.body.innerHTML = '';
});

type Row = [phrase: string, screen: string];

function screens(verbs: string[], names: Record<string, string[]>): Row[] {
  const rows: Row[] = [];
  for (const [screen, spoken] of Object.entries(names)) {
    for (const verb of verbs) {
      for (const name of spoken) rows.push([verb.replace('{x}', name), screen]);
    }
  }
  return rows;
}

const ENGLISH: Row[] = [
  ...screens(['go to {x}', 'open {x}', 'please open {x}', 'take me to {x}', 'show me {x}'], {
    Dashboard: ['dashboard'], Cases: ['cases'], Updates: ['updates'], 'Ask MrCourt': ['ask mrcourt', 'ask mr court'],
    Drafts: ['drafts'], Settings: ['settings'],
  }),
  ['open the history tab', 'History'], ['go to the knowledge tab', 'Knowledge'], ['click history', 'History'],
  ['press knowledge', 'Knowledge'], ['open the settings page', 'Settings'], ['go to the cases page', 'Cases'],
  ['navigate to dashboard', 'Dashboard'], ['switch to drafts', 'Drafts'], ['open home', 'Dashboard'],
  ['click on cases', 'Cases'], ['tap dashboard', 'Dashboard'], ['please click settings', 'Settings'],
  ['open my updates', 'Updates'], ['go to my drafts', 'Drafts'], ['open knowledge', 'Knowledge'],
];

// Tamil and Hindi action words around English screen names, as people actually mix them.
const MIXED: Row[] = [
  ['dashboard ku po', 'Dashboard'], ['chella to dashboard', 'Dashboard'], ['cases open pannu', 'Cases'],
  ['settings kholo', 'Settings'], ['dashboard par jao', 'Dashboard'], ['cases kholo', 'Cases'],
  ['drafts open pannu', 'Drafts'], ['updates kholo', 'Updates'], ['ask mrcourt ku po', 'Ask MrCourt'],
  ['settings ku po', 'Settings'], ['cases par jao', 'Cases'], ['history tab kholo', 'History'],
  ['history click pannu', 'History'], ['knowledge dabao', 'Knowledge'], ['drafts par jao', 'Drafts'],
  ['dashboard open pannu', 'Dashboard'], ['updates ku po', 'Updates'], ['settings open pannu', 'Settings'],
];

const HINDI: Row[] = [
  ...screens(['{x} खोलो', '{x} खोलिए', '{x} पर जाओ', '{x} kholo', '{x} par jao'], {
    Dashboard: ['डैशबोर्ड'], Cases: ['केस'], Updates: ['अपडेट'], Drafts: ['ड्राफ्ट'], Settings: ['सेटिंग'],
  }),
  ['dashboard par jao', 'Dashboard'], ['cases kholo', 'Cases'], ['settings kholo', 'Settings'], ['drafts kholo', 'Drafts'],
  ['updates kholo', 'Updates'], ['history dabao', 'History'], ['knowledge dabao', 'Knowledge'], ['डैशबोर्ड dabao', 'Dashboard'],
  ['history tab kholo', 'History'], ['ask mrcourt kholo', 'Ask MrCourt'], ['ask mrcourt par jao', 'Ask MrCourt'],
  ...MIXED.filter(([p]) => /kholo|jao|dabao/.test(p)),
  ['ड्राफ्ट dabao', 'Drafts'], ['केस dabao', 'Cases'], ['अपडेट dabao', 'Updates'], ['सेटिंग dabao', 'Settings'],
  ['hindi mein dashboard par jao', 'Dashboard'], ['please cases kholo', 'Cases'],
];

const TAMIL: Row[] = [
  ...screens(['{x} ku po', '{x} open pannu', '{x} செல்', '{x} போ', 'chella to {x}'], {
    Dashboard: ['டாஷ்போர்டு', 'dashboard'], Cases: ['வழக்குகள்', 'cases'], Settings: ['அமைப்புகள்', 'settings'],
    Drafts: ['வரைவுகள்', 'drafts'], Updates: ['updates'],
  }),
  ['history click pannu', 'History'], ['knowledge click pannu', 'Knowledge'], ['ask mrcourt ku po', 'Ask MrCourt'],
  ...MIXED.filter(([p]) => /ku po|pannu|chella/.test(p)),
];

const UNCLEAR = [
  'uh', 'the', 'dash', 'go', 'open', 'click', 'save', 'delete document', 'hello there',
  'what is section 138', 'go to', 'open the', 'banana', 'send it', 'turn', 'sdfgh', 'please',
  'open the unicorn page', 'go to the moon', 'click the purple elephant', 'um open uh', 'ku po', 'kholo',
  'dabao', 'pannu', 'ok google open cases please',
];

function run(rows: Row[]) {
  const failures: string[] = [];
  for (const [phrase, screen] of rows) {
    document.body.innerHTML = MENU;
    clicked.length = 0;
    engine().handle(phrase);
    if (clicked.length !== 1 || !clicked[0].toLowerCase().startsWith(screen.toLowerCase().split(' ')[0])) {
      failures.push(`“${phrase}” → ${JSON.stringify(clicked)} (wanted ${screen})`);
    }
  }
  return failures;
}

describe('navigation phrase tables', () => {
  it.each([
    ['English', ENGLISH, 50, 0],
    ['Hindi', HINDI, 50, 15],
    ['Tamil', TAMIL, 50, 15],
  ] as const)('%s: every phrase opens the right screen (and there are enough of them)', (_name, rows, minimum, mixed) => {
    expect(rows.length).toBeGreaterThanOrEqual(minimum);
    if (mixed) expect(rows.filter(([p]) => /[a-z]+ (ku po|par jao|kholo|open pannu|dabao|click pannu)|chella/.test(p)).length).toBeGreaterThanOrEqual(mixed);
    expect(run(rows)).toEqual([]);
  });

  it('the mixed Tamil/Hindi/English phrases all work, whichever language is chosen', () => {
    expect(MIXED.length).toBeGreaterThanOrEqual(15);
    expect(run(MIXED)).toEqual([]);
  });

  it('none of the unclear phrases acts', () => {
    expect(UNCLEAR.length).toBeGreaterThanOrEqual(20);
    const acted: string[] = [];
    for (const phrase of UNCLEAR) {
      document.body.innerHTML = MENU;
      clicked.length = 0;
      const result = engine().handle(phrase);
      if (clicked.length || result.kind === 'done') acted.push(`“${phrase}” → ${JSON.stringify(clicked)} ${result.message}`);
    }
    expect(acted).toEqual([]);
  });
});
