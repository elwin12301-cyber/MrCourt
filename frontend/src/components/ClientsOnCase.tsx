import { dayOf, useCaseMutation } from '../services/cases';
import { removeClient, useClientsOnCase } from '../services/clientAdmin';
import { Button, Chip } from './ui';

/** The clients invited to a case, with their state and a way to remove access. */
export function ClientsOnCase({ caseId }: { caseId: string }) {
  const { data } = useClientsOnCase(caseId);
  const remove = useCaseMutation((invitationId: string) => removeClient(caseId, invitationId));
  if (!data || data.length === 0) return <p className="fine" style={{ marginTop: 8 }}>No clients invited yet.</p>;

  return (
    <div style={{ marginTop: 10 }}>
      <div className="eyebrow" style={{ color: 'var(--muted)', marginBottom: 6 }}>Clients on this case</div>
      {data.map((c) => (
        <div className="act" key={c.id} style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ flex: 1, minWidth: 140 }}>
            <b>{c.contact_or_name}</b>
            <span>{c.accepted_at ? `Can see this case since ${dayOf(c.accepted_at)}` : 'Invitation not accepted yet'}</span>
          </span>
          <Chip tone={c.status === 'accepted' ? 'active' : 'soon'}>
            {c.status === 'accepted' ? 'Accepted' : 'Pending'}
          </Chip>
          <Button
            small
            variant="ghost"
            disabled={remove.isPending}
            aria-label={`Remove ${c.contact_or_name}`}
            onClick={() => {
              if (window.confirm(`Remove ${c.contact_or_name}? They will no longer see this case.`)) remove.mutate(c.id);
            }}
          >
            Remove
          </Button>
        </div>
      ))}
    </div>
  );
}
