import { useState } from 'react';
import { ApiError } from '../services/api';
import { type Hearing, useCaseMutation } from '../services/cases';
import { setHearingOutcome } from '../services/clientAdmin';
import { Button, Chip } from './ui';

/** Records what happened at a hearing and lets the advocate decide whether clients may see it. */
export function OutcomeForm({ caseId, hearing }: { caseId: string; hearing: Hearing }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(hearing.outcome ?? '');
  const [share, setShare] = useState(hearing.outcome_shared);
  const [error, setError] = useState<string | null>(null);
  const save = useCaseMutation((v: { outcome: string; shared: boolean }) =>
    setHearingOutcome(caseId, hearing.id, v.outcome, v.shared),
  );

  if (!open) {
    return (
      <span style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        {hearing.outcome ? (
          <>
            <span>Outcome: {hearing.outcome}</span>
            <Chip tone={hearing.outcome_shared ? 'active' : 'closed'}>
              {hearing.outcome_shared ? 'Visible to clients' : 'Private'}
            </Chip>
          </>
        ) : null}
        <Button small variant="ghost" onClick={() => setOpen(true)}>
          {hearing.outcome ? 'Edit outcome' : 'Record outcome'}
        </Button>
      </span>
    );
  }

  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        setError(null);
        try {
          await save.mutateAsync({ outcome: text, shared: share });
          setOpen(false);
        } catch (e) {
          setError(e instanceof ApiError ? e.message : 'Could not save the outcome.');
        }
      }}
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <label className="field" htmlFor={`outcome-${hearing.id}`}>
        What happened at this hearing
        <textarea
          id={`outcome-${hearing.id}`}
          rows={3}
          maxLength={2000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ font: 'inherit', padding: 10, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)' }}
        />
      </label>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
        Share this outcome with clients
      </label>
      {error && <p className="fine" role="alert">{error}</p>}
      <span style={{ display: 'flex', gap: 8 }}>
        <Button type="submit" small disabled={save.isPending}>Save outcome</Button>
        <Button small variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </span>
    </form>
  );
}
