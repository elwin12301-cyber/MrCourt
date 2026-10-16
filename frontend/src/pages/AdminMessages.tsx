import { useState } from 'react';
import { Button, Chip } from '../components/ui';
import {
  KIND_NAME,
  REASON_TEXT,
  useMessageFailures,
  useMessageSummary,
  useResend,
  type FailureRow,
} from '../services/adminMessages';

const when = (iso: string) => new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });

function Failures({
  days,
  before,
  onMore,
  onResent,
}: {
  days: number;
  before: string | null;
  onMore: (cursor: string) => void;
  onResent: (text: string) => void;
}) {
  const { data, isLoading, isError } = useMessageFailures(days, before, true);
  const resend = useResend();
  if (isLoading) {
    return (
      <tr>
        <td colSpan={6} style={{ color: 'var(--muted)' }}>
          Loading…
        </td>
      </tr>
    );
  }
  if (isError || !data) {
    return (
      <tr>
        <td colSpan={6}>
          <span role="alert">We could not load the failures. Please try again.</span>
        </td>
      </tr>
    );
  }
  if (data.items.length === 0 && !before) {
    return (
      <tr>
        <td colSpan={6} style={{ color: 'var(--muted)' }}>
          No WhatsApp failures in this period.
        </td>
      </tr>
    );
  }

  function again(row: FailureRow) {
    resend.mutate(row.id, {
      onSuccess: (result) => onResent(result.status === 'failed' ? 'Sent again, but it failed again.' : 'Sent again.'),
      onError: () => onResent('That message cannot be sent again.'),
    });
  }

  return (
    <>
      {data.items.map((row) => (
        <tr key={row.id}>
          <td>{when(row.time)}</td>
          <td>{row.person}</td>
          <td>{KIND_NAME[row.kind] ?? row.kind}</td>
          <td>{REASON_TEXT[row.reason] ?? 'WhatsApp refused it'}</td>
          <td>{row.fell_back_to_sms ? 'Yes, by text message' : 'No'}</td>
          <td>
            {row.can_resend && (
              <Button small variant="ghost" disabled={resend.isPending} onClick={() => again(row)} aria-label={`Send again to ${row.person}`}>
                Send again
              </Button>
            )}
          </td>
        </tr>
      ))}
      {data.next_before && (
        <tr>
          <td colSpan={6}>
            <Button small variant="ghost" onClick={() => onMore(data.next_before as string)}>
              Show older failures
            </Button>
          </td>
        </tr>
      )}
    </>
  );
}

/** Counts of WhatsApp and text messages, recent failures and whether the service works. Never any message text. */
export default function AdminMessages() {
  const [days, setDays] = useState(7);
  const { data, isError, isLoading } = useMessageSummary(days);
  const [showFailures, setShowFailures] = useState(false);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [note, setNote] = useState<string | null>(null);

  const service = data?.service;
  const health = !service
    ? null
    : !service.configured
      ? ({ tone: 'closed', text: 'Not connected' } as const)
      : service.healthy
        ? ({ tone: 'ok', text: 'Working' } as const)
        : ({ tone: 'soon', text: 'Having trouble' } as const);

  return (
    <section className="view" id="admin-messages" data-view="admin-messages">
      <div>
        <h1>Messages</h1>
        <p className="sub">
          How WhatsApp and text messages are doing. Only counts and reasons are shown here: never the words of a message or a
          phone number.
        </p>
      </div>

      <div className="card" style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <b style={{ fontWeight: 500 }}>WhatsApp service</b>
        {health && <Chip tone={health.tone}>{health.text}</Chip>}
        <span className="fine" style={{ margin: 0 }}>
          {service?.configured
            ? `Provider: ${service.provider}${service.last_ok_at ? `, last message handed over ${when(service.last_ok_at)}` : ''}`
            : 'No WhatsApp service is connected on this server; messages stay on the development page.'}
        </span>
        <span style={{ marginLeft: 'auto' }}>
          <label htmlFor="msg-period" style={{ marginRight: 8 }}>
            Period
          </label>
          <select
            id="msg-period"
            value={days}
            onChange={(e) => {
              setDays(Number(e.target.value));
              setCursors([null]);
            }}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
          </select>
        </span>
      </div>

      {/* The table scrolls sideways on narrow screens, so the region must be reachable by keyboard. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
      <div className="card tablewrap" tabIndex={0} role="region" aria-label="Messages by kind and status">
        <table>
          <caption className="sr-only">Messages by kind and status</caption>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Channel</th>
              <th>Waiting</th>
              <th>Sent</th>
              <th>Delivered</th>
              <th>Read</th>
              <th>Failed</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} style={{ color: 'var(--muted)' }}>
                  Loading…
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={7}>
                  <span role="alert">We could not load the counts. Please try again.</span>
                </td>
              </tr>
            )}
            {data && data.totals.length === 0 && (
              <tr>
                <td colSpan={7} style={{ color: 'var(--muted)' }}>
                  No messages in this period.
                </td>
              </tr>
            )}
            {data?.totals.map((t) => (
              <tr key={`${t.kind}-${t.channel}`}>
                <td>{KIND_NAME[t.kind] ?? t.kind}</td>
                <td>{t.channel === 'whatsapp' ? 'WhatsApp' : 'Text message'}</td>
                <td>{t.queued}</td>
                <td>{t.sent}</td>
                <td>{t.delivered}</td>
                <td>{t.read}</td>
                <td>{t.failed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* The table scrolls sideways on narrow screens, so the region must be reachable by keyboard. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
      <div className="card tablewrap" tabIndex={0} role="region" aria-label="Recent failures">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Recent failures</h2>
          {!showFailures && (
            <Button small variant="ghost" onClick={() => setShowFailures(true)}>
              Show recent failures
            </Button>
          )}
        </div>
        {!showFailures && <p className="fine">Opening the list is recorded in the audit log (how many were shown, not who).</p>}
        {showFailures && (
          <table>
            <caption className="sr-only">WhatsApp messages that failed</caption>
            <thead>
              <tr>
                <th>When</th>
                <th>Person</th>
                <th>Kind</th>
                <th>Why</th>
                <th>Text message instead</th>
                <th>
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {cursors.map((cursor) => (
                <Failures
                  key={cursor ?? 'first'}
                  days={days}
                  before={cursor}
                  onMore={(next) => setCursors((list) => [...list, next])}
                  onResent={setNote}
                />
              ))}
            </tbody>
          </table>
        )}
        <p className="fine" role="status">
          {note ?? ''}
        </p>
      </div>
    </section>
  );
}
