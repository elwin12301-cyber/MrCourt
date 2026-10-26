import { afterEach, describe, expect, it } from 'vitest';
import { numberControls, openDialog, scanControls } from '../../src/voice/controls';

function page(html: string) {
  document.body.innerHTML = html;
}

const names = () => scanControls().map((c) => c.name);

afterEach(() => {
  document.body.innerHTML = '';
});

describe('finding controls', () => {
  it('lists links, buttons, tabs, switches, check boxes and options with their names', () => {
    page(`
      <nav aria-label="Main"><a href="/dashboard">Dashboard</a><a href="/cases">Cases</a></nav>
      <main>
        <div role="tablist"><button role="tab">History</button><button role="tab">Ask</button></div>
        <button>Save</button>
        <button role="switch" aria-checked="false" aria-label="Text message reminders"></button>
        <label><input type="checkbox"> Remember me</label>
        <label for="q">Ask a legal question</label><textarea id="q"></textarea>
        <select aria-label="Court"><option>Madras High Court</option><option>Delhi High Court</option></select>
      </main>`);
    expect(names()).toEqual([
      'Dashboard', 'Cases', 'History', 'Ask', 'Save', 'Text message reminders', 'Remember me', 'Ask a legal question',
      'Court', 'Madras High Court', 'Delhi High Court',
    ]);
    const kinds = Object.fromEntries(scanControls().map((c) => [c.name, c.kind]));
    expect(kinds).toMatchObject({
      Dashboard: 'link', History: 'tab', Save: 'button', 'Text message reminders': 'switch', 'Remember me': 'checkbox',
      'Ask a legal question': 'input', 'Madras High Court': 'option',
    });
  });

  it('leaves out what a person cannot reach or should not dictate into', () => {
    page(`
      <button>Visible</button>
      <button hidden>Hidden attribute</button>
      <button style="display:none">Display none</button>
      <div style="display:none"><button>Inside hidden</button></div>
      <div aria-hidden="true"><button>Aria hidden</button></div>
      <button style="visibility:hidden">Invisible</button>
      <input type="password" aria-label="Password">
      <input type="hidden" name="x">
      <div data-voice-ui><button>Stop</button></div>
      <button></button>`);
    expect(names()).toEqual(['Visible']);
  });

  it('keeps a disabled control in the list, marked as not enabled', () => {
    page('<button disabled>Send</button><button aria-disabled="true">Resend</button><button>Open</button>');
    expect(scanControls().map((c) => [c.name, c.enabled])).toEqual([['Send', false], ['Resend', false], ['Open', true]]);
  });

  it('names a control from aria-labelledby, an icon button from aria-label, an image from alt', () => {
    page(`
      <span id="t">Case number</span><input aria-labelledby="t">
      <button aria-label="Close"><svg aria-hidden="true"></svg></button>
      <button><img alt="Download" src="x.png"></button>`);
    expect(names()).toEqual(['Case number', 'Close', 'Download']);
  });

  it('only counts the controls inside an open dialog', () => {
    page('<button>Behind</button><dialog open><button>Close</button><button>Agree</button></dialog>');
    expect(names()).toEqual(['Close', 'Agree']);
    expect(openDialog()).not.toBeNull();
    expect(scanControls({ ignoreDialog: true }).map((c) => c.name)).toEqual(['Behind', 'Close', 'Agree']);
  });

  it('marks the repeated items of the main list with their place', () => {
    page(`
      <nav><a href="/a">Dashboard</a></nav>
      <main><ul>
        <li><a href="/c/1">Sharma v. Verma</a></li>
        <li><a href="/c/2">Rao v. State</a></li>
        <li><a href="/c/3">Iyer v. Bank</a></li>
      </ul></main>`);
    const list = scanControls().filter((c) => c.listIndex !== undefined);
    expect(list.map((c) => [c.name, c.listIndex, c.listSize])).toEqual([
      ['Sharma v. Verma', 0, 3], ['Rao v. State', 1, 3], ['Iyer v. Bank', 2, 3],
    ]);
  });

  it('treats a control as risky by its tag or by the words in its name', () => {
    page(`
      <button data-voice-risk="logout">Leave</button>
      <button>Delete document</button>
      <button>Sign out</button>
      <button>Save</button>
      <div data-voice-risk="delete"><button>Yes</button></div>`);
    expect(scanControls().map((c) => [c.name, c.risky])).toEqual([
      ['Leave', true], ['Delete document', true], ['Sign out', true], ['Save', false], ['Yes', true],
    ]);
    expect(scanControls()[0].riskKind).toBe('logout');
  });

  it('numbers the enabled controls in order', () => {
    page('<a href="/x">One</a><button>Two</button><button>Three</button>');
    const numbered = numberControls(scanControls());
    expect(numbered.map((c) => [c.number, c.name])).toEqual([[1, 'One'], [2, 'Two'], [3, 'Three']]);
  });
});
