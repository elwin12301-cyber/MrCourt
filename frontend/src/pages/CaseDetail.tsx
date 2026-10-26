import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ClientViewPanel } from '../components/ClientViewPanel';
import { ClientsOnCase } from '../components/ClientsOnCase';
import { DocumentUpload } from '../components/DocumentUpload';
import { HearingForm } from '../components/HearingForm';
import { Icon } from '../components/Icon';
import { OutcomeForm } from '../components/OutcomeForm';
import { Button, Chip } from '../components/ui';
import { ApiError } from '../services/api';
import { useMe } from '../services/auth';
import {
  STATUS_LABEL,
  STATUS_TONE,
  dateTimeOf,
  fileSize,
  inviteToCase,
  patchCase,
  useCase,
  useCaseMutation,
} from '../services/cases';
import { setDocumentSharing } from '../services/clientAdmin';

type Tab = 'overview' | 'hearings' | 'documents' | 'notes' | 'client';

function InvitePetitioner({ caseId }: { caseId: string }) {
  const [contact, setContact] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const invite = useCaseMutation((c: string) => inviteToCase(caseId, c));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setNote(null);
    try {
      await invite.mutateAsync(contact.trim());
      setContact('');
      setNote('Invitation sent. They will see the case once they accept.');
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : 'Could not send the invitation.');
    }
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 14 }}>
      <label className="field" htmlFor="invite-contact">
        Invite a petitioner to view this case
        <input
          id="invite-contact"
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          placeholder="Their email or phone"
          required
        />
      </label>
      <div>
        <Button type="submit" small variant="ghost" data-voice-risk="send" disabled={invite.isPending}>
          Send invitation
        </Button>
      </div>
      {note && (
        <p className="fine" role="status">
          {note}
        </p>
      )}
      <ClientsOnCase caseId={caseId} />
    </form>
  );
}

function NotesEditor({ caseId, initial }: { caseId: string; initial: string }) {
  const [value, setValue] = useState(initial);
  const [saved, setSaved] = useState(false);
  const save = useCaseMutation((notes: string) => patchCase(caseId, { notes }));
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <label className="field" htmlFor="case-notes">
        Private notes (not shared with petitioners)
        <textarea
          id="case-notes"
          rows={8}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setSaved(false);
          }}
          style={{ font: 'inherit', padding: 12, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)' }}
        />
      </label>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <Button
          small
          disabled={save.isPending}
          onClick={async () => {
            await save.mutateAsync(value);
            setSaved(true);
          }}
        >
          Save notes
        </Button>
        {saved && <span className="fine" role="status">Saved</span>}
      </div>
    </div>
  );
}

function DocumentShare({ shared, name, onChange }: { shared: boolean; name: string; onChange: (shared: boolean) => Promise<unknown> }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      small
      variant="ghost"
      disabled={busy}
      aria-pressed={shared}
      aria-label={`${shared ? 'Shared with client' : 'Share with client'}: ${name}`}
      onClick={async () => {
        setBusy(true);
        try {
          await onChange(!shared);
          await client.invalidateQueries({ queryKey: ['case'] });
        } finally {
          setBusy(false);
        }
      }}
    >
      {shared ? 'Shared with client' : 'Share with client'}
    </Button>
  );
}

export default function CaseDetail() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const { data: c, isLoading, error } = useCase(caseId);
  const [tab, setTab] = useState<Tab>('overview');
  const close = useCaseMutation((status: 'active' | 'closed') => patchCase(caseId as string, { status }));

  if (isLoading) return <section className="view" aria-busy="true" />;
  if (error || !c || !me) {
    return (
      <section className="view">
        <Link to="/cases" className="back">
          <Icon name="back" />
          All cases
        </Link>
        <h1>Case not found</h1>
        <p className="sub">It may have been removed, or you may not have access to it.</p>
      </section>
    );
  }

  const isAdvocate = me.role === 'advocate';
  const tabs: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'hearings', label: 'Hearings' },
    { id: 'documents', label: 'Documents' },
    ...(isAdvocate ? [{ id: 'notes' as const, label: 'Notes' }, { id: 'client' as const, label: 'Client view' }] : []),
  ];
  const parties = c.parties;
  const petitioner = parties.find((p) => p.side === 'petitioner');
  const respondent = parties.find((p) => p.side === 'respondent');

  const shareDocument = (documentId: string, shared: boolean) => setDocumentSharing(c.id, documentId, shared);

  const documentsCard = (
    <div className="card">
      <h2 style={{ marginBottom: 12 }}>Documents</h2>
      {c.documents.length === 0 && <p className="sub">No documents yet.</p>}
      {c.documents.map((d) => (
        <div className="act" key={d.id}>
          <a href={`/api/v1/cases/${c.id}/documents/${d.id}/download`}>
            <b>{d.file_name}</b>
          </a>
          <span>{fileSize(d.size_bytes)}</span>
          {isAdvocate && (
            <DocumentShare
              shared={d.shared_with_client}
              name={d.file_name}
              onChange={(shared) => shareDocument(d.id, shared)}
            />
          )}
        </div>
      ))}
      {isAdvocate && <DocumentUpload caseId={c.id} />}
    </div>
  );

  return (
    <section className="view" id="case" data-view="case">
      <Link to="/cases" className="back">
        <Icon name="back" />
        All cases
      </Link>
      <div>
        <h1 id="cTitle">{c.title}</h1>
        <p className="sub" id="cSub">
          CNR {c.cnr_number} · {c.court}
        </p>
        <p style={{ margin: '10px 0 0', display: 'flex', gap: 8 }} id="cTags">
          <Chip tone={STATUS_TONE[c.status]}>{STATUS_LABEL[c.status]}</Chip>
        </p>
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Button onClick={() => navigate('/ask', { state: { caseId: c.id } })}>
          <Icon name="chat" />
          Ask MrCourt
        </Button>
        {isAdvocate && (
          <Button variant="ghost" onClick={() => navigate('/drafts', { state: { caseId: c.id } })}>
            <Icon name="file" />
            Draft document
          </Button>
        )}
        {isAdvocate && (
          <Button variant="ghost" onClick={() => close.mutate(c.status === 'closed' ? 'active' : 'closed')}>
            {c.status === 'closed' ? 'Reopen case' : 'Close case'}
          </Button>
        )}
      </div>
      <div className="tabs" role="tablist" aria-label="Case sections">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'overview' && (
          <div className="row" style={{ alignItems: 'flex-start' }}>
            <div className="stack">
              <div className="card">
                <div className="eyebrow" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Icon name="cal" size={18} />
                  Next hearing
                </div>
                <h2 style={{ margin: '10px 0 4px', fontSize: 24 }} id="cNext">
                  {c.next_hearing_at ? dateTimeOf(c.next_hearing_at) : 'No hearing scheduled'}
                </h2>
                {(c.stage || c.court_room) && (
                  <span style={{ color: 'var(--muted)' }}>
                    {[c.stage ? `${c.stage} stage` : null, c.court_room].filter(Boolean).join(' · ')}
                  </span>
                )}
              </div>
              <div className="card">
                <h2 style={{ marginBottom: 12 }}>Parties</h2>
                {petitioner && (
                  <div className="act">
                    <span className="eyebrow" style={{ color: 'var(--muted)' }}>Petitioner</span>
                    {petitioner.name}
                    {petitioner.is_client ? ' (your client)' : ''}
                  </div>
                )}
                {respondent && (
                  <div className="act">
                    <span className="eyebrow" style={{ color: 'var(--muted)' }}>Respondent</span>
                    {respondent.name}
                  </div>
                )}
                {!petitioner && !respondent && <p className="sub">No parties recorded.</p>}
                {isAdvocate && <InvitePetitioner caseId={c.id} />}
              </div>
            </div>
            {documentsCard}
          </div>
        )}

        {tab === 'hearings' && (
          <div className="row" style={{ alignItems: 'flex-start' }}>
            <div className="card">
              <h2 style={{ marginBottom: 12 }}>Hearings</h2>
              {c.hearings.length === 0 && <p className="sub">No hearings scheduled.</p>}
              {c.hearings.map((h) => (
                <div className="act" key={h.id}>
                  <b>{dateTimeOf(h.scheduled_at)}</b>
                  <span>{[h.purpose, h.court_room].filter(Boolean).join(' · ') || 'Hearing'}</span>
                  {isAdvocate && new Date(h.scheduled_at).getTime() < Date.now() && (
                    <OutcomeForm caseId={c.id} hearing={h} />
                  )}
                </div>
              ))}
            </div>
            {isAdvocate && (
              <div className="card">
                <HearingForm caseId={c.id} />
              </div>
            )}
          </div>
        )}

        {tab === 'documents' && documentsCard}

        {tab === 'notes' && isAdvocate && <NotesEditor caseId={c.id} initial={c.notes ?? ''} />}

        {tab === 'client' && isAdvocate && (
          <ClientViewPanel caseId={c.id} current={c.client_status} changedAt={c.client_status_changed_at} />
        )}
      </div>
    </section>
  );
}
