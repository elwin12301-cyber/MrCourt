import { type FormEvent, useState } from 'react';
import { ApiError } from '../services/api';
import { type CaseDetail, createCase, useCaseMutation } from '../services/cases';
import { Button, Card } from './ui';

/** Inline form for an advocate to add a case (FR-022). */
export function CaseForm({ onCreated, onCancel }: { onCreated: (c: CaseDetail) => void; onCancel: () => void }) {
  const [title, setTitle] = useState('');
  const [cnr, setCnr] = useState('');
  const [court, setCourt] = useState('');
  const [client, setClient] = useState('');
  const [other, setOther] = useState('');
  const [stage, setStage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const create = useCaseMutation(createCase);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const parties = [
      ...(client.trim() ? [{ side: 'petitioner' as const, name: client.trim(), is_client: true }] : []),
      ...(other.trim() ? [{ side: 'respondent' as const, name: other.trim(), is_client: false }] : []),
    ];
    try {
      const created = await create.mutateAsync({
        title: title.trim(),
        cnr_number: cnr.trim(),
        court: court.trim(),
        stage: stage.trim() || undefined,
        parties,
      });
      onCreated(created as CaseDetail);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save the case. Please try again.');
    }
  }

  return (
    <Card>
      <form onSubmit={submit} aria-label="New case" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <h2>New case</h2>
        <label className="field" htmlFor="nc-title">
          Case title
          <input id="nc-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Sharma v. Verma Traders" required />
        </label>
        <label className="field" htmlFor="nc-cnr">
          CNR number
          <input id="nc-cnr" value={cnr} onChange={(e) => setCnr(e.target.value)} required />
        </label>
        <label className="field" htmlFor="nc-court">
          Court
          <input id="nc-court" value={court} onChange={(e) => setCourt(e.target.value)} required />
        </label>
        <label className="field" htmlFor="nc-client">
          Your client (petitioner)
          <input id="nc-client" value={client} onChange={(e) => setClient(e.target.value)} />
        </label>
        <label className="field" htmlFor="nc-other">
          Respondent
          <input id="nc-other" value={other} onChange={(e) => setOther(e.target.value)} />
        </label>
        <label className="field" htmlFor="nc-stage">
          Stage (optional)
          <input id="nc-stage" value={stage} onChange={(e) => setStage(e.target.value)} placeholder="e.g. Evidence" />
        </label>
        {error && (
          <p className="fine" role="alert" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
            {error}
          </p>
        )}
        <div style={{ display: 'flex', gap: 10 }}>
          <Button type="submit" small disabled={create.isPending}>
            Save case
          </Button>
          <Button variant="ghost" small onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
