import { useState } from 'react';
import {
  KIND_LABEL,
  useLinkWhatsApp,
  useSetWhatsAppKind,
  useUnlinkWhatsApp,
  useWhatsApp,
  whatsappError,
} from '../services/whatsapp';
import { Button, Chip } from './ui';

function day(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Settings → WhatsApp: link the verified number, choose each kind of message (all off at first), unlink. */
export function WhatsAppCard() {
  const { data } = useWhatsApp();
  const link = useLinkWhatsApp();
  const unlink = useUnlinkWhatsApp();
  const setKind = useSetWhatsAppKind();
  const [note, setNote] = useState<string | null>(null);
  if (!data) return null;

  function run(promise: Promise<unknown>, done: string) {
    setNote(null);
    promise.then(
      () => setNote(done),
      (error) => setNote(whatsappError(error)),
    );
  }

  const intro = data.linked
    ? `Choose what MrCourt may send to ${data.number}. Reply STOP to any message to switch everything off.`
    : data.can_link
      ? 'Link your verified number to get messages on WhatsApp. Every kind of message is off until you switch it on.'
      : 'Verify your mobile number above first, then you can link it to WhatsApp.';

  return (
    <section className="wa" aria-labelledby="wa-title">
      <div className="set">
        <b id="wa-title" style={{ fontWeight: 500 }}>
          WhatsApp
        </b>
        {data.linked ? <Chip tone="ok">Linked</Chip> : <Chip tone="closed">Not linked</Chip>}
      </div>
      <p className="fine wa-note">{intro}</p>
      {!data.available && (
        <p className="fine wa-note">
          WhatsApp sending is not connected on this server yet. Your choices are saved and take effect once it is.
        </p>
      )}
      {!data.linked && (
        <div className="wa-actions">
          <Button
            small
            disabled={!data.can_link || link.isPending}
            onClick={() => run(link.mutateAsync(), 'WhatsApp is linked. Nothing is sent until you switch a kind on.')}
          >
            Link WhatsApp
          </Button>
        </div>
      )}
      {data.linked && (
        <>
          <ul className="wa-kinds">
            {data.kinds.map((k) => {
              const labelId = `wa-kind-${k.kind}`;
              return (
                <li key={k.kind} className="set wa-kind">
                  <span className="wa-kind-text">
                    <b id={labelId} style={{ fontWeight: 500, color: 'var(--ink)' }}>
                      {KIND_LABEL[k.kind]}
                    </b>
                    <small className="fine">{k.describes}</small>
                    {k.enabled && k.changed_at && <small className="fine">You agreed on {day(k.changed_at)}.</small>}
                  </span>
                  <button
                    type="button"
                    className="toggle"
                    role="switch"
                    aria-checked={k.enabled}
                    aria-labelledby={labelId}
                    disabled={setKind.isPending}
                    onClick={() =>
                      run(
                        setKind.mutateAsync({ kind: k.kind, enabled: !k.enabled }),
                        `${KIND_LABEL[k.kind]} are now ${k.enabled ? 'off' : 'on'}.`,
                      )
                    }
                  />
                </li>
              );
            })}
          </ul>
          <div className="wa-actions">
            <Button
              small
              variant="ghost"
              disabled={unlink.isPending}
              onClick={() => run(unlink.mutateAsync(), 'WhatsApp is unlinked and everything is switched off.')}
            >
              Unlink WhatsApp
            </Button>
          </div>
        </>
      )}
      <p className="fine wa-note" role="status">
        {note ?? ''}
      </p>
    </section>
  );
}
