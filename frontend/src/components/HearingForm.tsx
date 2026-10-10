import { type FormEvent, useState } from 'react';
import { ApiError } from '../services/api';
import { addHearing, useCaseMutation } from '../services/cases';
import { Button } from './ui';

/** Adds a hearing to a case. Rescheduling is done by adding the new date and editing via the API. */
export function HearingForm({ caseId }: { caseId: string }) {
  const [when, setWhen] = useState('');
  const [purpose, setPurpose] = useState('');
  const [error, setError] = useState<string | null>(null);
  const add = useCaseMutation((input: { scheduled_at: string; purpose?: string }) => addHearing(caseId, input));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await add.mutateAsync({
        scheduled_at: new Date(when).toISOString(),
        purpose: purpose.trim() || undefined,
      });
      setWhen('');
      setPurpose('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not add the hearing.');
    }
  }

  return (
    <form onSubmit={submit} aria-label="Add hearing" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h2 style={{ fontSize: 18 }}>Add a hearing</h2>
      <label className="field" htmlFor="h-when">
        Date and time
        <input id="h-when" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
      </label>
      <label className="field" htmlFor="h-purpose">
        Purpose (optional)
        <input id="h-purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
      </label>
      {error && (
        <p className="fine" role="alert">
          {error}
        </p>
      )}
      <div>
        <Button type="submit" small disabled={add.isPending || !when}>
          Add hearing
        </Button>
      </div>
    </form>
  );
}
