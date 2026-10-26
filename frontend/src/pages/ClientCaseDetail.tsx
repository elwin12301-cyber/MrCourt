import { useEffect } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { AccessPanel } from '../components/AccessPanel';
import { AskLawyer } from '../components/AskLawyer';
import { ClientStatusChip } from '../components/ClientStatusChip';
import { Explain } from '../components/Explain';
import { Icon } from '../components/Icon';
import { LawyerCard } from '../components/LawyerCard';
import { Timeline } from '../components/Timeline';
import { Button, Disclaimer } from '../components/ui';
import { dateTimeOf, dayOf, fileSize } from '../services/cases';
import { type ClientCase, type HearingForClient, useClientCase } from '../services/client';

/** Glossary term that explains a status. "Hearing scheduled" is explained next to the hearing itself. */
const STATUS_TERM: Partial<Record<NonNullable<ClientCase['status']>, string>> = {
  notice_stage: 'Notice',
  awaiting_order: 'Order',
};

function HearingDescription({ hearing }: { hearing: HearingForClient }) {
  if (!hearing.description) return null;
  return (
    <div className="hearingdesc">
      <div className="eyebrow">{hearing.description.label}</div>
      <p>{hearing.description.text}</p>
      <Disclaimer text={hearing.description.disclaimer} />
    </div>
  );
}

export default function ClientCaseDetail() {
  const { caseId } = useParams();
  const { data: c, isLoading, error } = useClientCase(caseId);
  const navigate = useNavigate();
  const { hash } = useLocation();

  // A link such as "Ask your lawyer" from Ask MrCourt lands on the question box.
  useEffect(() => {
    if (c && hash === '#ask-lawyer') document.getElementById('ask-lawyer')?.scrollIntoView?.({ block: 'center' });
  }, [c, hash]);

  if (isLoading) return <section className="view" aria-busy="true" />;
  if (error || !c) {
    return (
      <section className="view">
        <Link to="/cases" className="back" aria-label="Back to my cases">
          <Icon name="back" />
          My cases
        </Link>
        <h1>Case not found</h1>
        <p className="sub">It may have been removed, or you may not have access to it.</p>
      </section>
    );
  }

  const now = Date.now();
  const upcoming = c.hearings.filter((h) => new Date(h.scheduled_at).getTime() >= now);
  const past = c.hearings.filter((h) => new Date(h.scheduled_at).getTime() < now).reverse();
  const next = c.next_hearing;

  return (
    <section className="view" id="case" data-view="client-case">
      <Link to="/cases" className="back" aria-label="Back to my cases">
        <Icon name="back" />
        My cases
      </Link>

      <div>
        <h1 id="cTitle">{c.title}</h1>
        <p className="sub">{c.court}</p>
        <p style={{ margin: '10px 0 0', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <ClientStatusChip status={c.status} />
          <span className="fine">
            {c.status && c.status_changed_at
              ? `Status updated ${dayOf(c.status_changed_at)}`
              : 'Your lawyer has not shared a status yet'}
          </span>
        </p>
        {c.status && STATUS_TERM[c.status] && <Explain term={STATUS_TERM[c.status] as string} />}
      </div>

      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="stack">
          <div className="card">
            <div className="eyebrow" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Icon name="cal" size={18} />
              Next hearing
            </div>
            {next ? (
              <>
                <h2 style={{ margin: '10px 0 4px', fontSize: 24 }} id="cNext">
                  {dateTimeOf(next.scheduled_at)}
                </h2>
                <span style={{ color: 'var(--muted)' }}>{next.court}</span>
                <HearingDescription hearing={next} />
                <Explain term="Hearing" />
              </>
            ) : (
              <h2 style={{ margin: '10px 0 4px', fontSize: 22 }} id="cNext">
                No hearing scheduled yet
              </h2>
            )}
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 12 }}>What has happened</h2>
            <Timeline entries={c.timeline} />
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 12 }}>Hearings</h2>
            {c.hearings.length === 0 && <p className="sub">No hearings yet.</p>}
            {upcoming.map((h) => (
              <div className="act" key={h.id}>
                <b>{dateTimeOf(h.scheduled_at)}</b>
                <span>Coming up · {h.court}</span>
              </div>
            ))}
            {past.map((h) => (
              <div className="act" key={h.id}>
                <b>{dateTimeOf(h.scheduled_at)}</b>
                <span>{h.outcome ? `Outcome: ${h.outcome}` : 'Held'}</span>
              </div>
            ))}
            <Explain term="Adjournment" />
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2 style={{ marginBottom: 12 }}>Documents shared with you</h2>
            {c.documents.length === 0 && <p className="sub">Your lawyer has not shared any documents yet.</p>}
            {c.documents.map((d) => (
              <div className="act" key={d.id}>
                <a href={`/api/v1/client/cases/${c.id}/documents/${d.id}/download`}>
                  <b>{d.file_name}</b>
                </a>
                <span>{fileSize(d.size_bytes)}</span>
              </div>
            ))}
          </div>
          <LawyerCard lawyer={c.lawyer} />
          <AskLawyer caseId={c.id} available={c.lawyer.available} />
          <AccessPanel access={c.access} />
          <Button variant="ghost" small onClick={() => navigate('/ask', { state: { caseId: c.id } })}>
            <Icon name="chat" />
            Ask MrCourt a general legal question
          </Button>
        </div>
      </div>
    </section>
  );
}
