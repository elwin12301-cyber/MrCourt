import { describe, expect, it } from 'vitest';
import { parseCommand } from '../../src/voice/commands';
import { PACKS, packProblems } from '../../src/voice/lang';

const parse = (phrase: string, numbersShown = false) => parseCommand(phrase, { numbersShown });

describe('language packs', () => {
  it.each(PACKS.map((p) => [p.code, p]))('the %s pack is complete', (_code, pack) => {
    expect(packProblems(pack)).toEqual([]);
  });
});

describe('going and clicking', () => {
  it.each([
    ['go to dashboard', 'dashboard'],
    ['open cases', 'cases'],
    ['Open Ask MrCourt', 'ask mrcourt'],
    ['please go to the settings page', 'settings'],
    ['open the history tab', 'history'],
    ['click save', 'save'],
    ['press add case', 'add case'],
  ])('"%s" opens "%s"', (phrase, target) => {
    const c = parse(phrase);
    expect(c.intent).toBe('open');
    expect(c.target).toBe(target);
  });

  it.each([
    ['dashboard ku po', 'dashboard'],
    ['chella to dashboard', 'dashboard'],
    ['settings kholo', 'settings'],
    ['dashboard par jao', 'dashboard'],
    ['cases open pannu', 'cases'],
    ['save click pannu', 'save'],
  ])('the mixed phrase "%s" opens "%s"', (phrase, target) => {
    const c = parse(phrase);
    expect(c.intent).toBe('open');
    expect(c.target).toBe(target);
  });

  it('a bare name is only a candidate: the engine acts on it only if it is exactly a main-menu item', () => {
    for (const name of ['settings', 'overview', 'save']) {
      expect(parse(name)).toMatchObject({ intent: 'open', bare: true, target: name });
    }
    expect(parse('what a lovely day it is today').intent).toBe('none'); // long talk is never a name
  });
});

describe('numbers and positions', () => {
  it('click 7 and "click seven" are the number 7', () => {
    expect(parse('click 7')).toMatchObject({ intent: 'number', index: 7 });
    expect(parse('click seven')).toMatchObject({ intent: 'number', index: 7 });
    expect(parse('click twenty five')).toMatchObject({ intent: 'number', index: 25 });
  });
  it('a bare number is a command only while numbers are shown', () => {
    expect(parse('seven').intent).not.toBe('number'); // without numbers on screen it is only a possible menu name
    expect(parse('seven', true)).toMatchObject({ intent: 'number', index: 7 });
    expect(parse('7', true)).toMatchObject({ intent: 'number', index: 7 });
  });
  it('positions: first, third, last', () => {
    expect(parse('open the first case')).toMatchObject({ intent: 'position', index: 0 });
    expect(parse('click the third document')).toMatchObject({ intent: 'position', index: 2 });
    expect(parse('open the last one')).toMatchObject({ intent: 'position', index: -1 });
  });
});

describe('switches', () => {
  it('turn on and turn off carry the state', () => {
    expect(parse('turn on text message reminders')).toMatchObject({ intent: 'set', state: true, target: 'text message reminders' });
    expect(parse('turn off dark mode')).toMatchObject({ intent: 'set', state: false, target: 'dark mode' });
    expect(parse('reminders on pannu')).toMatchObject({ intent: 'set', state: true, target: 'reminders' });
  });
});

describe('movement and the rest', () => {
  it.each([
    ['scroll down', 'scroll', 'scroll_down'],
    ['scroll up', 'scroll', 'scroll_up'],
    ['go to top', 'scroll', 'top'],
    ['bottom', 'scroll', 'bottom'],
    ['go back', 'history', 'back'],
    ['go forward', 'history', 'forward'],
    ['refresh', 'history', 'refresh'],
    ['go home', 'history', 'home'],
    ['close dialog', 'close', 'close'],
    ['cancel', 'cancel', 'cancel'],
    ['confirm', 'confirm', 'confirm'],
    ['yes confirm', 'confirm', 'confirm'],
    ['show numbers', 'numbers', 'show_numbers'],
    ['hide numbers', 'numbers', 'hide_numbers'],
    ['dictate', 'dictate', 'dictate'],
    ['stop dictating', 'dictate', 'stop_dictating'],
    ['clear field', 'dictate', 'clear_field'],
    ['read the answer', 'read', 'read_answer'],
    ['read the screen', 'read', 'read_screen'],
    ['stop reading', 'read', 'stop_reading'],
    ['what can I say', 'help', 'help'],
    ['stop listening', 'stop', 'stop_listening'],
    ['speak Tamil', 'language', 'speak'],
  ])('"%s" is %s / %s', (phrase, intent, action) => {
    expect(parse(phrase)).toMatchObject({ intent, action });
  });

  it('speak Tamil names the language', () => {
    expect(parse('speak Tamil').target).toBe('tamil');
  });
});

describe('one command per phrase', () => {
  it('only the first command runs and the rest is reported', () => {
    const c = parse('open cases and delete the first');
    expect(c.intent).toBe('open');
    expect(c.target).toBe('cases');
    expect(c.ignored).toBe('and delete the first');
  });
  it('a name that contains "and" is not split', () => {
    const c = parse('click terms and conditions');
    expect(c.target).toBe('terms conditions'); // filler words are dropped on both sides when matching
    expect(c.ignored).toBe('');
  });
  it('"confirm" with other words is not a confirmation', () => {
    expect(parse('confirm delete').intent).toBe('none');
  });
});
