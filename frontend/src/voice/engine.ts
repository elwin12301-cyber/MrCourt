import { parseCommand } from './commands';
import { numberControls, openDialog, scanControls } from './controls';
import { clearField, isTextField, refusalFor, typeInto, type TextField } from './dictation';
import { PACKS, VOICE_CONTROL_LANGUAGES, packFor } from './lang';
import { matchTarget } from './matcher';
import { answerText, screenText, speak, stopSpeaking } from './reader';
import { Confirmation, describeRisk } from './safety';
import { normalise, tokens } from './text';
import type { ActionResult, Command, VoiceControl } from './types';

/**
 * What happens to a phrase once it has been heard (FR-004 to FR-021): understand it, find the control, refuse
 * anything unclear, ask before anything risky, then act. The engine knows nothing about React; the provider gives it
 * a small `EngineUi` to show numbers, the help list and confirmations. Nothing a person said is kept: the phrase
 * lives in this call only.
 */

export interface EngineUi {
  /** Draws number labels on these controls; null removes them. */
  setNumbers(controls: VoiceControl[] | null): void;
  openHelp(): void;
  stopListening(): void;
  /** Changes the voice language; false when it is not offered. */
  setLanguage(code: string): boolean;
  /** Shows (or removes, with null) the spoken-and-visible confirmation. */
  confirmPrompt(prompt: string | null): void;
  /** Tells the provider whether dictation is on. */
  dictating(on: boolean): void;
  language(): string;
}

/** A recogniser that is not sure of a phrase is not trusted with an action. */
export const MIN_CONFIDENCE = 0.4;

const done = (message: string): ActionResult => ({ kind: 'done', message });
const ask = (message: string): ActionResult => ({ kind: 'ask', message });
const refused = (message: string): ActionResult => ({ kind: 'refused', message });
const info = (message: string): ActionResult => ({ kind: 'info', message });

function quoted(name: string): string {
  return `“${name.length > 60 ? `${name.slice(0, 57)}…` : name}”`;
}

export class VoiceEngine {
  readonly confirmation: Confirmation;
  private phraseId = 0;
  private numbersShown = false;
  /** True when every control on screen is numbered (not just the matches of an ambiguous phrase). */
  private numbersAll = false;
  private numbered: VoiceControl[] = [];
  private dictation: TextField | null = null;

  constructor(
    private readonly ui: EngineUi,
    now: () => number = () => Date.now(),
  ) {
    this.confirmation = new Confirmation(now);
  }

  get dictating(): boolean {
    return this.dictation !== null;
  }

  get isShowingNumbers(): boolean {
    return this.numbersShown;
  }

  /** Called when the page changes, so numbers stay in step with what is on screen. */
  refreshNumbers(): void {
    if (!this.numbersShown || !this.numbersAll) return;
    this.numbered = numberControls(scanControls().filter((c) => c.enabled));
    this.ui.setNumbers(this.numbered);
  }

  /** Voice control is being turned off or left: drop everything pending. */
  reset(): void {
    this.confirmation.clear();
    this.ui.confirmPrompt(null);
    this.dictation = null;
    this.ui.dictating(false);
    this.hideNumbers();
    stopSpeaking();
  }

  /** A person using the mouse or keyboard answers the confirmation with its buttons. */
  resolveByHand(confirm: boolean): ActionResult | null {
    const pending = this.confirmation.pending;
    if (!pending) return null;
    this.confirmation.clear();
    this.ui.confirmPrompt(null);
    if (!confirm) return info('Cancelled. Nothing was done.');
    pending.run();
    return done('Confirmed. Done.');
  }

  /** The person pressed Escape, or the confirmation timed out. */
  cancelPending(): boolean {
    const had = this.confirmation.pending !== null;
    this.confirmation.clear();
    this.ui.confirmPrompt(null);
    return had;
  }

  /** Handles one finished phrase. */
  handle(raw: string, confidence: number | null = null): ActionResult {
    const phraseId = (this.phraseId += 1);
    const lowConfidence = confidence !== null && confidence < MIN_CONFIDENCE;

    if (this.dictation) return this.whileDictating(raw, lowConfidence);

    if (this.confirmation.expireIfDue()) {
      this.ui.confirmPrompt(null);
      const command = parseCommand(raw, { numbersShown: this.numbersShown });
      if (command.intent === 'confirm') return info('That confirmation had timed out. Nothing was done.');
    }

    const command = parseCommand(raw, { numbersShown: this.numbersShown });
    const tail = command.ignored ? ` I ignored “${command.ignored}”: one command at a time.` : '';

    if (this.confirmation.active()) {
      if (lowConfidence) return ask('I did not catch that clearly. Say confirm or cancel.');
      const answer = this.confirmation.answer(command.intent, phraseId);
      if (answer === 'confirmed') {
        this.ui.confirmPrompt(null);
        return done('Confirmed. Done.');
      }
      if (answer === 'cancelled') {
        this.ui.confirmPrompt(null);
        return info('Cancelled. Nothing was done.');
      }
    }

    if (lowConfidence) {
      return refused(`I did not catch that clearly (heard “${normalise(raw)}”). Please say it again.`);
    }

    const result = this.run(command, phraseId, raw);
    return tail && result.kind !== 'unknown' ? { ...result, message: result.message + tail } : result;
  }

  private run(command: Command, phraseId: number, raw: string): ActionResult {
    switch (command.intent) {
      case 'none':
        return { kind: 'unknown', message: `I did not understand “${normalise(raw)}”. Say “what can I say” for help.` };
      case 'open':
        return this.open(command, phraseId);
      case 'number':
        return this.byNumber(command, phraseId);
      case 'position':
        return this.byPosition(command, phraseId);
      case 'set':
        return this.setState(command, phraseId);
      case 'choose':
        return this.choose(command, phraseId);
      case 'scroll':
        return this.scroll(command);
      case 'history':
        return this.history(command);
      case 'close':
      case 'cancel':
        return this.closeDialog(command);
      case 'numbers':
        return command.action === 'show_numbers' ? this.showNumbers() : this.hideNumbers();
      case 'dictate':
        return this.startDictation(command);
      case 'read':
        return this.read(command);
      case 'help':
        this.ui.openHelp();
        return done('Here is what you can say.');
      case 'language':
        return this.language(command);
      case 'stop':
        this.ui.stopListening();
        return { ...done('Stopped listening.'), quiet: true };
      case 'confirm':
        return info('There is nothing to confirm.');
      default:
        return { kind: 'unknown', message: `I did not understand “${normalise(raw)}”.` };
    }
  }

  // ----- clicking ---------------------------------------------------------------------------------------

  private activate(control: VoiceControl, phraseId: number): ActionResult {
    if (!control.enabled) return refused(`${quoted(control.name)} is not available now.`);
    if (control.risky) {
      const prompt = describeRisk(control);
      this.confirmation.begin(prompt, control.riskKind, () => this.perform(control, true), phraseId);
      this.ui.confirmPrompt(prompt);
      return ask(prompt);
    }
    return this.perform(control);
  }

  /** The one place a control is pressed. Risky controls reach it only through a confirmation. */
  private perform(control: VoiceControl, confirmed = false): ActionResult {
    const el = control.element;
    if (!el.isConnected) return refused(`${quoted(control.name)} is no longer on screen.`);
    el.scrollIntoView?.({ block: 'center' });
    if (control.kind === 'option') {
      const select = el.closest('select');
      if (select) {
        select.value = (el as HTMLOptionElement).value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        return done(`Chose ${quoted(control.name)}.`);
      }
    }
    if (control.kind === 'input') {
      el.focus();
      return done(`Selected ${quoted(control.name)}.`);
    }
    // The person has just confirmed this by voice, with a full description. A browser confirm box that the page
    // raises in answer to this one click would need the mouse, so it is accepted for the length of the click only.
    const original = window.confirm;
    if (confirmed) window.confirm = () => true;
    try {
      el.click();
    } finally {
      window.confirm = original;
    }
    this.afterChange();
    if (control.kind === 'link' || control.kind === 'tab') return done(`Opened ${quoted(control.name)}.`);
    if (control.kind === 'switch' || control.kind === 'checkbox' || control.kind === 'radio') {
      return done(`Changed ${quoted(control.name)}.`);
    }
    return done(`Pressed ${quoted(control.name)}.`);
  }

  private afterChange(): void {
    // The screen may change under the numbers: draw them again once it has settled.
    if (this.numbersShown) setTimeout(() => this.refreshNumbers(), 250);
  }

  private open(command: Command, phraseId: number): ActionResult {
    if (!command.target) return ask('What should I open or press? Say its name, or say “show numbers”.');
    const controls = scanControls();
    if (command.bare) {
      // Said with no action word: only an exact main-menu name counts, so ordinary talk near the microphone is ignored.
      const menu = matchTarget(command.target, controls.filter((c) => c.isNav && c.kind === 'link'), { preferNav: true });
      if (menu.kind === 'one' && menu.score >= 0.99) return this.activate(menu.control, phraseId);
      return { kind: 'unknown', message: `I did not understand “${command.phrase}”. Say “what can I say” for help.` };
    }
    const found = matchTarget(command.target, controls, { preferNav: command.action === 'go', hint: command.hint });
    if (found.kind === 'one') return this.activate(found.control, phraseId);
    if (found.kind === 'several') return this.askWhich(found.controls);
    if (this.isKnownScreen(command.target)) return refused(`${quoted(command.target)} is not available to you.`);
    return { kind: 'unknown', message: `I could not find ${quoted(command.target)} on this screen. ${this.suggest(found.closest, controls)}` };
  }

  /** What to say instead: the closest names, or the menu, in the voice language's own way of saying "go to". */
  private suggest(closest: VoiceControl[], controls: VoiceControl[]): string {
    const pack = packFor(this.ui.language());
    const pool = closest.length ? closest : controls.filter((c) => c.isNav && c.kind === 'link');
    const names = Array.from(new Set(pool.map((c) => c.name))).slice(0, 3);
    if (!names.length) return 'Say “what can I say” to hear the commands for this screen.';
    const say = names.map((n) => `“${pack.goTemplate.replace('{x}', n)}”`).join(' or ');
    return `Try saying ${say}, or “show numbers” and then a number.`;
  }

  /** A name the packs know as a screen, so a person without access is told "not available" rather than "not found". */
  private isKnownScreen(target: string): boolean {
    const wanted = normalise(target);
    return PACKS.some((pack) =>
      Object.entries(pack.names).some(([key, forms]) => key === wanted || forms.some((f) => normalise(f) === wanted)),
    );
  }

  private askWhich(controls: VoiceControl[]): ActionResult {
    // Number only the matches, so the question is short.
    this.numbersShown = true;
    this.numbersAll = false;
    this.numbered = controls.filter((c) => c.enabled);
    this.numbered.forEach((c, i) => {
      c.number = i + 1;
    });
    this.ui.setNumbers(this.numbered);
    return ask(`Which one? ${this.numbered.map((c) => `${c.number}: ${quoted(c.name)}`).join(', ')}. Say a number.`);
  }

  private byNumber(command: Command, phraseId: number): ActionResult {
    if (!this.numbersShown) return refused('Numbers are not shown. Say “show numbers” first.');
    const n = command.index ?? 0;
    const control = this.numbered.find((c) => c.number === n);
    if (!control) return refused(`There is no number ${n} on screen.`);
    if (!control.element.isConnected) {
      return refused(`Number ${n} is no longer on screen.`);
    }
    return this.activate(control, phraseId);
  }

  private byPosition(command: Command, phraseId: number): ActionResult {
    const items = scanControls()
      .filter((c) => c.listIndex !== undefined)
      .sort((a, b) => (a.listIndex ?? 0) - (b.listIndex ?? 0));
    if (!items.length) return refused('There is no list on this screen.');
    const wanted = command.index ?? 0;
    const at = wanted < 0 ? items.length - 1 : wanted;
    const control = items[at];
    if (!control) return refused(`There are only ${items.length} items in the list.`);
    return this.activate(control, phraseId);
  }

  private stateOf(control: VoiceControl): boolean | null {
    const el = control.element;
    if (control.kind === 'checkbox' || control.kind === 'radio') {
      if (el instanceof HTMLInputElement) return el.checked;
    }
    const checked = el.getAttribute('aria-checked');
    if (checked === 'true' || checked === 'false') return checked === 'true';
    const pressed = el.getAttribute('aria-pressed');
    if (pressed === 'true' || pressed === 'false') return pressed === 'true';
    return null;
  }

  private setState(command: Command, phraseId: number): ActionResult {
    if (!command.target) return ask('Which setting? Say its name.');
    const switches = scanControls().filter((c) => ['switch', 'checkbox', 'radio'].includes(c.kind) || this.stateOf(c) !== null);
    const found = matchTarget(command.target, switches);
    if (found.kind === 'several') return this.askWhich(found.controls);
    if (found.kind === 'none') {
      return { kind: 'unknown', message: `I could not find a switch called ${quoted(command.target)} on this screen.` };
    }
    const control = found.control;
    const now = this.stateOf(control);
    const wanted = command.state === true;
    if (now === wanted) return info(`${quoted(control.name)} is already ${wanted ? 'on' : 'off'}.`);
    return this.activate(control, phraseId);
  }

  private choose(command: Command, phraseId: number): ActionResult {
    if (!command.target) return ask('What should I choose? Say its name.');
    const options = scanControls().filter((c) => c.kind === 'option' || c.kind === 'radio');
    const found = matchTarget(command.target, options);
    if (found.kind === 'one') return this.activate(found.control, phraseId);
    if (found.kind === 'several') return this.askWhich(found.controls);
    return { kind: 'unknown', message: `I could not find the choice ${quoted(command.target)}.` };
  }

  // ----- numbers ----------------------------------------------------------------------------------------

  private showNumbers(): ActionResult {
    this.numbersShown = true;
    this.numbersAll = true;
    this.numbered = numberControls(scanControls().filter((c) => c.enabled));
    this.ui.setNumbers(this.numbered);
    return done(`Numbers shown on ${this.numbered.length} controls. Say “click” and a number.`);
  }

  private hideNumbers(): ActionResult {
    if (!this.numbersShown) {
      this.ui.setNumbers(null);
      return info('Numbers were not shown.');
    }
    this.numbersShown = false;
    this.numbersAll = false;
    this.numbered = [];
    this.ui.setNumbers(null);
    return done('Numbers hidden.');
  }

  // ----- moving the page --------------------------------------------------------------------------------

  private scroller(): HTMLElement | null {
    const dialog = openDialog();
    const candidates = [dialog, document.querySelector<HTMLElement>('main'), document.scrollingElement as HTMLElement | null];
    return candidates.find((el) => el && el.scrollHeight > el.clientHeight + 4) ?? null;
  }

  private scroll(command: Command): ActionResult {
    const el = this.scroller();
    const step = Math.round((el?.clientHeight ?? window.innerHeight) * 0.8);
    const by = (top: number) => (el ? el.scrollBy({ top, behavior: 'auto' }) : window.scrollBy({ top, behavior: 'auto' }));
    switch (command.action) {
      case 'scroll_down':
        by(step);
        return done('Scrolled down.');
      case 'scroll_up':
        by(-step);
        return done('Scrolled up.');
      case 'top':
        if (el) el.scrollTo({ top: 0 });
        else window.scrollTo({ top: 0 });
        return done('At the top.');
      case 'bottom':
        if (el) el.scrollTo({ top: el.scrollHeight });
        else window.scrollTo({ top: document.body.scrollHeight });
        return done('At the bottom.');
      case 'next_page': {
        const next = matchTarget('next', scanControls().filter((c) => c.enabled));
        if (next.kind === 'one') return this.perform(next.control);
        by(step);
        return done('Scrolled down.');
      }
      default:
        return refused('I could not scroll.');
    }
  }

  private history(command: Command): ActionResult {
    switch (command.action) {
      case 'back':
        window.history.back();
        return done('Went back.');
      case 'forward':
        window.history.forward();
        return done('Went forward.');
      case 'refresh':
        window.location.reload();
        return done('Refreshing.');
      case 'home': {
        const controls = scanControls();
        for (const name of ['dashboard', 'overview', 'home']) {
          const found = matchTarget(name, controls.filter((c) => c.isNav), { preferNav: true });
          if (found.kind === 'one') return this.perform(found.control);
        }
        return refused('I could not find the dashboard link.');
      }
      default:
        return refused('I could not do that.');
    }
  }

  private closeDialog(command: Command): ActionResult {
    const dialog = openDialog();
    if (!dialog) {
      return info(command.intent === 'cancel' ? 'There is nothing to cancel.' : 'No dialog is open.');
    }
    const inside = scanControls().filter((c) => c.enabled && !c.risky);
    for (const name of ['close', 'cancel', 'not now', 'dismiss']) {
      const found = matchTarget(name, inside);
      if (found.kind === 'one') {
        this.perform(found.control);
        return done('Closed the dialog. Nothing was changed.');
      }
    }
    // No close or cancel button: close it the way Escape would. A native dialog is closed directly (a pretend key
    // press does not close one), which also raises its close event for the page to react to.
    if (dialog instanceof HTMLDialogElement) dialog.close();
    else dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return done('Closed the dialog. Nothing was changed.');
  }

  // ----- dictation --------------------------------------------------------------------------------------

  private startDictation(command: Command): ActionResult {
    if (command.action === 'stop_dictating') return info('Dictation was not on.');
    if (command.action === 'clear_field') {
      const field = document.activeElement;
      if (isTextField(field)) {
        clearField(field);
        return done('Cleared the field.');
      }
      return refused('Click a text field first.');
    }
    let field: Element | null = null;
    if (command.target) {
      const fields = scanControls().filter((c) => c.kind === 'input' && isTextField(c.element));
      const found = matchTarget(command.target, fields);
      if (found.kind === 'several') return this.askWhich(found.controls);
      if (found.kind === 'one') field = found.control.element;
    } else if (isTextField(document.activeElement)) {
      field = document.activeElement;
    }
    if (!field || !isTextField(field)) return refused('Click a text field first, then say “dictate”.');
    const reason = refusalFor(field);
    if (reason) return refused(reason);
    field.focus();
    this.dictation = field;
    this.ui.dictating(true);
    return done('Dictating. Speak now. Say “stop dictating” when you are done.');
  }

  /** While dictating, only "stop dictating" is a command; every other phrase is words for the field. */
  private whileDictating(raw: string, lowConfidence: boolean): ActionResult {
    const command = parseCommand(raw);
    const field = this.dictation as TextField;
    if (command.action === 'stop_dictating') {
      this.dictation = null;
      this.ui.dictating(false);
      return done('Stopped dictating.');
    }
    if (command.action === 'clear_field') {
      clearField(field);
      return done('Cleared the field.');
    }
    if (!field.isConnected) {
      this.dictation = null;
      this.ui.dictating(false);
      return refused('The field has gone, so dictation stopped.');
    }
    if (lowConfidence) return refused('I did not catch that clearly. Please say it again.');
    typeInto(field, raw.trim());
    return info('Typed.');
  }

  // ----- reading ----------------------------------------------------------------------------------------

  private read(command: Command): ActionResult {
    if (command.action === 'stop_reading') {
      stopSpeaking();
      return done('Stopped reading.');
    }
    const text = command.action === 'read_answer' ? answerText() : screenText();
    if (!text) return refused(command.action === 'read_answer' ? 'There is no answer on screen to read.' : 'There is nothing to read.');
    const result = speak(text, this.ui.language());
    if (result.ok) return { ...done(command.action === 'read_answer' ? 'Reading the answer.' : 'Reading the screen.'), quiet: true };
    if (result.reason === 'no-voice') return refused('This device has no voice for that language. The text stays on screen.');
    if (result.reason === 'unsupported') return refused('This browser cannot read aloud. The text stays on screen.');
    return refused('There is nothing to read.');
  }

  // ----- language ---------------------------------------------------------------------------------------

  private language(command: Command): ActionResult {
    const wanted = command.target;
    if (!wanted) return ask('Which language? Say English, Hindi or Tamil.');
    for (const pack of PACKS) {
      for (const [spoken, code] of Object.entries(pack.languages)) {
        if (normalise(spoken) === wanted || tokens(wanted).includes(normalise(spoken))) {
          const offered = VOICE_CONTROL_LANGUAGES.find((l) => l.code === code);
          if (offered && this.ui.setLanguage(code)) return done(`Now listening in ${offered.label}.`);
          return refused('That language is not offered for voice control.');
        }
      }
    }
    return refused(`I do not know the language ${quoted(wanted)}. Say English, Hindi or Tamil.`);
  }
}

