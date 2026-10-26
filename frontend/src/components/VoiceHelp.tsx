import { useEffect, useMemo, useRef } from 'react';
import { scanControls } from '../voice/controls';
import { packFor } from '../voice/lang';
import { VOICE_SHORTCUT, useVoice } from '../voice/voiceContext';

function unique(names: string[], limit: number): string[] {
  return Array.from(new Set(names)).slice(0, limit);
}

/**
 * "What can I say": the commands that work everywhere, then the names found on this screen (menu, tabs and
 * buttons), in the chosen language (FR-015). Reachable by button and keyboard as well as by voice.
 */
export function VoiceHelp() {
  const { helpOpen, closeHelp, language } = useVoice();
  const dialog = useRef<HTMLDialogElement>(null);
  const pack = packFor(language);

  // Looked at when it opens, before the help itself is on the page.
  const groups = useMemo(() => {
    if (!helpOpen) return { menu: [], tabs: [], buttons: [] };
    const controls = scanControls({ ignoreDialog: true });
    return {
      menu: unique(controls.filter((c) => c.isNav && c.kind === 'link').map((c) => c.name), 12),
      tabs: unique(controls.filter((c) => c.kind === 'tab').map((c) => c.name), 12),
      buttons: unique(
        controls.filter((c) => !c.isNav && ['button', 'link', 'switch', 'checkbox'].includes(c.kind) && c.enabled).map((c) => c.name),
        14,
      ),
    };
  }, [helpOpen]);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (helpOpen && !el.open) el.showModal();
    if (!helpOpen && el.open) el.close();
  }, [helpOpen]);

  return (
    <dialog ref={dialog} className="vc-help" aria-labelledby="vc-help-title" onClose={closeHelp}>
      <h2 id="vc-help-title">What can I say?</h2>
      <p className="fine">Language: {pack.label}. Start or stop with {VOICE_SHORTCUT.label}.</p>
      <dl className="vc-help-list">
        <dt>Move around</dt>
        <dd>{pack.help.go}</dd>
        <dt>Click</dt>
        <dd>{pack.help.click}</dd>
        <dt>Numbers and lists</dt>
        <dd>{pack.help.numbers}</dd>
        <dt>Switches</dt>
        <dd>{pack.help.set}</dd>
        <dt>Scroll and dialogs</dt>
        <dd>{pack.help.scroll}</dd>
        <dt>Dictate</dt>
        <dd>{pack.help.dictate}</dd>
        <dt>Read aloud</dt>
        <dd>{pack.help.read}</dd>
        <dt>Help and stop</dt>
        <dd>{pack.help.stop}</dd>
      </dl>
      <h3>On this screen</h3>
      <dl className="vc-help-list">
        {groups.menu.length > 0 && (
          <>
            <dt>Menu</dt>
            <dd>{groups.menu.join(' · ')}</dd>
          </>
        )}
        {groups.tabs.length > 0 && (
          <>
            <dt>Tabs</dt>
            <dd>{groups.tabs.join(' · ')}</dd>
          </>
        )}
        {groups.buttons.length > 0 && (
          <>
            <dt>Buttons</dt>
            <dd>{groups.buttons.join(' · ')}</dd>
          </>
        )}
      </dl>
      <p className="fine">Say “show numbers” to put a number on everything you can click.</p>
      <button type="button" className="btn" onClick={closeHelp}>
        Close
      </button>
    </dialog>
  );
}
